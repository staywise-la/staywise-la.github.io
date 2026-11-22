# Data processing record

How the raw Inside Airbnb files become the cleaned tables in `data/processed/`.
All numbers come from `data/processed/build_report.json` or from reading the files directly.

## Purpose

- `python -m airbnb.clean` turns four quarterly Inside Airbnb snapshots for Los Angeles into cleaned Parquet tables.
- It fixes formats, keeps every row, and adds flags. It does not decide what to filter out. Each module makes that choice.
- **Who uses the output:** all four modules (search, price, market map, reviews) and the website. Everyone reads the same tables through `airbnb.load`.

## Inputs

Each quarter is one folder in `data/raw/`, named by the first scrape date (`YYYY-MM-DD`). Every folder has the same four files.

| Folder | `listings.csv.gz` | `reviews.csv.gz` | `calendar.csv.gz` | `neighbourhoods.geojson` |
|---|---|---|---|---|
| `2025-12-04` | 45,585 rows (27.1 MB) | 1,785,848 rows (193.9 MB) | 16,638,552 rows (40.7 MB) | 0.7 MB |
| `2026-03-16` | 46,088 rows (27.9 MB) | 1,818,140 rows (198.3 MB) | 16,822,146 rows (38.9 MB) | 0.7 MB |
| `2026-06-15` | 43,751 rows (26.8 MB) | 1,856,294 rows (202.5 MB) | 16,035,198 rows (38.4 MB) | 0.7 MB |
| `2026-09-14` | 43,781 rows (26.8 MB) | 1,890,200 rows (207.2 MB) | 15,980,081 rows (38.6 MB) | 0.7 MB |

- **Source:** [Inside Airbnb](https://insideairbnb.com/get-the-data/), Los Angeles. The files are kept on the team Google Drive, not in git.
- **Reviews:** each reviews file holds the full review history, so only the latest one (`2026-09-14`) is used.

## How to reproduce

From the repo root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-core.txt
pip install -e .
python -m airbnb.clean
```

- **Run time:** about 1 min 15 s on a MacBook.
- **Options:**
  - `--snapshots 2026-09-14` cleans only the quarters you list.
  - `--skip-calendar` and `--skip-reviews` skip the large tables.
- **Re-running is safe:** each quarter's folder is replaced, never appended to.

**Environment used for the current output (built 2026-11-21):**
- Python 3.11.9
- pandas 3.1.1, pyarrow 26.0.1, numpy 2.4.6
- Git: branch `data/cleaning-pipeline`, commit `f54b9f872b28bbd5a789b1492780a9281f3d68e3` ("data: add cleaning pipeline to build Parquet tables from raw snapshots"). This commit has the `src/airbnb/clean.py` and `src/airbnb/load.py` used for this output.
- `src/airbnb/clean.py` git blob `7de18a496d7df4d9d312ff233653f440ea2bae51`. Check that your copy is the same file with `git hash-object src/airbnb/clean.py`.
- **Use the blob hash as the reference, not the commit hash.** The blob hash depends only on the file's content, so it stays the same after any merge. The commit hash above will change if the pull request is squash-merged or rebased.

## Outputs

Everything is written to `data/processed/`. This folder is ignored by git and shared on Google Drive.

| Path | Partitioning | Rows | Size |
|---|---|---|---|
| `listings/snapshot_date=<date>/part-0.parquet` | One folder per quarter | 2025-12-04: 45,585 · 2026-03-16: 46,088 · 2026-06-15: 43,751 · 2026-09-14: 43,781 · **total 179,205** | 232.1 MB total (57–60 MB per quarter) |
| `calendar/snapshot_date=<date>/part-0.parquet` | One folder per quarter | 2025-12-04: 16,638,552 · 2026-03-16: 16,822,146 · 2026-06-15: 16,035,198 · 2026-09-14: 15,980,081 · **total 65,475,977** | 30.5 MB total (7–8 MB per quarter) |
| `reviews.parquet` | None (latest snapshot only) | 1,890,200 | 528.3 MB |
| `neighbourhoods.geojson` | None (copied from `2026-09-14`) | n/a | 0.7 MB |
| `build_report.json` | None | n/a | row counts, checks and summary numbers |

- **Columns:** listings have 98 columns in each file, plus `snapshot_date` from the folder name, so 99 when loaded. Calendar has 6 columns (7 when loaded, with `snapshot_date`) and reviews has 7.

**Loading with `load_processed()`:**

```python
from airbnb.load import load_processed

listings = load_processed("listings")                              # all quarters, adds snapshot_date
latest   = load_processed("listings", snapshots="2026-09-14")      # one quarter
two      = load_processed("calendar", snapshots=["2026-06-15", "2026-09-14"])
reviews  = load_processed("reviews")                               # always the full table
```

- **`snapshots`:** `None` (the default) loads all quarters. You can also pass one date or a list of dates.
- **Reviews:** there is only one reviews table, so `snapshots` does not apply to it.

## Cleaning steps

Every step below is in `src/airbnb/clean.py`. No rows are removed. Raw columns are kept, and cleaned versions are added next to them.

- **Snapshot date:** `snapshot_date` comes from the folder name. The script checks that it falls within 3 days of the `last_scraped` range.
  - Why: so every row is tied to a known quarter.
- **Text cleaning** (`name`, `description`, `host_about`, review `comments`):
  - What it does: decodes HTML entities, removes real HTML tags (`<br />`, `<p>`, `<b>`, …), drops half tags left where Airbnb cut a description at 1,000 characters, turns non-breaking spaces and line breaks into spaces, collapses repeated spaces, and trims.
  - It keeps text that only looks like a tag, such as `<3` or `< 1mi`.
  - A value that is blank after cleaning becomes missing.
  - Why: search and review models need plain text.
- **Search text:** `text` is `name_clean` followed by `description_clean`, with ". " between them when the name doesn't already end in punctuation. `host_about_clean` is not included.
  - Why: one text field per listing for search.
- **Price parsing:** `"$1,234.00"` becomes `price_num = 1234.0`. Blank cells become missing.
  - Why: `price` is text and can't be used in models.
- **Type fixes:**
  - `t`/`f` columns become nullable booleans: `host_is_superhost`, `host_has_profile_pic`, `host_identity_verified`, `has_availability`, `instant_bookable`.
  - `"95%"` becomes `0.95` in `host_response_rate` and `host_acceptance_rate`.
  - Date text becomes datetimes in `last_scraped`, `host_since`, `first_review`, `last_review`, `calendar_last_scraped` and the `price_quote_*` dates.
  - Why: so you can filter and do arithmetic on these columns.
- **Amenities:** the JSON text becomes `amenities_list`, a list of trimmed strings. Text that can't be parsed becomes an empty list.
  - Why: easier to search and count.
- **Bathrooms:** `bathrooms_text` becomes `baths_num` (a number, with "Half-bath" counted as 0.5) and `bath_type` (`private` / `shared` / `unspecified`).
  - Why: `bathrooms_text` mixes a number and a type in one field.
- **Exact IDs:**
  - Columns covered:
    - listings: `id`, `scrape_id`, `host_id`, `host_profile_id`
    - reviews: `id` (renamed `review_id`), `listing_id`, `reviewer_id`
    - calendar: `listing_id`
  - These columns are read as text, then stored as nullable `Int64`.
  - Why: Airbnb IDs are larger than 2^53, so a float can't store them exactly. pandas reads a column with blanks as float, which would change the last digits.
- **Same columns in every quarter:** a column missing from one quarter is added there as empty.
  - Why: so all quarters can be loaded together.
- **Column type unification:** each column gets one type for all quarters. The type comes from the quarters where the column has data. ID columns and `desc_dup_group` are always `Int64`. `build_report.json` lists the 13 columns that this step changed under `listings_types_unified`:
  - Text in some quarters, empty in others, now `string`: `neighborhood_overview`, `host_response_time`, `host_neighbourhood`, `host_verifications`, `neighbourhood`, `price`, `price_quote_raw`.
  - Numbers, now `Float64`: `bathrooms`, `price_quote_total_price`, `price_quote_price_per_night`.
  - Dates, now `datetime64[us]`: `host_since`, `price_quote_checkin_date`, `price_quote_checkout_date`.
  - Why: without this, `data/processed/listings` can't be read as one table.
- **Calendar schema:** every quarter has exactly these 6 columns:

  | Column | Type |
  |---|---|
  | `listing_id` | `Int64` |
  | `date` | datetime |
  | `available` | boolean |
  | `minimum_nights` | `Int64` |
  | `maximum_nights` | `Int64` |
  | `price_num` | `Float64` |

  Other raw columns are dropped. The only one this removed was `adjusted_price`, in 2025-12-04, and it was empty.
  - Why: the raw calendar files have different columns in different quarters.
- **Neighbourhoods:** `neighbourhoods.geojson` is copied from the latest quarter.

## Team decisions

Principle: keep the information and add flags. Each module decides what to filter.

**Dropped:**
- **Columns that are empty in every quarter:** only `calendar_updated`.
  - Columns that are empty in some quarters but have data in another are kept. For example, `host_since`, `host_response_rate`, `neighbourhood` and `instant_bookable` have data only in 2025-12-04, and `bathrooms` is empty only in 2026-09-14.
  - Why: an empty column carries no information. A partly filled one still might.
- **Privacy columns:** listings lose `host_name`, `host_picture_url` and `host_thumbnail_url`. Reviews lose `reviewer_name`. They are still in `data/raw/` if ever needed.
  - Why: no module needs personal names or photos.

**Flagged only (rows kept):**
- **Price outliers:** `price_outlier` is true when `price_num` is below $20 or above $3,000, and missing when there is no price. 1,147 rows are flagged (all quarters together).
  - Why: the price module removes them for modelling, but other modules may still want those listings.
- **Listings without a price:** kept, with `price_num` missing.
  - Why: search and the market map don't need a price.
- **Monthly listings:** `is_short_stay` is false when `minimum_nights` is 30 or more.
  - Why: they are part of the LA market. The price module models short stays only.
- **Duplicate descriptions:** `desc_dup_group` groups listings in the same quarter that have exactly the same `description_clean`.
  - Why: search results and evaluation can be distorted by copied text.
- **Generic descriptions:** `desc_is_generic` is true when 5 or more different hosts use the same description. These are Airbnb's default one-liners, such as "Relax with the whole family at this peaceful place to stay."
  - Why: this text says nothing about the listing.
- **Non-English reviews:** `is_english` is false when less than 97% of the characters are ASCII.
  - Why: the review module can choose English-only text. It's a rough rule, not a language detector.
- **All calendar quarters kept.** Raw text columns (`name`, `description`, `comments`) are kept next to the cleaned ones.

## Data dictionary

New or changed columns only. All other columns are as Inside Airbnb publishes them.

**Listings**

| Column | Type | Meaning | How it is computed |
|---|---|---|---|
| `snapshot_date` | category (dates as text, e.g. `"2026-09-14"`) | Quarter the row comes from | From the partition folder `snapshot_date=<date>`. Not stored inside the files |
| `name_clean` | string | Listing title, plain text | Text cleaning on `name` |
| `description_clean` | string | Description, plain text | Text cleaning on `description` |
| `host_about_clean` | string | Host bio, plain text | Text cleaning on `host_about`. Not part of `text` |
| `text` | string | One search text per listing | `name_clean` + ". " + `description_clean` |
| `price_num` | Float64 | Nightly price in USD | `price` with `$` and `,` removed. Missing if blank |
| `is_short_stay` | boolean | Minimum stay is under 30 nights | `minimum_nights < 30` |
| `price_outlier` | boolean | Price is outside $20–$3,000 | `price_num < 20` or `> 3000`. Missing when there is no price |
| `desc_dup_group` | Int64 | Group of listings with the same description | Smallest `id` among listings in the same quarter with identical `description_clean`. Missing if the description is unique |
| `desc_is_generic` | boolean | Description is an Airbnb default text | 5 or more distinct `host_id` values share the same `description_clean`. Missing when there is no description |
| `amenities_list` | list of strings | Amenities as a list | Parsed from the JSON text in `amenities`, items trimmed |
| `baths_num` | Float64 | Number of bathrooms | First number in `bathrooms_text`. "Half-bath" = 0.5 |
| `bath_type` | string | `private`, `shared` or `unspecified` | Keyword in `bathrooms_text`. Missing when it is blank |
| `id`, `scrape_id`, `host_id`, `host_profile_id` | Int64 | IDs | Read as text, stored exactly |
| `host_is_superhost`, `host_has_profile_pic`, `host_identity_verified`, `has_availability`, `instant_bookable` | boolean | Yes/no fields | `t` → true, `f` → false |
| `host_response_rate`, `host_acceptance_rate` | Float64 | Rates as fractions | `"95%"` → 0.95 |
| `last_scraped`, `host_since`, `first_review`, `last_review`, `calendar_last_scraped`, `price_quote_checkin_date`, `price_quote_checkout_date` | datetime | Dates | Parsed from text |

**Reviews** (`reviews.parquet`, 7 columns)

| Column | Type | Meaning | How it is computed |
|---|---|---|---|
| `review_id` | Int64 | Review ID | Raw `id`, renamed, stored exactly |
| `listing_id`, `reviewer_id` | Int64 | IDs | Read as text, stored exactly |
| `date` | datetime | Review date | Parsed from text |
| `comments_clean` | string | Review text, plain | Text cleaning on `comments` |
| `is_english` | boolean | Review is probably English | At least 97% of characters in `comments_clean` are ASCII. Missing when the comment is empty |

**Calendar** (6 columns)

| Column | Type | Meaning | How it is computed |
|---|---|---|---|
| `listing_id` | Int64 | Listing ID | Read as text, stored exactly |
| `date` | datetime | Calendar day | Parsed from text |
| `available` | boolean | Open to book that day | `t` → true, `f` → false |
| `minimum_nights`, `maximum_nights` | Int64 | Stay limits for that day | Parsed as numbers |
| `price_num` | Float64 | Price for that day | Parsed like the listings price. Empty in every quarter (see below) |

## Known data issues

- **2025-12-04 has no prices.** `price` is empty in all 45,585 rows (`has_any_price: false`), and the quarter has none of the five `price_quote_*` columns. Leave this quarter out of price modelling.
- **Calendar prices are empty everywhere.** `has_any_calendar_price` is false in all four quarters. Only 2025-12-04 has a raw `price` column, and it is empty.
- **Missing prices in the other quarters:** 19.3% (2026-03-16), 12.7% (2026-06-15) and 16.2% (2026-09-14) of listings have no price. Across all quarters, 112,051 of 179,205 rows have a price.
- **Monthly listings:** 50.3%, 49.0%, 46.8% and 47.4% of listings (in quarter order) require 30 or more nights. Overall that is 86,793 of 179,205 rows (48.4%).
- **Generic descriptions:** 4.3%, 4.5%, 4.6% and 4.7% of listings per quarter (8,052 rows in total).
- **Duplicate descriptions:** 16.8% to 19.3% of listings with a description share it with another listing in the same quarter. That's 1,724 to 1,815 groups per quarter.
- **Price outliers:** below $20 in 0.05–0.26% of listings and above $3,000 in 0.79–0.96%, per priced quarter.
- **Airbnb IDs exceed 2^53** (9,007,199,254,740,992):
  - `id`: 118,068 of 179,205 values
  - `host_profile_id`: all 178,463 non-empty values
  - `host_id`: 988 values
- **Missing `host_profile_id`:** 742 rows (183, 356, 203 and 0 per quarter).
- **Host columns are empty after 2025-12-04.** In 2026-03-16, 2026-06-15 and 2026-09-14, these 12 columns are completely empty:
  - `neighborhood_overview`, `host_since`, `host_response_time`, `host_response_rate`, `host_acceptance_rate`, `host_thumbnail_url`, `host_neighbourhood`, `host_total_listings_count`, `host_verifications`, `neighbourhood`, `calendar_updated`, `instant_bookable`
  - `bathrooms` is also empty in 2026-09-14. Use `baths_num` instead.
- **`estimated_revenue_l365d`** is empty in 2025-12-04.
- **Scrape dates span several days.** `last_scraped` runs 2025-12-04 to 2025-12-11, 2026-03-16 to 03-18, 2026-06-15 to 06-23, and 2026-09-14 to 09-16.
- **Reviews:**
  - 1,890,200 reviews dated 2009-05-26 to 2026-09-15, covering 32,936 listings.
  - 46.2% are from 2024 or later.
  - 3.8% are mostly non-ASCII, and 422 have empty comments.
- **Amenities:** 9,820 to 10,064 distinct spellings per quarter. 241 listings have an empty list.
- **Bathroom type:** `bath_type` is `unspecified` for 138,259 listings, `private` for 22,293, `shared` for 18,199 and missing for 454.

## Validation checks

Run on the final output in `data/processed/` on 2026-11-21. All passed.

- **Rows per quarter:** listings 45,585 / 46,088 / 43,751 / 43,781, which equals the raw `listings.csv.gz` row counts and `build_report.json`. Calendar rows also equal the raw files.
- **Identical schemas:** `pyarrow.dataset` shows the 4 listings files have identical physical schemas (98 columns each), and so do the 4 calendar files (6 columns each).
- **Reads as one table:** listings give 179,205 rows and calendar 65,475,977 rows.
- **IDs match raw exactly:** for every quarter, `id`, `host_id` and `host_profile_id` were read from `listings.csv.gz` as text and compared with the processed table. All 179,205 rows matched, and blank raw cells are missing in the processed table.
- **Scrape dates:** `snapshot_matches_last_scraped` is true for all four quarters.
- **No HTML left:** zero `<br`, zero HTML tags and zero HTML entities in `text`, `name_clean`, `description_clean`, `host_about_clean` and the reviews' `comments_clean`. Six rows of `text` (2 listings, in several quarters) keep angle brackets that hosts typed around a phrase on purpose. These are not HTML.
- **`text` is never empty:** 179,205 of 179,205 rows have it.
- **Privacy columns are gone:** `host_name`, `host_picture_url` and `host_thumbnail_url` from listings, and `reviewer_name` from reviews.
- **No duplicates:** zero duplicate listing IDs within a quarter, and zero duplicate review IDs.

## Open items

- **Amenity standardization:** reduce 9,800+ spellings to about 15–20 attributes. The rules still need review.
- **Better language detection:** `is_english` is an ASCII rule and could be replaced with a real language detector.
- **Pandas deprecation:** `clean.py` calls `convert_dtypes(convert_floating=True)`, which pandas 3.1 warns will be removed. It still works now.
- **Older loaders read raw files:** `load_listings`, `load_reviews` and `load_calendar` in `airbnb.load` read the raw CSVs, not the cleaned tables. Decide whether they should switch to the processed data.
- **Dec 2025 prices:** decide whether the price module uses this quarter at all. It has no listing or calendar prices.
