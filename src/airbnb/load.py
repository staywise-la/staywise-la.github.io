"""Shared data loading for all four modules.

Expected layout (download from the team Google Drive):

    data/raw/
        2025-12-xx/   listings.csv.gz  reviews.csv.gz  calendar.csv.gz  neighbourhoods.geojson
        2026-03-xx/   ...
        2026-06-xx/   ...
        2026-09-14/   ...

Rules we agreed on:
- Listings: each snapshot gets a `snapshot` column. The same listing appears
  in several snapshots, so pick `latest_only=True` unless you need history.
- Reviews: every snapshot contains the FULL review history, so only the
  latest snapshot's reviews file is loaded (no duplicates).
- Prices: `price` is a text field like "$1,234.00"; use `price_num`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from . import config


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------
def list_snapshots(raw_dir: Path | None = None) -> list[str]:
    """Snapshot folder names, oldest first (e.g. ['2026-06-10', '2026-09-14'])."""
    raw_dir = Path(raw_dir or config.RAW_DIR)
    snaps = sorted(p.name for p in raw_dir.iterdir() if p.is_dir() and not p.name.startswith("."))
    if not snaps:
        raise FileNotFoundError(f"No snapshot folders in {raw_dir}. See data/README.md.")
    return snaps


def latest_snapshot(raw_dir: Path | None = None) -> str:
    return list_snapshots(raw_dir)[-1]


def _resolve(snapshots: str | Iterable[str]) -> list[str]:
    if snapshots == "all":
        return list_snapshots()
    if snapshots == "latest":
        return [latest_snapshot()]
    if isinstance(snapshots, str):
        return [snapshots]
    return list(snapshots)


# ---------------------------------------------------------------------------
# Listings
# ---------------------------------------------------------------------------
def parse_price(s: pd.Series) -> pd.Series:
    """'$1,234.00' -> 1234.0 ; blanks -> NaN."""
    return pd.to_numeric(s.astype(str).str.replace(r"[$,]", "", regex=True), errors="coerce")


def parse_amenities(s: pd.Series) -> pd.Series:
    """JSON-like string -> list of lower-case amenity names."""
    def _one(x):
        if not isinstance(x, str) or not x.startswith("["):
            return []
        try:
            return [a.strip().lower() for a in json.loads(x)]
        except json.JSONDecodeError:
            return []
    return s.map(_one)


def load_listings(snapshots: str | Iterable[str] = "latest", latest_only: bool = True) -> pd.DataFrame:
    """Load listings from one or more snapshots.

    snapshots   : "latest", "all", one folder name, or a list of names
    latest_only : if several snapshots, keep only the newest row per listing id
    """
    frames = []
    for snap in _resolve(snapshots):
        path = config.RAW_DIR / snap / "listings.csv.gz"
        df = pd.read_csv(path, low_memory=False)
        df["snapshot"] = snap
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)

    if latest_only and df["snapshot"].nunique() > 1:
        df = df.sort_values("snapshot").drop_duplicates("id", keep="last")

    # Derived columns everyone needs
    df["price_num"] = parse_price(df["price"])
    df["is_short_stay"] = df["minimum_nights"] < config.SHORT_STAY_MAX_NIGHTS
    ok = df["price_num"].between(config.PRICE_MIN, config.PRICE_MAX)
    df["log_price"] = np.where(ok, np.log(df["price_num"]), np.nan)
    df["amenity_list"] = parse_amenities(df["amenities"])
    return df.reset_index(drop=True)


def short_stay_with_price(df: pd.DataFrame) -> pd.DataFrame:
    """The modelling set for the price module: short stays with a usable price."""
    return df[df["is_short_stay"] & df["log_price"].notna()].copy()


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------
def load_reviews(snapshot: str = "latest", since: str | None = None,
                 english_only: bool = False, usecols: list[str] | None = None) -> pd.DataFrame:
    """Load reviews from ONE snapshot (the latest by default).

    since        : keep reviews on/after this date, e.g. "2024-01-01"
    english_only : rough filter (>= 97% ASCII characters); replace with a
                   proper language detector if needed
    """
    snap = latest_snapshot() if snapshot == "latest" else snapshot
    df = pd.read_csv(config.RAW_DIR / snap / "reviews.csv.gz", usecols=usecols)
    df["date"] = pd.to_datetime(df["date"])
    if since:
        df = df[df["date"] >= pd.Timestamp(since)]
    if "comments" in df:
        df["comments"] = df["comments"].fillna("").str.replace("<br/>", " ", regex=False)
        if english_only:
            ascii_share = df["comments"].map(lambda s: sum(c.isascii() for c in s) / max(len(s), 1))
            df = df[ascii_share >= 0.97]
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Calendar and neighbourhoods
# ---------------------------------------------------------------------------
def load_calendar(snapshot: str = "latest") -> pd.DataFrame:
    """Availability per listing per day. NOTE: this file has no price column."""
    snap = latest_snapshot() if snapshot == "latest" else snapshot
    df = pd.read_csv(config.RAW_DIR / snap / "calendar.csv.gz")
    df["date"] = pd.to_datetime(df["date"])
    df["available"] = df["available"].eq("t")
    return df


def load_neighbourhoods_geojson(snapshot: str = "latest") -> dict:
    snap = latest_snapshot() if snapshot == "latest" else snapshot
    with open(config.RAW_DIR / snap / "neighbourhoods.geojson", encoding="utf-8") as f:
        return json.load(f)
