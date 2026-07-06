import time
import re
import pandas as pd
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

from scraper.services.logger import safe_print

print = safe_print


class RAKEZScraper:
    URL = "https://rakez.com/en/start-a-business/license-activity-list"

    def _normalize_zone(self, text):
        text = str(text or "")
        text = text.replace("\xa0", " ")
        text = re.sub(r"\s+", " ", text)
        return text.strip().lower()

    def scrape(self):
        print("\n[RAKEZ] Starting scraper...")

        options = Options()

        # IMPORTANT FOR AWS / UBUNTU / EC2
        options.binary_location = "/snap/bin/chromium"

        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-infobars")
        options.add_argument("--remote-debugging-port=9222")

        # Use Selenium Manager / system chromedriver
        driver = webdriver.Chrome(options=options)

        try:
            wait = WebDriverWait(driver, 40)

            print(f"[RAKEZ] Opening: {self.URL}")
            driver.get(self.URL)
            time.sleep(5)

            # =========================
            # STEP 1: SELECT FREE ZONE
            # =========================
            print("[RAKEZ] Looking for zone dropdown...")

            zone_selected = False

            # Try multiple selectors because site structure can change
            zone_selectors = [
                "select",
                "select[name*='zone' i]",
                "select[id*='zone' i]",
                "select.form-select",
            ]

            for css in zone_selectors:
                try:
                    elems = driver.find_elements(By.CSS_SELECTOR, css)
                    for elem in elems:
                        try:
                            select = Select(elem)
                            options_text = [o.text.strip() for o in select.options]
                            print(f"[RAKEZ] Dropdown options found: {options_text[:10]}")

                            for idx, opt in enumerate(select.options):
                                zone_text = self._normalize_zone(opt.text)
                                if "free zone" in zone_text:
                                    print(f"[RAKEZ] Selecting zone option: {opt.text}")
                                    select.select_by_index(idx)
                                    zone_selected = True
                                    time.sleep(4)
                                    break

                            if zone_selected:
                                break
                        except Exception:
                            continue
                    if zone_selected:
                        break
                except Exception:
                    continue

            if not zone_selected:
                print("[RAKEZ] Could not find/select Free Zone in dropdown.")
                print("[RAKEZ] Continuing anyway to inspect page data...")

            # =========================
            # STEP 2: LOAD TABLE / ROWS
            # =========================
            print("[RAKEZ] Waiting for activity data to appear...")

            # Wait for any table-ish content
            possible_table_selectors = [
                "table",
                "tbody tr",
                ".table tbody tr",
                ".table-responsive table tbody tr",
            ]

            table_found = False
            for sel in possible_table_selectors:
                try:
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
                    print(f"[RAKEZ] Found table using selector: {sel}")
                    table_found = True
                    break
                except Exception:
                    continue

            if not table_found:
                print("[RAKEZ] No standard table found. Dumping page source for parsing anyway...")

            time.sleep(3)

            # Sometimes rows lazy-load, so scroll
            last_height = driver.execute_script("return document.body.scrollHeight")
            for i in range(10):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height

            # =========================
            # STEP 3: PARSE PAGE HTML
            # =========================
            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")

            rows_data = []

            # Try to parse normal HTML tables first
            tables = soup.find_all("table")
            print(f"[RAKEZ] Tables found in HTML: {len(tables)}")

            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all(["td", "th"])
                    cell_texts = [c.get_text(" ", strip=True) for c in cells]

                    # We expect activity rows to have at least a few columns
                    if len(cell_texts) >= 2:
                        joined = " | ".join(cell_texts).strip()
                        if joined and "activity" not in joined.lower():
                            rows_data.append(cell_texts)

            # Fallback: sometimes page content is in divs instead of table
            if not rows_data:
                print("[RAKEZ] No rows extracted from tables. Trying fallback div parsing...")
                blocks = soup.find_all(["div", "li", "p"])
                for b in blocks:
                    txt = b.get_text(" ", strip=True)
                    if txt and len(txt) > 20:
                        # Very loose fallback — only keep lines that look like business activities
                        if any(word in txt.lower() for word in ["trading", "services", "manufacturing", "consultancy", "repair"]):
                            rows_data.append([txt])

            print(f"[RAKEZ] Raw extracted rows: {len(rows_data)}")

            # =========================
            # STEP 4: BUILD DATAFRAME
            # =========================
            cleaned = []

            for row in rows_data:
                row = [str(x).strip() for x in row if str(x).strip()]
                if not row:
                    continue

                # Flexible mapping because site columns may vary
                record = {
                    "Activity Code": row[0] if len(row) > 0 else "",
                    "Activity Name": row[1] if len(row) > 1 else row[0],
                    "Group": row[2] if len(row) > 2 else "",
                    "Category": row[3] if len(row) > 3 else "",
                }

                # Skip obvious junk/header rows
                name = str(record["Activity Name"]).strip().lower()
                if not name:
                    continue
                if name in {"activity name", "activities", "name"}:
                    continue

                cleaned.append(record)

            df = pd.DataFrame(cleaned)

            if df.empty:
                raise Exception("RAKEZ scraper returned no rows after parsing.")

            # Clean duplicates
            if "Activity Name" in df.columns:
                df["Activity Name"] = df["Activity Name"].astype(str).str.strip()
                df = df[df["Activity Name"] != ""]
                df.drop_duplicates(subset=["Activity Name"], inplace=True)

            df.reset_index(drop=True, inplace=True)

            print(f"[RAKEZ] Final unique activities: {len(df)}")
            return df

        finally:
            driver.quit()