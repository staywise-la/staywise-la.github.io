"""Project paths and shared settings.

Everyone imports paths from here, so nobody hard-codes their own folders.
Set the DATA_DIR environment variable (or put it in .env) if your data
lives somewhere other than <repo>/data.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

try:  # optional: read .env if python-dotenv is installed
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass

DATA_DIR = Path(os.getenv("DATA_DIR", REPO_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"            # one sub-folder per snapshot: raw/2026-09-14/
INTERIM_DIR = DATA_DIR / "interim"    # cleaned but not final
PROCESSED_DIR = DATA_DIR / "processed"  # model-ready tables, embeddings
WEB_DATA_DIR = REPO_ROOT / "web" / "data"  # small JSON files the website loads
FIGURES_DIR = REPO_ROOT / "reports" / "figures"

# Listings with minimum_nights >= this are monthly rentals, not short stays.
SHORT_STAY_MAX_NIGHTS = 30

# Price filter used for modelling (USD per night).
PRICE_MIN, PRICE_MAX = 20, 3000

RANDOM_SEED = 6740
