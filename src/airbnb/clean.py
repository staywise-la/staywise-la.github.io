"""Build cleaned, merged Parquet tables from the raw Inside Airbnb snapshots.

Usage (from the repo root):
    python -m airbnb.clean                      # all snapshots in data/raw/
    python -m airbnb.clean --snapshots 2026-09-14
    python -m airbnb.clean --skip-calendar      # faster, skips the big calendar files

Input  : data/raw/<YYYY-MM-DD>/listings.csv.gz, reviews.csv.gz, calendar.csv.gz,
         neighbourhoods.geojson
Output : data/processed/
    listings/snapshot_date=<date>/part-0.parquet   all quarters, one folder each
    calendar/snapshot_date=<date>/part-0.parquet   all quarters, one folder each
    reviews.parquet                                 latest snapshot only (it has the full history)
    neighbourhoods.geojson                          copied from the latest snapshot
    build_report.json                               row counts, checks, numbers for open decisions

Read the result with:
    pd.read_parquet("data/processed/listings")               # all quarters, adds snapshot_date
    pd.read_parquet("data/processed/listings",
                    filters=[("snapshot_date", "=", "2026-09-14")])

---------------------------------------------------------------------------
LEVEL 1: SAFE CLEANING (done in this script)
Format fixes only. No rows are removed. Raw columns are kept (new cleaned columns
are added next to them), except the empty and privacy columns dropped in Level 2.
  L1-1  Add `snapshot_date` from the folder name; check it against `last_scraped`.
  L1-2  Text: unescape HTML entities, remove real HTML tags (<br />, <p>, <b>, ...)
        but keep text like "<3" or "< 1mi", drop half tags left at the 1,000-character
        cut ("...pool<br /"), turn non-breaking spaces and line
        breaks into spaces, collapse repeated whitespace, trim.
        -> name_clean, description_clean, host_about_clean
  L1-3  `text` = name_clean + ". " + description_clean (one search text per listing).
  L1-4  price "$1,234.00" -> price_num (float).
  L1-5  t/f columns -> booleans; "95%" columns -> 0.95; date text -> datetime.
  L1-6  amenities JSON text -> amenities_list (list of strings, trimmed).
  L1-7  bathrooms_text -> baths_num (float, "Half-bath" = 0.5) and bath_type
        (private / shared / unspecified).
  L1-8  is_short_stay = minimum_nights < 30 (a flag only; nothing is dropped).
  L1-9  Same columns for every quarter (union; a column missing in one quarter is empty there).
  L1-10 Reviews: date -> datetime, comments_clean with the same text cleaning as L1-2.
  L1-11 Calendar: the same 6 columns in every quarter (listing_id, date, available,
        minimum_nights, maximum_nights, price_num); price_num is empty where
        Inside Airbnb left calendar prices blank.
  L1-12 IDs are read as text and stored as Int64 so no digits are lost (Airbnb IDs
        exceed 2^53). Every column gets the same type in every quarter, so
        data/processed/listings reads as one table.
  L1-13 price_quote_nights = price_quote_checkout_date - price_quote_checkin_date in
        days (Int64; <NA> if either date is missing). price is a per-night value from
        a quote of this length.
  L1-14 is_bookable_next_year = availability_365 > 0 (a flag only; nothing is dropped).

LEVEL 2: TEAM DECISIONS (approved, done in this script)
Principle: keep information in the cleaned data; each module decides how to use it.
  L2-1  Drop columns that are 100% empty in EVERY quarter (with the current four
        quarters this is only calendar_updated). A column with data in any quarter is
        kept: e.g. host_since and host_response_rate are empty after 2025-12-04 and
        bathrooms is empty in 2026-09-14, but all three are kept.
  L2-2  Privacy: drop reviewer_name, host_name, host_picture_url, host_thumbnail_url
        (still available in data/raw/ if ever needed).
  L2-3  price_outlier flag: price_num < $20 or > $3,000 (<NA> when there is no price).
  L2-4  Listings without a price are kept (price_num is empty).
  L2-5  Monthly listings are kept (is_short_stay = False).
  L2-6  desc_dup_group: listings with the exact same description_clean in a quarter
        share a group id (= the smallest listing id in the group); <NA> if unique.
        desc_is_generic: the same description is used by 5+ different hosts, i.e. one
        of Airbnb's default one-liners ("Relax with the whole family at this peaceful
        place to stay."). Such text says nothing about the listing.
  L2-7  Reviews: is_english flag (rough rule: >= 97% ASCII characters). Nothing dropped.
  L2-9  Calendar: all quarters are kept.
  L2-10 Raw text columns (name, description, comments) are kept for now.
  L2-11 host_about_clean is a separate column and NOT part of `text`.

STILL OPEN
  L2-8  Amenity standardization (9,800+ spellings -> ~15-20 attributes): rules need review.
---------------------------------------------------------------------------
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from . import config

# ---------------------------------------------------------------------------
# Text cleaning (L1-2)
# ---------------------------------------------------------------------------
# Only real HTML tags. A generic "<...>" pattern would also delete text such as
# "<3", "< 1mi<br />" or "<15min", which appear in LA descriptions.
_HTML_TAG = re.compile(
    r"</?\s*(?:br|p|b|strong|i|em|u|ul|ol|li|div|span|a|h[1-6]|hr|small|sup|sub)\b[^<>]*?/?\s*>",
    flags=re.IGNORECASE,
)
# Descriptions are cut at 1,000 characters, so some end in half a tag ("...pool<br /").
_CUT_TAG_AT_END = re.compile(
    r"<\s*/?\s*(?:br|p|b|strong|i|em|u|ul|ol|li|div|span|a)\b[^<>]*$",
    flags=re.IGNORECASE,
)
_SPACES = re.compile(r"\s+")


def clean_text(s: pd.Series) -> pd.Series:
    """HTML entities and tags out, whitespace normalized. Missing/blank -> <NA>."""
    out = s.astype("string")
    out = out.map(lambda x: html.unescape(x) if isinstance(x, str) else x, na_action="ignore").astype("string")
    out = out.str.replace(_HTML_TAG, " ", regex=True)
    out = out.str.replace(_CUT_TAG_AT_END, "", regex=True)
    out = out.str.replace(" ", " ", regex=False)  # non-breaking space
    out = out.str.replace(_SPACES, " ", regex=True).str.strip()
    return out.mask(out == "")


def combine_name_description(name: pd.Series, desc: pd.Series) -> pd.Series:
    """'Cozy studio' + 'Walk to the beach.' -> 'Cozy studio. Walk to the beach.'"""
    n = name.fillna("")
    d = desc.fillna("")
    ends_with_punct = n.str.contains(r"[.!?]$", regex=True)
    sep = np.where(ends_with_punct, " ", ". ")
    both = (n != "") & (d != "")
    text = np.where(both, n + sep + d, n + d)
    out = pd.Series(text, index=name.index, dtype="string").str.strip()
    return out.mask(out == "")


# ---------------------------------------------------------------------------
# Small parsers (L1-4 to L1-7)
# ---------------------------------------------------------------------------
PRIVACY_COLS_LISTINGS = ["host_name", "host_picture_url", "host_thumbnail_url"]
PRIVACY_COLS_REVIEWS = ["reviewer_name"]

BOOL_COLS = ["host_is_superhost", "host_has_profile_pic", "host_identity_verified",
             "has_availability", "instant_bookable"]
PERCENT_COLS = ["host_response_rate", "host_acceptance_rate"]
DATE_COLS = ["last_scraped", "host_since", "first_review", "last_review",
             "calendar_last_scraped", "price_quote_checkin_date", "price_quote_checkout_date"]


def parse_price(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype("string").str.replace(r"[$,]", "", regex=True), errors="coerce")


def parse_bool(s: pd.Series) -> pd.Series:
    return s.map({"t": True, "f": False}).astype("boolean")


def parse_percent(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype("string").str.rstrip("%"), errors="coerce") / 100


def parse_amenities(s: pd.Series) -> pd.Series:
    def one(x):
        if not isinstance(x, str) or not x.startswith("["):
            return []
        try:
            return [a.strip() for a in json.loads(x) if isinstance(a, str) and a.strip()]
        except json.JSONDecodeError:
            return []
    return s.map(one)


def parse_bathrooms(s: pd.Series) -> pd.DataFrame:
    t = s.astype("string").str.lower()
    num = pd.to_numeric(t.str.extract(r"(\d+(?:\.\d+)?)")[0], errors="coerce")
    num = num.mask(t.str.contains("half-bath", na=False) & num.isna(), 0.5)
    kind = pd.Series("unspecified", index=s.index, dtype="string")
    kind = kind.mask(t.str.contains("shared", na=False), "shared")
    kind = kind.mask(t.str.contains("private", na=False), "private")
    kind = kind.mask(t.isna())
    return pd.DataFrame({"baths_num": num, "bath_type": kind})


# ---------------------------------------------------------------------------
# Exact IDs and consistent column types across quarters (L1-12)
# ---------------------------------------------------------------------------
# Airbnb IDs go above 2^53, so they lose digits if pandas ever reads them as float
# (which it does when a column has a missing value). Read them as text, then
# convert to nullable Int64, which keeps every digit.
ID_COLS = {
    "listings": ["id", "scrape_id", "host_id", "host_profile_id"],
    "reviews": ["id", "listing_id", "reviewer_id"],
    "calendar": ["listing_id"],
}


def read_raw(path: Path, table: str, **kw) -> pd.DataFrame:
    """read_csv with every ID column read as text, so no digits are lost."""
    return pd.read_csv(path, dtype={c: "string" for c in ID_COLS[table]}, **kw)


def to_int64_exact(s: pd.Series) -> pd.Series:
    s = s.astype("string").str.strip()
    try:
        return s.astype("Int64")
    except (TypeError, ValueError):  # stray non-numeric text -> <NA>
        return s.where(s.str.fullmatch(r"-?\d+", na=False)).astype("Int64")


def _kind(s: pd.Series) -> str:
    from pandas.api import types as t
    if s.dtype == object and s.dropna().map(lambda v: isinstance(v, list)).any():
        return "list"
    if t.is_bool_dtype(s.dtype):
        return "bool"
    if t.is_integer_dtype(s.dtype):
        return "int"
    if t.is_float_dtype(s.dtype):
        return "float"
    if t.is_datetime64_any_dtype(s.dtype):
        return "datetime"
    return "string"


def harmonize_dtypes(frames: dict[str, pd.DataFrame], columns: list[str],
                     force_int: list[str]) -> tuple[dict[str, pd.DataFrame], dict]:
    """Give every quarter the same columns AND the same type per column, so the
    partitioned dataset reads as one table. The type comes from the quarters where
    the column has data; a column that is empty in one quarter takes that type."""
    frames = {k: df.reindex(columns=columns).convert_dtypes(convert_floating=True)
              for k, df in frames.items()}
    targets, changed = {}, {}
    for c in columns:
        with_data = [df[c] for df in frames.values() if df[c].notna().any()]
        kinds = {_kind(s) for s in with_data} or {"string"}
        if c in force_int:
            target = "Int64"
        elif "list" in kinds:
            target = object
        elif kinds <= {"int"}:
            target = "Int64"
        elif kinds <= {"int", "float"}:
            target = "Float64"
        elif kinds == {"bool"}:
            target = "boolean"
        elif kinds == {"datetime"}:
            target = with_data[0].dtype
        else:
            target = "string"
        before = {str(df[c].dtype) for df in frames.values()}
        for k, df in frames.items():
            if target is object:
                continue
            if str(target).startswith("datetime"):
                df[c] = pd.to_datetime(df[c], errors="coerce").astype(target)
            elif target == "Int64" and c in force_int:
                df[c] = to_int64_exact(df[c])
            else:
                df[c] = df[c].astype(target)
        targets[c] = str(target)
        if len(before) > 1:
            changed[c] = {"before": sorted(before), "after": str(target)}
    return frames, {"column_types": targets, "types_unified": changed}


def _share(x) -> float | None:
    """Mean of a 0/1 or boolean series, rounded; None when every value is missing
    (e.g. a quarter where Inside Airbnb published no prices at all)."""
    m = pd.Series(x).mean()
    return None if pd.isna(m) else round(float(m), 4)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------
def clean_listings(raw: pd.DataFrame, snapshot: str) -> tuple[pd.DataFrame, dict]:
    df = raw.copy()
    report: dict = {"rows": len(df)}

    # L1-1 snapshot date + sanity check
    df["snapshot_date"] = snapshot
    scraped = pd.to_datetime(df["last_scraped"], errors="coerce")
    report["last_scraped_range"] = [str(scraped.min().date()), str(scraped.max().date())]
    report["snapshot_matches_last_scraped"] = bool(
        (scraped.min() - pd.Timedelta(days=3)) <= pd.Timestamp(snapshot) <= (scraped.max() + pd.Timedelta(days=3))
    )

    # L1-2 / L1-3 text
    df["name_clean"] = clean_text(df["name"])
    df["description_clean"] = clean_text(df["description"])
    if "host_about" in df:
        df["host_about_clean"] = clean_text(df["host_about"])
    df["text"] = combine_name_description(df["name_clean"], df["description_clean"])

    # L1-4 price
    df["price_num"] = parse_price(df["price"])
    report["has_any_price"] = bool(df["price_num"].notna().any())
    if not report["has_any_price"]:
        print(f"  WARNING: {snapshot} has no prices at all (price column is empty). "
              "Listings are kept; exclude this quarter from price modelling.", flush=True)

    # L1-5 types
    for c in BOOL_COLS:
        if c in df:
            df[c] = parse_bool(df[c])
    for c in PERCENT_COLS:
        if c in df:
            df[c] = parse_percent(df[c])
    for c in DATE_COLS:
        if c in df:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    for c in ID_COLS["listings"]:
        if c in df:
            df[c] = to_int64_exact(df[c])

    # L1-6 amenities, L1-7 bathrooms, L1-8 short-stay flag
    df["amenities_list"] = parse_amenities(df["amenities"])
    df = pd.concat([df, parse_bathrooms(df["bathrooms_text"])], axis=1)
    df["is_short_stay"] = (df["minimum_nights"] < config.SHORT_STAY_MAX_NIGHTS).astype("boolean")

    # L1-13 length of the price quote; L1-14 open for booking in the next 365 days
    if {"price_quote_checkin_date", "price_quote_checkout_date"} <= set(df.columns):
        nights = (df["price_quote_checkout_date"] - df["price_quote_checkin_date"]).dt.days
        df["price_quote_nights"] = nights.astype("Int64")
    else:  # e.g. 2025-12-04 has no price_quote_* columns
        df["price_quote_nights"] = pd.Series(pd.NA, index=df.index, dtype="Int64")
    avail = pd.to_numeric(df["availability_365"], errors="coerce")
    df["is_bookable_next_year"] = (avail > 0).astype("boolean").mask(avail.isna())

    # L2-3 price outlier flag (<NA> when there is no price)
    out = (df["price_num"] < config.PRICE_MIN) | (df["price_num"] > config.PRICE_MAX)
    df["price_outlier"] = out.astype("boolean").mask(df["price_num"].isna())

    # L2-6 duplicate-description group id = smallest listing id sharing that text
    desc = df["description_clean"]
    group_min_id = df.groupby(desc, dropna=True)["id"].transform("min")
    is_dup = desc.notna() & desc.duplicated(keep=False)
    df["desc_dup_group"] = group_min_id.where(is_dup).astype("Int64")
    # Airbnb's default one-line texts ("Relax with the whole family at this peaceful
    # place to stay.") appear for many different hosts and say nothing about the listing.
    hosts_per_desc = df.groupby(desc, dropna=True)["host_id"].transform("nunique")
    df["desc_is_generic"] = (hosts_per_desc >= 5).astype("boolean").mask(desc.isna())

    # L2-2 privacy columns
    df = df.drop(columns=[c for c in PRIVACY_COLS_LISTINGS if c in df.columns])

    # Summary numbers for the report
    report["level2_inputs"] = {
        "all_empty_columns": [c for c in raw.columns if raw[c].isna().all()],
        "share_no_price": _share(df["price_num"].isna()),
        "share_price_below_20": _share(df["price_num"] < config.PRICE_MIN),
        "share_price_above_3000": _share(df["price_num"] > config.PRICE_MAX),
        "share_min_nights_30_plus": _share(~df["is_short_stay"]),
        "share_bookable_next_year": _share(df["is_bookable_next_year"]),
        "price_quote_nights_counts": {
            ("missing" if pd.isna(k) else str(int(k))): int(v)
            for k, v in df["price_quote_nights"].value_counts(dropna=False).sort_index().items()
        },
        "share_duplicate_description": round(float(is_dup.sum() / max(desc.notna().sum(), 1)), 4),
        "duplicate_description_groups": int(df["desc_dup_group"].nunique()),
        "share_generic_description": _share(df["desc_is_generic"].fillna(False)),
        "share_no_description": _share(df["description_clean"].isna()),
        "distinct_amenity_spellings": int(df["amenities_list"].explode().str.lower().nunique()),
        "duplicate_ids": int(df["id"].duplicated().sum()),
    }
    return df, report


def clean_reviews(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    df = raw.rename(columns={"id": "review_id"}).copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for c in ["review_id", "listing_id", "reviewer_id"]:
        if c in df:
            df[c] = to_int64_exact(df[c])
    df["comments_clean"] = clean_text(df["comments"])
    cc = df["comments_clean"].fillna("")
    ascii_share = cc.map(lambda s: sum(ch.isascii() for ch in s) / max(len(s), 1))
    # L2-7 rough English flag; swap in a real language detector later if needed
    df["is_english"] = (ascii_share >= 0.97).astype("boolean").mask(df["comments_clean"].isna())
    # L2-2 privacy
    df = df.drop(columns=[c for c in PRIVACY_COLS_REVIEWS if c in df.columns])
    report = {
        "rows": len(df),
        "date_range": [str(df["date"].min().date()), str(df["date"].max().date())],
        "listings_with_reviews": int(df["listing_id"].nunique()),
        "level2_inputs": {
            "share_empty_comment": _share(df["comments_clean"].isna()),
            "share_mostly_non_ascii": _share(ascii_share < 0.97),
            "share_since_2024": _share(df["date"] >= "2024-01-01"),
            "duplicate_review_ids": int(df["review_id"].duplicated().sum()),
        },
    }
    return df, report


def clean_calendar(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Same 6 columns and types in every quarter, so the calendar reads as one table.
    price_num is kept (empty when Inside Airbnb left calendar prices blank)."""
    df = pd.DataFrame({
        "listing_id": to_int64_exact(raw["listing_id"]),
        "date": pd.to_datetime(raw["date"], errors="coerce"),
        "available": parse_bool(raw["available"]),
        "minimum_nights": pd.to_numeric(raw.get("minimum_nights"), errors="coerce").astype("Int64"),
        "maximum_nights": pd.to_numeric(raw.get("maximum_nights"), errors="coerce").astype("Int64"),
        "price_num": (parse_price(raw["price"]) if "price" in raw
                      else pd.Series(np.nan, index=raw.index)).astype("Float64"),
    })
    report = {
        "rows": len(df),
        "date_range": [str(df["date"].min().date()), str(df["date"].max().date())],
        "share_available": _share(df["available"]),
        "has_price_column": "price" in raw.columns,
        "has_any_calendar_price": bool(df["price_num"].notna().any()),
        "dropped_columns": [c for c in raw.columns if c not in
                            {"listing_id", "date", "available", "minimum_nights", "maximum_nights", "price"}],
    }
    return df, report


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------
def write_parquet(df: pd.DataFrame, path: Path) -> None:
    """Separate function so tests can swap the writer."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def write_partition(df: pd.DataFrame, table_dir: Path, snapshot: str) -> Path:
    """Write one quarter to <table>/snapshot_date=<date>/part-0.parquet.
    The partition column comes from the folder name, so it is not stored in the file.
    Re-running replaces that quarter instead of adding duplicates."""
    part_dir = table_dir / f"snapshot_date={snapshot}"
    if part_dir.exists():
        shutil.rmtree(part_dir)
    path = part_dir / "part-0.parquet"
    write_parquet(df.drop(columns=["snapshot_date"], errors="ignore"), path)
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def build(raw_dir: Path, out_dir: Path, snapshots: list[str] | None = None,
          skip_calendar: bool = False, skip_reviews: bool = False) -> dict:
    all_snaps = sorted(p.name for p in raw_dir.iterdir() if p.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name))
    if not all_snaps:
        raise FileNotFoundError(f"No YYYY-MM-DD snapshot folders in {raw_dir}")
    snaps = snapshots or all_snaps
    latest = max(snaps)
    out_dir.mkdir(parents=True, exist_ok=True)
    report: dict = {"snapshots": snaps, "latest": latest, "listings": {}, "calendar": {}}

    # Listings: all quarters with the same columns (L1-9)
    cleaned = {}
    for snap in snaps:
        print(f"[listings] {snap} ...", flush=True)
        raw = read_raw(raw_dir / snap / "listings.csv.gz", "listings", low_memory=False)
        cleaned[snap], report["listings"][snap] = clean_listings(raw, snap)
    all_cols = list(dict.fromkeys(c for df in cleaned.values() for c in df.columns))
    # L2-1 drop columns that are empty in every quarter
    empty_everywhere = [c for c in all_cols
                        if all((c not in df.columns) or df[c].isna().all() for df in cleaned.values())]
    all_cols = [c for c in all_cols if c not in empty_everywhere]
    report["listings_dropped_empty_columns"] = empty_everywhere
    report["listings_dropped_privacy_columns"] = PRIVACY_COLS_LISTINGS
    for snap, df in cleaned.items():
        report["listings"][snap]["columns_missing_vs_other_quarters"] = [c for c in all_cols if c not in df.columns]
    # L1-12 same type for each column in every quarter
    cleaned, type_report = harmonize_dtypes(cleaned, all_cols, force_int=ID_COLS["listings"] + ["desc_dup_group"])
    report["listings_types_unified"] = type_report["types_unified"]
    report["listings_column_types"] = type_report["column_types"]
    for snap, df in cleaned.items():
        path = write_partition(df, out_dir / "listings", snap)
        print(f"  -> {path} ({len(df):,} rows)")

    # Reviews: latest only (it already contains the full history)
    if not skip_reviews:
        print(f"[reviews] {latest} ...", flush=True)
        raw = read_raw(raw_dir / latest / "reviews.csv.gz", "reviews")
        reviews, report["reviews"] = clean_reviews(raw)
        write_parquet(reviews, out_dir / "reviews.parquet")
        print(f"  -> {out_dir / 'reviews.parquet'} ({len(reviews):,} rows)")

    # Calendar: every quarter that has the file
    if not skip_calendar:
        for snap in snaps:
            f = raw_dir / snap / "calendar.csv.gz"
            if not f.exists():
                continue
            print(f"[calendar] {snap} ...", flush=True)
            cal, report["calendar"][snap] = clean_calendar(read_raw(f, "calendar"))
            path = write_partition(cal, out_dir / "calendar", snap)
            print(f"  -> {path} ({len(cal):,} rows)")

    # Neighbourhoods: copy from the latest snapshot that has it
    for snap in sorted(snaps, reverse=True):
        geo = raw_dir / snap / "neighbourhoods.geojson"
        if geo.exists():
            shutil.copy2(geo, out_dir / "neighbourhoods.geojson")
            report["neighbourhoods_from"] = snap
            break

    with open(out_dir / "build_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"[done] report: {out_dir / 'build_report.json'}")
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--raw-dir", type=Path, default=config.RAW_DIR)
    ap.add_argument("--out-dir", type=Path, default=config.PROCESSED_DIR)
    ap.add_argument("--snapshots", nargs="*", help="e.g. 2026-06-12 2026-09-14 (default: all)")
    ap.add_argument("--skip-calendar", action="store_true")
    ap.add_argument("--skip-reviews", action="store_true")
    a = ap.parse_args()
    build(a.raw_dir, a.out_dir, a.snapshots, a.skip_calendar, a.skip_reviews)


if __name__ == "__main__":
    main()
