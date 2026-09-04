#!/usr/bin/env python3
"""
AEO/GEO/SEO Visibility Screener — CLI entrypoint.

Usage:
    python cli.py --business "Wynn H. Okuda, DMD" --category "cosmetic dentist" \\
        --location "Honolulu, HI" --website https://www.okudacosmeticdentistry.com

Run `python cli.py --help` for all options.
"""
from __future__ import annotations

import argparse
import os
import sys

from screener import config, engines, manual_capture, recommend, report, scorer, site_signals


def build_prompts(category: str, location: str) -> list[str]:
    return [t.format(category=category, location=location) for t in config.DEFAULT_PROMPT_TEMPLATES]


def main() -> int:
    parser = argparse.ArgumentParser(description="Screen a business's AEO/GEO/SEO visibility.")
    parser.add_argument("--business", required=True, help="Business or practitioner name, e.g. 'Wynn H. Okuda, DMD'")
    parser.add_argument("--category", required=True, help="Service category, e.g. 'cosmetic dentist'")
    parser.add_argument("--location", required=True, help="Location, e.g. 'Honolulu, HI'")
    parser.add_argument("--website", default=None, help="Business website URL (recommended — enables on-site checks)")
    parser.add_argument("--engines", default="google,bing,chatgpt",
                         help="Comma-separated automated engines to run (default: google,bing,chatgpt). "
                              "See screener/config.py ENGINES for the full list and what's automatable.")
    parser.add_argument("--captures-dir", default="captures",
                         help="Directory of manually-pasted transcripts for non-automatable engines "
                              "(default: ./captures — see manual_capture.py for the file format)")
    parser.add_argument("--prompts", default=None,
                         help="Path to a text file of custom prompts, one per line, overriding the "
                              "default templates (each is used as-is, no {category}/{location} filling)")
    parser.add_argument("--out", default=None,
                         help="Output path for the Markdown report (default: reports/<business-slug>.md)")
    parser.add_argument("--headed", action="store_true",
                         help="Run the ChatGPT browser automation headed (visible) instead of headless — "
                              "useful for debugging if it stops working")
    args = parser.parse_args()

    prompts = (
        [line.strip() for line in open(args.prompts, encoding="utf-8")
         if line.strip() and not line.strip().startswith("#")]
        if args.prompts else build_prompts(args.category, args.location)
    )

    engine_list = [e.strip() for e in args.engines.split(",") if e.strip()]
    unknown = [e for e in engine_list if e not in config.ENGINES]
    if unknown:
        print(f"Unknown engine(s): {', '.join(unknown)}. Known engines: {', '.join(config.ENGINES)}", file=sys.stderr)
        return 1

    print(f"Running {len(prompts)} prompt(s) across {len(engine_list)} engine(s) for "
          f"'{args.business}' ({args.category}, {args.location})...\n")

    results: list[engines.EngineResult] = []
    for engine_name in engine_list:
        meta = config.ENGINES[engine_name]
        if not meta["automatable"]:
            print(f"  [{engine_name}] not automatable — {meta['notes']} (skipping; use --captures-dir)")
            continue
        for prompt in prompts:
            print(f"  [{engine_name}] running: {prompt!r}")
            kwargs = {"headless": not args.headed} if engine_name == "chatgpt" else {}
            result = engines.run_engine(engine_name, prompt, args.business, args.website, **kwargs)
            status = "mentioned" if result.mentioned else ("no mention" if result.success else f"ERROR: {result.error}")
            print(f"    -> {status}")
            results.append(result)

    manual_results = manual_capture.load_captures_dir(args.captures_dir, args.business, args.website)
    if manual_results:
        print(f"\nLoaded {len(manual_results)} manual capture(s) from {args.captures_dir}/")
        results.extend(manual_results)
    else:
        print(f"\nNo manual captures found in {args.captures_dir}/ — run the non-automatable "
              f"engines by hand and drop transcripts there to include them (see manual_capture.py).")

    site = None
    if args.website:
        print(f"\nFetching site signals from {args.website}...")
        site = site_signals.collect(args.website)
        if not site.fetched_ok:
            print(f"  WARNING: {site.error}")
    else:
        print("\nNo --website given — skipping on-site technical/structured-data checks.")

    sc = scorer.build_scorecard(results, site, args.website)
    actions = recommend.build_action_plan(site, results)
    markdown = report.render_markdown(args.business, args.category, args.location, site, results, sc, actions)

    out_path = args.out or os.path.join("reports", _slug(args.business) + ".md")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"\nComposite score: {sc.composite}/100 — recommended: {sc.recommended_package['name']}")
    print(f"Report written to {out_path}")
    return 0


def _slug(text: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in text).strip("-")


if __name__ == "__main__":
    raise SystemExit(main())
