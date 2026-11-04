# Module 4: Review insights

**Goal:** show users the real downsides of a listing without reading 100 mostly positive reviews, and show hosts what to fix first.

**Owner:** _name_

## Key idea

- **Reviews are very positive:** the median rating is 4.91. Clustering whole reviews only gives "clean, great host, great location".
- **Complaints are rare** in a sample of reviews from 2025 on:
  - noise: 2.6%
  - dirty: 1.4%
  - smell: 1.3%
- **So we focus on negative sentences only.**

## Inputs

- Reviews from the latest snapshot, from 2024 on, English only (`load_reviews(since="2024-01-01", english_only=True)`).
- Listing sub-scores: cleanliness, accuracy, check-in, communication, location, value.

## Methods

1. Split reviews into sentences.
2. A pretrained Transformer sentiment model marks negative sentences.
3. Embed the negative sentences and cluster them with K-means or GMM to get complaint topics, e.g. noise, cleanliness, parking, broken items, privacy.
4. **Driver analysis:** regress each sub-score on the share of each complaint topic, which tells us which complaint lowers ratings most (with confidence intervals).
5. **LLM summary per listing:** three pros and three cons.

## Evaluation

- **Topics:** hand-check about 200 sentences for correct topic labels.
- **Summaries:** hand-check a sample for invented facts (hallucination rate).
- **Trends:** topic shares over time (2021–2026) and by area. The by-area results feed the market map.

## To-do

- [ ] Sentence splitting + language filter
- [ ] Sentiment model, keep negative sentences
- [ ] Embeddings + clustering, name the topics
- [ ] Driver regression on sub-scores
- [ ] LLM summaries + hallucination check
- [ ] Export `web/data/review_insights.json` (per listing pros/cons, per area topics)

## Reminders

- Do not show reviewer names on the website.
- Summaries may only use the listing's own reviews; never add facts.
