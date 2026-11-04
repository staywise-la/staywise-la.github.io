# StayWise LA

ISYE 6740 (Fall 2026) final project · Georgia Tech

Find a good-value stay in Los Angeles with one sentence. Built on public Inside Airbnb data; not affiliated with Airbnb.

**Website:** https://staywise-la.github.io

---

## What we are building

- A web app that helps travelers search Airbnb listings in Los Angeles using plain language.
- Example query: *"pet-friendly place near Santa Monica under $250"*.
- Each search result also shows whether the price is fair and what guests complain about.
- A market map shows what each part of LA is like.

## Why

- **Main goal:** a search (retrieval) problem with clear ground truth, as the professor suggested.
- We generate test queries from listing facts (amenities, area, price, bedrooms), so we know the correct answers and can measure accuracy objectively.
- Each module uses a different part of the course: supervised learning, unsupervised learning, optimization, and deep learning.

## The four modules

| # | Module | What it does for users | Main methods |
|---|--------|------------------------|--------------|
| 1 | **Search** (core) | Type one sentence, get matching listings | LLM query parsing, Transformer text embeddings, CLIP image embeddings, boosting ranker, PCA compression |
| 2 | **Price evaluation** | See if a listing is fairly priced ("14% below similar stays") | Linear regression, Lasso, random forest, boosting, kNN, quantile regression |
| 3 | **Market map** | Understand each area at a glance | K-means and GMM on neighbourhood features, graph (spectral) clustering for connected regions |
| 4 | **Review insights** | See the real downsides without reading 100 reviews | Sentence-level sentiment, clustering of negative sentences, regression of complaints on ratings, LLM summaries |

Details, owners and to-do lists live in each module folder: [`modules/`](modules/).

## Data

- **Source:** [Inside Airbnb](https://insideairbnb.com/get-the-data/), Los Angeles, four quarterly snapshots (past year).
- **Size (Sep 2026 snapshot):** 43,781 listings, 1.89M reviews, 269 neighbourhoods.
- **Data is NOT stored in git.** Download it from the team Google Drive. See [`data/README.md`](data/README.md).
- **Known limits:**
  - 16% of listings have no price.
  - 47% of listings require 30+ nights (monthly rentals).
  - The calendar file has no prices.

## Repository layout

```
staywise-la.github.io/
├── README.md               ← you are here
├── .gitignore              ← blocks data, secrets, .DS_Store, caches
├── .env.example            ← copy to .env for local settings and keys
├── requirements.txt
├── pyproject.toml          ← lets you `pip install -e .`
├── data/                   ← local only (git-ignored), see data/README.md
│   ├── raw/<snapshot>/     ← files exactly as downloaded
│   ├── interim/            ← cleaned intermediate files
│   └── processed/          ← model-ready tables, embeddings
├── src/airbnb/             ← SHARED code: everyone imports from here
│   ├── config.py           ← paths and constants
│   ├── load.py             ← load_listings(), load_reviews(), ...
│   └── evaluate.py         ← Recall@K, nDCG, MRR, MAE, bootstrap CI
├── modules/
│   ├── 1_search/
│   ├── 2_price/
│   ├── 3_market_map/
│   └── 4_reviews/          ← each has notebooks/, scripts, README with to-dos
├── notebooks/              ← shared EDA only
├── web/                    ← the website (published with GitHub Pages)
│   └── data/               ← small precomputed JSON the site reads
├── worker/                 ← Cloudflare Worker for LLM search (option B)
├── reports/                ← proposal, final report, slides, figures/
├── tests/                  ← tests for shared code
└── .github/                ← Pages deploy workflow, PR template
```

## Getting started

1. Clone the repo:
   ```bash
   git clone https://github.com/staywise-la/staywise-la.github.io.git
   cd staywise-la.github.io
   ```
2. Create an environment and install:
   ```bash
   python -m venv .venv
   source .venv/bin/activate          # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   pip install -e .                   # makes `import airbnb` work everywhere
   nbstripout --install               # strips notebook outputs before commits
   ```
3. Download the data from Google Drive into `data/raw/` (see `data/README.md`).
4. Check it works:
   ```python
   from airbnb.load import load_listings, load_reviews
   listings = load_listings("latest")
   print(listings.shape)
   ```

## How we work together

- **Branches:**
  - `main` is always working.
  - Do your work on a branch named `<module>/<short-topic>`, e.g. `price/baseline-lasso`.
- **Pull requests:**
  - Open a PR into `main` and ask one teammate to review.
  - Keep PRs small: one idea per PR.
- **Issues and Projects board:** one issue per task, assigned to a person, tracked on the GitHub Projects board (To do → In progress → Done).
- **Notebooks:**
  - Name them `NN_initials_topic.ipynb`, e.g. `01_jc_eda_prices.ipynb`.
  - Move reusable code into `src/airbnb/` or the module's `.py` files.
- **Shared code:** change `src/airbnb/` only through a PR, because everyone depends on it.
- **Results:** every reported number comes from `airbnb.evaluate`, with a 95% confidence interval.

## Rules (please read)

- **Never commit data:** no CSV, Parquet, model weights or photos. `.gitignore` blocks most of it, but double-check `git status` before you commit.
- **Never commit keys:** keys go in `.env` (ignored). If a key is committed by accident, revoke it immediately; deleting the file is not enough.
- **No data leakage:**
  - Search must NOT index the amenity list it is tested on.
  - Price models use neighbourhood-grouped cross-validation.
  - Fit scalers and encoders on training data only.
- **Fixed random seed:** use `config.RANDOM_SEED` (6740).
- **Website data stays small:** files in `web/data/` should stay under about 20 MB each.
- **Cite the data:** credit Inside Airbnb on the website and in the report, and follow its license terms.

## Team

| Role | Owner | Module folder |
|------|-------|---------------|
| Data and shared evaluation | _name_ | `src/airbnb/`, `notebooks/` |
| Text search and LLM | _name_ | `modules/1_search/` |
| Image features and ranking | _name_ | `modules/1_search/` |
| Price model | _name_ | `modules/2_price/` |
| Market map and review insights | _name_ | `modules/3_market_map/`, `modules/4_reviews/` |

## Timeline

| Week | Dates | Goal |
|------|-------|------|
| 1 | Nov 2–8 | Repo, data on Drive, loader works for everyone, EDA, roles fixed |
| 2 | Nov 9–15 | Baselines for every module (BM25, linear price model, first clusters, review sentences) |
| 3 | Nov 16–22 | Main models and full evaluation with confidence intervals |
| 4 | Nov 23–29 | Website integration, ablations, error analysis (Thanksgiving Nov 26) |
| 5 | Nov 30–Dec 6 | Report, slides, rehearsal; only bug fixes |
| — | Dec 7–9 | Final presentation |

## Website

- **Published with GitHub Pages** at https://staywise-la.github.io, from the `web/` folder by `.github/workflows/pages.yml`.
- **All models run offline.** The site only reads precomputed JSON, plus in-browser search with transformers.js.
- **Optional:** LLM query parsing through a Cloudflare Worker (`worker/`), which falls back to browser search if it fails.
