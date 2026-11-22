## What changed

<!-- One or two sentences. What does this PR do, and why? -->

## Module

<!-- Delete the ones that don't apply. -->
- [ ] 1 Search
- [ ] 2 Price
- [ ] 3 Market map
- [ ] 4 Reviews
- [ ] Shared code (`src/airbnb/`)
- [ ] Website (`web/`)
- [ ] Docs / repo setup

## Checklist

- [ ] This branch is not `main`, and the PR is small (one idea).
- [ ] `git status` showed nothing from `data/`, no model files, no `.env`, no `.DS_Store`.
- [ ] Notebooks have outputs cleared (`nbstripout`).
- [ ] Data is loaded through `airbnb.load`, not with hard-coded paths.
- [ ] If `src/airbnb/clean.py` changed: `docs/data_processing.md` is updated in this PR, with numbers from `build_report.json`.
- [ ] Results use `airbnb.config.RANDOM_SEED` and are reported through `airbnb.evaluate`.
- [ ] Tests pass (`pytest`), if this touches `src/airbnb/`.
