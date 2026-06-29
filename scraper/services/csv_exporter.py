import os
import pandas as pd

from scraper.paths_config import OUTPUT_DIR


class CSVExporter:

    # ── FIX: use the same persistent volume path as views.py ──
    # Before, this hardcoded os.getcwd()/scraper/output, which
    # is a DIFFERENT location than what views.py reads from
    # (paths_config.OUTPUT_DIR -> /data/output on Railway).
    # CSVs were being saved to one place and looked for in
    # another, so the dashboard never saw them.
    OUTPUT_FOLDER = OUTPUT_DIR

    @classmethod
    def save(cls, dataframe, website):

        os.makedirs(cls.OUTPUT_FOLDER, exist_ok=True)

        filename = f"{website.upper()}.csv"

        file_path = os.path.join(
            cls.OUTPUT_FOLDER,
            filename
        )

        dataframe.to_csv(
            file_path,
            index=False,
            encoding="utf-8-sig"
        )

        print(f"[CSV] Saved -> {file_path}")

        return file_path