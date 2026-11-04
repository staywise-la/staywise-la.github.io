# Module 3: Market map

**Goal:** show what each part of LA is like, so travelers can pick an area and hosts can see the market.

**Owner:** _name_

## Key idea

- **Cluster neighbourhoods, not single listings.** Listing-level clusters overlap a lot: the silhouette score was about 0.13 in our first test.
- **Neighbourhood level separates better:** after combining each neighbourhood's listings into one row, the silhouette rose to about 0.24.

## Inputs

- **Unit:** neighbourhoods with at least 30 listings (about 184). Merge smaller ones into a neighbour or mark them "not enough data".
- **Features per neighbourhood:**
  - median price of short stays
  - share of short stays
  - share of entire homes
  - share of professional hosts (10+ listings)
  - share with a pool
  - share with beach access
  - median guests
  - median rating
  - median estimated occupancy
- **Shapes:** `neighbourhoods.geojson`.

## Methods

- **Market types:** K-means and GMM on the standardized features; choose K with silhouette and BIC; PCA for a 2D view.
- **Connected regions:** spectral (graph) clustering. Neighbouring areas are linked, and each link is weighted by feature similarity, so regions form contiguous blocks on the map.
- **Listing types (optional):** cluster listings without location to name types, e.g. "beach house", "pool villa", "private room".

## First findings (Sep 2026, to verify)

- **Rules shape the market:**
  - Short-stay-heavy areas are mostly separate cities (West Hollywood, Pasadena, Glendale).
  - Mostly-monthly areas are inside the City of LA.
  - This likely reflects short-term rental rules. It is a hypothesis, so test it.
- **Professional monthly rentals:** areas with many professional hosts and monthly rentals sit near USC and UCLA.

## Evaluation

- **Quality:** silhouette; stability (re-run on bootstrap samples, compare with ARI).
- **Hypothesis test:** ARI between our clusters and the official groups (City of LA / Other Cities / Unincorporated).

## To-do

- [ ] Neighbourhood feature table
- [ ] K-means / GMM + choose K
- [ ] Graph clustering on the neighbour graph
- [ ] Stability + ARI with the official groups
- [ ] Name each cluster and write a short profile
- [ ] Export `web/data/neighbourhoods.geojson` with cluster labels and stats

## Reminders

- Estimated occupancy is near 0 in monthly-rental areas because it is based on short-stay reviews. Explain this on the map.
