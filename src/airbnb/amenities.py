"""Amenity standardization: thousands of host-written spellings -> ~30 yes/no attributes.

How it works:

    RULES + OVERRIDES (both below, in git)
            |  python -m airbnb.amenities map
            v
    data/processed/amenity_map.csv    <- one row per (amenity spelling, attribute).
            |                            A generated output, shared on Google Drive with
            |                            the other processed data (not in git).
            |  python -m airbnb.amenities attributes
            v
    data/processed/listing_attributes/snapshot_date=<date>/part-0.parquet
                                      <- one row per listing per quarter, one boolean column
                                         per attribute. Join with listings on
                                         (listing_id, snapshot_date).

    python -m airbnb.amenities all    runs both steps and writes reports/amenity_review.md
                                      (in git, so every rule change is visible in the PR)

The rules in this file are the source of truth; the map is rebuilt from them, so the
same raw data always gives the same map.

To change a decision:
  - A whole pattern is wrong (e.g. "pool table" counted as pool): edit RULES.
  - One spelling is wrong: add a line to OVERRIDES, e.g.
        ("pool cover", "pool", "remove", "not a pool"),
        ("whirlpool bath", "hot_tub", "add", "jetted tub counts as hot tub"),
  Then run `python -m airbnb.amenities all` again and commit this file and
  reports/amenity_review.md.

Important: amenities are self-reported. A listing that does not list "pool" may still
have one, so False means "not listed", not "does not have".
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import config

MAP_PATH = config.PROCESSED_DIR / "amenity_map.csv"
REVIEW_PATH = config.REPO_ROOT / "reports" / "amenity_review.md"
OUT_DIR = config.PROCESSED_DIR / "listing_attributes"


# ---------------------------------------------------------------------------
# Normalization: only harmless changes, so the map key stays readable
# ---------------------------------------------------------------------------
def normalize(s: str) -> str:
    s = str(s).lower()
    s = s.replace(" ", " ").replace("’", "'").replace("‘", "'")
    s = s.replace("–", "-").replace("—", "-")
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ---------------------------------------------------------------------------
# Rules: one per attribute. `include` must match, `exclude` must not,
# `require` (optional) must also match. Regexes run on the normalized spelling.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Rule:
    include: str
    exclude: str | None = None
    require: str | None = None
    meaning: str = ""


RULES: dict[str, Rule] = {
    # Water and outdoors
    "pool": Rule(r"\bpool\b", r"pool (table|view|cue|noodle|toy|float)|whirlpool|carpool|pool ?side view",
                 meaning="Pool at the listing (private or shared)"),
    "pool_private": Rule(r"\bpool\b", r"pool (table|view|cue|noodle|toy|float)|whirlpool|carpool|\bshared\b",
                         require=r"\bprivate\b", meaning="Pool marked as private"),
    "hot_tub": Rule(r"hot tub|jacuzzi", r"nearby", meaning="Hot tub (private or shared)"),
    "beach_access": Rule(r"beach access|beachfront", meaning="Beach access or beachfront"),
    "waterfront": Rule(r"waterfront|beachfront|lake access", meaning="On the water"),
    "outdoor_space": Rule(r"patio or balcony|backyard", meaning="Patio, balcony or backyard"),
    "bbq_grill": Rule(r"bbq grill|barbecue grill|^(private |shared )?bbq\b", r"utensil|stove|induction|oven|foreman",
                      meaning="BBQ grill"),
    # Views
    "ocean_view": Rule(r"\b(ocean|sea|beach|bay|harbor|harbour) view", meaning="Ocean, sea, beach or bay view"),
    "city_view": Rule(r"city skyline view|city view", meaning="City or skyline view"),
    "mountain_view": Rule(r"mountain view|valley view|canyon view|hill view", meaning="Mountain, valley or hill view"),
    # Practical
    "pets_allowed": Rule(r"^pets allowed$", meaning="Pets allowed"),
    "free_parking": Rule(r"\bfree\b.*\b(parking|garage|carport|driveway)\b", meaning="Any free parking (on site or street)"),
    "parking_on_premises": Rule(r"\b(parking|garage|carport|driveway)\b.*\bon premises\b",
                                meaning="Parking on the property (free or paid)"),
    "ev_charger": Rule(r"\bev charger\b", meaning="Electric-vehicle charger"),
    "workspace": Rule(r"dedicated workspace", meaning="Dedicated workspace"),
    "wifi": Rule(r"\bwifi\b|wi-fi|internet", r"pocket wifi", meaning="Wifi in the listing"),
    "kitchen": Rule(r"^(full |private |shared )?kitchen(ette)?$", meaning="Indoor kitchen or kitchenette"),
    "washer": Rule(r"^(free |paid )?washer\b", meaning="Clothes washer (in unit or building)"),
    "dryer": Rule(r"^(free |paid )?dryer\b", meaning="Clothes dryer (in unit or building)"),
    "dishwasher": Rule(r"\bdishwasher\b", meaning="Dishwasher"),
    # "... conditioner" spellings are toiletries (hair conditioner slot), not AC units.
    "air_conditioning": Rule(r"air conditioning|\bac\b|a/c", r"\bno ac\b|fan only|conditioner$",
                             meaning="Air conditioning"),
    "heating": Rule(r"\bheating\b|\bheater\b", r"water heater|towel heater|pool heater|patio heater|conditioner$",
                    meaning="Indoor heating"),
    "indoor_fireplace": Rule(r"indoor fireplace", meaning="Indoor fireplace"),
    "gym": Rule(r"\bgym\b|fitness center|exercise equipment", r"nearby|club & fitness",
                meaning="Gym or exercise equipment on site"),
    "elevator": Rule(r"\belevator\b", meaning="Elevator"),
    "self_check_in": Rule(r"self check-in|smart lock|keypad|lockbox", meaning="Self check-in"),
    "family_friendly": Rule(r"\bcrib\b|high chair|children's|baby (bath|monitor|safety)|changing table",
                            meaning="Crib, high chair or children's items"),
    "tv": Rule(r"\b(hd)?tv\b|television", meaning="TV"),
    "long_term_stays": Rule(r"^long term stays allowed$", meaning="Long-term stays allowed"),
    "smoking_allowed": Rule(r"^smoking allowed$", meaning="Smoking allowed"),
}

ATTRIBUTES = list(RULES)


def match(amenity_norm: str, rule: Rule) -> bool:
    if not re.search(rule.include, amenity_norm):
        return False
    if rule.exclude and re.search(rule.exclude, amenity_norm):
        return False
    if rule.require and not re.search(rule.require, amenity_norm):
        return False
    return True


# ---------------------------------------------------------------------------
# Step 1: build the map
# ---------------------------------------------------------------------------
def _as_list(xs) -> list:
    """amenities_list comes back from Parquet as a list or numpy array; missing -> []."""
    if xs is None or isinstance(xs, (float, str)):
        return []
    return list(xs)


def count_spellings(listings: pd.DataFrame) -> pd.DataFrame:
    """Distinct normalized spellings and how many listing rows use them."""
    s = listings["amenities_list"].map(lambda xs: {normalize(a) for a in _as_list(xs)})
    counts = pd.Series([a for xs in s for a in xs]).value_counts()
    return counts.rename_axis("amenity").reset_index(name="n_listings")


# Manual fixes on top of RULES: (spelling, attribute, "add" or "remove", why).
# Spellings are matched after normalize() (lower case, plain dashes and apostrophes).
OVERRIDES: list[tuple[str, str, str, str]] = [
    # ("pool cover", "pool", "remove", "not a pool"),
    # A stove, not heating.
    ("fast-heating electric smooth glass top electric stove", "heating", "remove", "a stove, not heating"),
    # "Access" is not "on the water" (beach access is not counted as waterfront either; only beachfront is).
    ("lake access", "waterfront", "remove", "access, not waterfront"),
    # Sound systems that mention wifi: about the speaker, not the internet connection.
    ('denon avr-x1300w 7.2-channel home theater receiver with wi-fi®, bluetooth®, apple® airplay®, and dolby atmos®. yamaha ns-iw470 natural sound in-wall speaker system. klipsch reference r-120sw powered subwoofer. sound system with bluetooth and aux', "wifi", "remove", "sound system, not internet"),
    ('sonos (connection via wifi only) sound system', "wifi", "remove", "sound system, not internet"),
    ('sonos (wifi player), klipsch speakers, denon receiver, sound system', "wifi", "remove", "sound system, not internet"),
    ('sonos (wifi) sound system', "wifi", "remove", "sound system, not internet"),
    ('sonos connect via wifi sound system', "wifi", "remove", "sound system, not internet"),
    ('sonos wifi sound system', "wifi", "remove", "sound system, not internet"),
    ('sonos, connect through wifi w sonos app sound system', "wifi", "remove", "sound system, not internet"),
    ('surround sound homepod - these are the high end originals, not the smaller, less effective new ones (will need wifi to connect) bluetooth sound system', "wifi", "remove", "sound system, not internet"),
    ('surround sound sonos. easy airplay when playing music while connected to the wifi. bluetooth sound system', "wifi", "remove", "sound system, not internet"),
    ('wifi for your sound system bluetooth sound system', "wifi", "remove", "sound system, not internet"),
    ('wifi blue tooth bluetooth sound system', "wifi", "remove", "sound system, not internet"),
    ('sonos wifi connected sound system', "wifi", "remove", "sound system, not internet"),
]


def load_overrides(overrides: list[tuple[str, str, str, str]] | None = None) -> pd.DataFrame:
    ov = pd.DataFrame(OVERRIDES if overrides is None else overrides,
                      columns=["amenity", "attribute", "action", "note"])
    ov["amenity"] = ov["amenity"].map(normalize)
    bad = sorted(set(ov["attribute"]) - set(ATTRIBUTES))
    if bad:
        raise ValueError(f"Unknown attribute(s) in OVERRIDES: {bad}")
    if not set(ov["action"]) <= {"add", "remove"}:
        raise ValueError("OVERRIDES action must be 'add' or 'remove'")
    return ov


def build_map(spellings: pd.DataFrame, overrides: pd.DataFrame | None = None) -> pd.DataFrame:
    rows = []
    for amen, n in zip(spellings["amenity"], spellings["n_listings"]):
        for attr, rule in RULES.items():
            if match(amen, rule):
                rows.append((amen, attr, int(n), "rule"))
    m = pd.DataFrame(rows, columns=["amenity", "attribute", "n_listings", "source"])
    if overrides is not None and len(overrides):
        n_by = dict(zip(spellings["amenity"], spellings["n_listings"]))
        for _, o in overrides.iterrows():
            key = (m["amenity"] == o["amenity"]) & (m["attribute"] == o["attribute"])
            if o["action"] == "remove":
                m = m[~key]
            elif not key.any():
                m.loc[len(m)] = [o["amenity"], o["attribute"], int(n_by.get(o["amenity"], 0)), "override"]
    return m.sort_values(["attribute", "n_listings", "amenity"], ascending=[True, False, True]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Step 2: build the attribute table from the map
# ---------------------------------------------------------------------------
def build_attributes(listings: pd.DataFrame, amenity_map: pd.DataFrame) -> pd.DataFrame:
    lookup: dict[str, set[str]] = {}
    for a, attr in zip(amenity_map["amenity"], amenity_map["attribute"]):
        lookup.setdefault(a, set()).add(attr)
    attrs = listings["amenities_list"].map(
        lambda xs: set().union(*(lookup.get(normalize(a), set()) for a in _as_list(xs)))
    )
    out = pd.DataFrame({"listing_id": listings["id"].astype("Int64").values})
    if "snapshot_date" in listings:
        out["snapshot_date"] = listings["snapshot_date"].astype(str).values
    for attr in ATTRIBUTES:
        out[attr] = attrs.map(lambda s, a=attr: a in s).astype("boolean").values
    out["n_amenities_listed"] = listings["amenities_list"].map(lambda xs: len(_as_list(xs))).astype("Int64").values
    return out


# ---------------------------------------------------------------------------
# Review report (for the PR)
# ---------------------------------------------------------------------------
def write_review(amenity_map: pd.DataFrame, spellings: pd.DataFrame, attributes: pd.DataFrame,
                 path: Path = REVIEW_PATH, top: int = 25) -> None:
    lines = ["# Amenity standardization review", "",
             "Generated by `python -m airbnb.amenities all`. Check that the top spellings under each",
             "attribute really belong there, and that nothing important is in the unmatched list.", ""]
    share = attributes[ATTRIBUTES].mean().round(3)
    total = spellings["n_listings"].sum()
    covered = spellings[spellings["amenity"].isin(amenity_map["amenity"])]["n_listings"].sum()
    lines += [f"- Listing rows: {len(attributes):,}",
              f"- Distinct spellings: {len(spellings):,}; matched to an attribute: {amenity_map['amenity'].nunique():,}",
              f"- Share of all amenity mentions that match some attribute: {covered / total:.1%}", "",
              "## Attributes", "", "| attribute | meaning | share of listings | spellings |", "|---|---|---|---|"]
    for a in ATTRIBUTES:
        k = int((amenity_map["attribute"] == a).sum())
        lines.append(f"| `{a}` | {RULES[a].meaning} | {share[a]:.1%} | {k} |")
    for a in ATTRIBUTES:
        sub = amenity_map[amenity_map["attribute"] == a].head(top)
        lines += ["", f"### `{a}`", "", "| spelling | listings | source |", "|---|---|---|"]
        lines += [f"| {r.amenity.replace('|', '/')} | {r.n_listings:,} | {r.source} |" for r in sub.itertuples()]
    un = spellings[~spellings["amenity"].isin(amenity_map["amenity"])].head(60)
    lines += ["", "## Most common unmatched spellings", "",
              "Not every amenity needs an attribute. Look for ones that should belong to an existing attribute.",
              "", "| spelling | listings |", "|---|---|"]
    lines += [f"| {r.amenity.replace('|', '/')} | {r.n_listings:,} |" for r in un.itertuples()]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# I/O and CLI
# ---------------------------------------------------------------------------
def write_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def _read_listings() -> pd.DataFrame:
    df = pd.read_parquet(config.PROCESSED_DIR / "listings", columns=["id", "amenities_list", "snapshot_date"])
    df["snapshot_date"] = df["snapshot_date"].astype(str)
    return df


def run(step: str) -> None:
    listings = _read_listings()
    spellings = count_spellings(listings)
    if step in ("map", "all"):
        m = build_map(spellings, load_overrides())
        m.to_csv(MAP_PATH, index=False)
        print(f"[map] {len(m):,} rows ({m['amenity'].nunique():,} spellings) -> {MAP_PATH}")
    if step in ("attributes", "all"):
        m = pd.read_csv(MAP_PATH, dtype={"amenity": str, "attribute": str})
        unknown = sorted(set(m["attribute"]) - set(ATTRIBUTES))
        if unknown:
            raise ValueError(f"amenity_map.csv has attributes not in RULES: {unknown}")
        attrs = build_attributes(listings, m)
        if OUT_DIR.exists():
            shutil.rmtree(OUT_DIR)
        summary = {}
        for snap, part in attrs.groupby("snapshot_date"):
            write_parquet(part.drop(columns=["snapshot_date"]), OUT_DIR / f"snapshot_date={snap}" / "part-0.parquet")
            summary[snap] = {"rows": int(len(part)), "share": {a: round(float(part[a].mean()), 4) for a in ATTRIBUTES}}
        (config.PROCESSED_DIR / "listing_attributes_report.json").write_text(json.dumps(summary, indent=2))
        print(f"[attributes] {len(attrs):,} rows x {len(ATTRIBUTES)} attributes -> {OUT_DIR}")
        if step == "all":
            write_review(m, spellings, attrs)
            print(f"[review] -> {REVIEW_PATH}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Amenity standardization (map + attribute table).")
    ap.add_argument("step", choices=["map", "attributes", "all"], nargs="?", default="all")
    run(ap.parse_args().step)


if __name__ == "__main__":
    main()
