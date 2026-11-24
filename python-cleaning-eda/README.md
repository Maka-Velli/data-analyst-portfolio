# Data Cleaning and Exploration (Python)

What drives the sale price of a home in Nashville, and how often do homes sell
above their assessed value? This project cleans a messy 56,477-row housing file
and explores it with pandas, Matplotlib and scikit-learn.

## The data

- **Source:** Nashville housing sales (Kaggle, the classic data-cleaning dataset)
- **Size:** 56,477 rows × 19 columns, one row per property sale
- **Period:** January 2013 to December 2016 (two rows dated 2019 are dropped as errors)
- **Problems found:** 168 duplicate sales, text dates, a `SoldAsVacant` column
  written four different ways (`Yes`, `No`, `Y`, `N`), missing owner and value
  fields for about 30,000 rows, 43 homes with 0 bedrooms, 39 land-use codes
  (many rare), and 783 homes whose year built is after their sale date
- **Limitations:** the file has the sale price but not the assessment date, and
  the land-use codes are coarse. Location is only available at city level.

## Setup

```bash
python download_data.py        # saves the raw CSV to ../.rawdata
python build_notebook.py       # builds analysis.ipynb
jupyter nbconvert --to notebook --execute --inplace analysis.ipynb
```

The notebook writes `nashville_housing_clean.csv` (24,043 rows × 26 columns)
and `../images/python-summary.png`.

## The process

1. **Inspect** — shape, types, missing values, duplicates and a set of specific
   checks for whitespace, odd values and rare categories.
2. **Clean** — every step is logged with the row count after it:

   | Step | Rows |
   |---|---|
   | Raw file | 56,477 |
   | Drop duplicate sales (same parcel, date, price, value) | 56,309 |
   | Keep valid sale prices | 56,309 |
   | Keep valid dates (drops 2 rows dated 2019) | 56,307 |
   | Keep rows with a bedroom count | 24,043 |
   | Keep rows with an assessed value | 24,043 |

   The cleaning also parses text dates, converts the sale price to a number,
   normalises `SoldAsVacant`, converts the numeric fields, splits the property
   address into street and city, flags homes built after their sale date, groups
   land-use codes with fewer than 100 sales into `OTHER`, and adds over/under
   assessment, sale-to-value ratio and price per acre.
3. **Explore** — log-scale distributions, medians by year, city and decade,
   over/under assessment by year and city, and a correlation matrix.
4. **Model** — a 5-fold cross-validated ridge regression on log sale price.
   Features are added in groups to show how much each one explains:

   | Model | Features | Cross-validated R² |
   |---|---|---|
   | 1 | Assessed value only | 0.639 |
   | 2 | + city | 0.641 |
   | 3 | + land use | 0.684 |
   | 4 | + size, rooms, age, sale year, city, land use | 0.734 |

   A second model of the assessed value itself reaches 0.551 with size and
   rooms, 0.611 with city and 0.652 with land use.
5. **Check a suspicion** — the 768 homes built after their sale date behave very
   differently (4.2% sell above assessment against 76.3% of other sales), so they
   are flagged and excluded from the over/under comparison. The rising trend is
   the same either way.

## Key findings

- **Most homes sell above their assessed value, and the share rises every
  year:** 53.0% (2013), 68.7% (2014), 79.5% (2015) and 91.5% (2016). The median
  sale price rose from $160K to $215K over the same period.
- **The assessed value is the strongest single predictor of sale price:** it
  explains 64% of the variation in log sale price; adding size, rooms, age,
  location and land use raises that to 73%.
- **Location is the biggest visible gap:** Brentwood's median sale is about
  $420K, against $129K in Madison and $131K in Antioch — roughly 3.3 times
  higher. Antioch has the highest over-assessment share (82.4%) and Madison the
  lowest (64.3%).
- **Size and rooms explain about 55% of the assessed value**; adding city raises
  it to 61% and land use to 65%.
- **Age is not a straight line:** homes built before the 1930s and after 2000
  sell for more than those from the 1950s to the 1980s. The 2010s median is
  $331K against $133K for the 1980s.
- **Vacant land behaves differently:** only 6.1% of vacant-land sales are above
  assessment, against 75.2% of improved properties.

## What I'd do next

Add the assessment date and neighbourhood data, model location at a finer
level than city, and compare the linear model with gradient boosting to capture
interactions the linear model misses.

## Files

| File | What it is |
|---|---|
| `analysis.ipynb` | Executed notebook with the full cleaning and exploration |
| `nashville_housing_clean.csv` | Cleaned dataset (24,043 rows × 26 columns) |
| `build_notebook.py` | Rebuilds the notebook from source |
| `download_data.py` | Downloads the raw CSV |
