import pandas as pd
from playwright.sync_api import sync_playwright


class SRTIPScraper:

    URL = "https://www.srtipacc.ae/business-activities/"

    def scrape(self):

        print("\n[SRTIP] Scraping activities...")

        activities = []

        with sync_playwright() as p:

            browser = p.chromium.launch(
                headless=True,
                executable_path="/snap/bin/chromium",
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-setuid-sandbox",
                ],
            )
            context = browser.new_context(
                viewport={"width": 1400, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()

            page.goto(
                self.URL,
                timeout=60000,
                wait_until="networkidle"
            )

            selector_candidates = [
                "#activitiesBody tr.activity-row",
                "#activitiesBody tr",
                "table tr.activity-row",
                "table tbody tr"
            ]

            rows = []
            for selector in selector_candidates:
                try:
                    page.wait_for_selector(selector, timeout=10000)
                    rows = page.query_selector_all(selector)
                    if rows:
                        print(f"[SRTIP] Using selector: {selector}")
                        break
                except Exception:
                    continue

            if not rows:
                raise Exception("No activity rows found on SRTIP page")

            page.evaluate(
                "() => window.scrollTo(0, document.body.scrollHeight)"
            )

            page.wait_for_timeout(2000)

            print(f"[SRTIP] Found {len(rows)} rows in table")

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

            context.close()
            browser.close()

        df = pd.DataFrame(activities)

        if df.empty:
            print("[SRTIP] No activities found.")
            return df

        df.drop_duplicates(subset=["activity name"], inplace=True)
        df.reset_index(drop=True, inplace=True)

        print(f"[SRTIP] Scraped {len(df)} unique activities")

        return df