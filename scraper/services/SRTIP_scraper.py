import requests
import pandas as pd
from bs4 import BeautifulSoup


class SRTIPScraper:

    URL = "https://www.srtipacc.ae/business-activities/"

    def scrape(self):

        print("\n[SRTIP] Scraping activities...")

        response = requests.get(
            self.URL,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        activities = []

        # ==========================================
        # Target the activities table directly
        # ==========================================
        tbody = soup.find("tbody", id="activitiesBody")

        if not tbody:
            print("[SRTIP] Could not find activitiesBody table.")
            return pd.DataFrame()

        for tr in tbody.find_all("tr", class_="activity-row"):

            cols = tr.find_all("td")

            if len(cols) < 4:
                continue

            category      = cols[0].get_text(strip=True)
            group         = cols[1].get_text(strip=True)
            code          = cols[2].get_text(strip=True)
            activity_name = cols[3].get_text(strip=True)

            if not activity_name:
                continue

            activities.append({
                "activity name": activity_name,
                "description":   ""
            })

        df = pd.DataFrame(activities)

        if df.empty:
            print("[SRTIP] No activities found.")
            return df

        df.drop_duplicates(subset=["activity name"], inplace=True)
        df.reset_index(drop=True, inplace=True)

        print(f"[SRTIP] Found {len(df)} activities")

        return df