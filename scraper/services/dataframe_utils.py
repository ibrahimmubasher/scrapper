import pandas as pd


def filter_by_jurisdiction(df, jurisdiction):
    """
    Returns only activities belonging to one jurisdiction.
    """

    if df.empty:
        return df.copy()

    return df[
        df["jurisdiction"]
        .astype(str)
        .str.strip()
        .str.lower()
        ==
        jurisdiction.strip().lower()
    ].copy()