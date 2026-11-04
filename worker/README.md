# Cloudflare Worker (option B, optional)

- **What it does:** a small Worker that
  - turns a search sentence into filters with a Workers AI LLM, and
  - optionally searches Vectorize.
- **Fallback:** the website falls back to in-browser search (option A) if the Worker fails or hits its quota.

## Setup notes

- Create it with `npm create cloudflare@latest` inside this folder.
- **Keys and account IDs:**
  - Put them in `.dev.vars` locally and in Cloudflare secrets for production.
  - Both `.dev.vars` and `.wrangler/` are git-ignored.
- **Stay on the Workers Free plan:** going over the daily limit returns errors instead of charging money. Check current limits in the Cloudflare docs.
- **Embedding model:** the embedding model used to build the Vectorize index must be the same model the Worker uses for queries.
