import requests
import pandas as pd

from bs4 import BeautifulSoup


class SRTIPScraper:

    URL = (
        "https://www.srtipacc.ae/"
        "business-activities-to-register-in-srtip-free-zone/"
    )

    def scrape(self):

        print("\n[SRTIP] Scraping activities...")

        response = requests.get(
            self.URL,
            timeout=30,
            headers={
                "User-Agent":
                    "Mozilla/5.0"
            }
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        activities = []

        # ==========================================
        # Find all list items
        # ==========================================
        for li in soup.find_all("li"):

            text = li.get_text(
                " ",
                strip=True
            )

            if not text:
                continue

            if len(text) < 3:
                continue

            activities.append({

                "activity name":
                    text,

                "description":
                    ""
            })

        df = pd.DataFrame(
            activities
        )

        if df.empty:

            print(
                "[SRTIP] No activities found."
            )

            return df

        df.drop_duplicates(
            subset=["activity name"],
            inplace=True
        )

        df.reset_index(
            drop=True,
            inplace=True
        )

        print(
            f"[SRTIP] Found "
            f"{len(df)} activities"
        )

        return df