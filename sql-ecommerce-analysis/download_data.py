"""
Download the six Olist CSV files used by this project.

The original dataset is on Kaggle:
    https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

This script pulls a public mirror of the same files from GitHub using the
Contents API (no token needed, 60 requests/hour unauthenticated). Files are
saved to ../.rawdata/ by default so they stay out of git.

Usage:
    python download_data.py
    python download_data.py --out ./data
"""

from pathlib import Path
import argparse
import sys
import urllib.request

REPO = "Anshukun888/olist-ecommerce-analysis"
BRANCH = "main"
FILES = {
    "olist_customers_dataset.csv": "data/raw/olist_customers_dataset.csv",
    "olist_sellers_dataset.csv": "data/raw/olist_sellers_dataset.csv",
    "olist_products_dataset.csv": "data/raw/olist_products_dataset.csv",
    "olist_orders_dataset.csv": "data/raw/olist_orders_dataset.csv",
    "olist_order_items_dataset.csv": "data/raw/olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv": "data/raw/olist_order_payments_dataset.csv",
}


def download(url: str, dest: Path) -> int:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github.raw",
            "User-Agent": "data-analyst-portfolio",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as response:
        data = response.read()
    dest.write_bytes(data)
    return len(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / ".rawdata"),
                        help="folder to save the CSV files (default: ../.rawdata)")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    for name, path in FILES.items():
        dest = out / name
        if dest.exists() and dest.stat().st_size > 1000:
            print(f"skip    {name} (already {dest.stat().st_size:,} bytes)")
            continue
        url = f"https://api.github.com/repos/{REPO}/contents/{path}?ref={BRANCH}"
        try:
            size = download(url, dest)
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED  {name}: {exc}", file=sys.stderr)
            return 1
        print(f"saved   {name} ({size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
