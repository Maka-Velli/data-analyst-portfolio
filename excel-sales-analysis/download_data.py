"""
Download the Sample Superstore CSV used by the Excel project.

The source file includes two stray helper tables after row 9,994. The build
script keeps only the real 9,994-row table, so no cleaning is needed here.

Usage:
    python download_data.py
    python download_data.py --out ./data
"""

from pathlib import Path
import argparse
import sys
import urllib.request

REPO = "leonism/sample-superstore"
PATH = "data/superstore.csv"
FILENAME = "Sample-Superstore.csv"


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
                        help="folder to save the CSV (default: ../.rawdata)")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / FILENAME

    if dest.exists() and dest.stat().st_size > 1_000_000:
        print(f"skip    {FILENAME} (already {dest.stat().st_size:,} bytes)")
        return 0

    url = f"https://api.github.com/repos/{REPO}/contents/{PATH}"
    try:
        size = download(url, dest)
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED  {FILENAME}: {exc}", file=sys.stderr)
        return 1
    print(f"saved   {FILENAME} ({size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
