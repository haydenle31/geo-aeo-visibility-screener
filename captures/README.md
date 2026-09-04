---
engine: perplexity
prompt: who is the best cosmetic dentist in honolulu
---
(Delete this example and replace with a real pasted transcript.)

To capture a non-automatable engine (Perplexity, Gemini — see screener/config.py
ENGINES for the current list and why):

1. Open the engine in a normal browser and sign in if it requires it.
2. Run the exact prompt this tool printed when it skipped that engine.
3. Copy the full answer text (links included, if any).
4. Create a new file in this folder named `<engine>__<short-slug>.md`.
5. Keep the `---` frontmatter block above with the correct `engine:` and
   `prompt:` values, and paste the answer below the second `---`.

The next `python cli.py` run will pick up every `.md` file in this folder
automatically and score it alongside the automated engine runs.
