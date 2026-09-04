"""
Loader for engines that can't be automated (Perplexity, Gemini — see
config.ENGINES for why). Run the prompt yourself in the engine's UI, paste
the answer into a capture file, and this reads it into the same
EngineResult shape the automated runners produce so scoring treats every
engine identically.

Capture file format (captures/<engine>__<slug>.md) — YAML frontmatter plus
the pasted answer as the body:

    ---
    engine: perplexity
    prompt: who is the best cosmetic dentist in honolulu
    ---
    (paste the full answer text here, links and all)
"""
from __future__ import annotations

import glob
import os
import re

import yaml

from .engines import EngineResult, _detect_mentions, _domain_of

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def load_capture_file(path: str, business_name: str, domain: str | None = None) -> EngineResult:
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    m = FRONTMATTER_RE.match(raw)
    if not m:
        return EngineResult(
            engine=os.path.basename(path), prompt="", success=False, method="manual",
            error=f"{path} is missing the '---' YAML frontmatter block — see the "
                  f"format in this file's docstring",
        )

    front, body = m.groups()
    meta = yaml.safe_load(front) or {}
    engine = meta.get("engine", "unknown")
    prompt = meta.get("prompt", "")
    body = body.strip()

    if not body:
        return EngineResult(engine=engine, prompt=prompt, success=False, method="manual",
                             error=f"{path} has no pasted answer text in the body")

    mentioned, contexts = _detect_mentions(body, business_name, domain)
    # pick up any bare URLs pasted alongside the answer as rough citations
    cited = []
    for url in re.findall(r"https?://[^\s)\]]+", body):
        d = _domain_of(url)
        if d and d not in cited:
            cited.append(d)

    return EngineResult(
        engine=engine, prompt=prompt, success=True, method="manual",
        raw_text=body, mentioned=mentioned, mention_context=contexts,
        cited_domains=cited[:20],
    )


def load_captures_dir(captures_dir: str, business_name: str, domain: str | None = None) -> list[EngineResult]:
    """Load every .md capture file in a directory. Silently returns an empty
    list if the directory doesn't exist yet — manual capture is optional."""
    if not os.path.isdir(captures_dir):
        return []
    results = []
    for path in sorted(glob.glob(os.path.join(captures_dir, "*.md"))):
        if os.path.basename(path).lower() == "readme.md":
            continue  # format docs, not a capture
        results.append(load_capture_file(path, business_name, domain))
    return results
