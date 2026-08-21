import requests
import pandas as pd


API_URL = "https://freezone.dwtc.workers.dev/"

COLUMN_MAP = {
    "PARENT GROUP CODE": "Parent Group Code",
    "ACTIVITY CODE": "Activity Code",
    "LICENSE TYPE": "License Type",
    "ACTIVITY NAME": "Activity Name",
    "ACTIVITY DESCRIPTION": "Activity Description",
    "ADDITIONAL REQUIREMENTS": "Additional Requirements",
}


def _normalize_cell(value):
    if value is None or value == "No Value":
        return ""
    return value


def scrape_DWTC_activities():

    print("\n" + "=" * 50)
    print("Starting DWTC scraper...")
    print("=" * 50)

    headers = {
        "accept": "application/json, text/plain, */*",
        "referer": "https://www.dwtc.com/",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    try:
        response = requests.get(API_URL, headers=headers, timeout=120)

        print(f"Status Code: {response.status_code}")
        response.raise_for_status()

        data = response.json()
        table = data["items"][0]
        column_names = table["columnNames"]
        rows = table["rows"]

        print(f"Total records received: {table.get('count', len(rows))}")

        activities = []
        for row in rows:
            record = {
                COLUMN_MAP.get(col, col): _normalize_cell(
                    row[i] if i < len(row) else None
                )
                for i, col in enumerate(column_names)
            }
            activities.append(record)

        df = pd.DataFrame(activities)
        print(f"Total activities scraped: {len(df)}")
        return df

    except Exception as e:
        print(f"DWTC scraper failed: {e}")
        return pd.DataFrame()
