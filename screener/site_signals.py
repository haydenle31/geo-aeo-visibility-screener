"""
Pulls the technical / on-site signals that determine whether an AI crawler
or answer engine can actually extract facts about a business from its own
website: structured data, an llms.txt, FAQ content, and the specific
credibility language (credentials, years of experience, awards) that showed
up as the deciding factor in the live ChatGPT capture under examples/.

Everything here is a plain HTTP GET against a site the user is auditing —
run this from a machine with normal internet access (it will not work from
a network-locked sandbox).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (compatible; GEO-AEO-Screener/1.0; +https://github.com/)"
TIMEOUT = 10

# Words that signal the E-E-A-T ("experience, expertise, authoritativeness,
# trust") content an AI engine's answer leaned on in the live capture:
# named credentials, an explicit years-of-experience claim, and award /
# press language.
CREDENTIAL_PATTERNS = [
    r"\bcertified\b", r"\baccredited\b", r"\bfellow\b", r"\bboard[- ]certified\b",
    r"\blicensed\b", r"\bdiplomate\b",
]
EXPERIENCE_PATTERN = r"\b(\d{1,2})\+?\s*years?\b"
AWARD_PATTERNS = [
    r"\bbest of\b", r"\baward\b", r"\bvoted\b", r"\btop[- ]rated\b",
    r"\brecognized\b", r"\branked\b", r"\bwinner\b",
]


@dataclass
class SiteSignals:
    url: str
    fetched_ok: bool = False
    error: str | None = None

    has_https: bool = False
    has_robots_txt: bool = False
    has_sitemap_xml: bool = False
    has_llms_txt: bool = False

    schema_types_found: list[str] = field(default_factory=list)
    has_local_business_schema: bool = False
    has_faq_schema: bool = False
    has_review_schema: bool = False

    title: str | None = None
    meta_description: str | None = None
    h1_count: int = 0
    word_count: int = 0

    faq_style_headings: list[str] = field(default_factory=list)
    credential_mentions: list[str] = field(default_factory=list)
    stated_years_experience: int | None = None
    award_mentions: list[str] = field(default_factory=list)

    has_phone_on_site: bool = False
    has_address_on_site: bool = False

    def to_dict(self) -> dict:
        return self.__dict__


def _get(url: str) -> requests.Response | None:
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        return resp
    except requests.RequestException:
        return None


def _check_exists(base_url: str, path: str) -> bool:
    resp = _get(urljoin(base_url, path))
    return bool(resp and resp.status_code == 200 and len(resp.text.strip()) > 0)


def _extract_jsonld_types(soup: BeautifulSoup) -> list[str]:
    types: list[str] = []
    for tag in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            t = item.get("@type")
            if isinstance(t, list):
                types.extend(t)
            elif isinstance(t, str):
                types.append(t)
            # Some sites nest an @graph array
            for node in item.get("@graph", []) if isinstance(item.get("@graph"), list) else []:
                if isinstance(node, dict) and isinstance(node.get("@type"), str):
                    types.append(node["@type"])
    return types


def _find_matches(text: str, patterns: list[str], window: int = 60) -> list[str]:
    hits = []
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            start = max(0, m.start() - window)
            end = min(len(text), m.end() + window)
            # snap to word boundaries so snippets don't start/end mid-word
            if start > 0:
                next_space = text.find(" ", start)
                start = next_space + 1 if 0 <= next_space < m.start() else start
            if end < len(text):
                prev_space = text.rfind(" ", m.end(), end)
                end = prev_space if prev_space > m.end() else end
            snippet = " ".join(text[start:end].split())
            hits.append(snippet)
    # de-dupe while preserving order, cap so the report stays readable
    seen = set()
    deduped = []
    for h in hits:
        if h not in seen:
            seen.add(h)
            deduped.append(h)
    return deduped[:5]


def collect(url: str) -> SiteSignals:
    """Fetch `url` and every signal the scorer needs from it."""
    signals = SiteSignals(url=url)
    signals.has_https = url.lower().startswith("https://")

    resp = _get(url)
    if not resp or resp.status_code >= 400:
        signals.error = f"could not fetch {url} (status={getattr(resp, 'status_code', 'n/a')})"
        return signals

    signals.fetched_ok = True
    soup = BeautifulSoup(resp.text, "html.parser")
    text = soup.get_text(" ", strip=True)

    signals.title = soup.title.string.strip() if soup.title and soup.title.string else None
    meta = soup.find("meta", attrs={"name": "description"})
    signals.meta_description = meta.get("content", "").strip() if meta else None
    signals.h1_count = len(soup.find_all("h1"))
    signals.word_count = len(text.split())

    schema_types = _extract_jsonld_types(soup)
    signals.schema_types_found = sorted(set(schema_types))
    local_biz_types = {
        "LocalBusiness", "Dentist", "MedicalBusiness", "Physician", "Store",
        "ProfessionalService", "HomeAndConstructionBusiness", "Restaurant",
        "AutoRepair", "Attorney", "RealEstateAgent",
    }
    signals.has_local_business_schema = any(t in local_biz_types for t in schema_types)
    signals.has_faq_schema = "FAQPage" in schema_types
    signals.has_review_schema = any(t in {"Review", "AggregateRating"} for t in schema_types)

    # FAQ-style headings even without formal schema — still crawlable/quotable
    heading_texts = [h.get_text(strip=True) for h in soup.find_all(["h2", "h3"])]
    question_words = ("who", "what", "how", "why", "when", "where", "is ", "does", "can ")
    signals.faq_style_headings = [
        h for h in heading_texts
        if h.strip("? ").lower().startswith(question_words) or h.strip().endswith("?")
    ][:10]

    signals.credential_mentions = _find_matches(text, CREDENTIAL_PATTERNS)
    signals.award_mentions = _find_matches(text, AWARD_PATTERNS)
    years_match = re.search(EXPERIENCE_PATTERN, text, re.IGNORECASE)
    if years_match:
        try:
            signals.stated_years_experience = int(years_match.group(1))
        except ValueError:
            pass

    signals.has_phone_on_site = bool(re.search(r"\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}", text))
    # Loose NAP heuristic: "<Street words> ... <2-letter state> <5-digit zip>"
    signals.has_address_on_site = bool(
        re.search(r"\b\d{2,6}\s+[A-Za-z0-9.'\s]{3,40},?\s*[A-Za-z\s]{2,20},?\s*[A-Z]{2}\s*\d{5}\b", text)
    )

    signals.has_robots_txt = _check_exists(url, "/robots.txt")
    signals.has_sitemap_xml = _check_exists(url, "/sitemap.xml")
    # llms.txt is the emerging (still informal, not yet widely adopted)
    # convention for exposing a plain-language summary to AI crawlers —
    # https://llmstxt.org/. Absence is normal today; presence is a real
    # differentiator worth flagging.
    signals.has_llms_txt = _check_exists(url, "/llms.txt")

    return signals
