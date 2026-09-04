"""
Constants shared across the screener: prompt templates, scoring weights,
and the productized service tiers a gap maps to.

Edit this file to retune the tool for a different niche — nothing else
in the package needs to change.
"""

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------
# {category} and {location} are filled in from the CLI arguments.
# These mirror how real people actually phrase these questions to an AI
# assistant — validated against a live run (see examples/cosmetic-dentist-
# honolulu/). Keep them conversational, not keyword-stuffed.

DEFAULT_PROMPT_TEMPLATES = [
    "who is the best {category} in {location}",
    "recommend a good {category} in {location}",
    "top rated {category} near {location}",
    "what is the best {category} in {location} and why",
    "I need a {category} in {location}, who should I go with",
]

# Engines the tool knows how to reach, and how reliable automation is for
# each. This is documentation as much as configuration — set expectations
# before someone runs the tool and hits a login wall.
ENGINES = {
    "chatgpt": {
        "label": "ChatGPT (chatgpt.com, logged out)",
        "automatable": True,
        "notes": "Anonymous chat works as of this writing and does not require sign-in.",
    },
    "google": {
        "label": "Google Search (organic + local pack + People Also Ask)",
        "automatable": True,
        "notes": "Plain SERP fetch. Google AI Mode/AI Overviews render behind "
                 "JS the automated fetch won't execute — capture that one manually.",
    },
    "bing": {
        "label": "Bing Search",
        "automatable": True,
        "notes": "Heavily ad-dominated for commercial-intent queries — treat organic "
                 "results only.",
    },
    "perplexity": {
        "label": "Perplexity",
        "automatable": False,
        "notes": "Now requires sign-in for a single query (confirmed live, not "
                 "a training-data assumption) — run this one manually and paste "
                 "the transcript into captures/.",
    },
    "gemini": {
        "label": "Google Gemini",
        "automatable": False,
        "notes": "Requires a logged-in Google account — run manually and paste "
                 "the transcript into captures/.",
    },
}

# ---------------------------------------------------------------------------
# Scoring weights (0-100 total)
# ---------------------------------------------------------------------------
# These weights encode a judgment call: for a local-service business, being
# the answer an AI assistant actually names matters most, credibility
# signals are what get you named, and pure technical SEO is necessary but
# not sufficient. Retune per client if warranted.

CATEGORY_WEIGHTS = {
    "ai_visibility": 35,   # named/cited across the AI engines tested
    "credibility": 25,     # credentials, awards, years of experience, press
    "citations_local": 20, # NAP consistency, directory presence, GBP signal, reviews
    "structured_data": 12, # schema.org markup, llms.txt, FAQ markup
    "content_depth": 8,    # FAQ content, page depth, freshness
}

assert sum(CATEGORY_WEIGHTS.values()) == 100

# ---------------------------------------------------------------------------
# Service package tiers — mirrors the productized packages the agency sells
# (Audit / Monitoring / Full-GEO). The scorer maps a business's composite
# score to a recommended entry point; recommend.py maps individual gaps to
# specific line items within whichever package fits.
# ---------------------------------------------------------------------------

# Every business gets the Audit (this report is it). score_band picks the
# NEXT recommended package on top of that, based on the composite score.
AUDIT_TIER = {
    "name": "AI Visibility Audit",
    "description": "One-time diagnostic: where the business stands across AI "
                    "engines today, what's actively hurting it, and a prioritized "
                    "fix list. This report *is* that deliverable.",
}

# (min_score_inclusive, max_score_inclusive, tier)
SCORE_BANDS = [
    (0, 54, {
        "name": "Full-GEO Buildout",
        "description": "Score under 55 — foundational gaps (schema, citations, "
                        "credibility content) need fixing before visibility will "
                        "move. Recommend the buildout package: structured-data "
                        "implementation, citation building, credential/FAQ content, "
                        "and a re-test once the fixes are live.",
    }),
    (55, 79, {
        "name": "AI Visibility Monitoring",
        "description": "Score 55-79 — foundations are reasonably solid. Recommend "
                        "ongoing monitoring (recurring re-runs of this screener, or "
                        "an Ahrefs Brand Radar / Semrush AI-tracking connector) plus "
                        "targeted fixes for whatever's still missing.",
    }),
    (80, 100, {
        "name": "Maintain & Expand",
        "description": "Score 80+ — already visible and credible. Recommend "
                        "expanding prompt coverage (more query variations, adjacent "
                        "services) and defending position against competitors doing "
                        "the same work.",
    }),
]


def recommend_package(score: float) -> dict:
    """Return the next recommended package tier for a given composite score."""
    for low, high, tier in SCORE_BANDS:
        if low <= score <= high:
            return tier
    return SCORE_BANDS[0][2]
