import os
import pandas as pd

from scraper.paths_config import OUTPUT_DIR


class CSVExporter:

    # Use the shared output directory from paths_config so
    # CSVs are written and read from the same location.
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