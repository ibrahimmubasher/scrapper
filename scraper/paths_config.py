"""
scraper/paths_config.py

Centralized path configuration for persistent vs ephemeral storage.

On Railway, /data is a mounted Volume that survives redeploys/restarts.
Locally (your Windows machine), /data won't exist, so we fall back
to the original project-relative paths automatically.

Import DATA_DIR and OUTPUT_DIR from this file everywhere instead of
hardcoding "scraper/data" or "scraper/output".

ALSO: automatically seeds the volume with the Consolidated Excel file
from the Git repo on first run, since a fresh volume starts empty.
"""

import os
import shutil

# ============================================================
# DETECT IF /data VOLUME EXISTS (Railway) OR NOT (local)
# ============================================================
RAILWAY_VOLUME_PATH = "/data"

if os.path.isdir(RAILWAY_VOLUME_PATH):
    # ── Running on Railway with volume attached ──────────
    BASE_DATA_DIR = RAILWAY_VOLUME_PATH
    ON_RAILWAY_VOLUME = True
else:
    # ── Running locally — use project-relative folder ────
    BASE_DATA_DIR = os.path.join(os.getcwd(), "scraper")
    ON_RAILWAY_VOLUME = False

DATA_DIR   = os.path.join(BASE_DATA_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DATA_DIR, "output")

# Ensure both directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

print(f"[PATHS] DATA_DIR   = {DATA_DIR}")
print(f"[PATHS] OUTPUT_DIR = {OUTPUT_DIR}")

# ============================================================
# SEED THE VOLUME ON FIRST RUN
#
# The volume starts EMPTY. The Excel file lives in the Git
# repo at scraper/data/Consolidated List of Activities.xlsx.
# If the volume doesn't have it yet, copy it over once.
# ============================================================
if ON_RAILWAY_VOLUME:

    SEED_FILENAME = "Consolidated List of Activities.xlsx"

    repo_data_dir    = os.path.join(os.getcwd(), "scraper", "data")
    repo_seed_path   = os.path.join(repo_data_dir, SEED_FILENAME)
    volume_seed_path = os.path.join(DATA_DIR, SEED_FILENAME)

    if not os.path.exists(volume_seed_path):

        if os.path.exists(repo_seed_path):

            print(
                f"[PATHS] Seeding volume with {SEED_FILENAME} "
                f"from repo (first run)..."
            )

            shutil.copy2(repo_seed_path, volume_seed_path)

            print(f"[PATHS] Seeded: {volume_seed_path}")

        else:

            print(
                f"[PATHS] WARNING: {SEED_FILENAME} not found in "
                f"repo at {repo_seed_path}. Volume will start "
                f"without it."
            )

    else:

        print(
            f"[PATHS] {SEED_FILENAME} already exists on volume "
            f"— skipping seed."
        )