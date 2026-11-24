"""
Build the capstone dashboard and summary tables.

Inputs : ../.rawdata/owid-co2-data.csv (OWID CO2 and Greenhouse Gas Emissions data)
Outputs: dashboard.html                interactive Plotly dashboard
         ../images/dashboard.png       static preview
         summary/*.csv                 summary tables used by the dashboard and SQL

Run:
    python build_dashboard.py
"""

from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RAW = ROOT / ".rawdata" / "owid-co2-data.csv"
SUMMARY = HERE / "summary"
IMG = ROOT / "images" / "dashboard.png"

NAVY = "#1F3864"
BLUE = "#2E75B6"
ORANGE = "#C55A11"
GREEN = "#548235"
GREY = "#A5A5A5"
LIGHT = "#F7F9FC"

SEGMENT_COLORS = {
    "Growth engine": ORANGE,
    "Managed decline": BLUE,
    "Watchlist": GREY,
    "On track": GREEN,
}


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
def load_snapshot() -> pd.DataFrame:
    df = pd.read_csv(RAW)
    # Keep countries (ISO-3 codes), not OWID regions or income groups.
    c = df[df["iso_code"].notna() & ~df["iso_code"].str.startswith("OWID")].copy()

    latest = c[c["year"] == 2023].copy()
    gdp_2022 = c[c["year"] == 2022][["country", "iso_code", "gdp", "co2_per_gdp"]].rename(
        columns={"gdp": "gdp_2022", "co2_per_gdp": "co2_per_gdp_2022"}
    )
    co2_2013 = c[c["year"] == 2013][["country", "iso_code", "co2"]].rename(
        columns={"co2": "co2_2013"}
    )

    snap = (
        latest.merge(gdp_2022, on=["country", "iso_code"], how="left")
        .merge(co2_2013, on=["country", "iso_code"], how="left")
    )
    snap["gdp_per_capita"] = snap["gdp_2022"] / snap["population"]
    snap["growth_abs"] = snap["co2"] - snap["co2_2013"]
    snap["growth_pct"] = (snap["co2"] / snap["co2_2013"] - 1) * 100
    snap["coal_share"] = snap["coal_co2"] / snap["co2"] * 100
    # OWID's own share columns use a different denominator; recompute them from
    # this snapshot so the shares add up to 100% and match the headline totals.
    snap["share_global_co2"] = snap["co2"] / snap["co2"].sum() * 100
    snap["share_global_cumulative_co2"] = (
        snap["cumulative_co2"] / snap["cumulative_co2"].sum() * 100
    )
    snap["segment"] = np.select(
        [
            (snap["co2"] >= 100) & (snap["growth_abs"] > 0),
            (snap["co2"] >= 100) & (snap["growth_abs"] <= 0),
            (snap["co2"] < 100) & (snap["growth_abs"] > 0),
        ],
        ["Growth engine", "Managed decline", "Watchlist"],
        default="On track",
    )

    # Priority score within the 41 countries emitting at least 100 Mt in 2023.
    # Weights: absolute emissions 40%, growth 30%, carbon intensity 20%, coal 10%.
    pool = snap[snap["co2"] >= 100].copy()
    n_pool = len(pool)
    for col in ["co2", "growth_abs", "co2_per_gdp_2022", "coal_share"]:
        # Same definition as SQL PERCENT_RANK(): (rank - 1) / (N - 1)
        pool[f"{col}_pct"] = (pool[col].rank(method="average") - 1) / (n_pool - 1) * 100
    pool["priority_score"] = (
        0.40 * pool["co2_pct"]
        + 0.30 * pool["growth_abs_pct"]
        + 0.20 * pool["co2_per_gdp_2022_pct"]
        + 0.10 * pool["coal_share_pct"]
    ).round(1)
    snap = snap.merge(
        pool[["country", "priority_score"]], on="country", how="left"
    )
    return snap, c


def save_tables(snap: pd.DataFrame, c: pd.DataFrame) -> dict:
    SUMMARY.mkdir(exist_ok=True)
    snapshot_cols = [
        "country", "iso_code", "population", "co2", "co2_per_capita",
        "share_global_co2", "cumulative_co2", "share_global_cumulative_co2",
        "coal_share", "growth_abs", "growth_pct", "gdp_per_capita",
        "co2_per_gdp_2022", "segment", "priority_score",
    ]
    snap.sort_values("co2", ascending=False)[snapshot_cols].to_csv(
        SUMMARY / "co2_2023_snapshot.csv", index=False
    )

    priority = snap.dropna(subset=["priority_score"]).sort_values(
        "priority_score", ascending=False
    )
    priority = priority.head(15).copy()
    priority.insert(0, "rank", range(1, len(priority) + 1))
    priority[[
        "rank", "country", "co2", "growth_abs", "growth_pct", "coal_share",
        "co2_per_gdp_2022", "priority_score", "segment",
    ]].round(1).to_csv(SUMMARY / "priority_table.csv", index=False)

    seg = snap.groupby("segment").agg(
        countries=("country", "size"), co2=("co2", "sum")
    ).reset_index()
    seg["share_of_global"] = seg["co2"] / seg["co2"].sum() * 100
    seg.round(1).to_csv(SUMMARY / "segment_summary.csv", index=False)

    snap.nlargest(15, "co2")[
        ["country", "co2", "co2_per_capita", "share_global_co2", "segment"]
    ].round(2).to_csv(SUMMARY / "top_emitters.csv", index=False)

    trends = c[c["country"].isin(["China", "United States", "India", "Russia", "Japan"])
               & (c["year"] >= 1990)][["country", "year", "co2"]]
    trends.to_csv(SUMMARY / "trends_top5.csv", index=False)

    return {
        "global_co2": snap["co2"].sum(),
        "top3_share": snap.nlargest(3, "co2")["co2"].sum() / snap["co2"].sum() * 100,
        "top10_share": snap.nlargest(10, "co2")["co2"].sum() / snap["co2"].sum() * 100,
        # Share of all CO2 since 1750 held by the ten largest *cumulative* emitters
        # (a different set from the ten largest current emitters).
        "top10_cum_emitters_share": snap.nlargest(10, "cumulative_co2")["cumulative_co2"].sum()
        / snap["cumulative_co2"].sum() * 100,
        "top10_current_cum_share": snap.nlargest(10, "co2")["cumulative_co2"].sum()
        / snap["cumulative_co2"].sum() * 100,
        "growth_engine_share": seg.loc[seg.segment == "Growth engine", "share_of_global"].iloc[0],
        "growth_engine_growth": snap.loc[snap.segment == "Growth engine", "growth_abs"].sum(),
        "decline_growth": snap.loc[snap.segment == "Managed decline", "growth_abs"].sum(),
        "countries_100mt": int((snap["co2"] >= 100).sum()),
        "n_countries": int(snap["co2"].notna().sum()),
        "median_pc": snap["co2_per_capita"].median(),
        "priority": priority,
        "seg": seg,
    }


# --------------------------------------------------------------------------- #
# Plotly dashboard
# --------------------------------------------------------------------------- #
def build_html(snap: pd.DataFrame, c: pd.DataFrame, k: dict) -> str:
    # --- Choropleth: CO2 per capita -----------------------------------------
    fig_map = go.Figure(go.Choropleth(
        locations=snap["iso_code"],
        z=snap["co2_per_capita"],
        text=snap["country"],
        colorscale="YlOrRd",
        zmin=0,
        zmax=20,
        marker_line_color="white",
        marker_line_width=0.4,
        colorbar=dict(title="t CO2 per person", thickness=12, len=0.65, x=1.0),
        hovertemplate=(
            "<b>%{text}</b><br>%{z:.1f} t CO2 per person"
            "<br>%{customdata[0]:,.0f} Mt total"
            "<br>%{customdata[1]:.1f}% of global<extra></extra>"
        ),
        customdata=np.stack([
            snap["co2"].fillna(0),
            snap["share_global_co2"].fillna(0),
        ], axis=1),
    ))
    fig_map.update_layout(
        geo=dict(
            showframe=False, showcoastlines=False, projection_type="natural earth",
            landcolor="#F1F1F1", showcountries=False, bgcolor="white",
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=430,
        paper_bgcolor="white",
    )

    # --- Top 15 emitters -----------------------------------------------------
    top = snap.nlargest(15, "co2").sort_values("co2")
    fig_top = go.Figure()
    for segment in ["Growth engine", "Managed decline", "Watchlist", "On track"]:
        d = top[top["segment"] == segment]
        if d.empty:
            continue
        fig_top.add_trace(go.Bar(
            y=d["country"], x=d["co2"], orientation="h", name=segment,
            marker_color=SEGMENT_COLORS[segment],
            text=d["co2"].round(0).astype(int).astype(str),
            textposition="outside", textfont=dict(size=9),
            hovertemplate="<b>%{y}</b><br>%{x:,.0f} Mt CO2<extra></extra>",
        ))
    fig_top.update_layout(
        barmode="stack", height=430, margin=dict(l=10, r=30, t=10, b=10),
        legend=dict(orientation="h", y=1.06, x=0, font=dict(size=9)),
        xaxis=dict(title="Mt CO2 in 2023"),
        paper_bgcolor="white", plot_bgcolor="white",
    )

    # --- GDP vs CO2 per capita ----------------------------------------------
    d = snap.dropna(subset=["gdp_per_capita", "co2_per_capita"]).copy()
    d = d[(d["gdp_per_capita"] > 0) & (d["co2_per_capita"] > 0)]
    fig_scatter = go.Figure()
    for segment in ["Growth engine", "Managed decline", "Watchlist", "On track"]:
        dd = d[d["segment"] == segment]
        if dd.empty:
            continue
        fig_scatter.add_trace(go.Scatter(
            x=dd["gdp_per_capita"], y=dd["co2_per_capita"],
            mode="markers", name=segment,
            marker=dict(
                size=np.sqrt(dd["population"] / 1e6).clip(lower=1) * 2.1,
                sizemode="diameter", color=SEGMENT_COLORS[segment],
                line=dict(width=0.6, color="white"), opacity=0.75,
            ),
            text=dd["country"],
            hovertemplate=(
                "<b>%{text}</b><br>GDP per capita: $%{x:,.0f}"
                "<br>CO2 per capita: %{y:.1f} t<extra></extra>"
            ),
        ))
    labels = ["China", "United States", "India", "Russia", "Indonesia", "Iran",
              "Vietnam", "Saudi Arabia", "South Africa", "Germany", "Japan",
              "Brazil", "Australia", "Canada", "Qatar"]
    lab = d[d["country"].isin(labels)]
    fig_scatter.add_trace(go.Scatter(
        x=lab["gdp_per_capita"], y=lab["co2_per_capita"], mode="markers+text",
        text=lab["country"], textposition="top center",
        textfont=dict(size=9, color="#262626"),
        marker=dict(size=5, color="rgba(0,0,0,0)"),
        hoverinfo="skip", showlegend=False,
    ))
    fig_scatter.update_layout(
        xaxis=dict(type="log", title="GDP per capita, 2022 (log)"),
        yaxis=dict(type="log", title="CO2 per capita, 2023 (log)"),
        height=430, margin=dict(l=10, r=20, t=10, b=10),
        legend=dict(orientation="h", y=1.06, x=0, font=dict(size=9)),
        paper_bgcolor="white", plot_bgcolor="white",
    )

    # --- Growth 2013-2023 ----------------------------------------------------
    grow = pd.concat([
        snap.nlargest(12, "growth_abs"),
        snap.nsmallest(6, "growth_abs"),
    ]).drop_duplicates(subset=["country"]).sort_values("growth_abs")
    fig_growth = go.Figure(go.Bar(
        y=grow["country"], x=grow["growth_abs"], orientation="h",
        marker_color=[ORANGE if v > 0 else BLUE for v in grow["growth_abs"]],
        text=grow["growth_abs"].round(0).astype(int).astype(str),
        textposition="outside", textfont=dict(size=9),
        hovertemplate="<b>%{y}</b><br>%{x:+,.0f} Mt since 2013<extra></extra>",
    ))
    fig_growth.update_layout(
        height=430, margin=dict(l=10, r=40, t=10, b=10),
        xaxis=dict(title="Change in CO2, 2013–2023 (Mt)"),
        paper_bgcolor="white", plot_bgcolor="white",
    )

    # --- Trends for the top 5 emitters --------------------------------------
    trend_countries = ["China", "United States", "India", "Russia", "Japan"]
    fig_trend = go.Figure()
    for country in trend_countries:
        dd = c[(c["country"] == country) & (c["year"] >= 1990)]
        fig_trend.add_trace(go.Scatter(
            x=dd["year"], y=dd["co2"], mode="lines", name=country,
            line=dict(width=2.2), hovertemplate="%{y:,.0f} Mt in %{x}<extra>"
            + country + "</extra>",
        ))
    fig_trend.update_layout(
        xaxis=dict(title="Year"), yaxis=dict(title="Mt CO2"),
        height=430, margin=dict(l=10, r=20, t=10, b=10),
        legend=dict(orientation="h", y=1.08, x=0, font=dict(size=9)),
        paper_bgcolor="white", plot_bgcolor="white",
    )

    # --- Priority table ------------------------------------------------------
    priority = k["priority"].copy()
    fig_table = go.Figure(go.Table(
        columnwidth=[45, 130, 70, 85, 65, 65, 75],
        header=dict(
            values=["Rank", "Country", "CO2 Mt", "Growth Mt", "Coal %", "CO2/$", "Score"],
            fill_color=NAVY, font=dict(color="white", size=11), align="left", height=28,
        ),
        cells=dict(
            values=[
                priority["rank"], priority["country"], priority["co2"].round(0).astype(int),
                priority["growth_abs"].round(0).astype(int), priority["coal_share"].round(0),
                priority["co2_per_gdp_2022"].round(2), priority["priority_score"],
            ],
            fill_color=[["#F7F9FC" if i % 2 == 0 else "white" for i in range(len(priority))]] * 7,
            align="left", font=dict(size=10), height=24,
        ),
    ))
    fig_table.update_layout(
        margin=dict(l=0, r=0, t=0, b=0), height=430, paper_bgcolor="white"
    )

    # --- HTML ---------------------------------------------------------------
    kpis = [
        ("Global CO2, 2023", f"{k['global_co2']/1000:.1f} Gt"),
        ("Share from top 3 emitters", f"{k['top3_share']:.1f}%"),
        ("Share from growth engines", f"{k['growth_engine_share']:.1f}%"),
        ("Countries emitting 100 Mt+", f"{k['countries_100mt']}"),
    ]
    kpi_html = "".join(
        f'<div class="kpi"><div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div></div>'
        for label, value in kpis
    )

    charts = [
        ("Where emissions are concentrated", fig_map, "span2"),
        ("Top 15 emitters, 2023", fig_top, ""),
        ("GDP per capita vs CO2 per capita", fig_scatter, ""),
        ("Who added and who cut emissions, 2013–2023", fig_growth, ""),
        ("Priority score — the 15 countries to focus on", fig_table, ""),
        ("Emissions trend for the top 5 emitters, 1990–2023", fig_trend, ""),
    ]
    chart_html = "".join(
        f'<div class="card {cls}"><h2>{title}</h2>'
        f'{fig.to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": False})}</div>'
        for title, fig, cls in charts
    )

    findings = [
        f"The top three emitters — China, the United States and India — produce <b>{k['top3_share']:.1f}%</b> of global CO2; the top ten produce <b>{k['top10_share']:.1f}%</b>.",
        f"The 23 growth-engine countries produce <b>{k['growth_engine_share']:.1f}%</b> of global CO2 and added <b>{k['growth_engine_growth']:,.0f} Mt</b> since 2013. The 18 managed decliners cut <b>{abs(k['decline_growth']):,.0f} Mt</b> over the same period.",
        "Coal is the dominant fuel in the priority countries: 71.1% of China's CO2, 66.6% of India's, 81.9% of South Africa's and 58.1% of Vietnam's.",
        f"Per-capita emissions range from 0.1 t in the poorest countries to 32.8 t in Qatar; the global median is <b>{k['median_pc']:.1f} t</b> per person.",
        "A 20% reduction in the growth engines' 2013–2023 trajectory would avoid roughly <b>950 Mt</b> of CO2 per year by 2033.",
    ]
    findings_html = "".join(f"<li>{f}</li>" for f in findings)

    css = """
    * { box-sizing: border-box; }
    body { margin: 0; font-family: 'Segoe UI', Arial, sans-serif; background: #F2F4F8; color: #262626; }
    header { background: #1F3864; color: white; padding: 26px 36px 22px; }
    header h1 { margin: 0 0 6px; font-size: 26px; letter-spacing: -0.3px; }
    header p { margin: 0; color: #D9E2F3; font-size: 13px; }
    .wrap { max-width: 1440px; margin: 0 auto; padding: 18px 24px 40px; }
    .kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
    .kpi { background: white; border-radius: 10px; padding: 14px 18px; box-shadow: 0 1px 3px rgba(31,56,100,0.10); }
    .kpi-label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.6px; color: #595959; font-weight: 600; }
    .kpi-value { font-size: 26px; font-weight: 700; color: #1F3864; margin-top: 4px; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
    .card { background: white; border-radius: 10px; padding: 14px 16px 8px; box-shadow: 0 1px 3px rgba(31,56,100,0.10); }
    .card.span2 { grid-column: span 2; }
    .card h2 { margin: 0 0 6px; font-size: 14px; color: #1F3864; font-weight: 600; }
    .card .plotly { width: 100% !important; }
    .findings { background: white; border-radius: 10px; padding: 18px 24px; margin-top: 14px; box-shadow: 0 1px 3px rgba(31,56,100,0.10); }
    .findings h2 { margin: 0 0 8px; font-size: 15px; color: #1F3864; }
    .findings ul { margin: 0; padding-left: 20px; }
    .findings li { margin: 7px 0; font-size: 13px; line-height: 1.45; }
    footer { color: #7F7F7F; font-size: 11px; margin-top: 14px; line-height: 1.5; }
    @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } .card.span2 { grid-column: span 1; } .kpis { grid-template-columns: repeat(2, 1fr); } }
    """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Global CO2 Priorities — Capstone Dashboard</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>{css}</style>
</head>
<body>
<header>
  <h1>Where Should a Climate Fund Invest? — Global CO2 Priorities</h1>
  <p>OWID CO2 and Greenhouse Gas Emissions data · 2023 emissions, 2022 GDP · {k['n_countries']} countries with data</p>
</header>
<div class="wrap">
  <div class="kpis">{kpi_html}</div>
  <div class="grid">{chart_html}</div>
  <section class="findings">
    <h2>What the dashboard says</h2>
    <ul>{findings_html}</ul>
  </section>
  <footer>
    Source: <a href="https://github.com/owid/co2-data">Our World in Data — CO2 and Greenhouse Gas Emissions data</a>.
    Priority score = 40% absolute emissions + 30% emissions growth 2013–2023 + 20% carbon intensity (2022) + 10% coal share,
    ranked among the 41 countries emitting at least 100 Mt in 2023. GDP data is only available to 2022.
    This is a portfolio project, not investment advice.
  </footer>
</div>
</body>
</html>"""
    return html


# --------------------------------------------------------------------------- #
# Static PNG preview
# --------------------------------------------------------------------------- #
def build_png(snap: pd.DataFrame, k: dict):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mtick
    from matplotlib.patches import FancyBboxPatch
    from matplotlib.lines import Line2D

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
    fig.patches.append(FancyBboxPatch((0, 0.925), 1, 0.075, boxstyle="square,pad=0",
                                      transform=fig.transFigure, facecolor=NAVY, edgecolor="none"))
    fig.text(0.035, 0.968, "Global CO2 Priorities — Where Should a Climate Fund Invest?",
             color="white", fontsize=24, fontweight="bold", va="center")
    fig.text(0.035, 0.940, "OWID CO2 data · 2023 emissions, 2022 GDP · 220 countries · 41 emit at least 100 Mt",
             color="#D9E2F3", fontsize=12, va="center")

    cards = [
        ("GLOBAL CO2, 2023", f"{k['global_co2']/1000:.1f} Gt"),
        ("TOP 3 SHARE", f"{k['top3_share']:.1f}%"),
        ("GROWTH ENGINES", f"{k['growth_engine_share']:.1f}%"),
        ("100 Mt+ EMITTERS", f"{k['countries_100mt']}"),
    ]
    x0, y0, w, h, gap = 0.035, 0.825, 0.2225, 0.078, 0.010
    for i, (label, value) in enumerate(cards):
        x = x0 + i * (w + gap)
        fig.patches.append(FancyBboxPatch((x, y0), w, h, boxstyle="round,pad=0.004,rounding_size=0.008",
                                          transform=fig.transFigure, facecolor="#D9E2F3",
                                          edgecolor="#8EA9DB", linewidth=0.8))
        fig.text(x + w / 2, y0 + h * 0.67, label, ha="center", va="center",
                 fontsize=9.5, fontweight="bold", color="#595959")
        fig.text(x + w / 2, y0 + h * 0.30, value, ha="center", va="center",
                 fontsize=20, fontweight="bold", color=NAVY)

    def add_axes(rect):
        ax = fig.add_axes(rect)
        ax.set_facecolor("white")
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.grid(axis="y", color="#E7E6E6", linewidth=0.8)
        ax.set_axisbelow(True)
        return ax

    # 1. Top 15 emitters
    ax = add_axes([0.06, 0.535, 0.40, 0.215])
    top = snap.nlargest(15, "co2").sort_values("co2")
    ax.barh(top["country"], top["co2"], color=[SEGMENT_COLORS[s] for s in top["segment"]], height=0.65)
    ax.set_title("Top 15 emitters, 2023 (Mt CO2)", fontsize=12, fontweight="bold", color=NAVY, loc="left")
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color="#E7E6E6", linewidth=0.8)
    for y, v in zip(top["country"], top["co2"]):
        ax.text(v + 120, y, f"{v:,.0f}", va="center", fontsize=8, color="#404040")
    ax.set_xlim(0, top["co2"].max() * 1.18)
    ax.tick_params(labelsize=7.8)
    handles = [Line2D([0], [0], marker="s", color="w", markerfacecolor=SEGMENT_COLORS[s], markersize=8, label=s)
               for s in ["Growth engine", "Managed decline", "Watchlist", "On track"]]
    ax.legend(handles=handles, loc="lower right", frameon=False, fontsize=7.5)

    # 2. Growth 2013-2023
    ax = add_axes([0.56, 0.545, 0.40, 0.20])
    grow = pd.concat([snap.nlargest(10, "growth_abs"), snap.nsmallest(5, "growth_abs")]).drop_duplicates("country").sort_values("growth_abs")
    colors = [ORANGE if v > 0 else BLUE for v in grow["growth_abs"]]
    ax.barh(grow["country"], grow["growth_abs"], color=colors, height=0.65)
    ax.axvline(0, color="#7F7F7F", linewidth=0.8)
    ax.set_title("Change in CO2, 2013–2023 (Mt)", fontsize=12, fontweight="bold", color=NAVY, loc="left")
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color="#E7E6E6", linewidth=0.8)
    for y, v in zip(grow["country"], grow["growth_abs"]):
        ax.text(v + (40 if v >= 0 else -40), y, f"{v:+,.0f}", va="center",
                ha="left" if v >= 0 else "right", fontsize=7.5, color="#404040")
    ax.tick_params(labelsize=8.5)

    # 3. Scatter GDP vs CO2 per capita
    ax = add_axes([0.06, 0.275, 0.40, 0.20])
    d = snap.dropna(subset=["gdp_per_capita", "co2_per_capita"])
    d = d[(d.gdp_per_capita > 0) & (d.co2_per_capita > 0)]
    for segment in ["Growth engine", "Managed decline", "Watchlist", "On track"]:
        dd = d[d.segment == segment]
        ax.scatter(dd.gdp_per_capita, dd.co2_per_capita, s=np.sqrt(dd.population / 1e6) * 1.8,
                   color=SEGMENT_COLORS[segment], alpha=0.6, edgecolor="white", linewidth=0.5, label=segment)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(300, 160000)
    ax.set_ylim(0.07, 60)
    ax.xaxis.set_major_locator(mtick.LogLocator(base=10, numticks=6))
    ax.yaxis.set_major_locator(mtick.LogLocator(base=10, numticks=6))
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda y, _: f"{y:g} t"))
    ax.xaxis.set_minor_formatter(mtick.NullFormatter())
    ax.yaxis.set_minor_formatter(mtick.NullFormatter())
    ax.set_xlabel("GDP per capita, 2022 (log)")
    ax.set_ylabel("CO2 per capita, 2023 (log)")
    ax.set_title("GDP per capita vs CO2 per capita (bubble = population)", fontsize=12,
                 fontweight="bold", color=NAVY, loc="left")
    for country in ["China", "United States", "India", "Russia", "Indonesia", "Iran",
                    "Vietnam", "Saudi Arabia", "South Africa", "Germany", "Japan",
                    "Australia", "Canada", "Qatar"]:
        row = d[d.country == country]
        if len(row):
            ax.annotate(country, (row.gdp_per_capita.iloc[0], row.co2_per_capita.iloc[0]),
                        fontsize=7, color=NAVY, xytext=(4, 3), textcoords="offset points")
    ax.tick_params(labelsize=8)

    # 4. Priority score
    ax = add_axes([0.56, 0.265, 0.40, 0.215])
    pr = k["priority"].head(15).sort_values("priority_score")
    ax.barh(pr["country"], pr["priority_score"], color=ORANGE, height=0.65)
    ax.set_title("Priority score — top 15 (0–100)", fontsize=12, fontweight="bold", color=NAVY, loc="left")
    ax.set_xlim(0, 100)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color="#E7E6E6", linewidth=0.8)
    for y, v in zip(pr["country"], pr["priority_score"]):
        ax.text(v + 1, y, f"{v:.0f}", va="center", fontsize=8, color="#404040")
    ax.tick_params(labelsize=7.8)

    # Findings
    fig.patches.append(FancyBboxPatch((0.035, 0.025), 0.93, 0.19, boxstyle="round,pad=0.004,rounding_size=0.008",
                                      transform=fig.transFigure, facecolor="#FAFAFA",
                                      edgecolor="#D9D9D9", linewidth=0.8))
    fig.text(0.05, 0.196, "WHAT THE DASHBOARD SAYS", fontsize=10.5, fontweight="bold", color=NAVY)
    findings = [
        f"China, the US and India produce {k['top3_share']:.1f}% of global CO2; the top ten produce {k['top10_share']:.1f}%.",
        f"The 23 growth engines produce {k['growth_engine_share']:.1f}% of global CO2 and added {k['growth_engine_growth']:,.0f} Mt since 2013; the 18 managed decliners cut {abs(k['decline_growth']):,.0f} Mt.",
        "Coal dominates the priority countries: 71% of China's CO2, 67% of India's, 82% of South Africa's and 58% of Vietnam's.",
        "Per-capita emissions run from 0.1 t in the poorest countries to 32.8 t in Qatar; the global median is 3.2 t per person.",
        "A 20% cut in the growth engines' 2013–2023 trajectory would avoid about 950 Mt CO2 per year by 2033.",
    ]
    for i, text in enumerate(findings):
        fig.text(0.055, 0.168 - i * 0.028, "•  " + text, fontsize=9.0, color="#404040", va="top")

    IMG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(IMG, dpi=100, facecolor="white")
    plt.close(fig)
    print(f"Wrote {IMG}")


if __name__ == "__main__":
    snap, c = load_snapshot()
    k = save_tables(snap, c)
    html = build_html(snap, c, k)
    out = HERE / "dashboard.html"
    out.write_text(html, encoding="utf-8")
    print(f"Wrote {out} ({out.stat().st_size/1e6:.2f} MB)")
    build_png(snap, k)
    print("\nKey metrics")
    for key in ["global_co2", "top3_share", "top10_share", "top10_cum_emitters_share", "top10_current_cum_share",
                "growth_engine_share", "growth_engine_growth", "decline_growth",
                "countries_100mt", "n_countries", "median_pc"]:
        print(f"  {key}: {k[key]:,.2f}" if isinstance(k[key], (int, float, np.floating)) else f"  {key}: {k[key]}")
