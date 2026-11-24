# Sales Performance Analysis (Excel)

Which products, regions and customer segments drive profit for a fictional US
retailer, and where is the business losing money?

## The data

- **Source:** Sample Superstore (Tableau sample data)
- **Size:** 9,994 order lines × 21 columns (5,009 orders, 793 customers, 1,862 products)
- **Period:** January 2015 to December 2018
- **Limitations:** no cost, marketing or returns data; one country; a fictional company

## Setup

```bash
python download_data.py      # saves the raw CSV to ../.rawdata
python build_workbook.py     # rebuilds the workbook and images/excel-summary.png
```

The build script needs `pandas`, `numpy`, `xlsxwriter` and `matplotlib`
(see the repository `requirements.txt`).

## The workbook

`superstore_sales_analysis.xlsx` contains nine sheets:

| Sheet | What it shows |
|---|---|
| README | Project overview, sheet guide and method |
| Summary | Six KPI cards, six key findings and four charts |
| Category Analysis | Sales, profit and margin by category and sub-category |
| Regional Analysis | Performance by region and by all 49 states |
| Discount Analysis | Profitability by discount band, plus a profit-vs-discount scatter |
| Time Analysis | Sales and profit by year and by month |
| Customer Analysis | Segments, top 10 customers and shipping modes |
| Pivot Tables | Pivot-style cross-tabs (region × category, segment × category, year × region, discount band × category) |
| Data | The clean 9,994-row dataset with helper columns |

Every summary table is built with **SUMIFS formulas** against the Data sheet,
with cached values so the numbers display correctly before Excel recalculates.
The workbook also has conditional formatting (data bars, colour scales and red
negatives), frozen panes and filters on the Data sheet.

## Key findings

- Total sales were **$2.30M** and total profit **$286K**, a **12.5%** margin.
- **Furniture sells a lot but earns very little:** $742K of sales (32%) at a
  2.5% margin, only 6.4% of total profit.
- **Three sub-categories lose money:** Tables (−$17.7K), Bookcases (−$3.5K) and
  Supplies (−$1.2K). Copiers ($55.6K, 37% margin) and Phones ($44.5K) lead.
- **Discounts above 20% lose $135K** in total; 72% of loss-making lines carry a
  discount above 20%. Tables only make money at full price (+$13.3K).
- **Central is the weak spot:** 7.9% margin against 14.9% in the West; 10 of 49
  states lose money, led by Texas (−$25.7K), Ohio (−$17.0K) and Pennsylvania
  (−$15.6K).
- **The business is growing:** sales rose from $484K (2015) to $733K (2018) and
  profit from $49.5K to $93.4K. Top 10 customers are only 6.7% of sales.

## Files

| File | What it is |
|---|---|
| `superstore_sales_analysis.xlsx` | The workbook |
| `build_workbook.py` | Rebuilds the workbook and the preview image |
| `download_data.py` | Downloads the raw CSV |
