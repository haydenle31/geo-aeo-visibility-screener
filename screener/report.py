"""Renders the collected engine results, site signals, scorecard, and
action plan into a single Markdown report."""
from __future__ import annotations

from datetime import datetime, timezone

from .engines import EngineResult
from .recommend import Action, split_quick_wins
from .scorer import Scorecard
from .site_signals import SiteSignals


def _engine_section(results: list[EngineResult]) -> str:
    lines = ["## Engine-by-Engine Results\n"]
    if not results:
        lines.append("_No engine runs were attempted._\n")
        return "\n".join(lines)

    lines.append("| Engine | Method | Prompt | Mentioned? | Notes |")
    lines.append("|---|---|---|---|---|")
    for r in results:
        mentioned = "✅ Yes" if r.mentioned else ("❌ No" if r.success else "⚠️ Error")
        note = r.error if not r.success else (
            f"cited alongside: {', '.join(r.cited_domains[:5])}" if r.cited_domains else "—"
        )
        lines.append(f"| {r.engine} | {r.method} | {r.prompt} | {mentioned} | {note} |")
    lines.append("")

    for r in results:
        if r.success and r.mention_context:
            lines.append(f"**{r.engine}** — \"{r.prompt}\"")
            for ctx in r.mention_context[:2]:
                lines.append(f"> …{ctx}…")
            lines.append("")

    return "\n".join(lines)


def _scorecard_section(sc: Scorecard) -> str:
    lines = [f"## Scorecard — {sc.composite}/100\n"]
    lines.append(f"**Recommended next step: {sc.recommended_package['name']}**  ")
    lines.append(f"{sc.recommended_package['description']}\n")
    lines.append("| Category | Weight | Score | Weighted |")
    lines.append("|---|---|---|---|")
    for c in sc.categories:
        lines.append(f"| {c.name} | {c.weight}% | {c.score}/100 | {c.weighted_points} |")
    lines.append("")
    for c in sc.categories:
        lines.append(f"**{c.name}**")
        for note in c.notes:
            lines.append(f"- {note}")
        lines.append("")
    return "\n".join(lines)


def _site_signals_section(site: SiteSignals | None) -> str:
    if site is None:
        return "## Website Signals\n\n_No website URL was provided — technical/structured-" \
               "data signals were not checked._\n"
    if not site.fetched_ok:
        return f"## Website Signals\n\n_Could not fetch {site.url}: {site.error}_\n"
    lines = [f"## Website Signals — {site.url}\n"]
    lines.append(f"- Title: {site.title or '_missing_'}")
    lines.append(f"- Meta description: {site.meta_description or '_missing_'}")
    lines.append(f"- H1 count: {site.h1_count}")
    lines.append(f"- Word count (homepage): {site.word_count}")
    lines.append(f"- HTTPS: {'yes' if site.has_https else 'no'}")
    lines.append(f"- robots.txt: {'found' if site.has_robots_txt else 'not found'}")
    lines.append(f"- sitemap.xml: {'found' if site.has_sitemap_xml else 'not found'}")
    lines.append(f"- llms.txt: {'found' if site.has_llms_txt else 'not found'}")
    lines.append(f"- schema.org types found: {', '.join(site.schema_types_found) or 'none'}")
    lines.append(f"- Phone number on homepage: {'yes' if site.has_phone_on_site else 'no'}")
    lines.append(f"- Full address on homepage: {'yes' if site.has_address_on_site else 'no'}")
    if site.stated_years_experience:
        lines.append(f"- Stated years of experience: {site.stated_years_experience}+")
    lines.append("")
    return "\n".join(lines)


def _action_plan_section(actions: list[Action]) -> str:
    quick, strategic = split_quick_wins(actions)
    lines = ["## Prioritized Action Plan\n"]
    lines.append("### Quick Wins (do this week)\n")
    if not quick:
        lines.append("_None identified — the foundations already cover the basics._\n")
    for a in quick:
        lines.append(f"- **{a.what}** _(impact: {a.impact})_")
        lines.append(f"  {a.why}")
    lines.append("")
    lines.append("### Strategic Investments (plan for this quarter)\n")
    if not strategic:
        lines.append("_None identified._\n")
    for a in strategic:
        lines.append(f"- **{a.what}** _(impact: {a.impact}, effort: {a.effort})_")
        lines.append(f"  {a.why}")
    lines.append("")
    return "\n".join(lines)


def render_markdown(business_name: str, category: str, location: str,
                      site: SiteSignals | None, engine_results: list[EngineResult],
                      scorecard: Scorecard, actions: list[Action]) -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    parts = [
        f"# AI Visibility Audit — {business_name}",
        f"\n_{category} · {location} · generated {generated}_\n",
        "## Executive Summary\n",
        _executive_summary(business_name, scorecard, engine_results),
        _scorecard_section(scorecard),
        _engine_section(engine_results),
        _site_signals_section(site),
        _action_plan_section(actions),
    ]
    return "\n".join(parts)


def _executive_summary(business_name: str, sc: Scorecard, engine_results: list[EngineResult]) -> str:
    attempted = [r for r in engine_results if r.success]
    mentioned = [r for r in attempted if r.mentioned]
    if attempted:
        visibility_line = (f"{business_name} was mentioned in {len(mentioned)} of "
                            f"{len(attempted)} successful prompt runs across the engines tested.")
    else:
        visibility_line = "No engine runs succeeded, so current AI visibility is unmeasured."

    band = "strong foundation" if sc.composite >= 80 else \
        "needs targeted work" if sc.composite >= 55 else "has critical gaps to close"

    return (
        f"{visibility_line} Composite score: **{sc.composite}/100** — {band}. "
        f"Recommended next step: **{sc.recommended_package['name']}**.\n"
    )
