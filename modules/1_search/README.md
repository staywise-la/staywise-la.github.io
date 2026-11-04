# Module 1: Search (core)

**Goal:** a user types one sentence ("pet-friendly place near Santa Monica under $250") and gets the best matching listings.

**Owners:** _text search + LLM_, _image features + ranking_

## Inputs

- **From listings:** `description`, `name`, `picture_url`, `neighbourhood_cleansed`, `price_num`, `bedrooms`, `accommodates`, `room_type`, and `amenity_list`. Use `amenity_list` ONLY to build test queries, never as search content.
- **From reviews:** the text of each listing's reviews.

## Ground truth

- Build test queries from structured facts, e.g. area + amenity + price cap + bedrooms. A listing is relevant if it meets every condition.
- Rewrite some queries into natural language with an LLM, to test robustness.
- Hand-label about 100 queries (top 10 results) to check that the automatic labels agree with people (Cohen's kappa).
- **Split queries into train, validation and test sets.** Only look at test scores at the end.

## Methods

- **Baseline:** BM25 keyword search on description + reviews.
- **Text:** Transformer sentence embeddings (MiniLM family); fine-tune on the train queries.
- **Image:** CLIP embeddings of the cover photo.
- **Query parsing:** an LLM turns the sentence into filters (area, max price, pets, bedrooms).
- **Ranking:** a boosting model combines BM25, text and image similarity, and filter matches.
- **Compression:** PCA from 384 to 128 dimensions or fewer, to keep the website fast.
- **Cold start:** train on older snapshots, test on listings that are new in the latest snapshot and have no reviews.

## Architecture comparison

- **A1:** MiniLM in the browser (transformers.js), no LLM.
- **B1:** Cloudflare Workers AI embeddings + Vectorize, no LLM.
- **B2:** B1 + LLM query parsing.
- **Hybrid:** LLM parsing in a Worker + browser search.
- **Compare:** first page load (cold and cached), download size, query latency (p50/p95), laptop vs. phone.

## Metrics

- Recall@10, nDCG@10, MRR (main); F1@10 (extra)
- Constraint satisfaction rate: share of the top 10 that really meet the price and pet conditions
- LLM parsing precision, recall and F1 per condition
- 95% bootstrap CI, plus a paired test between systems

## To-do

- [ ] Query generator + qrels saved to `data/processed/search/`
- [ ] BM25 baseline through `airbnb.evaluate`
- [ ] Text embeddings (zero-shot), then fine-tuned
- [ ] CLIP image embeddings (test downloading 100 photos first)
- [ ] LLM query parser + per-slot F1
- [ ] Boosting ranker + ablation (drop each feature group)
- [ ] Cold-start experiment
- [ ] Latency benchmark for A1 / B1 / B2 / hybrid
- [ ] Export compressed vectors to `web/data/` for the website

## Reminders

- Search content must not include the amenity list (leakage).
- Watch the Cloudflare free daily quota when running B on the test set.
