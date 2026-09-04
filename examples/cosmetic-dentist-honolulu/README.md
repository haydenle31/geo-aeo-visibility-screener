# Case study: "who is the best cosmetic dentist in honolulu"

This is a real run, done live in a browser on 2026-09-04, not a simulated
example. It's the query this whole tool is built to answer at scale: what
does a business actually need to do to get named when someone asks an AI
assistant for a recommendation in their category and city.

## What happened, engine by engine

| Engine | Result |
|---|---|
| **ChatGPT** (anonymous, no login) | Answered directly and named one business by name as its "top pick," with reasons. See [captures/chatgpt.md](captures/chatgpt.md). |
| **Google** (organic + local pack) | Local pack (map cards) surfaced three practices by review volume/rating; the #1 organic result was a Yelp directory page, not any single practice's own site. See [captures/google.md](captures/google.md). |
| **Bing** | First screen was dominated by loosely-related paid ads; a real answer would require digging past them. See [captures/bing.md](captures/bing.md). |
| **Perplexity** | Blocked — hit a hard sign-in wall on the very first query, no anonymous access. See [captures/perplexity.md](captures/perplexity.md). |

## The pattern that repeated across every engine

One name showed up everywhere: **Dr. Wynn Okuda** (Cosmetic Dentist Honolulu :
Wynn H. Okuda DMD Inc). Not because of a single trick — because the same few
signals kept reinforcing each other:

1. **A named, verifiable credential.** ChatGPT's reasoning led with "AACD
   Accredited Fellow, the highest credential awarded by the American Academy
   of Cosmetic Dentistry" — a specific, checkable fact, not "highly rated."
2. **A specific, stated number.** "28+ years of cosmetic/restorative
   experience." AI answers reach for quotable numbers over vague claims.
3. **A recurring, name-checked local award.** "Voted Best Cosmetic Dentist in
   Hawaii" (Honolulu Star-Advertiser poll) — appeared on Google in his own
   site's meta description, on a second branded property (Dental Day Spa of
   Hawaii, "founded by world renowned cosmetic dentist Dr. Wynn Okuda"), and
   was the exact reasoning ChatGPT cited.
4. **Third-party directory presence.** ChatGPT's alternate picks came
   tagged with sources like AACD's own directory, ThreeBestRated, and a
   competing practice's own branding — every business ChatGPT named had a
   citable third-party source behind it.
5. **Consistent NAP across properties.** The same practice, address, and
   positioning showed up on his own site, his spa brand's site, and multiple
   directories — nothing contradicted anything else.
6. **Content shaped like the question being asked.** Google's Local Pack
   entry literally noted *"Their website mentions best cosmetic dentist"* —
   Google matched the page's own text against the query.

None of that is exotic. It's schema-worthy structured facts, a specific
credential and number, a real award pursued and then repeated consistently,
and citations on the directories that matter for the niche — the same five
categories this tool's scorecard measures.

## What this means for the product

This is exactly why `screener/scorer.py` weights **AI Visibility** and
**Credibility Signals** highest (35% + 25% = 60% of the composite): getting
named isn't a technical-SEO problem first, it's a "does the AI have a
specific, quotable, third-party-verified fact to reach for" problem.
Technical structured data (12%) is what makes those facts machine-readable;
it doesn't manufacture the facts themselves.

## Try it yourself

```bash
python cli.py --business "Wynn H. Okuda, DMD" --category "cosmetic dentist" \
  --location "Honolulu, HI" --website https://www.okudacosmeticdentistry.com \
  --engines google,bing,chatgpt
```

Then drop a real, signed-in Perplexity transcript into `captures/` to fill
the last gap this example hit. The generated report will score the actual
current state of the site — the numbers above are qualitative findings from
this capture, not a substitute for running the real tool against a real
site.
