# AEO/GEO/SEO Visibility Screener

A template audit tool: point it at a business (name, category, location,
optional website) and it tells you what AEO (Answer Engine Optimization),
GEO (Generative Engine Optimization), and technical SEO work that business
actually needs to start showing up when someone asks an AI assistant "who
is the best `<category>` in `<location>`."

It does this by actually running that question against real AI engines and
checking whether the business gets named — not by guessing from a generic
checklist. See [`examples/cosmetic-dentist-honolulu/`](examples/cosmetic-dentist-honolulu/)
for a real, live-captured run this was built from.

This is meant to be the engine behind an **AI Visibility Audit** — a
free/flagship deliverable to hand a prospect, and the diagnostic that decides
whether they need a Full-GEO buildout or ongoing monitoring next.

## What it actually does

1. **Runs a batch of realistic prompts** ("who is the best X in Y", "top
   rated X near Y", ...) against the AI engines that can be automated today
   (ChatGPT, Google, Bing), and checks whether the business is named and who
   else got cited alongside it.
2. **Loads manually-captured transcripts** for the engines that can't be
   automated right now (Perplexity, Gemini — see below for why), so every
   engine gets scored on equal footing.
3. **Fetches the business's own website** and checks the on-site signals
   that determine whether an AI crawler can extract facts from it at all:
   schema.org structured data, an `llms.txt`, FAQ content, stated
   credentials/years of experience/awards, and basic NAP (name/address/
   phone) consistency.
4. **Scores all of it** into a weighted 0-100 composite across five
   categories, and maps the score to a recommended next package (Full-GEO
   Buildout / AI Visibility Monitoring / Maintain & Expand).
5. **Outputs a prioritized action plan** (Quick Wins vs. Strategic
   Investments) — concrete, sellable line items, not vague advice.

## Quickstart

```bash
pip install -r requirements.txt
python -m playwright install chromium   # only needed for the ChatGPT engine

python cli.py \
  --business "Wynn H. Okuda, DMD" \
  --category "cosmetic dentist" \
  --location "Honolulu, HI" \
  --website https://www.okudacosmeticdentistry.com
```

This prints progress as it runs and writes a Markdown report to
`reports/<business-slug>.md`. Run `python cli.py --help` for every option
(custom prompts, which engines to run, output path, etc.).

### Filling in the engines that can't be automated

Perplexity currently hard-gates a single query behind sign-in, and Gemini
requires a logged-in Google account — confirmed live, not assumed (see the
case study). For those, run the prompt yourself in the engine's UI, paste
the answer into a file in `captures/` following the format in
[`captures/README.md`](captures/README.md), and the next run picks it up
automatically.

Engine automatability is tracked centrally in `screener/config.py` under
`ENGINES` — if ChatGPT/Google/Bing start blocking the automated path too
(these things drift), flip that engine to manual there rather than fighting
the block in code.

### Running it on autopilot

`.github/workflows/run-screener.yml` runs the same CLI from a
`workflow_dispatch` trigger — useful because GitHub Actions runners have
normal outbound internet access, unlike a network-locked sandbox. It's
best-effort for the same reasons as above; check the job log for per-engine
errors.

## How scoring works

Five weighted categories (`screener/config.py` → `CATEGORY_WEIGHTS`):

| Category | Weight | What it measures |
|---|---|---|
| AI Visibility | 35% | Named across the engine/prompt runs actually attempted |
| Credibility Signals | 25% | Stated credentials, years of experience, awards/press on-site |
| Citations & Local Signals | 20% | Third-party domains citing the business + NAP presence on-site |
| Structured Data | 12% | schema.org markup, FAQ content, `llms.txt` |
| Content Depth | 8% | Homepage word count, H1 usage, meta description |

The weighting is a judgment call, grounded in the case study: getting named
turned out to depend on the AI having a specific, quotable, third-party-
verified fact to reach for — not on technical SEO alone. Retune the weights
in `screener/config.py` if a different vertical warrants it.

## Repo layout

```
cli.py                      entrypoint — see --help
screener/
  config.py                 prompt templates, engine list, scoring weights, package tiers
  engines.py                automated engine runners (Google, Bing, ChatGPT via Playwright)
  manual_capture.py         loader for pasted-in transcripts (Perplexity, Gemini, ...)
  site_signals.py           on-site technical/structured-data/credibility checks
  scorer.py                 combines everything into the weighted scorecard
  recommend.py              turns gaps into a prioritized action plan
  report.py                 renders the Markdown report
prompts/example_prompts.txt example custom prompt list (--prompts)
captures/README.md          manual-capture file format
examples/cosmetic-dentist-honolulu/   real, live-captured case study
.github/workflows/run-screener.yml    on-demand CI run
```

## Connectors, skills, and plugins worth adding

Searched the MCP connector registry and the Cowork skill catalog while
building this — worth connecting depending on how far you want to take it:

- **Ahrefs** (`Ahrefs` connector) — has purpose-built AI-search tracking
  tools (`brand-radar-ai-responses`, `brand-radar-mentions-overview/history`,
  `brand-radar-cited-domains/pages`) that do at scale, continuously, and
  within each engine's terms of service what this repo's engine runners do
  one-off and best-effort. This is the natural upgrade path for the
  **AI Visibility Monitoring** package tier — connect it once a client signs
  on for ongoing tracking rather than one-off audits. Requires a paid Ahrefs
  plan with API access.
- **Semrush** (`Semrush` connector) — keyword research, competitor gap
  analysis, backlink data. Strengthens the traditional-SEO side of a Full-GEO
  buildout (keyword targeting for the FAQ/content recommendations this tool
  surfaces).
- **OpenRush** — live SERP data, rank tracking, competitor discovery,
  backlink-gap analysis. A cheaper/alternative option to Semrush for the
  same job, worth comparing.
- **`marketing:seo-audit` skill** (already available via the installed
  `marketing` plugin) — a general-purpose technical/on-page/keyword SEO
  audit. Complementary, not overlapping: run it for the classic-SEO half of
  a Full-GEO engagement (keyword gaps, on-page issues, backlink profile),
  and this tool for the AI-visibility half. Neither replaces the other —
  `seo-audit` doesn't test AI engines, and this tool doesn't do keyword
  research or backlink analysis.

None of these are required — the tool works standalone with plain HTTP
requests and browser automation. They're upgrades for when a client's
engagement justifies the API cost, particularly Ahrefs for anything that
needs to run as recurring monitoring rather than a one-time audit.

## Limitations, stated plainly

- Automated engine coverage is inherently fragile — these are unofficial
  integrations against consumer UIs, not stable APIs, and any of them can
  start blocking automated traffic at any time. Treat every automated run's
  errors as real signal, not a bug to route around.
- The Google/Bing runners fetch the plain server-rendered SERP. Anything
  Google renders client-side (AI Mode, AI Overviews) will not appear in an
  automated run — capture those manually, same as Perplexity/Gemini.
- Structured scraping of Google/Bing result cards (ratings, review counts,
  local-pack structure) was deliberately *not* attempted — their markup is
  obfuscated and changes constantly, so this only trusts full-page visible
  text for mention detection. For real local-pack/rating data, use a paid
  SERP API or the Ahrefs/Semrush connectors above.
- This produces a diagnostic, not a guarantee — the recommendations are
  informed by one real case study plus general GEO/AEO principles, not a
  large-scale statistical study of what actually moves AI citations.
