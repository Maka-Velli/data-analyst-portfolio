"""
Verify the MySQL queries in queries.sql and regenerate expected_results.md.

The queries are written for MySQL 8.0. This script transpiles each
statement to DuckDB with sqlglot, runs it against the same six CSV files,
and writes the output to expected_results.md. Numbers produced here are
the ones quoted in the README.

Usage:
    python verify_results.py            # run all queries and write the markdown
    python verify_results.py --no-write # just run and print the results

The CSV files are looked for in ../.rawdata/ (the repository's ignored
raw-data folder) or in ./data/.
"""

from pathlib import Path
import re
import sys

import duckdb
import pandas as pd
import sqlglot

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
QUERIES = HERE / "queries.sql"
OUTPUT = HERE / "expected_results.md"

CANDIDATE_DIRS = [ROOT / ".rawdata", HERE / "data"]

TABLES = {
    "customers": "olist_customers_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
}

DATE_COLUMNS = {
    "orders": [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
    "order_items": ["shipping_limit_date"],
}


def find_data_dir() -> Path:
    for d in CANDIDATE_DIRS:
        if (d / TABLES["orders"]).exists():
            return d
    raise FileNotFoundError(
        "Olist CSV files not found. Put them in ../.rawdata/ or ./data/ "
        "(see download_data.py)."
    )


def load_tables() -> dict[str, pd.DataFrame]:
    data_dir = find_data_dir()
    frames = {}
    for table, filename in TABLES.items():
        df = pd.read_csv(data_dir / filename)
        for col in DATE_COLUMNS.get(table, []):
            df[col] = pd.to_datetime(df[col], errors="coerce")
        frames[table] = df
    return frames


def parse_queries(path: Path) -> list[tuple[str, str, str]]:
    """Return a list of (title, sql, finding) blocks from queries.sql.

    Comments are skipped while collecting SQL, so semicolons inside
    comments cannot split a statement. The finding comment that follows
    a query (if any) is attached to it.
    """
    blocks: list[tuple[str, list[str], list[str]]] = []
    title: str | None = None
    sql_lines: list[str] = []
    finding_lines: list[str] = []

    def flush():
        nonlocal title, sql_lines, finding_lines
        sql = "\n".join(sql_lines).strip()
        if sql and not re.fullmatch(r"USE\s+olist\s*;?", sql, flags=re.IGNORECASE):
            blocks.append((title or "Query", sql, "\n".join(finding_lines).strip()))
        title, sql_lines, finding_lines = None, [], []

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        title_match = re.match(r"--\s*(Q\d+\..*)", stripped)
        if title_match:
            flush()
            title = title_match.group(1).strip()
            continue
        if stripped.startswith("--"):
            if stripped.startswith("-- Finding:"):
                finding_lines.append(stripped)
            continue
        if not stripped:
            continue
        sql_lines.append(line)
        if stripped.endswith(";"):
            flush()
    flush()

    return [(t, sql, f) for t, sql, f in blocks]


def to_duckdb(sql: str) -> str:
    return sqlglot.transpile(sql, read="mysql", write="duckdb", pretty=False)[0]


def format_table(df: pd.DataFrame) -> str:
    """Render a dataframe as a GitHub markdown table, rounded sensibly."""
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_float_dtype(out[col]):
            out[col] = out[col].map(lambda x: "" if pd.isna(x) else f"{x:,.2f}")
        elif pd.api.types.is_integer_dtype(out[col]):
            out[col] = out[col].map(lambda x: "" if pd.isna(x) else f"{x:,}")
        else:
            out[col] = out[col].map(lambda x: "" if pd.isna(x) else str(x))
    header = "| " + " | ".join(out.columns) + " |"
    sep = "|" + "|".join(["---"] * len(out.columns)) + "|"
    rows = ["| " + " | ".join(str(v) for v in row) + " |" for row in out.itertuples(index=False)]
    return "\n".join([header, sep] + rows)


def main(write: bool = True) -> int:
    frames = load_tables()
    con = duckdb.connect()
    for name, df in frames.items():
        con.register(name, df)

    blocks = parse_queries(QUERIES)
    results = []
    for title, sql, finding in blocks:
        duck_sql = to_duckdb(sql)
        try:
            df = con.execute(duck_sql).fetchdf()
        except Exception as exc:  # noqa: BLE001 - report and continue
            print(f"FAILED  {title}\n  {exc}\n  DuckDB SQL:\n{duck_sql}\n")
            return 1
        results.append((title, sql, df, finding))
        print(f"OK      {title}  ({len(df)} rows)")

    # Assertions for the headline numbers used in the README
    q1 = results[0][2]
    assert int(q1.loc[0, "delivered_orders"]) == 96_478, q1
    assert abs(float(q1.loc[0, "revenue"]) - 13_221_498.11) < 1, q1
    q6 = results[5][2].set_index("repeat_bucket")["pct_of_customers"]
    assert abs(float(q6["1 order"]) - 97.0) < 0.1, q6
    q7 = results[6][2]
    assert int(q7.loc[0, "revenue_rank"]) == 1, q7
    print("\nAll headline assertions passed.")

    if write:
        lines = [
            "# Expected query results",
            "",
            "Generated by `verify_results.py`, which runs the MySQL queries in",
            "`queries.sql` through DuckDB (via sqlglot) against the same six",
            "Olist CSV files. All values are Brazilian reais (R$).",
            "",
        ]
        for title, sql, df, finding in results:
            lines.append(f"## {title}")
            lines.append("")
            lines.append("```sql")
            lines.append(sql.strip())
            lines.append("```")
            lines.append("")
            lines.append(format_table(df))
            lines.append("")
            if finding:
                lines.append(finding.replace("-- Finding:", "**Finding:**", 1))
                lines.append("")
        OUTPUT.write_text("\n".join(lines), encoding="utf-8")
        print(f"Wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(write="--no-write" not in sys.argv))
