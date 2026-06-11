import os
import pandas as pd


class CSVExporter:

    OUTPUT_FOLDER = os.path.join(
        os.getcwd(),
        "scraper",
        "output"
    )

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