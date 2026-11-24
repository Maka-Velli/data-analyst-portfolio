"""
Verify the capstone SQL queries against the OWID CSV with DuckDB.

The queries in capstone_analysis.sql are written for MySQL 8.0. This script
skips the DDL/LOAD DATA section, transpiles each query to DuckDB with sqlglot
and runs it against the same CSV.

Usage:
    python verify_sql.py
"""

from pathlib import Path
import re
import sys

import duckdb
import pandas as pd
import sqlglot

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SQL = HERE / "capstone_analysis.sql"
CSV = ROOT / ".rawdata" / "owid-co2-data.csv"


def parse_queries(text: str) -> list[tuple[str, str]]:
    """Return (title, sql) for the Q1-Q5 blocks, ignoring comments."""
    blocks = []
    title = None
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        match = re.match(r"--\s*(Q\d+\..*)", stripped)
        if match:
            title = match.group(1).strip()
            continue
        if stripped.startswith("--"):
            continue
        if not stripped:
            continue
        lines.append(line)
        if stripped.endswith(";"):
            sql = "\n".join(lines).strip()
            if sql and not re.search(r"\b(CREATE|DROP|LOAD)\b", sql, re.IGNORECASE):
                blocks.append((title or "Query", sql))
            title, lines = None, []
    return blocks


def main() -> int:
    if not CSV.exists():
        print(f"Missing {CSV}. Run download_data.py first.", file=sys.stderr)
        return 1

    df = pd.read_csv(CSV)
    con = duckdb.connect()
    con.register("co2_data", df)

    queries = parse_queries(SQL.read_text(encoding="utf-8"))
    print(f"Found {len(queries)} queries")
    results = {}
    for title, sql in queries:
        duck_sql = sqlglot.transpile(sql, read="mysql", write="duckdb", pretty=False)[0]
        try:
            out = con.execute(duck_sql).fetchdf()
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED  {title}\n{exc}\n{duck_sql}\n")
            return 1
        results[title.split(".")[0]] = out
        print(f"\n=== {title} ===")
        print(out.to_string(index=False))

    # Headline assertions
    q1 = results["Q1"]
    assert abs(float(q1.loc[0, "global_co2_mt"]) - 37_048.5) < 1, q1
    assert abs(float(q1.loc[0, "top3_share_pct"]) - 54.7) < 0.2, q1
    q4 = results["Q4"]
    assert q4.iloc[0]["country"] == "China", q4.head()
    q5 = results["Q5"].set_index("segment")
    assert abs(float(q5.loc["Growth engine", "pct_of_global"]) - 61.8) < 0.2, q5
    print("\nAll capstone SQL assertions passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
