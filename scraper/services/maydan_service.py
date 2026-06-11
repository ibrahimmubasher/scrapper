import io
import time
import requests
import pandas as pd


# ──────────────────────────────────────────────────────
# UPDATE THESE WHEN MEYDAN ROTATES THEIR API KEY
# How to get new key:
#   1. Open https://www.meydanfz.ae/business-activities-list
#   2. F12 → Network tab → filter by "sb.meydanfz.ae"
#   3. Click any request → Headers → copy apikey value
# ──────────────────────────────────────────────────────
MEYDAN_API_KEY = (
    "eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9."
    "eyJyb2xlIjogImFub24iLCAiaXNzIjogInN1cGFiYXNlIiwg"
    "ImlhdCI6IDE3MzU2ODk2MDAsICJleHAiOiAxODkzNDU2MDAwfQ."
    "aBe8_k56hke4Yk8KmoEVrVIh1eGD5m583N3k66j-uww"
)


def scrape_meydan():

    print("\n[MEYDAN] Starting scraper...")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept":        "application/json",
        "Referer":       "https://www.meydanfz.ae/business-activities-list",
        "apikey":        MEYDAN_API_KEY,
        "Authorization": f"Bearer {MEYDAN_API_KEY}",
    }

    BASE_URL = "https://sb.meydanfz.ae/rest/v1/Activity%20List"

    data   = []
    offset = 0
    limit  = 1000

    while True:

        response    = None
        MAX_RETRIES = 5

        for attempt in range(MAX_RETRIES):

            try:

                print(
                    f"[MEYDAN] Fetching offset={offset} "
                    f"(Attempt {attempt + 1}/{MAX_RETRIES})"
                )

                response = requests.get(
                    BASE_URL,
                    params={
                        "select": "*",
                        "order":  "Code.asc",
                        "offset": offset,
                        "limit":  limit,
                    },
                    headers=headers,
                    timeout=30,
                )

                # ──────────────────────────────────────
                # 401 = API key rejected / rotated
                # No point retrying — fail immediately
                # with a clear message
                # ──────────────────────────────────────
                if response.status_code == 401:
                    raise PermissionError(
                        "Meydan API key rejected (401).\n"
                        "The key has been rotated.\n"
                        "To get the new key:\n"
                        "  1. Open https://www.meydanfz.ae/business-activities-list\n"
                        "  2. F12 → Network tab → filter by 'sb.meydanfz.ae'\n"
                        "  3. Click any request → Headers → copy apikey\n"
                        "  4. Update MEYDAN_API_KEY in maydan_service.py"
                    )

                if response.status_code != 200:
                    raise Exception(
                        f"API error {response.status_code}: "
                        f"{response.text[:300]}"
                    )

                print("[MEYDAN] Request successful")
                break

            except PermissionError:
                # Re-raise immediately — retrying won't help
                raise

            except Exception as e:

                print(f"[MEYDAN] Request failed: {e}")

                if attempt == MAX_RETRIES - 1:
                    print("[MEYDAN] Maximum retries reached.")
                    raise

                wait_time = min(2 ** attempt, 30)

                print(
                    f"[MEYDAN] Retrying in "
                    f"{wait_time} seconds..."
                )

                time.sleep(wait_time)

        if response is None:
            break

        items = response.json()

        if not items:
            print("[MEYDAN] No more records.")
            break

        for item in items:

            data.append({
                "Activity Code": item.get("Code", ""),
                "Activity Name": item.get("Activity Name", ""),
                "Category":      item.get("Category", ""),
                "Group":         item.get("Group", ""),
                "ThirdParty":    item.get("ThirdParty", ""),
            })

        print(f"[MEYDAN] Total scraped: {len(data)}")

        if len(items) < limit:
            break

        offset += limit

    if not data:
        raise Exception("No data found.")

    df = pd.DataFrame(
        data,
        columns=[
            "Activity Code",
            "Activity Name",
            "Category",
            "Group",
            "ThirdParty",
        ],
    )

    df.drop_duplicates(subset=["Activity Code"], inplace=True)
    df.reset_index(drop=True, inplace=True)

    print(
        f"[MEYDAN] Finished. "
        f"{len(df)} activities scraped."
    )

    return df