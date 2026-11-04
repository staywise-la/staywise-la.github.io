# Shared notebooks

- **Use:** shared exploration (EDA) that several modules need. Module-specific notebooks go in `modules/<module>/notebooks/`.
- **Naming:** `NN_initials_topic.ipynb`, e.g. `01_jc_eda_listings.ipynb`.
- **Clear outputs before committing:** `nbstripout --install` does this automatically.
- **Loading data:** always load through `airbnb.load`, never with hard-coded paths.
