# Module 2: Price evaluation

**Goal:** tell users whether a listing's price is fair, e.g. "14% below similar stays", with a price range instead of one number.

**Owner:** _name_

## Inputs

- Listings from `short_stay_with_price()`: short stays (minimum nights < 30) with a price between $20 and $3,000. That is about 20.4K listings in the Sep 2026 snapshot.
- **Features:** room type, accommodates, bedrooms, beds, `bathrooms_text` (parsed), amenities (one-hot for the top ones), latitude/longitude, neighbourhood, review scores, number of reviews, host listing count.
- **Target:** `log_price`.

## Methods

- **Baselines:** neighbourhood median price; linear regression; Lasso.
- **Main:** random forest, gradient boosting (LightGBM).
- **Comparables:** kNN finds the most similar listings for "similar stays".
- **Price range:** quantile regression (e.g. 10th and 90th percentiles) gives an 80% interval.
- **"Good deal":** price below the predicted range AND rating of at least 4.7.

## Evaluation

- **Validation:** neighbourhood-grouped cross-validation, so the same area is never in both train and test.
- **Accuracy:** MAE and MAPE in dollars, and the 80% interval coverage (should be close to 80%).
- **Fairness:** error by neighbourhood (is any area always over- or under-predicted?).

## DS extras

- **Hedonic regression:** how many dollars per night a pool, pets allowed or an extra bedroom adds, with confidence intervals.
- **Validate deal flags with the next quarter:** did flagged listings get more reviews, or did hosts raise prices?

## To-do

- [ ] Feature table saved to `data/processed/price/`
- [ ] Baselines + grouped CV
- [ ] Random forest and LightGBM
- [ ] Quantile models + coverage check
- [ ] Deal flag + next-quarter validation
- [ ] Export per-listing fair price range to `web/data/prices.json`

## Reminders

- Do not mix monthly rentals (30+ nights) with short stays.
- The price is a one-date quote (mid-September). Say so in the report.
