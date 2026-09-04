"""
Combines engine results + on-site signals into the weighted scorecard
defined in config.CATEGORY_WEIGHTS. Every sub-score is 0-100; the composite
is the weighted sum.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import CATEGORY_WEIGHTS, recommend_package
from .engines import EngineResult
from .site_signals import SiteSignals


@dataclass
class CategoryScore:
    name: str
    weight: int
    score: float          # 0-100
    notes: list[str] = field(default_factory=list)

    @property
    def weighted_points(self) -> float:
        return round(self.score * self.weight / 100, 1)


@dataclass
class Scorecard:
    categories: list[CategoryScore]
    composite: float
    recommended_package: dict

    def to_dict(self) -> dict:
        return {
            "composite": self.composite,
            "recommended_package": self.recommended_package,
            "categories": [
                {"name": c.name, "weight": c.weight, "score": c.score,
                 "weighted_points": c.weighted_points, "notes": c.notes}
                for c in self.categories
            ],
        }


def _score_ai_visibility(engine_results: list[EngineResult]) -> CategoryScore:
    attempted = [r for r in engine_results if r.success]
    if not attempted:
        return CategoryScore("AI Visibility", CATEGORY_WEIGHTS["ai_visibility"], 0,
                              ["No engine runs succeeded — can't measure visibility yet. "
                               "Fix whatever's blocking the runs (see errors above) and re-run."])
    mentioned = [r for r in attempted if r.mentioned]
    pct = round(100 * len(mentioned) / len(attempted))
    by_engine = {}
    for r in attempted:
        by_engine.setdefault(r.engine, []).append(r.mentioned)
    notes = [
        f"Mentioned in {len(mentioned)}/{len(attempted)} prompt runs across "
        f"{len(by_engine)} engine(s)."
    ]
    for engine, hits in by_engine.items():
        notes.append(f"  {engine}: {sum(hits)}/{len(hits)} prompts mentioned the business")
    return CategoryScore("AI Visibility", CATEGORY_WEIGHTS["ai_visibility"], pct, notes)


def _score_credibility(site: SiteSignals | None) -> CategoryScore:
    if site is None or not site.fetched_ok:
        return CategoryScore("Credibility Signals", CATEGORY_WEIGHTS["credibility"], 0,
                              ["Website could not be fetched — credibility signals unknown."])
    points, notes = 0, []
    if site.credential_mentions:
        points += 40
        notes.append(f"Credential language found on-site (e.g. \"{site.credential_mentions[0]}\")")
    else:
        notes.append("No certification/credential language found on-site — add one if "
                      "the practitioner holds any (board-certified, AACD-accredited, etc.)")
    if site.stated_years_experience:
        points += 30
        notes.append(f"States {site.stated_years_experience}+ years of experience")
    else:
        notes.append("No explicit years-of-experience claim found — AI answers lean on "
                      "stated tenure, add one if it's a strength")
    if site.award_mentions:
        points += 30
        notes.append(f"Award/recognition language found (e.g. \"{site.award_mentions[0]}\")")
    else:
        notes.append("No award, press, or 'best of' language found — local awards and "
                      "press mentions are exactly what showed up as citations in the live "
                      "engine captures (see examples/)")
    return CategoryScore("Credibility Signals", CATEGORY_WEIGHTS["credibility"], min(points, 100), notes)


def _score_citations_local(site: SiteSignals | None, engine_results: list[EngineResult],
                             domain: str | None) -> CategoryScore:
    notes = []
    points = 0

    own_domain = domain.replace("https://", "").replace("http://", "").lstrip("www.") if domain else None
    third_party_domains = set()
    for r in engine_results:
        for d in r.cited_domains:
            if d and d != own_domain:
                third_party_domains.add(d)
    citation_points = min(60, len(third_party_domains) * 12)
    points += citation_points
    if third_party_domains:
        notes.append(f"Cited alongside {len(third_party_domains)} third-party domain(s) "
                      f"across engine results: {', '.join(sorted(third_party_domains)[:8])}")
    else:
        notes.append("No third-party citing domains detected across engine results — "
                      "directory/press citations are what AI engines lean on for local "
                      "businesses")

    if site is not None and site.fetched_ok:
        if site.has_phone_on_site:
            points += 20
        else:
            notes.append("No phone number detected on the site's homepage text")
        if site.has_address_on_site:
            points += 20
        else:
            notes.append("No full street address detected on the site's homepage text — "
                          "NAP (name/address/phone) consistency is a core local-SEO signal")

    return CategoryScore("Citations & Local Signals", CATEGORY_WEIGHTS["citations_local"],
                          min(points, 100), notes)


def _score_structured_data(site: SiteSignals | None) -> CategoryScore:
    if site is None or not site.fetched_ok:
        return CategoryScore("Structured Data", CATEGORY_WEIGHTS["structured_data"], 0,
                              ["Website could not be fetched — structured data unknown."])
    points, notes = 0, []
    if site.has_local_business_schema:
        points += 45
        notes.append(f"LocalBusiness-type schema.org markup found ({', '.join(site.schema_types_found) or 'n/a'})")
    else:
        notes.append("No LocalBusiness/Dentist/ProfessionalService schema.org JSON-LD found — "
                      "this is the single most direct way to hand an AI crawler structured facts")
    if site.has_faq_schema or site.faq_style_headings:
        points += 35
        notes.append("FAQ-style content found" + (" (with FAQPage schema)" if site.has_faq_schema else " (headings only, no schema)"))
    else:
        notes.append("No FAQ content or FAQPage schema found — question-phrased headings "
                      "are exactly the format 'who is the best X in Y' prompts match against")
    if site.has_llms_txt:
        points += 20
        notes.append("llms.txt present — still an early/informal convention, but a real "
                      "differentiator right now")
    else:
        notes.append("No llms.txt (informal, emerging convention for AI crawlers — "
                      "optional but cheap to add, see llmstxt.org)")
    return CategoryScore("Structured Data", CATEGORY_WEIGHTS["structured_data"], min(points, 100), notes)


def _score_content_depth(site: SiteSignals | None) -> CategoryScore:
    if site is None or not site.fetched_ok:
        return CategoryScore("Content Depth", CATEGORY_WEIGHTS["content_depth"], 0,
                              ["Website could not be fetched — content depth unknown."])
    points, notes = 0, []
    if site.word_count >= 600:
        points += 50
        notes.append(f"Homepage has substantial content ({site.word_count} words)")
    elif site.word_count >= 300:
        points += 25
        notes.append(f"Homepage content is moderate ({site.word_count} words) — thin by AI-answer standards")
    else:
        notes.append(f"Homepage is thin ({site.word_count} words) — little for an AI engine to extract from")
    if site.h1_count == 1:
        points += 25
        notes.append("Exactly one H1 (correct)")
    elif site.h1_count == 0:
        notes.append("No H1 found")
    else:
        notes.append(f"{site.h1_count} H1 tags found (should be exactly one)")
    if site.meta_description:
        points += 25
        notes.append("Meta description present")
    else:
        notes.append("No meta description found")
    return CategoryScore("Content Depth", CATEGORY_WEIGHTS["content_depth"], min(points, 100), notes)


def build_scorecard(engine_results: list[EngineResult], site: SiteSignals | None,
                      domain: str | None = None) -> Scorecard:
    categories = [
        _score_ai_visibility(engine_results),
        _score_credibility(site),
        _score_citations_local(site, engine_results, domain),
        _score_structured_data(site),
        _score_content_depth(site),
    ]
    composite = round(sum(c.weighted_points for c in categories), 1)
    return Scorecard(categories=categories, composite=composite,
                      recommended_package=recommend_package(composite))
