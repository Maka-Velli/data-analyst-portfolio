"""
Build the Superstore sales analysis workbook and its summary preview image.

Reads the raw Sample Superstore CSV, rebuilds the clean 9,994-row dataset
(the source file also contains two stray helper tables after row 9,994) and
writes:
  - superstore_sales_analysis.xlsx  (Summary, analysis sheets, Data)
  - ../images/excel-summary.png     (preview of the Summary sheet)

Run from anywhere:
    python build_workbook.py
"""

from pathlib import Path
import numpy as np
import pandas as pd
import xlsxwriter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RAW = ROOT / ".rawdata" / "Sample-Superstore.csv"
OUT = HERE / "superstore_sales_analysis.xlsx"
IMG = ROOT / "images" / "excel-summary.png"

# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
BAND_BINS = [-0.001, 0, 0.1, 0.2, 0.4, 0.6, 1.0]
BAND_LABELS = ["0%", "1-10%", "11-20%", "21-40%", "41-60%", "61%+"]


def load_data() -> pd.DataFrame:
    """Return the clean 9,994-row Superstore dataset with helper columns."""
    df = pd.read_csv(RAW, encoding="latin-1")

    # The file has two unrelated tables appended after the real data.
    numeric_row_id = pd.to_numeric(df["Row ID"], errors="coerce")
    df = df[numeric_row_id.notna()].copy()
    df["Row ID"] = numeric_row_id[numeric_row_id.notna()].astype(int)
    df = df.drop_duplicates(subset=["Row ID"])

    df["Order Date"] = pd.to_datetime(df["Order Date"], format="%m/%d/%Y")
    df["Ship Date"] = pd.to_datetime(df["Ship Date"], format="%m/%d/%Y")
    df["Order Year"] = df["Order Date"].dt.year
    df["Order Month"] = df["Order Date"].dt.month
    df["Order Month Name"] = df["Order Date"].dt.strftime("%b")
    # read_csv turns ZIPs into floats ("42420.0"); keep them as text.
    df["Postal Code"] = (
        pd.to_numeric(df["Postal Code"], errors="coerce")
        .astype("Int64")
        .astype(str)
        .str.replace("<NA>", "", regex=False)
    )
    df["Profit Margin"] = df["Profit"] / df["Sales"]
    df["Discount Band"] = pd.cut(
        df["Discount"], bins=BAND_BINS, labels=BAND_LABELS
    ).astype(str)
    return df.reset_index(drop=True)


def build_tables(df: pd.DataFrame) -> dict:
    """All summary tables used by the workbook and the preview image."""
    t = {}

    cat = df.groupby("Category").agg(
        Sales=("Sales", "sum"), Profit=("Profit", "sum"), Lines=("Sales", "size")
    ).sort_values("Sales", ascending=False)
    cat["Margin"] = cat["Profit"] / cat["Sales"]
    cat["Sales Share"] = cat["Sales"] / cat["Sales"].sum()
    cat["Profit Share"] = cat["Profit"] / cat["Profit"].sum()
    t["category"] = cat.reset_index()

    sub = df.groupby("Sub-Category").agg(
        Sales=("Sales", "sum"), Profit=("Profit", "sum"), Lines=("Sales", "size")
    ).sort_values("Profit", ascending=False)
    sub["Margin"] = sub["Profit"] / sub["Sales"]
    t["subcategory"] = sub.reset_index()

    band = df.groupby("Discount Band").agg(
        Sales=("Sales", "sum"), Profit=("Profit", "sum"), Lines=("Sales", "size")
    ).reindex(BAND_LABELS).reset_index()
    loss = (
        df[df["Profit"] < 0].groupby("Discount Band").size()
        .reindex(BAND_LABELS).fillna(0).astype(int)
    )
    band["Loss Lines"] = loss.values
    band["Margin"] = band["Profit"] / band["Sales"]
    band["Loss Share"] = band["Loss Lines"] / band["Lines"]
    t["band"] = band

    reg = df.groupby("Region").agg(
        Sales=("Sales", "sum"), Profit=("Profit", "sum")
    ).sort_values("Profit", ascending=False)
    reg["Margin"] = reg["Profit"] / reg["Sales"]
    t["region"] = reg.reset_index()

    st = df.groupby("State").agg(
        Sales=("Sales", "sum"), Profit=("Profit", "sum")
    ).sort_values("Profit")
    st["Margin"] = st["Profit"] / st["Sales"]
    t["state"] = st.reset_index()

    seg = df.groupby("Segment").agg(
        Sales=("Sales", "sum"), Profit=("Profit", "sum")
    ).sort_values("Profit", ascending=False)
    seg["Margin"] = seg["Profit"] / seg["Sales"]
    t["segment"] = seg.reset_index()

    yr = df.groupby("Order Year").agg(
        Sales=("Sales", "sum"), Profit=("Profit", "sum")
    )
    yr["Margin"] = yr["Profit"] / yr["Sales"]
    t["yearly"] = yr.reset_index()

    mo = df.groupby("Order Month").agg(
        Sales=("Sales", "sum"), Profit=("Profit", "sum")
    )
    t["monthly"] = mo.reset_index()

    ship = df.groupby("Ship Mode").agg(
        Sales=("Sales", "sum"), Profit=("Profit", "sum"), Orders=("Order ID", "nunique")
    ).sort_values("Sales", ascending=False)
    ship["Margin"] = ship["Profit"] / ship["Sales"]
    t["ship"] = ship.reset_index()

    top = (
        df.groupby(["Customer ID", "Customer Name"])["Sales"].sum()
        .nlargest(10).reset_index()
    )
    top["Profit"] = top.apply(
        lambda r: df[(df["Customer ID"] == r["Customer ID"])]["Profit"].sum(), axis=1
    )
    t["top_customers"] = top

    # Pivot-style cross tabs
    t["pivot_region_category"] = df.pivot_table(
        index="Region", columns="Category", values="Sales", aggfunc="sum", fill_value=0
    )
    t["pivot_segment_category"] = df.pivot_table(
        index="Segment", columns="Category", values="Profit", aggfunc="sum", fill_value=0
    )
    t["pivot_year_region"] = df.pivot_table(
        index="Order Year", columns="Region", values="Sales", aggfunc="sum", fill_value=0
    )
    t["pivot_band_category"] = df.pivot_table(
        index="Discount Band", columns="Category", values="Profit", aggfunc="sum", fill_value=0
    ).reindex(BAND_LABELS)

    t["kpi"] = {
        "sales": df["Sales"].sum(),
        "profit": df["Profit"].sum(),
        "margin": df["Profit"].sum() / df["Sales"].sum(),
        "orders": df["Order ID"].nunique(),
        "customers": df["Customer ID"].nunique(),
        "lines": len(df),
    }
    t["extra"] = {
        "loss_lines": int((df["Profit"] < 0).sum()),
        "loss_lines_gt20": int(((df["Profit"] < 0) & (df["Discount"] > 0.2)).sum()),
        "loss_gt20": df.loc[df["Discount"] > 0.2, "Profit"].sum(),
        "tables_undiscounted": df.loc[
            (df["Sub-Category"] == "Tables") & (df["Discount"] == 0), "Profit"
        ].sum(),
        "central_furniture": df.loc[
            (df["Region"] == "Central") & (df["Category"] == "Furniture"), "Profit"
        ].sum(),
        "losing_states": int((st["Profit"] < 0).sum()),
        "state_count": len(st),
        "top10_share": top["Sales"].sum() / df["Sales"].sum(),
    }
    return t


# --------------------------------------------------------------------------- #
# Workbook
# --------------------------------------------------------------------------- #
NAVY = "#1F3864"
BLUE = "#2E75B6"
LIGHT_BLUE = "#D9E2F3"
GREY = "#F2F2F2"
MID_GREY = "#D9D9D9"
ORANGE = "#C55A11"
GREEN = "#548235"
RED = "#C00000"
WHITE = "#FFFFFF"


def make_formats(wb):
    f = {}
    base = {"font_name": "Calibri", "font_size": 10}
    f["title"] = wb.add_format({**base, "font_size": 22, "bold": True, "font_color": NAVY})
    f["subtitle"] = wb.add_format({**base, "font_size": 11, "font_color": "#595959", "italic": True})
    f["section"] = wb.add_format({
        **base, "font_size": 12, "bold": True, "font_color": WHITE,
        "bg_color": NAVY, "align": "left", "valign": "vcenter", "indent": 1,
    })
    f["header"] = wb.add_format({
        **base, "bold": True, "font_color": WHITE, "bg_color": BLUE,
        "align": "center", "valign": "vcenter", "text_wrap": True, "border": 1,
        "border_color": WHITE,
    })
    f["body"] = wb.add_format({**base, "border": 1, "border_color": "#D9D9D9", "valign": "vcenter"})
    f["body_center"] = wb.add_format({**base, "border": 1, "border_color": "#D9D9D9", "align": "center"})
    f["body_bold"] = wb.add_format({**base, "bold": True, "border": 1, "border_color": "#D9D9D9"})
    f["money"] = wb.add_format({
        **base, "num_format": "$#,##0", "border": 1, "border_color": "#D9D9D9"
    })
    f["money_bold"] = wb.add_format({
        **base, "num_format": "$#,##0", "bold": True, "border": 1, "border_color": "#D9D9D9"
    })
    f["pct"] = wb.add_format({
        **base, "num_format": "0.0%", "border": 1, "border_color": "#D9D9D9"
    })
    f["num"] = wb.add_format({
        **base, "num_format": "#,##0", "border": 1, "border_color": "#D9D9D9"
    })
    f["num_bold"] = wb.add_format({
        **base, "num_format": "#,##0", "bold": True, "border": 1, "border_color": "#D9D9D9"
    })
    f["total_label"] = wb.add_format({
        **base, "bold": True, "bg_color": LIGHT_BLUE, "border": 1, "border_color": "#8EA9DB"
    })
    f["total_money"] = wb.add_format({
        **base, "num_format": "$#,##0", "bold": True, "bg_color": LIGHT_BLUE,
        "border": 1, "border_color": "#8EA9DB"
    })
    f["total_pct"] = wb.add_format({
        **base, "num_format": "0.0%", "bold": True, "bg_color": LIGHT_BLUE,
        "border": 1, "border_color": "#8EA9DB"
    })
    f["total_num"] = wb.add_format({
        **base, "num_format": "#,##0", "bold": True, "bg_color": LIGHT_BLUE,
        "border": 1, "border_color": "#8EA9DB"
    })
    f["kpi_label"] = wb.add_format({
        **base, "font_size": 9, "bold": True, "font_color": "#595959",
        "bg_color": LIGHT_BLUE, "align": "center", "valign": "vcenter",
        "top": 1, "left": 1, "right": 1, "border_color": "#8EA9DB",
    })
    f["kpi_value"] = wb.add_format({
        **base, "font_size": 20, "bold": True, "font_color": NAVY,
        "bg_color": LIGHT_BLUE, "align": "center", "valign": "vcenter",
        "bottom": 1, "left": 1, "right": 1, "border_color": "#8EA9DB",
    })
    f["kpi_value_pct"] = wb.add_format({
        **base, "font_size": 20, "bold": True, "font_color": NAVY,
        "bg_color": LIGHT_BLUE, "align": "center", "valign": "vcenter",
        "bottom": 1, "left": 1, "right": 1, "border_color": "#8EA9DB",
        "num_format": "0.0%",
    })
    f["kpi_value_num"] = wb.add_format({
        **base, "font_size": 20, "bold": True, "font_color": NAVY,
        "bg_color": LIGHT_BLUE, "align": "center", "valign": "vcenter",
        "bottom": 1, "left": 1, "right": 1, "border_color": "#8EA9DB",
        "num_format": "#,##0",
    })
    f["finding"] = wb.add_format({
        **base, "font_size": 10, "text_wrap": True, "valign": "top",
        "bg_color": "#FAFAFA", "border": 1, "border_color": "#E7E6E6", "indent": 1,
    })
    f["note"] = wb.add_format({**base, "font_size": 9, "font_color": "#7F7F7F", "italic": True})
    f["bullet"] = wb.add_format({**base, "font_size": 10, "text_wrap": True, "valign": "top"})
    f["date"] = wb.add_format({**base, "num_format": "yyyy-mm-dd"})
    f["neg"] = wb.add_format({**base, "font_color": RED, "bg_color": "#FCE4E4"})
    return f


def sheet_title(ws, title, subtitle, last_col=12):
    ws.set_row(0, 34)
    ws.write(0, 0, title, None)  # format applied below
    ws.write(1, 0, subtitle, None)


def add_title(ws, fmt, title, subtitle, last_col=12):
    ws.merge_range(0, 0, 0, last_col, title, fmt["title"])
    ws.merge_range(1, 0, 1, last_col, subtitle, fmt["subtitle"])
    ws.set_row(0, 34)
    ws.set_row(1, 18)


def section_header(ws, fmt, row, text, last_col=12):
    ws.merge_range(row, 0, row, last_col, text, fmt["section"])
    ws.set_row(row, 22)


def write_table(ws, fmt, df, start_row, start_col, money_cols=(), pct_cols=(),
                num_cols=(), text_cols=(), total_row=False, col_widths=None,
                total_label_col=None):
    """Write a dataframe with a header row and optional total row."""
    cols = list(df.columns)
    for j, c in enumerate(cols):
        ws.write(start_row, start_col + j, c, fmt["header"])
    for i, (_, r) in enumerate(df.iterrows(), start=1):
        for j, c in enumerate(cols):
            val = r[c]
            if pd.isna(val):
                ws.write_blank(start_row + i, start_col + j, None, fmt["body"])
            elif c in money_cols:
                ws.write_number(start_row + i, start_col + j, float(val), fmt["money"])
            elif c in pct_cols:
                ws.write_number(start_row + i, start_col + j, float(val), fmt["pct"])
            elif c in num_cols:
                ws.write_number(start_row + i, start_col + j, float(val), fmt["num"])
            else:
                ws.write(start_row + i, start_col + j, str(val), fmt["body"])
    if total_row:
        r = start_row + len(df) + 1
        for j, c in enumerate(cols):
            if c == total_label_col:
                ws.write(r, start_col + j, "Total", fmt["total_label"])
            elif c in money_cols:
                ws.write_formula(
                    r, start_col + j,
                    f"=SUM({xlsxwriter.utility.xl_col_to_name(start_col + j)}{start_row + 2}:"
                    f"{xlsxwriter.utility.xl_col_to_name(start_col + j)}{start_row + len(df) + 1})",
                    fmt["total_money"], float(df[c].sum()),
                )
            elif c in pct_cols:
                ws.write_blank(r, start_col + j, None, fmt["total_pct"])
            elif c in num_cols:
                ws.write_formula(
                    r, start_col + j,
                    f"=SUM({xlsxwriter.utility.xl_col_to_name(start_col + j)}{start_row + 2}:"
                    f"{xlsxwriter.utility.xl_col_to_name(start_col + j)}{start_row + len(df) + 1})",
                    fmt["total_num"], float(df[c].sum()),
                )
            else:
                ws.write_blank(r, start_col + j, None, fmt["total_label"])


def build_workbook(df: pd.DataFrame, t: dict):
    wb = xlsxwriter.Workbook(OUT, {"nan_inf_to_errors": True})
    wb.set_properties({
        "title": "Superstore Sales Performance Analysis",
        "subject": "Excel sales analysis portfolio project",
        "author": "Makafui Marvelous",
        "company": "Portfolio project",
        "comments": "Built from the Sample Superstore dataset with Python and xlsxwriter.",
    })
    fmt = make_formats(wb)

    # ------------------------------------------------------------------ README
    ws = wb.add_worksheet("README")
    ws.hide_gridlines(2)
    ws.set_column("A:A", 2)
    ws.set_column("B:B", 28)
    ws.set_column("C:C", 90)
    add_title(ws, fmt, "Superstore Sales Performance Analysis",
              "Which products, regions and customer segments drive profit — and where is the business losing money?", last_col=2)

    row = 3
    section_header(ws, fmt, row, "PROJECT OVERVIEW", last_col=2)
    row += 1
    info = [
        ("Dataset", "Sample Superstore (Tableau sample data) — a fictional US retailer"),
        ("Rows / columns", f"{len(df):,} order lines × 21 columns"),
        ("Period", "January 2015 to December 2018"),
        ("Total sales", f"${t['kpi']['sales']:,.2f}"),
        ("Total profit", f"${t['kpi']['profit']:,.2f}"),
        ("Profit margin", f"{t['kpi']['margin']:.1%}"),
        ("Orders / customers", f"{t['kpi']['orders']:,} orders, {t['kpi']['customers']:,} customers"),
        ("Prepared", "November 2026 · Makafui Marvelous"),
    ]
    for label, value in info:
        ws.write(row, 1, label, fmt["body_bold"])
        ws.write(row, 2, value, fmt["body"])
        row += 1

    row += 1
    section_header(ws, fmt, row, "SHEET GUIDE", last_col=2)
    row += 1
    guide = [
        ("Summary", "Headline KPIs, the six key findings and four charts."),
        ("Category Analysis", "Sales, profit and margin by category and sub-category."),
        ("Regional Analysis", "Performance by region and by all 49 states."),
        ("Discount Analysis", "Profitability by discount band and the size of the discount problem."),
        ("Time Analysis", "Sales and profit by year and by month."),
        ("Customer Analysis", "Customer segments, top 10 customers and shipping modes."),
        ("Pivot Tables", "Pivot-style cross-tabs: region × category, segment × category, year × region and discount band × category."),
        ("Data", "The clean 9,994-row dataset with helper columns (Order Year, Order Month, Profit Margin, Discount Band)."),
    ]
    for name, desc in guide:
        ws.write(row, 1, name, fmt["body_bold"])
        ws.write(row, 2, desc, fmt["body"])
        row += 1

    row += 1
    section_header(ws, fmt, row, "METHOD", last_col=2)
    row += 1
    method = [
        "1. Extracted the real 9,994-row table from the source CSV. The file also contains two stray helper tables after row 9,994; those were excluded.",
        "2. Converted Order Date and Ship Date from text to real dates and added Order Year, Order Month, Profit Margin and Discount Band helper columns.",
        "3. Built every summary table with SUMIFS formulas against the Data sheet, so the workbook recalculates if the data changes.",
        "4. Checked the numbers against an independent pandas calculation; all totals match.",
        "5. Added four charts on the Summary sheet and conditional formatting (data bars, colour scales, red negatives) throughout.",
    ]
    for m in method:
        ws.merge_range(row, 1, row, 2, m, fmt["bullet"])
        ws.set_row(row, 28)
        row += 1

    row += 1
    ws.merge_range(row, 1, row, 2,
                   "Note: the dataset is fictional and covers one country. It contains no cost, marketing or returns data, so the findings demonstrate the method rather than a real business.",
                   fmt["note"])
    ws.set_row(row, 30)

    # ---------------------------------------------------------------- Summary
    ws = wb.add_worksheet("Summary")
    ws.hide_gridlines(2)
    ws.set_column("A:A", 2)
    ws.set_column("B:M", 13)
    add_title(ws, fmt, "Executive Summary",
              "Superstore sales performance · 2015–2018 · all figures from the Data sheet", last_col=12)

    kpi = t["kpi"]
    cards = [
        ("TOTAL SALES", kpi["sales"], "money", "=SUM(Data!$R$2:$R$9995)"),
        ("TOTAL PROFIT", kpi["profit"], "money", "=SUM(Data!$U$2:$U$9995)"),
        ("PROFIT MARGIN", kpi["margin"], "pct",
         "=IFERROR(SUM(Data!$U$2:$U$9995)/SUM(Data!$R$2:$R$9995),0)"),
        ("ORDERS", kpi["orders"], "num",
         "=SUMPRODUCT(1/COUNTIF(Data!$B$2:$B$9995,Data!$B$2:$B$9995))"),
        ("CUSTOMERS", kpi["customers"], "num",
         "=SUMPRODUCT(1/COUNTIF(Data!$F$2:$F$9995,Data!$F$2:$F$9995))"),
        ("ORDER LINES", kpi["lines"], "num", "=COUNTA(Data!$B$2:$B$9995)"),
    ]
    for i, (label, value, kind, formula) in enumerate(cards):
        c0 = 1 + i * 2
        c1 = c0 + 1
        ws.merge_range(3, c0, 3, c1, label, fmt["kpi_label"])
        ws.merge_range(4, c0, 5, c1, "", fmt["kpi_value"])
        if kind == "money":
            ws.write_formula(4, c0, formula, fmt["kpi_value"], float(value))
        elif kind == "pct":
            ws.write_formula(4, c0, formula, fmt["kpi_value_pct"], float(value))
        else:
            ws.write_formula(4, c0, formula, fmt["kpi_value_num"], float(value))
    ws.set_row(3, 20)
    ws.set_row(4, 26)
    ws.set_row(5, 26)

    section_header(ws, fmt, 7, "KEY FINDINGS", last_col=12)
    findings = [
        "1. Furniture sells a lot but earns very little: $742K of sales (32%) at a 2.5% margin, only 6.4% of total profit.",
        "2. Three sub-categories lose money: Tables (−$17.7K), Bookcases (−$3.5K) and Supplies (−$1.2K). Copiers ($55.6K, 37% margin) and Phones ($44.5K) are the best.",
        "3. Discounts above 20% lose $135K in total, and 72% of loss-making lines carry a discount above 20%. Tables only make money at full price (+$13.3K).",
        "4. Central is the weak spot: 7.9% margin against 14.9% in the West, and Furniture loses $2.9K there. 10 of 49 states lose money, led by Texas (−$25.7K), Ohio (−$17.0K) and Pennsylvania (−$15.6K).",
        "5. The business is growing: sales rose from $484K in 2015 to $733K in 2018 and profit from $49.5K to $93.4K. September, November and December are the strongest months.",
        "6. No customer dependence: the top 10 customers are only 6.7% of sales. Home Office has the best segment margin (14.0%) and Consumer the lowest (11.5%).",
    ]
    r = 8
    for text in findings:
        ws.merge_range(r, 1, r, 12, text, fmt["finding"])
        ws.set_row(r, 28)
        r += 1

    # Charts -------------------------------------------------------------
    def style_chart(chart, title, y_format=None):
        chart.set_title({"name": title, "name_font": {"size": 12, "bold": True, "color": NAVY}})
        chart.set_legend({"position": "bottom", "font": {"size": 9}})
        chart.set_chartarea({"border": {"none": True}})
        chart.set_plotarea({"border": {"none": True}})
        chart.set_size({"width": 470, "height": 290})
        if y_format:
            chart.set_y_axis({
                "num_format": y_format,
                "major_gridlines": {"visible": True, "line": {"color": "#E7E6E6"}},
                "font": {"size": 9},
            })
        chart.set_x_axis({"font": {"size": 9}})
        return chart

    # Sales by category (column)
    ch = wb.add_chart({"type": "column"})
    ch.add_series({
        "name": "Sales",
        "categories": "='Category Analysis'!$A$6:$A$8",
        "values": "='Category Analysis'!$B$6:$B$8",
        "fill": {"color": BLUE},
        "data_labels": {"value": True, "num_format": "$#,##0", "font": {"size": 9}},
    })
    style_chart(ch, "Sales by category", "$#,##0")
    ch.set_legend({"none": True})
    ws.insert_chart("B16", ch, {"x_offset": 5, "y_offset": 5})

    # Margin by category (column)
    ch = wb.add_chart({"type": "column"})
    ch.add_series({
        "name": "Margin",
        "categories": "='Category Analysis'!$A$6:$A$8",
        "values": "='Category Analysis'!$D$6:$D$8",
        "fill": {"color": GREEN},
        "data_labels": {"value": True, "num_format": "0.0%", "font": {"size": 9}},
    })
    style_chart(ch, "Profit margin by category", "0%")
    ch.set_legend({"none": True})
    ws.insert_chart("H16", ch, {"x_offset": 5, "y_offset": 5})

    # Monthly sales (line)
    ch = wb.add_chart({"type": "line"})
    ch.add_series({
        "name": "Monthly sales",
        "categories": "='Time Analysis'!$A$14:$A$25",
        "values": "='Time Analysis'!$B$14:$B$25",
        "line": {"color": BLUE, "width": 2.5},
        "marker": {"type": "circle", "size": 5, "fill": {"color": NAVY}, "border": {"color": NAVY}},
        "smooth": False,
    })
    style_chart(ch, "Sales by month (all years)", "$#,##0")
    ch.set_legend({"none": True})
    ws.insert_chart("B32", ch, {"x_offset": 5, "y_offset": 5})

    # Profit by discount band (column)
    ch = wb.add_chart({"type": "column"})
    ch.add_series({
        "name": "Profit",
        "categories": "='Discount Analysis'!$A$6:$A$11",
        "values": "='Discount Analysis'!$D$6:$D$11",
        "fill": {"color": ORANGE},
        "negative_fill": {"color": RED},
        "data_labels": {"value": True, "num_format": "$#,##0", "font": {"size": 9}},
    })
    style_chart(ch, "Profit by discount band", "$#,##0")
    ch.set_legend({"none": True})
    ws.insert_chart("H32", ch, {"x_offset": 5, "y_offset": 5})

    ws.merge_range(48, 1, 48, 12,
                   "Sources: Sample Superstore dataset (Tableau sample data). Tables recalculate with SUMIFS formulas on the Data sheet.",
                   fmt["note"])

    # ----------------------------------------------------- Category Analysis
    ws = wb.add_worksheet("Category Analysis")
    ws.hide_gridlines(2)
    ws.set_column("A:A", 22)
    ws.set_column("B:H", 15)
    add_title(ws, fmt, "Category Analysis", "Sales, profit and margin by category and sub-category", last_col=7)

    section_header(ws, fmt, 3, "BY CATEGORY", last_col=7)
    headers = ["Category", "Sales", "Profit", "Margin", "Sales share", "Profit share", "Lines"]
    for j, h in enumerate(headers):
        ws.write(4, j, h, fmt["header"])
    for i, (_, r) in enumerate(t["category"].iterrows(), start=5):
        ws.write(i, 0, r["Category"], fmt["body_bold"])
        ws.write_formula(i, 1, f"=SUMIFS(Data!$R$2:$R$9995,Data!$O$2:$O$9995,$A{i+1})", fmt["money"], float(r["Sales"]))
        ws.write_formula(i, 2, f"=SUMIFS(Data!$U$2:$U$9995,Data!$O$2:$O$9995,$A{i+1})", fmt["money"], float(r["Profit"]))
        ws.write_formula(i, 3, f"=IFERROR(C{i+1}/B{i+1},0)", fmt["pct"], float(r["Margin"]))
        ws.write_formula(i, 4, f"=IFERROR(B{i+1}/SUM($B$6:$B$8),0)", fmt["pct"], float(r["Sales Share"]))
        ws.write_formula(i, 5, f"=IFERROR(C{i+1}/SUM($C$6:$C$8),0)", fmt["pct"], float(r["Profit Share"]))
        ws.write(i, 6, int(r["Lines"]), fmt["num"])
    tr = 5 + len(t["category"])
    ws.write(tr, 0, "Total", fmt["total_label"])
    ws.write_formula(tr, 1, "=SUM(B6:B8)", fmt["total_money"], float(t["category"]["Sales"].sum()))
    ws.write_formula(tr, 2, "=SUM(C6:C8)", fmt["total_money"], float(t["category"]["Profit"].sum()))
    ws.write_formula(tr, 3, f"=IFERROR(C{tr+1}/B{tr+1},0)", fmt["total_pct"], float(t["kpi"]["margin"]))
    ws.write(tr, 4, 1.0, fmt["total_pct"])
    ws.write(tr, 5, 1.0, fmt["total_pct"])
    ws.write_formula(tr, 6, "=SUM(G6:G8)", fmt["total_num"], int(t["category"]["Lines"].sum()))
    ws.conditional_format(5, 1, tr - 1, 1, {"type": "data_bar", "bar_color": LIGHT_BLUE, "bar_solid": True})
    ws.conditional_format(5, 3, tr - 1, 3, {"type": "3_color_scale", "min_color": "#F8696B", "mid_color": "#FFEB84", "max_color": "#63BE7B"})

    section_header(ws, fmt, 10, "BY SUB-CATEGORY (SORTED BY PROFIT)", last_col=7)
    headers = ["Sub-category", "Sales", "Profit", "Margin", "", "", ""]
    for j, h in enumerate(headers):
        ws.write(11, j, h, fmt["header"])
    for i, (_, r) in enumerate(t["subcategory"].iterrows(), start=12):
        ws.write(i, 0, r["Sub-Category"], fmt["body_bold"])
        ws.write_formula(i, 1, f"=SUMIFS(Data!$R$2:$R$9995,Data!$P$2:$P$9995,$A{i+1})", fmt["money"], float(r["Sales"]))
        ws.write_formula(i, 2, f"=SUMIFS(Data!$U$2:$U$9995,Data!$P$2:$P$9995,$A{i+1})", fmt["money"], float(r["Profit"]))
        ws.write_formula(i, 3, f"=IFERROR(C{i+1}/B{i+1},0)", fmt["pct"], float(r["Margin"]))
        ws.write(i, 4, int(r["Lines"]), fmt["num"])
    last = 12 + len(t["subcategory"])
    ws.conditional_format(12, 2, last - 1, 2, {"type": "cell", "criteria": "<", "value": 0, "format": fmt["neg"]})
    ws.conditional_format(12, 3, last - 1, 3, {"type": "3_color_scale", "min_color": "#F8696B", "mid_color": "#FFEB84", "max_color": "#63BE7B"})
    ws.conditional_format(12, 1, last - 1, 1, {"type": "data_bar", "bar_color": LIGHT_BLUE, "bar_solid": True})

    # ------------------------------------------------------ Regional Analysis
    ws = wb.add_worksheet("Regional Analysis")
    ws.hide_gridlines(2)
    ws.set_column("A:A", 22)
    ws.set_column("B:E", 15)
    add_title(ws, fmt, "Regional Analysis", "Profitability by region and by state", last_col=4)

    section_header(ws, fmt, 3, "BY REGION", last_col=4)
    for j, h in enumerate(["Region", "Sales", "Profit", "Margin", "Rank by profit"]):
        ws.write(4, j, h, fmt["header"])
    for i, (_, r) in enumerate(t["region"].iterrows(), start=5):
        ws.write(i, 0, r["Region"], fmt["body_bold"])
        ws.write_formula(i, 1, f"=SUMIFS(Data!$R$2:$R$9995,Data!$M$2:$M$9995,$A{i+1})", fmt["money"], float(r["Sales"]))
        ws.write_formula(i, 2, f"=SUMIFS(Data!$U$2:$U$9995,Data!$M$2:$M$9995,$A{i+1})", fmt["money"], float(r["Profit"]))
        ws.write_formula(i, 3, f"=IFERROR(C{i+1}/B{i+1},0)", fmt["pct"], float(r["Margin"]))
        ws.write(i, 4, i - 4, fmt["num"])
    tr = 9
    ws.write(tr, 0, "Total", fmt["total_label"])
    ws.write_formula(tr, 1, "=SUM(B6:B9)", fmt["total_money"], float(t["region"]["Sales"].sum()))
    ws.write_formula(tr, 2, "=SUM(C6:C9)", fmt["total_money"], float(t["region"]["Profit"].sum()))
    ws.write_formula(tr, 3, f"=IFERROR(C{tr+1}/B{tr+1},0)", fmt["total_pct"], float(t["kpi"]["margin"]))
    ws.conditional_format(5, 3, 8, 3, {"type": "3_color_scale", "min_color": "#F8696B", "mid_color": "#FFEB84", "max_color": "#63BE7B"})

    section_header(ws, fmt, 11, "BY STATE (SORTED BY PROFIT)", last_col=4)
    for j, h in enumerate(["State", "Sales", "Profit", "Margin", "Status"]):
        ws.write(12, j, h, fmt["header"])
    for i, (_, r) in enumerate(t["state"].iterrows(), start=13):
        ws.write(i, 0, r["State"], fmt["body"])
        ws.write_formula(i, 1, f"=SUMIFS(Data!$R$2:$R$9995,Data!$K$2:$K$9995,$A{i+1})", fmt["money"], float(r["Sales"]))
        ws.write_formula(i, 2, f"=SUMIFS(Data!$U$2:$U$9995,Data!$K$2:$K$9995,$A{i+1})", fmt["money"], float(r["Profit"]))
        ws.write_formula(i, 3, f"=IFERROR(C{i+1}/B{i+1},0)", fmt["pct"], float(r["Margin"]))
        ws.write_formula(i, 4, f'=IF(C{i+1}<0,"Losing money","Profitable")', fmt["body_center"], "Losing money" if r["Profit"] < 0 else "Profitable")
    last = 13 + len(t["state"])
    ws.conditional_format(13, 2, last - 1, 2, {"type": "cell", "criteria": "<", "value": 0, "format": fmt["neg"]})
    ws.freeze_panes(13, 1)

    # ----------------------------------------------------- Discount Analysis
    ws = wb.add_worksheet("Discount Analysis")
    ws.hide_gridlines(2)
    ws.set_column("A:A", 16)
    ws.set_column("B:H", 15)
    add_title(ws, fmt, "Discount Analysis", "Profitability by discount band", last_col=7)

    section_header(ws, fmt, 3, "BY DISCOUNT BAND", last_col=7)
    for j, h in enumerate(["Discount band", "Lines", "Sales", "Profit", "Margin", "Loss-making lines", "Share of band that loses"]):
        ws.write(4, j, h, fmt["header"])
    for i, (_, r) in enumerate(t["band"].iterrows(), start=5):
        ws.write(i, 0, r["Discount Band"], fmt["body_bold"])
        ws.write_formula(i, 1, f"=COUNTIFS(Data!$Z$2:$Z$9995,$A{i+1})", fmt["num"], int(r["Lines"]))
        ws.write_formula(i, 2, f"=SUMIFS(Data!$R$2:$R$9995,Data!$Z$2:$Z$9995,$A{i+1})", fmt["money"], float(r["Sales"]))
        ws.write_formula(i, 3, f"=SUMIFS(Data!$U$2:$U$9995,Data!$Z$2:$Z$9995,$A{i+1})", fmt["money"], float(r["Profit"]))
        ws.write_formula(i, 4, f"=IFERROR(D{i+1}/C{i+1},0)", fmt["pct"], float(r["Margin"]))
        ws.write(i, 5, int(r["Loss Lines"]), fmt["num"])
        ws.write_formula(i, 6, f"=IFERROR(F{i+1}/B{i+1},0)", fmt["pct"], float(r["Loss Share"]))
    ws.conditional_format(5, 3, 10, 3, {"type": "cell", "criteria": "<", "value": 0, "format": fmt["neg"]})
    ws.conditional_format(5, 4, 10, 4, {"type": "3_color_scale", "min_color": "#F8696B", "mid_color": "#FFEB84", "max_color": "#63BE7B"})

    # Discount vs profit scatter
    ch = wb.add_chart({"type": "scatter"})
    ch.add_series({
        "name": "Orders",
        "categories": "=Data!$T$2:$T$9995",
        "values": "=Data!$U$2:$U$9995",
        "marker": {"type": "circle", "size": 3, "fill": {"color": BLUE, "transparency": 60}, "border": {"none": True}},
    })
    style_chart(ch, "Profit vs discount (every order line)", "$#,##0")
    ch.set_x_axis({"num_format": "0%", "font": {"size": 9}, "name": "Discount"})
    ch.set_y_axis({"num_format": "$#,##0", "font": {"size": 9}, "major_gridlines": {"visible": True, "line": {"color": "#E7E6E6"}}})
    ch.set_legend({"none": True})
    ws.insert_chart("A14", ch, {"x_offset": 5, "y_offset": 5})

    ws.merge_range(32, 0, 32, 7,
                   "Discounts above 20% are associated with $135K of losses; 72% of loss-making lines carry a discount above 20%.",
                   fmt["note"])

    # ---------------------------------------------------------- Time Analysis
    ws = wb.add_worksheet("Time Analysis")
    ws.hide_gridlines(2)
    ws.set_column("A:A", 14)
    ws.set_column("B:F", 16)
    add_title(ws, fmt, "Time Analysis", "Sales and profit by year and by month", last_col=5)

    section_header(ws, fmt, 3, "BY YEAR", last_col=5)
    for j, h in enumerate(["Year", "Sales", "Profit", "Margin", "Sales growth", "Profit growth"]):
        ws.write(4, j, h, fmt["header"])
    for i, (_, r) in enumerate(t["yearly"].iterrows(), start=5):
        ws.write(i, 0, int(r["Order Year"]), fmt["body_bold"])
        ws.write_formula(i, 1, f"=SUMIFS(Data!$R$2:$R$9995,Data!$V$2:$V$9995,$A{i+1})", fmt["money"], float(r["Sales"]))
        ws.write_formula(i, 2, f"=SUMIFS(Data!$U$2:$U$9995,Data!$V$2:$V$9995,$A{i+1})", fmt["money"], float(r["Profit"]))
        ws.write_formula(i, 3, f"=IFERROR(C{i+1}/B{i+1},0)", fmt["pct"], float(r["Margin"]))
        if i > 5:
            ws.write_formula(i, 4, f"=IFERROR(B{i+1}/B{i}-1,0)", fmt["pct"], float(t["yearly"]["Sales"].iloc[i - 5] / t["yearly"]["Sales"].iloc[i - 6] - 1))
            ws.write_formula(i, 5, f"=IFERROR(C{i+1}/C{i}-1,0)", fmt["pct"], float(t["yearly"]["Profit"].iloc[i - 5] / t["yearly"]["Profit"].iloc[i - 6] - 1))
        else:
            ws.write_blank(i, 4, None, fmt["pct"])
            ws.write_blank(i, 5, None, fmt["pct"])

    section_header(ws, fmt, 11, "BY MONTH (ALL YEARS)", last_col=5)
    for j, h in enumerate(["Month", "Sales", "Profit", "Margin", "Rank by sales", ""]):
        ws.write(12, j, h, fmt["header"])
    month_rank = t["monthly"]["Sales"].rank(ascending=False).astype(int)
    for i, (_, r) in enumerate(t["monthly"].iterrows(), start=13):
        ws.write(i, 0, pd.Timestamp(2024, int(r["Order Month"]), 1).strftime("%b"), fmt["body_bold"])
        ws.write_formula(i, 1, f"=SUMIFS(Data!$R$2:$R$9995,Data!$W$2:$W$9995,{int(r['Order Month'])})", fmt["money"], float(r["Sales"]))
        ws.write_formula(i, 2, f"=SUMIFS(Data!$U$2:$U$9995,Data!$W$2:$W$9995,{int(r['Order Month'])})", fmt["money"], float(r["Profit"]))
        ws.write_formula(i, 3, f"=IFERROR(C{i+1}/B{i+1},0)", fmt["pct"], float(r["Profit"] / r["Sales"]))
        ws.write(i, 4, int(month_rank.iloc[i - 13]), fmt["num"])
    ws.conditional_format(13, 1, 24, 1, {"type": "data_bar", "bar_color": LIGHT_BLUE, "bar_solid": True})

    ch = wb.add_chart({"type": "column"})
    ch.add_series({
        "name": "Sales",
        "categories": "='Time Analysis'!$A$6:$A$9",
        "values": "='Time Analysis'!$B$6:$B$9",
        "fill": {"color": BLUE},
        "data_labels": {"value": True, "num_format": "$#,##0", "font": {"size": 9}},
    })
    ch.add_series({
        "name": "Profit",
        "categories": "='Time Analysis'!$A$6:$A$9",
        "values": "='Time Analysis'!$C$6:$C$9",
        "fill": {"color": GREEN},
        "data_labels": {"value": True, "num_format": "$#,##0", "font": {"size": 9}},
    })
    style_chart(ch, "Sales and profit by year", "$#,##0")
    ws.insert_chart("G4", ch, {"x_offset": 5, "y_offset": 5})

    # ------------------------------------------------------- Customer Analysis
    ws = wb.add_worksheet("Customer Analysis")
    ws.hide_gridlines(2)
    ws.set_column("A:A", 24)
    ws.set_column("B:E", 16)
    add_title(ws, fmt, "Customer Analysis", "Segments, top customers and shipping modes", last_col=4)

    section_header(ws, fmt, 3, "BY SEGMENT", last_col=4)
    for j, h in enumerate(["Segment", "Sales", "Profit", "Margin", "Share of sales"]):
        ws.write(4, j, h, fmt["header"])
    for i, (_, r) in enumerate(t["segment"].iterrows(), start=5):
        ws.write(i, 0, r["Segment"], fmt["body_bold"])
        ws.write_formula(i, 1, f"=SUMIFS(Data!$R$2:$R$9995,Data!$H$2:$H$9995,$A{i+1})", fmt["money"], float(r["Sales"]))
        ws.write_formula(i, 2, f"=SUMIFS(Data!$U$2:$U$9995,Data!$H$2:$H$9995,$A{i+1})", fmt["money"], float(r["Profit"]))
        ws.write_formula(i, 3, f"=IFERROR(C{i+1}/B{i+1},0)", fmt["pct"], float(r["Margin"]))
        ws.write_formula(i, 4, f"=IFERROR(B{i+1}/SUM($B$6:$B$8),0)", fmt["pct"], float(r["Sales"] / t["kpi"]["sales"]))
    ws.conditional_format(5, 3, 7, 3, {"type": "3_color_scale", "min_color": "#F8696B", "mid_color": "#FFEB84", "max_color": "#63BE7B"})

    section_header(ws, fmt, 10, "TOP 10 CUSTOMERS", last_col=4)
    for j, h in enumerate(["Customer", "Sales", "Profit", "Margin", "Share of total sales"]):
        ws.write(11, j, h, fmt["header"])
    for i, (_, r) in enumerate(t["top_customers"].iterrows(), start=12):
        ws.write(i, 0, r["Customer Name"], fmt["body"])
        ws.write_number(i, 1, float(r["Sales"]), fmt["money"])
        ws.write_number(i, 2, float(r["Profit"]), fmt["money"])
        ws.write_formula(i, 3, f"=IFERROR(C{i+1}/B{i+1},0)", fmt["pct"], float(r["Profit"] / r["Sales"]))
        ws.write_formula(i, 4, f"=IFERROR(B{i+1}/SUM(Data!$R$2:$R$9995),0)", fmt["pct"], float(r["Sales"] / t["kpi"]["sales"]))
    ws.merge_range(22, 0, 22, 4,
                   f"The top 10 customers account for only {t['extra']['top10_share']:.1%} of sales, so the business does not depend on a few accounts.",
                   fmt["note"])

    section_header(ws, fmt, 24, "BY SHIP MODE", last_col=4)
    for j, h in enumerate(["Ship mode", "Sales", "Profit", "Margin", "Orders"]):
        ws.write(25, j, h, fmt["header"])
    for i, (_, r) in enumerate(t["ship"].iterrows(), start=26):
        ws.write(i, 0, r["Ship Mode"], fmt["body_bold"])
        ws.write_number(i, 1, float(r["Sales"]), fmt["money"])
        ws.write_number(i, 2, float(r["Profit"]), fmt["money"])
        ws.write_formula(i, 3, f"=IFERROR(C{i+1}/B{i+1},0)", fmt["pct"], float(r["Margin"]))
        ws.write_number(i, 4, int(r["Orders"]), fmt["num"])

    # ----------------------------------------------------------- Pivot Tables
    ws = wb.add_worksheet("Pivot Tables")
    ws.hide_gridlines(2)
    ws.set_column("A:A", 18)
    ws.set_column("B:H", 15)
    add_title(ws, fmt, "Pivot Tables",
              "Pivot-style cross-tabs built from the Data sheet. These are static summaries; use the Data sheet to rebuild them in a PivotTable.", last_col=7)

    def write_pivot(ws, fmt, table, title, start_row, money=True):
        section_header(ws, fmt, start_row, title, last_col=1 + len(table.columns))
        ws.write(start_row + 1, 0, table.index.name or "", fmt["header"])
        for j, c in enumerate(table.columns, start=1):
            ws.write(start_row + 1, j, str(c), fmt["header"])
        for i, (idx, r) in enumerate(table.iterrows(), start=2):
            ws.write(start_row + i, 0, str(idx), fmt["body_bold"])
            for j, c in enumerate(table.columns, start=1):
                v = r[c]
                if money:
                    ws.write_number(start_row + i, j, float(v), fmt["money"])
                else:
                    ws.write_number(start_row + i, j, float(v), fmt["num"])
        # totals
        tr = start_row + 2 + len(table)
        ws.write(tr, 0, "Total", fmt["total_label"])
        for j, c in enumerate(table.columns, start=1):
            ws.write_number(tr, j, float(table[c].sum()), fmt["total_money"] if money else fmt["total_num"])

    write_pivot(ws, fmt, t["pivot_region_category"], "SALES BY REGION × CATEGORY", 3)
    write_pivot(ws, fmt, t["pivot_segment_category"], "PROFIT BY SEGMENT × CATEGORY", 10)
    write_pivot(ws, fmt, t["pivot_year_region"], "SALES BY YEAR × REGION", 17)
    write_pivot(ws, fmt, t["pivot_band_category"], "PROFIT BY DISCOUNT BAND × CATEGORY", 24)

    # ------------------------------------------------------------------ Data
    ws = wb.add_worksheet("Data")
    ws.freeze_panes(1, 0)
    ws.set_row(0, 30)
    out_cols = [
        "Row ID", "Order ID", "Order Date", "Ship Date", "Ship Mode", "Customer ID",
        "Customer Name", "Segment", "Country", "City", "State", "Postal Code", "Region",
        "Product ID", "Category", "Sub-Category", "Product Name", "Sales", "Quantity",
        "Discount", "Profit", "Order Year", "Order Month", "Order Month Name",
        "Profit Margin", "Discount Band",
    ]
    for j, c in enumerate(out_cols):
        ws.write(0, j, c, fmt["header"])
    # itertuples hands back native Python scalars, so test on Python types too.
    for i, r in enumerate(df[out_cols].itertuples(index=False), start=1):
        for j, v in enumerate(r):
            if isinstance(v, pd.Timestamp):
                ws.write_datetime(i, j, v.to_pydatetime(), fmt["date"])
            elif isinstance(v, (bool, np.bool_)):
                ws.write_boolean(i, j, bool(v))
            elif isinstance(v, (int, np.integer)):
                ws.write_number(i, j, int(v), fmt["num"])
            elif isinstance(v, (float, np.floating)):
                if pd.isna(v):
                    ws.write_blank(i, j, None)
                else:
                    ws.write_number(i, j, float(v), fmt["num"])
            elif v is None or (not isinstance(v, str) and pd.isna(v)):
                ws.write_blank(i, j, None)
            else:
                ws.write(i, j, str(v), fmt["body"])
    ws.autofilter(0, 0, len(df), len(out_cols) - 1)
    ws.set_column(0, 0, 8)
    ws.set_column(1, 1, 16)
    ws.set_column(2, 3, 12)
    ws.set_column(4, 4, 12)
    ws.set_column(5, 6, 13)
    ws.set_column(7, 7, 11)
    ws.set_column(8, 9, 16)
    ws.set_column(10, 11, 12)
    ws.set_column(12, 12, 10)
    ws.set_column(13, 13, 17)
    ws.set_column(14, 15, 16)
    ws.set_column(16, 16, 45)
    ws.set_column(17, 17, 11)
    ws.set_column(18, 18, 9)
    ws.set_column(19, 19, 10)
    ws.set_column(20, 20, 11)
    ws.set_column(21, 22, 10)
    ws.set_column(23, 23, 12)
    ws.set_column(24, 24, 12)
    ws.set_column(25, 25, 12)

    wb.close()
    print(f"Workbook written to {OUT} ({OUT.stat().st_size / 1e6:.2f} MB)")


# --------------------------------------------------------------------------- #
# Preview image
# --------------------------------------------------------------------------- #
def build_preview(df: pd.DataFrame, t: dict):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    import matplotlib.ticker as mtick

    plt.rcParams["text.parse_math"] = False
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "axes.edgecolor": "#D9D9D9",
        "axes.labelcolor": "#404040",
        "text.color": "#262626",
        "xtick.color": "#595959",
        "ytick.color": "#595959",
    })

    fig = plt.figure(figsize=(16, 10), dpi=100)
    fig.patch.set_facecolor("white")

    # Header
    fig.patches.append(FancyBboxPatch((0, 0.925), 1, 0.075, boxstyle="square,pad=0",
                                      transform=fig.transFigure, facecolor=NAVY, edgecolor="none"))
    fig.text(0.035, 0.968, "Superstore Sales Performance", color="white",
             fontsize=26, fontweight="bold", va="center")
    fig.text(0.035, 0.940, "Executive summary · 2015–2018 · 9,994 order lines · 5,009 orders · 793 customers",
             color="#D9E2F3", fontsize=12, va="center")

    # KPI cards
    kpi = t["kpi"]
    cards = [
        ("TOTAL SALES", f"${kpi['sales']/1e6:.2f}M"),
        ("TOTAL PROFIT", f"${kpi['profit']/1e3:.0f}K"),
        ("PROFIT MARGIN", f"{kpi['margin']:.1%}"),
        ("ORDERS", f"{kpi['orders']:,}"),
        ("CUSTOMERS", f"{kpi['customers']:,}"),
        ("ORDER LINES", f"{kpi['lines']:,}"),
    ]
    x0, y0, w, h, gap = 0.035, 0.815, 0.147, 0.085, 0.0085
    for i, (label, value) in enumerate(cards):
        x = x0 + i * (w + gap)
        fig.patches.append(FancyBboxPatch((x, y0), w, h, boxstyle="round,pad=0.004,rounding_size=0.008",
                                          transform=fig.transFigure, facecolor=LIGHT_BLUE,
                                          edgecolor="#8EA9DB", linewidth=0.8))
        fig.text(x + w / 2, y0 + h * 0.66, label, ha="center", va="center",
                 fontsize=9.5, fontweight="bold", color="#595959")
        fig.text(x + w / 2, y0 + h * 0.30, value, ha="center", va="center",
                 fontsize=20, fontweight="bold", color=NAVY)

    # Chart grid
    def add_axes(rect):
        ax = fig.add_axes(rect)
        ax.set_facecolor("white")
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.grid(axis="y", color="#E7E6E6", linewidth=0.8)
        ax.set_axisbelow(True)
        return ax

    # 1. Sales by category
    ax = add_axes([0.06, 0.545, 0.38, 0.20])
    cat = t["category"]
    bars = ax.bar(cat["Category"], cat["Sales"] / 1e6, color=BLUE, width=0.55)
    ax.set_title("Sales by category ($M)", fontsize=12, fontweight="bold", color=NAVY, loc="left")
    ax.yaxis.set_major_formatter(mtick.FormatStrFormatter("%.1f"))
    for b, v in zip(bars, cat["Sales"] / 1e6):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.03, f"${v:.2f}M",
                ha="center", fontsize=9, color="#404040")
    ax.set_ylim(0, (cat["Sales"].max() / 1e6) * 1.18)
    ax.tick_params(axis="x", labelsize=9.5)

    # 2. Margin by category
    ax = add_axes([0.56, 0.545, 0.38, 0.20])
    colors = [GREEN if m >= 0 else RED for m in cat["Margin"]]
    bars = ax.bar(cat["Category"], cat["Margin"] * 100, color=colors, width=0.55)
    ax.set_title("Profit margin by category (%)", fontsize=12, fontweight="bold", color=NAVY, loc="left")
    ax.yaxis.set_major_formatter(mtick.FormatStrFormatter("%.0f%%"))
    for b, v in zip(bars, cat["Margin"] * 100):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.4, f"{v:.1f}%",
                ha="center", fontsize=9, color="#404040")
    ax.set_ylim(0, max(cat["Margin"] * 100) * 1.25)
    ax.tick_params(axis="x", labelsize=9.5)

    # 3. Monthly sales
    ax = add_axes([0.06, 0.275, 0.38, 0.20])
    mo = t["monthly"]
    ax.plot(mo["Order Month"], mo["Sales"] / 1e3, color=BLUE, linewidth=2.5,
            marker="o", markersize=5, markerfacecolor=NAVY, markeredgecolor=NAVY)
    ax.fill_between(mo["Order Month"], mo["Sales"] / 1e3, color=LIGHT_BLUE, alpha=0.55)
    ax.set_title("Sales by month ($K, all years)", fontsize=12, fontweight="bold", color=NAVY, loc="left")
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], fontsize=8.5)
    ax.set_xlim(0.5, 12.5)

    # 4. Profit by discount band
    ax = add_axes([0.56, 0.275, 0.38, 0.20])
    band = t["band"]
    colors = [GREEN if p >= 0 else RED for p in band["Profit"]]
    bars = ax.bar(band["Discount Band"], band["Profit"] / 1e3, color=colors, width=0.6)
    ax.axhline(0, color="#7F7F7F", linewidth=0.8)
    ax.set_title("Profit by discount band ($K)", fontsize=12, fontweight="bold", color=NAVY, loc="left")
    ax.yaxis.set_major_formatter(mtick.FormatStrFormatter("%.0f"))
    ax.set_ylim(min(band["Profit"] / 1e3) * 1.45, max(band["Profit"] / 1e3) * 1.22)
    for b, v in zip(bars, band["Profit"] / 1e3):
        if v >= 0:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 8, f"${v:,.0f}K",
                    ha="center", va="bottom", fontsize=8.5, color="#404040")
        else:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() - 8, f"−${abs(v):,.0f}K",
                    ha="center", va="top", fontsize=8.5, color="#404040")
    ax.tick_params(axis="x", labelsize=8.5)

    # Findings panel
    fig.patches.append(FancyBboxPatch((0.035, 0.025), 0.93, 0.19, boxstyle="round,pad=0.004,rounding_size=0.008",
                                      transform=fig.transFigure, facecolor="#FAFAFA",
                                      edgecolor="#D9D9D9", linewidth=0.8))
    fig.text(0.05, 0.196, "KEY FINDINGS", fontsize=10.5, fontweight="bold", color=NAVY)
    findings = [
        "Furniture is 32% of sales but only 6.4% of profit (2.5% margin). Tables (−$17.7K), Bookcases (−$3.5K) and Supplies (−$1.2K) lose money.",
        "Discounts above 20% lose $135K in total; 72% of loss-making lines carry a discount above 20%. Tables only make money at full price (+$13.3K).",
        "Central's margin is 7.9% against 14.9% in the West; 10 of 49 states lose money, led by Texas (−$25.7K), Ohio (−$17.0K) and Pennsylvania (−$15.6K).",
        "Sales grew from $484K (2015) to $733K (2018) and profit from $49.5K to $93.4K. Top 10 customers are only 6.7% of sales; Home Office has the best margin (14.0%).",
    ]
    for i, text in enumerate(findings):
        fig.text(0.055, 0.168 - i * 0.033, "•  " + text, fontsize=9.2, color="#404040", va="top")

    IMG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(IMG, dpi=100, facecolor="white", bbox_inches=None)
    plt.close(fig)
    print(f"Preview image written to {IMG}")


if __name__ == "__main__":
    data = load_data()
    tables = build_tables(data)
    build_workbook(data, tables)
    build_preview(data, tables)
