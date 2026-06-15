import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service


class SRTIPScraper:

    URL = "https://www.srtipacc.ae/business-activities/"

    def scrape(self):

        print("\n[SRTIP] Scraping activities...")

        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")

        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )

        activities = []

        try:

            driver.get(self.URL)

            # Wait for table to load
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "#activitiesBody tr.activity-row")
                )
            )

            rows = driver.find_elements(
                By.CSS_SELECTOR,
                "#activitiesBody tr.activity-row"
            )

            print(f"[SRTIP] Found {len(rows)} rows")

            for row in rows:

                cols = row.find_elements(By.TAG_NAME, "td")

                if len(cols) < 4:
                    continue

                activity_name = cols[3].text.strip()

                if not activity_name:
                    continue

                activities.append({
                    "activity name": activity_name,
                    "description":   ""
                })

        finally:
            driver.quit()

        df = pd.DataFrame(activities)

        if df.empty:
            print("[SRTIP] No activities found.")
            return df

        df.drop_duplicates(subset=["activity name"], inplace=True)
        df.reset_index(drop=True, inplace=True)

        print(f"[SRTIP] Scraped {len(df)} unique activities")

        return df