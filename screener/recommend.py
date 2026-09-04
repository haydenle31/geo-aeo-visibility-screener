"""
Turns detected gaps into a prioritized, sellable action list — same
Quick Wins / Strategic Investments split as the marketing plugin's
/seo-audit skill, so this report slots into the same workflow.

Built off the same boolean signals the scorer uses (not by re-parsing its
notes) so the two never drift out of sync.
"""
from __future__ import annotations

from dataclasses import dataclass

from .engines import EngineResult
from .site_signals import SiteSignals


@dataclass
class Action:
    what: str
    why: str
    impact: str    # High / Medium / Low
    effort: str    # Quick win / Moderate / Substantial


def build_action_plan(site: SiteSignals | None, engine_results: list[EngineResult]) -> list[Action]:
    actions: list[Action] = []
    attempted = [r for r in engine_results if r.success]
    mention_rate = (sum(r.mentioned for r in attempted) / len(attempted)) if attempted else 0

    if site is None or not site.fetched_ok:
        actions.append(Action(
            what="Get the website reachable and re-run this audit",
            why="No on-site signals could be read, so most of this scorecard is a floor, "
                "not a real measurement.",
            impact="High", effort="Quick win",
        ))
        return actions

    if not site.has_local_business_schema:
        actions.append(Action(
            what="Add schema.org JSON-LD structured data (LocalBusiness + the specific "
                 "sub-type — Dentist, Attorney, Restaurant, etc.)",
            why="This is the most direct way to hand an AI crawler machine-readable facts "
                "(name, address, phone, services, hours) instead of making it infer them "
                "from prose.",
            impact="High", effort="Quick win",
        ))
    if not site.has_faq_schema and not site.faq_style_headings:
        actions.append(Action(
            what="Publish an FAQ section that directly answers question-phrased queries "
                 "(\"who is the best ___ in ___\", \"how much does ___ cost\") with "
                 "FAQPage schema",
            why="Every prompt this tool runs is phrased as a question — content that "
                "mirrors that phrasing is what gets lifted into an AI answer verbatim.",
            impact="High", effort="Moderate",
        ))
    if not site.credential_mentions:
        actions.append(Action(
            what="State credentials explicitly on the homepage/About page (board "
                 "certifications, professional-association accreditation, licenses)",
            why="In the live capture (see examples/), the #1 recommendation was picked "
                 "specifically because the AI could name a specific accreditation.",
            impact="High", effort="Quick win",
        ))
    if not site.stated_years_experience:
        actions.append(Action(
            what="Add an explicit years-of-experience statement",
            why="AI answers favor specific, quotable numbers over vague claims of "
                "experience.",
            impact="Medium", effort="Quick win",
        ))
    if not site.award_mentions:
        actions.append(Action(
            what="Pursue and then publicize a local 'best of' award, press feature, or "
                 "industry recognition",
            why="Award and press language was directly cited as a differentiator in the "
                "live capture — it's the kind of third-party validation an AI model "
                "treats as trustworthy.",
            impact="High", effort="Substantial",
        ))
    if not site.has_phone_on_site or not site.has_address_on_site:
        actions.append(Action(
            what="Put a full NAP block (name, address, phone) in the site footer or "
                 "header, matching the Google Business Profile exactly",
            why="Inconsistent or missing NAP is one of the most common reasons a "
                "legitimate local business doesn't get surfaced confidently.",
            impact="Medium", effort="Quick win",
        ))
    if not site.has_llms_txt:
        actions.append(Action(
            what="Add an llms.txt at the site root summarizing what the business does, "
                 "who it serves, and its key facts in plain language",
            why="Still an early, informally-adopted convention — cheap to add now and "
                "positions the site ahead of competitors before it's standard practice.",
            impact="Low", effort="Quick win",
        ))
    if site.word_count < 300:
        actions.append(Action(
            what="Expand homepage content — aim for 400-800+ words of substantive text",
            why="Thin pages give an AI engine little to extract or quote from.",
            impact="Medium", effort="Moderate",
        ))
    if site.h1_count != 1:
        actions.append(Action(
            what=f"Fix H1 usage ({site.h1_count} found on homepage — should be exactly 1)",
            why="Basic on-page signal, quick to fix, no reason to leave it broken.",
            impact="Low", effort="Quick win",
        ))
    if not site.meta_description:
        actions.append(Action(
            what="Add a meta description to the homepage",
            why="Cheap, standard fix with no real cost to skipping it any longer.",
            impact="Low", effort="Quick win",
        ))

    if attempted and mention_rate < 0.5:
        actions.append(Action(
            what="Build citations on 2-3 authoritative directories/aggregators in this "
                 "space (the live capture found Yelp's 'Best 10' list ranking above "
                 "individual practice sites — that pattern generalizes)",
            why=f"Only mentioned in {round(mention_rate * 100)}% of the prompt runs that "
                f"succeeded — third-party citation sites are frequently what an AI engine "
                f"cites when it won't commit to a single 'best' pick.",
            impact="High", effort="Moderate",
        ))
    if not attempted:
        actions.append(Action(
            what="Get at least one engine run succeeding (see the errors in this report) "
                 "before treating the AI Visibility score as real",
            why="Zero successful runs means the visibility score is an unmeasured floor, "
                "not an actual result.",
            impact="High", effort="Quick win",
        ))

    return actions


def split_quick_wins(actions: list[Action]) -> tuple[list[Action], list[Action]]:
    quick = [a for a in actions if a.effort == "Quick win"]
    strategic = [a for a in actions if a.effort != "Quick win"]
    return quick, strategic
