# Data

Everything in this folder except this README is git-ignored. Get the files from the team Google Drive.

## Folder layout

Use the same folder names as on Google Drive, so the loader finds the files:

```
data/
├── raw/
│   ├── 2025-12-xx/      ← one folder per quarterly snapshot (scrape date)
│   ├── 2026-03-xx/
│   ├── 2026-06-xx/
│   └── 2026-09-14/
│       ├── listings.csv.gz          (detailed listings, ~27 MB)
│       ├── reviews.csv.gz           (full review history, ~200 MB)
│       ├── calendar.csv.gz          (availability next 365 days, no prices)
│       └── neighbourhoods.geojson   (269 neighbourhood shapes)
├── interim/             ← cleaned files you create
└── processed/           ← model-ready files and embeddings
```

- Only the detailed `.csv.gz` files are needed. The summary `listings.csv` and `reviews.csv` are subsets.
- Rename each snapshot folder to its scrape date (YYYY-MM-DD) so they sort correctly.

## Loading

Always load through the shared loader:

```python
from airbnb.load import load_listings, load_reviews, load_calendar, short_stay_with_price

listings = load_listings("latest")                     # newest snapshot
history  = load_listings("all", latest_only=False)     # all snapshots, with a `snapshot` column
reviews  = load_reviews(since="2024-01-01", english_only=True)
prices   = short_stay_with_price(listings)              # price-module modelling set
```

## Things to know

- **Reviews:** each snapshot's reviews file holds the full history, so load ONE snapshot (the latest) to avoid duplicates.
- **Repeated listings:** the same listing appears in several snapshots. Use `latest_only=True` unless you are studying change over time.
- **Price:**
  - `price` is text; use `price_num` or `log_price`.
  - It is the quote for one check-in date (mostly mid-September).
  - For listings that require 30+ nights, it is a monthly rate converted to a nightly price.
- **Empty columns:** these are completely empty in the Sep 2026 snapshot: `host_since`, `host_response_rate`, `host_acceptance_rate`, `instant_bookable`, `neighborhood_overview`, and the numeric `bathrooms` (use `bathrooms_text` instead).
- **Estimated columns:** `estimated_occupancy_l365d` and `estimated_revenue_l365d` are Inside Airbnb's estimates from review counts, not real bookings.
- **Calendar:** `available = f` does not always mean booked; the host may have blocked the date.
- **Photos:** only one cover photo URL per listing (`picture_url`). If you download photos, keep them in `data/images/` (ignored).

## Source and credit

[Inside Airbnb](https://insideairbnb.com/get-the-data/), Los Angeles. Credit the source on the website and in the report, and follow its license terms.
