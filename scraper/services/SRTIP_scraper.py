import pandas as pd
from playwright.sync_api import sync_playwright


class SRTIPScraper:

    URL = "https://www.srtipacc.ae/business-activities/"

    def scrape(self):

        print("\n[SRTIP] Scraping activities...")

        activities = []

        with sync_playwright() as p:

            browser = p.chromium.launch(headless=True)
            page    = browser.new_page()

            page.goto(
                self.URL,
                timeout=60000,
                wait_until="networkidle"
            )

            page.wait_for_selector(
                "#activitiesBody tr.activity-row",
                timeout=30000
            )

            page.evaluate(
                "() => window.scrollTo(0, document.body.scrollHeight)"
            )

            page.wait_for_timeout(2000)

            rows = page.query_selector_all(
                "#activitiesBody tr.activity-row"
            )

            print(f"[SRTIP] Found {len(rows)} rows in table")

            for row in rows:

                cols = row.query_selector_all("td")

                if len(cols) < 4:
                    continue

                activity_name = cols[3].inner_text().strip()

                if not activity_name:
                    continue

                activities.append({
                    "activity name": activity_name,
                    "description":   ""
                })

            browser.close()

        df = pd.DataFrame(activities)

        if df.empty:
            print("[SRTIP] No activities found.")
            return df

        df.drop_duplicates(subset=["activity name"], inplace=True)
        df.reset_index(drop=True, inplace=True)

        print(f"[SRTIP] Scraped {len(df)} unique activities")

        return df