"""
Build images/sql-results.png — a preview of the eight SQL query results.

Run from anywhere:
    python make_preview.py
"""

from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
IMG = ROOT / "images" / "sql-results.png"
DATA = ROOT / ".rawdata"

NAVY = "#1F3864"
BLUE = "#2E75B6"
LIGHT_BLUE = "#D9E2F3"
GREEN = "#548235"
ORANGE = "#C55A11"
RED = "#C00000"
GREY = "#7F7F7F"

plt.rcParams["text.parse_math"] = False
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.edgecolor": "#D9D9D9",
    "axes.labelcolor": "#404040",
    "text.color": "#262626",
    "xtick.color": "#595959",
    "ytick.color": "#595959",
})


def load():
    o = pd.read_csv(DATA / "olist_orders_dataset.csv",
                    parse_dates=["order_purchase_timestamp", "order_delivered_customer_date",
                                 "order_estimated_delivery_date"])
    oi = pd.read_csv(DATA / "olist_order_items_dataset.csv")
    p = pd.read_csv(DATA / "olist_order_payments_dataset.csv")
    c = pd.read_csv(DATA / "olist_customers_dataset.csv")
    s = pd.read_csv(DATA / "olist_sellers_dataset.csv")
    pr = pd.read_csv(DATA / "olist_products_dataset.csv")
    return o, oi, p, c, s, pr


def main():
    o, oi, p, c, s, pr = load()
    d = o[o.order_status == "delivered"]
    delivered = d[["order_id", "order_purchase_timestamp", "order_delivered_customer_date",
                   "order_estimated_delivery_date", "customer_id"]]
    items = oi.merge(delivered, on="order_id")
    revenue = items.price.sum()

    # KPI numbers
    kpi = {
        "orders": d.order_id.nunique(),
        "revenue": revenue,
        "avg_days": (d.order_delivered_customer_date - d.order_purchase_timestamp).dt.total_seconds().div(86400).mean(),
    }
    oc = d.merge(c[["customer_id", "customer_unique_id"]], on="customer_id").groupby("customer_unique_id").size()
    kpi["one_time"] = (oc == 1).mean()

    # Monthly revenue (Jan 2017 - Aug 2018)
    m = items.copy()
    m["ym"] = m.order_purchase_timestamp.dt.to_period("M")
    monthly = m.groupby("ym").price.sum().loc["2017-01":"2018-08"]

    # Top categories
    cat = items.merge(pr[["product_id", "product_category_name"]], on="product_id")
    cats = cat.groupby("product_category_name").price.sum().nlargest(10).sort_values()

    # Delivery by state
    dd = d.dropna(subset=["order_delivered_customer_date"]).copy()
    dd["days"] = (dd.order_delivered_customer_date - dd.order_purchase_timestamp).dt.total_seconds() / 86400
    dd["late"] = dd.order_delivered_customer_date > dd.order_estimated_delivery_date
    st = dd.merge(c[["customer_id", "customer_state"]], on="customer_id").groupby("customer_state").agg(
        days=("days", "mean"), late=("late", "mean"), n=("days", "size"))
    st = st[st.n >= 100]

    # Payments
    pay = p[p.order_id.isin(d.order_id)].groupby("payment_type").payment_value.sum().sort_values(ascending=False)

    # ------------------------------------------------------------------ figure
    fig = plt.figure(figsize=(16, 10), dpi=100)
    fig.patch.set_facecolor("white")

    fig.patches.append(FancyBboxPatch((0, 0.925), 1, 0.075, boxstyle="square,pad=0",
                                      transform=fig.transFigure, facecolor=NAVY, edgecolor="none"))
    fig.text(0.035, 0.968, "Olist E-Commerce — SQL Query Results", color="white",
             fontsize=25, fontweight="bold", va="center")
    fig.text(0.035, 0.940, "Brazilian marketplace · 8 MySQL questions · Oct 2016 – Aug 2018",
             color="#D9E2F3", fontsize=12, va="center")

    cards = [
        ("DELIVERED ORDERS", f"{kpi['orders']:,}"),
        ("REVENUE", f"R${kpi['revenue']/1e6:.2f}M"),
        ("AVG DELIVERY", f"{kpi['avg_days']:.1f} days"),
        ("ONE-TIME BUYERS", f"{kpi['one_time']:.1%}"),
    ]
    x0, y0, w, h, gap = 0.035, 0.825, 0.2225, 0.078, 0.010
    for i, (label, value) in enumerate(cards):
        x = x0 + i * (w + gap)
        fig.patches.append(FancyBboxPatch((x, y0), w, h, boxstyle="round,pad=0.004,rounding_size=0.008",
                                          transform=fig.transFigure, facecolor=LIGHT_BLUE,
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

    # 1. Monthly revenue
    ax = add_axes([0.06, 0.545, 0.40, 0.20])
    colors = [ORANGE if str(x) == "2017-11" else BLUE for x in monthly.index]
    bars = ax.bar(range(len(monthly)), monthly.values / 1e3, color=colors, width=0.75)
    ax.set_title("Monthly revenue (R$K), Jan 2017 – Aug 2018", fontsize=12,
                 fontweight="bold", color=NAVY, loc="left")
    tick_pos = list(range(0, len(monthly), 3))
    ax.set_xticks(tick_pos)
    ax.set_xticklabels([str(monthly.index[i]) for i in tick_pos], fontsize=8.5, rotation=0)
    ax.yaxis.set_major_formatter(mtick.FormatStrFormatter("%.0f"))
    nov_i = list(monthly.index).index(pd.Period("2017-11"))
    ax.annotate("Black Friday\n+52.4% MoM", xy=(nov_i, monthly.iloc[nov_i] / 1e3),
                xytext=(nov_i - 6.5, monthly.iloc[nov_i] / 1e3 * 0.92),
                fontsize=8.5, color=ORANGE, fontweight="bold",
                arrowprops=dict(arrowstyle="->", color=ORANGE, lw=1.2))
    ax.set_ylim(0, monthly.max() / 1e3 * 1.2)

    # 2. Top categories
    ax = add_axes([0.56, 0.545, 0.40, 0.20])
    bars = ax.barh(range(len(cats)), cats.values / 1e3, color=BLUE, height=0.65)
    ax.set_title("Top 10 product categories by revenue (R$K)", fontsize=12,
                 fontweight="bold", color=NAVY, loc="left")
    ax.set_yticks(range(len(cats)))
    ax.set_yticklabels([x.replace("_", " ").title() for x in cats.index], fontsize=8.5)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color="#E7E6E6", linewidth=0.8)
    for b, v in zip(bars, cats.values / 1e3):
        ax.text(v + 12, b.get_y() + b.get_height() / 2, f"{v:,.0f}", va="center", fontsize=8, color="#404040")
    ax.set_xlim(0, cats.max() / 1e3 * 1.18)
    ax.tick_params(axis="x", labelsize=8)

    # 3. Delivery days vs late share
    ax = add_axes([0.06, 0.275, 0.40, 0.20])
    ax.grid(axis="x", color="#E7E6E6", linewidth=0.8)
    ax.scatter(st.days, st.late * 100, s=st.n / 40, color=BLUE, alpha=0.55,
               edgecolor=NAVY, linewidth=0.6, zorder=3)
    ax.set_title("Delivery time vs late share by state (bubble = order volume)", fontsize=12,
                 fontweight="bold", color=NAVY, loc="left")
    ax.set_xlabel("Average delivery days", fontsize=9)
    ax.set_ylabel("Orders late (%)", fontsize=9)
    ax.yaxis.set_major_formatter(mtick.FormatStrFormatter("%.0f%%"))
    for state in ["SP", "AL", "AM", "BA", "RJ", "CE", "MA", "RS"]:
        if state in st.index:
            ax.annotate(state, (st.loc[state, "days"], st.loc[state, "late"] * 100),
                        fontsize=8, color=NAVY, xytext=(4, 4), textcoords="offset points")
    ax.tick_params(labelsize=8.5)

    # 4. Payment mix donut
    ax = fig.add_axes([0.60, 0.255, 0.32, 0.24])
    labels = [x.replace("_", " ").title() for x in pay.index]
    colors_pie = [BLUE, ORANGE, GREEN, "#A5A5A5"]
    wedges, _ = ax.pie(pay.values, colors=colors_pie, startangle=90,
                       counterclock=False, wedgeprops=dict(width=0.42, edgecolor="white", linewidth=2))
    ax.text(0, 0.08, "78.5%", ha="center", va="center", fontsize=20, fontweight="bold", color=NAVY)
    ax.text(0, -0.16, "credit card", ha="center", va="center", fontsize=9, color="#595959")
    ax.set_title("Payment value mix", fontsize=12, fontweight="bold", color=NAVY, loc="center", pad=2)
    legend_labels = [f"{l}  {v/pay.sum()*100:.1f}%" for l, v in zip(labels, pay.values)]
    ax.legend(wedges, legend_labels, loc="center left", bbox_to_anchor=(1.0, 0.5),
              frameon=False, fontsize=8.5)

    # Footer
    fig.patches.append(FancyBboxPatch((0.035, 0.025), 0.93, 0.13, boxstyle="round,pad=0.004,rounding_size=0.008",
                                      transform=fig.transFigure, facecolor="#FAFAFA",
                                      edgecolor="#D9D9D9", linewidth=0.8))
    fig.text(0.05, 0.138, "SELECTED FINDINGS", fontsize=10.5, fontweight="bold", color=NAVY)
    findings = [
        "Revenue jumped 52.4% in November 2017 and fell 26.5% in December: Black Friday alone had 1,147 orders against a 243/day monthly average.",
        "Same-state shipping is twice as fast (7.9 vs 15.0 days), late less often (6.0% vs 9.0%) and cheaper (13.0% vs 18.3% of item price) — but only 36.2% of items travel that way.",
        "97.0% of customers order once. Credit cards are 78.5% of payment value; boleto is 18.0%. The top 10 sellers are only 13.3% of revenue, so no seller dominates.",
    ]
    for i, text in enumerate(findings):
        fig.text(0.055, 0.108 - i * 0.028, "•  " + text, fontsize=9.0, color="#404040", va="top")

    IMG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(IMG, dpi=100, facecolor="white")
    plt.close(fig)
    print(f"Wrote {IMG}")


if __name__ == "__main__":
    main()
