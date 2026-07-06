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
from webdriver_manager.chrome import ChromeDriverManager


class RAKEZScraper:

    URL = "https://rakez.com/en/start-a-business/license-activity-list"

    # ============================================
    # NORMALIZE ZONE TEXT FOR MATCHING
    # ============================================
    def _normalize_zone(self, text):
        text = str(text)
        text = text.replace("\xa0", " ")
        text = re.sub(r"[\s\-_]+", "", text)
        return text.strip().lower()

    def scrape(self):

        print("\n[RAKEZ] Starting scraper...")

        options = Options()

        # Use AWS Chromium binary
        options.binary_location = "/usr/bin/chromium-browser"

        # Linux / headless safe flags
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--remote-debugging-port=9222")

        # Optional but helps some sites behave like normal Chrome
        options.add_argument(
            "user-agent=Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        )

        # IMPORTANT FIX: explicitly use webdriver-manager
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        driver.set_page_load_timeout(60)
        wait = WebDriverWait(driver, 30)

        activities = []
        all_zones_seen = set()

        try:
            print(self.URL)

            MAX_RETRIES = 5

            for attempt in range(MAX_RETRIES):
                try:
                    print(f"[RAKEZ] Opening URL (Attempt {attempt + 1}/{MAX_RETRIES})")
                    driver.get(self.URL)

                    wait.until(
                        EC.presence_of_element_located(
                            (By.ID, "dnn_ctr3776_BusinessActivity_gvBusinessActivity")
                        )
                    )

                    print("[RAKEZ] Website loaded")
                    break

                except Exception as e:
                    print(f"[RAKEZ] Connection failed: {e}")

                    if attempt == MAX_RETRIES - 1:
                        driver.quit()
                        return pd.DataFrame()

                    time.sleep(10)

            wait.until(
                EC.presence_of_element_located(
                    (By.ID, "dnn_ctr3776_BusinessActivity_gvBusinessActivity")
                )
            )

            # ==========================================
            # SET PAGE SIZE TO 40
            # ==========================================
            try:
                dropdown = wait.until(
                    EC.element_to_be_clickable(
                        (By.ID, "dnn_ctr3776_BusinessActivity_ddlRecordNoTop")
                    )
                )

                driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});",
                    dropdown
                )

                Select(dropdown).select_by_visible_text("40")
                time.sleep(5)

                wait.until(
                    EC.presence_of_element_located(
                        (By.ID, "dnn_ctr3776_BusinessActivity_gvBusinessActivity")
                    )
                )

                print("[RAKEZ] Records set to 40")

            except Exception as e:
                print(f"[RAKEZ] Failed to set records: {e}")

            page = 1
            max_pages = 200
            seen_row_text = set()

            while page <= max_pages:

                print(f"[RAKEZ] Scraping page {page}")
                print(f"[RAKEZ] Current URL: {driver.current_url}")

                soup = BeautifulSoup(driver.page_source, "html.parser")

                table = soup.find(
                    "table",
                    id="dnn_ctr3776_BusinessActivity_gvBusinessActivity"
                )

                if not table:
                    print("[RAKEZ] Table not found.")
                    break

                rows = table.find_all("tr")
                data_rows = [row for row in rows if len(row.find_all("td")) >= 5]

                page_rows = 0
                page_total_rows = len(data_rows)
                page_zones_seen = []

                for row in data_rows:
                    cols = row.find_all("td")

                    try:
                        zone_raw = cols[0].get_text(" ", strip=True)
                        zone_normalized = self._normalize_zone(zone_raw)

                        page_zones_seen.append(zone_raw)
                        all_zones_seen.add(zone_raw)

                        # only keep Free Zone rows
                        if zone_normalized != "freezone":
                            continue

                        activity_code = cols[1].get_text(" ", strip=True)
                        activity_name = cols[2].get_text(" ", strip=True)
                        licence_type = cols[3].get_text(" ", strip=True)
                        activity_group = cols[4].get_text(" ", strip=True)

                        description = ""
                        desc_span = row.find(
                            "span",
                            id=lambda x: x and "activity_description" in x
                        )

                        if desc_span:
                            description = desc_span.get_text(" ", strip=True)

                        activities.append({
                            "activity code": activity_code,
                            "activity name": activity_name,
                            "description": description,
                            "zone": zone_raw,
                            "licence type": licence_type,
                            "activity group": activity_group,
                        })

                        page_rows += 1

                    except Exception as e:
                        print(f"[RAKEZ] Row parse error: {e}")

                print(
                    f"[RAKEZ] Page {page} | total rows: {page_total_rows} | "
                    f"matched 'freezone': {page_rows} | running total: {len(activities)}"
                )

                if page_rows == 0 and page_total_rows > 0:
                    print(
                        f"[RAKEZ DEBUG] Page {page} had {page_total_rows} rows but none matched "
                        f"'freezone'. Zones seen: {set(page_zones_seen)}"
                    )

                # stop if table truly empty
                if page_total_rows == 0:
                    print("[RAKEZ] Table genuinely empty, stopping pagination.")
                    break

                # stop if repeated page
                first_data_row_text = (
                    data_rows[0].get_text(" ", strip=True)
                    if data_rows else ""
                )

                if first_data_row_text in seen_row_text:
                    print("[RAKEZ] Table repeated content, stopping pagination.")
                    break

                seen_row_text.add(first_data_row_text)

                # ======================================
                # NEXT PAGE
                # ======================================
                next_page_success = False
                NEXT_PAGE_RETRIES = 3

                for next_attempt in range(NEXT_PAGE_RETRIES):
                    try:
                        old_table = driver.find_element(
                            By.ID,
                            "dnn_ctr3776_BusinessActivity_gvBusinessActivity"
                        )
                        old_table_html = old_table.get_attribute("innerHTML") or ""

                        next_btn = None

                        for locator in [
                            (By.XPATH, "//a[contains(text(),'>') or contains(text(),'Next') or contains(text(),'next')]"),
                            (By.XPATH, "//button[contains(text(),'Next') or contains(text(),'next')]"),
                            (By.CSS_SELECTOR, "a[aria-label='Next'], button[aria-label='Next'], a.next, button.next"),
                        ]:
                            try:
                                candidate = wait.until(
                                    EC.presence_of_element_located(locator)
                                )

                                aria_disabled = (
                                    candidate.get_attribute("aria-disabled") or ""
                                ).lower()

                                classes = (
                                    candidate.get_attribute("class") or ""
                                ).lower()

                                if aria_disabled == "true" or "disabled" in classes:
                                    continue

                                next_btn = candidate
                                break

                            except Exception:
                                continue

                        if next_btn is None:
                            print("[RAKEZ] No next page button found, stopping pagination.")
                            next_page_success = None
                            break

                        driver.execute_script(
                            "arguments[0].scrollIntoView({block:'center'});",
                            next_btn
                        )
                        time.sleep(1)

                        driver.execute_script("arguments[0].click();", next_btn)

                        wait.until(
                            lambda d: d.find_element(
                                By.ID,
                                "dnn_ctr3776_BusinessActivity_gvBusinessActivity"
                            ).get_attribute("innerHTML") != old_table_html
                        )

                        next_page_success = True
                        break

                    except StaleElementReferenceException:
                        print(
                            f"[RAKEZ] Stale element on next-page click "
                            f"(retry {next_attempt + 1}/{NEXT_PAGE_RETRIES})"
                        )
                        time.sleep(2)

                    except TimeoutException:
                        print(
                            f"[RAKEZ] Next page click did not update table "
                            f"(retry {next_attempt + 1}/{NEXT_PAGE_RETRIES})"
                        )
                        time.sleep(2)

                    except Exception as e:
                        print(f"[RAKEZ] Unexpected error on next-page: {e}")
                        time.sleep(2)

                if next_page_success is None:
                    break

                if not next_page_success:
                    print(
                        f"[RAKEZ] Failed to advance to next page after "
                        f"{NEXT_PAGE_RETRIES} retries, stopping pagination."
                    )
                    break

                page += 1

        finally:
            driver.quit()

        # ==========================================
        # DATAFRAME
        # ==========================================
        df = pd.DataFrame(activities)

        if not df.empty:
            df.drop_duplicates(
                subset=["activity code", "activity name"],
                inplace=True
            )
            df.reset_index(drop=True, inplace=True)

        print(f"[RAKEZ] Finished. {len(df)} activities.")

        if len(df) > 0:
            print(df["zone"].value_counts())

        print(f"[RAKEZ DEBUG] All distinct zone values seen across all pages: {all_zones_seen}")

        return df