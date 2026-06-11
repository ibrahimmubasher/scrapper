import requests
import pandas as pd


def scrape_IFZA_activities():

    print("\n" + "=" * 50)
    print("Starting IFZA scraper...")
    print("=" * 50)

    url = "https://one.ifza.com/api/utils/getBusinessActivities"

    headers = {
        "accept": "application/json, text/plain, */*",
        "origin": "https://activities.ifza.com",
        "referer": "https://activities.ifza.com/",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/148.0.0.0 Safari/537.36"
        )
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=120
        )

        print(f"Status Code: {response.status_code}")

        response.raise_for_status()

        data = response.json()

        print(f"Total records received: {len(data)}")

        activities = []

        for item in data:

            activities.append({
                "Activity Name": item.get("businessActivityName"),
                "Activity Code": item.get("businessActivityCode"),
                "Group": item.get("businessActivityGroup"),
                "Category": item.get("businessActivityCategory"),
            })

        df = pd.DataFrame(activities)

        print(f"Total activities scraped: {len(df)}")

        return df

    except Exception as e:

        print(f"IFZA scraper failed: {e}")

        return pd.DataFrame()