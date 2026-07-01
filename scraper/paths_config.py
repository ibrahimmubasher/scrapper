"""Centralized path configuration for local scraper output and data folders."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = str(BASE_DIR / "scraper" / "data")
OUTPUT_DIR = str(BASE_DIR / "scraper" / "output")

for path in (DATA_DIR, OUTPUT_DIR):
    Path(path).mkdir(parents=True, exist_ok=True)

print(f"[PATHS] DATA_DIR   = {DATA_DIR}")
print(f"[PATHS] OUTPUT_DIR = {OUTPUT_DIR}")