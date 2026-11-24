# Capstone: Global CO2 Priorities (Python + SQL + Plotly)

**The question:** Which countries should a climate investment fund prioritise to
cut CO2 emissions?

The project turns the Our World in Data CO2 dataset into a prioritisation
framework: a 2023 emissions snapshot, a 2013–2023 growth comparison, a weighted
priority score, and an interactive dashboard.

## The data

- **Source:** [Our World in Data — CO2 and Greenhouse Gas Emissions data](https://github.com/owid/co2-data)
- **Size and period:** 56,269 rows × 79 columns, country-year from 1750 to 2025
- **What the analysis uses:** 2023 emissions and 2022 GDP (the latest GDP in the file)
- **Coverage:** 223 countries and territories; 220 have 2023 CO2 data; 41 emit at least 100 Mt
- **Limitations:** GDP ends in 2022, emissions are production-based rather than
  consumption-based, and the data is country-level, so it cannot identify
  specific projects. This is a portfolio project, not investment advice.

## Method

1. **Collect and clean** — download the OWID CSV, keep ISO-coded countries, and
   build a 2023 snapshot with 2022 GDP and 2013 CO2 joined in.
2. **Calculate** — emissions growth (Mt and %), coal share of CO2, carbon
   intensity (CO2 per unit of GDP), CO2 per capita, and cumulative emissions.
3. **Segment** — growth engine (100 Mt+ and growing), managed decline
   (100 Mt+ and shrinking), watchlist (smaller and growing), on track
   (smaller and shrinking).
4. **Score** — among the 41 countries emitting at least 100 Mt:
   `40% absolute CO2 + 30% growth 2013–2023 + 20% carbon intensity + 10% coal share`,
   converted to percentile ranks so the scale is 0–100.
5. **Visualise** — an interactive Plotly dashboard plus a static preview.

## Key findings

- **Concentration:** China, the United States and India produce **54.7%** of
  global CO2; the top ten produce **71.1%**.
- **Growth engines:** 23 countries produce **61.8%** of global CO2 and added
  **+4,761 Mt** since 2013. The 18 managed decliners cut **−1,992 Mt**.
- **Priority ranking:** China (95.8), India (87.8), Russia (85.0), Iran (82.5),
  Indonesia (78.0), Vietnam (75.8), Saudi Arabia (74.5), Kazakhstan (67.5),
  South Africa (66.8) and Turkey (65.3).
- **Coal:** 71.1% of China's CO2, 66.6% of India's, 81.9% of South Africa's and
  58.1% of Vietnam's.
- **Per capita:** Qatar 32.8 t per person, the United States 14.3 t, Australia
  14.6 t, against a global median of 3.2 t.

## Recommendations

1. Concentrate on the growth engines — 61.8% of global CO2 and still growing.
2. Make coal the first target in China, India, Indonesia, Vietnam and South Africa.
3. Address per-capita laggards among rich countries (US, Australia, Canada, Saudi Arabia).
4. Support the managed decliners to keep cutting (US, Japan, Germany, UK).
5. Use carbon intensity to find cheap abatement (Russia, Kazakhstan, South Africa, Iran).

**Impact:** a 20% reduction in the growth engines' 2013–2023 trajectory would
avoid roughly **950 Mt of CO2 per year by 2033**.

## Files

| File | What it is |
|---|---|
| `build_dashboard.py` | Loads the data, builds the summary tables, HTML dashboard and PNG preview |
| `dashboard.html` | Interactive Plotly dashboard (open in a browser; Plotly loads from a CDN) |
| `capstone_analysis.sql` | MySQL 8.0 staging table and the same summary queries |
| `verify_sql.py` | Runs the SQL queries in DuckDB and checks the headline numbers |
| `summary/` | Five CSV summary tables (snapshot, priority, segments, top emitters, trends) |
| `download_data.py` | Downloads the OWID CO2 CSV |

## Reproduce

```bash
python download_data.py          # saves to ../.rawdata
python build_dashboard.py        # writes dashboard.html, summary/*.csv, ../images/dashboard.png
python verify_sql.py             # runs capstone_analysis.sql in DuckDB
```

To run the SQL in MySQL:

```bash
mysql --local-infile=1 -u root -p < capstone_analysis.sql
```
