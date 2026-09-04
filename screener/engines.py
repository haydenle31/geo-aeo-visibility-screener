"""
Runs a prompt against the AI/search engines that can realistically be
automated, and provides the loader for the ones that can't (see
manual_capture.py).

Ground truth for what's automatable came from actually doing it (see
examples/cosmetic-dentist-honolulu/): as of this writing, ChatGPT answers
anonymous queries with no login, Google/Bing serve a plain SERP, and
Perplexity now hard-gates a single query behind sign-in. That will drift
over time — if an engine starts blocking the automated path, fall back to
running it by hand and dropping the transcript in captures/ instead of
fighting the block.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from urllib.parse import quote_plus, urlparse

import requests
from bs4 import BeautifulSoup

from .config import ENGINES

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " \
             "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
TIMEOUT = 15


@dataclass
class EngineResult:
    engine: str
    prompt: str
    success: bool
    method: str = "automated"          # "automated" | "manual"
    raw_text: str = ""
    mentioned: bool = False
    mention_context: list[str] = field(default_factory=list)
    cited_domains: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict:
        return self.__dict__


def _domain_of(url_or_domain: str) -> str:
    if "://" not in url_or_domain:
        url_or_domain = "https://" + url_or_domain
    netloc = urlparse(url_or_domain).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def _detect_mentions(text: str, business_name: str, domain: str | None) -> tuple[bool, list[str]]:
    contexts: list[str] = []
    lowered = text.lower()
    needles = [business_name.lower()]
    if domain:
        needles.append(_domain_of(domain))
    found = False
    for needle in needles:
        if not needle:
            continue
        for m in re.finditer(re.escape(needle), lowered):
            found = True
            start, end = max(0, m.start() - 80), min(len(text), m.end() + 80)
            contexts.append(" ".join(text[start:end].split()))
    # de-dupe, cap
    seen, deduped = set(), []
    for c in contexts:
        if c not in seen:
            seen.add(c)
            deduped.append(c)
    return found, deduped[:5]


def _extract_linked_domains(soup: BeautifulSoup) -> list[str]:
    domains = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/url?q="):
            href = href[len("/url?q="):].split("&", 1)[0]
        if href.startswith("http"):
            d = _domain_of(href)
            if d and "google." not in d and "bing." not in d:
                domains.append(d)
    # de-dupe preserving order
    seen, out = set(), []
    for d in domains:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


# ---------------------------------------------------------------------------
# Google / Bing — plain SERP fetch. No JS execution, so anything Google
# renders client-side (AI Overviews, AI Mode) will not appear here — capture
# those manually. Selector-free by design: SERP markup is obfuscated and
# changes constantly, so this only trusts full-page visible text, not
# specific card structures.
# ---------------------------------------------------------------------------

def run_google(prompt: str, business_name: str, domain: str | None = None) -> EngineResult:
    url = f"https://www.google.com/search?q={quote_plus(prompt)}&num=20&hl=en"
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    except requests.RequestException as e:
        return EngineResult(engine="google", prompt=prompt, success=False, error=str(e))

    if resp.status_code != 200:
        return EngineResult(engine="google", prompt=prompt, success=False,
                             error=f"HTTP {resp.status_code} — Google may be showing a "
                                   f"consent/CAPTCHA wall to this IP")

    soup = BeautifulSoup(resp.text, "html.parser")
    text = soup.get_text(" ", strip=True)
    mentioned, contexts = _detect_mentions(text, business_name, domain)
    return EngineResult(
        engine="google", prompt=prompt, success=True, raw_text=text[:6000],
        mentioned=mentioned, mention_context=contexts,
        cited_domains=_extract_linked_domains(soup)[:20],
    )


def run_bing(prompt: str, business_name: str, domain: str | None = None) -> EngineResult:
    url = f"https://www.bing.com/search?q={quote_plus(prompt)}"
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    except requests.RequestException as e:
        return EngineResult(engine="bing", prompt=prompt, success=False, error=str(e))

    if resp.status_code != 200:
        return EngineResult(engine="bing", prompt=prompt, success=False,
                             error=f"HTTP {resp.status_code}")

    soup = BeautifulSoup(resp.text, "html.parser")
    text = soup.get_text(" ", strip=True)
    mentioned, contexts = _detect_mentions(text, business_name, domain)
    return EngineResult(
        engine="bing", prompt=prompt, success=True, raw_text=text[:6000],
        mentioned=mentioned, mention_context=contexts,
        cited_domains=_extract_linked_domains(soup)[:20],
    )


# ---------------------------------------------------------------------------
# ChatGPT — real browser automation via Playwright. This is a heavy SPA with
# a streaming response, so completion is detected by polling the answer text
# until it stops changing rather than trusting any specific CSS selector
# (those change often; a stability check does not).
# ---------------------------------------------------------------------------

def run_chatgpt(prompt: str, business_name: str, domain: str | None = None,
                 headless: bool = True, max_wait_seconds: int = 45) -> EngineResult:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return EngineResult(
            engine="chatgpt", prompt=prompt, success=False,
            error="playwright is not installed — run `pip install playwright && "
                  "playwright install chromium`",
        )

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            page = browser.new_page(user_agent=USER_AGENT)
            page.goto("https://chatgpt.com/", timeout=30000)
            page.wait_for_timeout(2000)

            composer = page.locator("#prompt-textarea")
            composer.wait_for(timeout=15000)
            composer.click()
            composer.type(prompt, delay=15)
            page.keyboard.press("Enter")

            # Poll the last assistant message until its text stabilizes —
            # robust to UI/markup changes, unlike waiting on a specific
            # "generation complete" selector.
            last_text, stable_ticks = "", 0
            deadline = time.time() + max_wait_seconds
            while time.time() < deadline:
                page.wait_for_timeout(1500)
                messages = page.locator('[data-message-author-role="assistant"]')
                count = messages.count()
                if count == 0:
                    continue
                current = messages.nth(count - 1).inner_text()
                if current == last_text and current.strip():
                    stable_ticks += 1
                    if stable_ticks >= 2:
                        break
                else:
                    stable_ticks = 0
                last_text = current

            # Pull any source links ChatGPT rendered alongside the answer.
            links = page.locator('[data-message-author-role="assistant"] a[href^="http"]')
            cited = []
            for i in range(links.count()):
                href = links.nth(i).get_attribute("href") or ""
                if href:
                    cited.append(_domain_of(href))
            browser.close()

        mentioned, contexts = _detect_mentions(last_text, business_name, domain)
        seen, cited_deduped = set(), []
        for d in cited:
            if d and d not in seen:
                seen.add(d)
                cited_deduped.append(d)

        if not last_text.strip():
            return EngineResult(engine="chatgpt", prompt=prompt, success=False,
                                 error="no response text captured — ChatGPT's UI may "
                                       "have changed, or the page hit a login/consent wall")

        return EngineResult(
            engine="chatgpt", prompt=prompt, success=True, raw_text=last_text,
            mentioned=mentioned, mention_context=contexts, cited_domains=cited_deduped,
        )
    except Exception as e:  # noqa: BLE001 — surface any Playwright failure as a result, not a crash
        return EngineResult(engine="chatgpt", prompt=prompt, success=False, error=str(e))


AUTOMATED_RUNNERS = {
    "google": run_google,
    "bing": run_bing,
    "chatgpt": run_chatgpt,
}


def run_engine(engine: str, prompt: str, business_name: str, domain: str | None = None,
                **kwargs) -> EngineResult:
    if engine not in ENGINES:
        return EngineResult(engine=engine, prompt=prompt, success=False,
                             error=f"unknown engine '{engine}'")
    if not ENGINES[engine]["automatable"]:
        return EngineResult(engine=engine, prompt=prompt, success=False,
                             error=f"{ENGINES[engine]['label']} is not automatable "
                                   f"({ENGINES[engine]['notes']}) — see manual_capture.py")
    return AUTOMATED_RUNNERS[engine](prompt, business_name, domain, **kwargs)
