import os
import re
import time
import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from scraper.services.logger import safe_print

print = safe_print


class RAKEZScraper:
    URL = "https://rakez.com/en/start-a-business/license-activity-list"

    def _normalize_text(self, text):
        text = str(text or "")
        text = text.replace("\xa0", " ")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _normalize_zone(self, text):
        return self._normalize_text(text).lower()

    def scrape(self):
        print("\n[RAKEZ] Starting scraper...")

        all_rows = []

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
            page.set_default_timeout(120000)
            page.set_default_navigation_timeout(120000)

            print(f"[RAKEZ] Opening: {self.URL}")
            page.goto(self.URL, wait_until="domcontentloaded", timeout=120000)
            page.wait_for_timeout(5000)

            # =========================================================
            # 1) TRY TO SELECT FREE ZONE FROM DROPDOWN
            # =========================================================
            print("[RAKEZ] Looking for zone dropdown...")
            zone_selected = False

            possible_selectors = [
                "select",
                "select[name*='zone' i]",
                "select[id*='zone' i]",
                "select.form-select",
            ]

            for css in possible_selectors:
                try:
                    selects = page.locator(css)
                    count = selects.count()

                    for i in range(count):
                        sel = selects.nth(i)

                        try:
                            options = sel.locator("option")
                            opt_count = options.count()
                            if opt_count == 0:
                                continue

                            option_texts = []

                            for j in range(opt_count):
                                raw_text = options.nth(j).inner_text().strip()
                                option_texts.append(raw_text)

                                zone_txt = self._normalize_zone(raw_text)
                                print(
                                    f"[RAKEZ] Checking zone option: raw='{raw_text}' normalized='{zone_txt}'"
                                )

                                if zone_txt in {"freezone", "free zone"}:
                                    free_zone_value = options.nth(j).get_attribute("value")
                                    if free_zone_value is None:
                                        free_zone_value = raw_text

                                    print(f"[RAKEZ] Selecting Free Zone using value/text: {raw_text}")
                                    try:
                                        sel.select_option(value=free_zone_value)
                                    except Exception:
                                        sel.select_option(label=raw_text)

                                    page.wait_for_timeout(5000)
                                    zone_selected = True
                                    break

                            print(f"[RAKEZ] Dropdown options found: {option_texts[:15]}")

                            if zone_selected:
                                break

                        except Exception:
                            continue

                    if zone_selected:
                        break

                except Exception:
                    continue

            if not zone_selected:
                raise Exception("RAKEZ Freezone option not found in dropdown.")

            # =========================================================
            # 2) WAIT + SCROLL TO LOAD TABLE
            # =========================================================
            print("[RAKEZ] Waiting for activity data...")
            page.wait_for_timeout(4000)

            last_height = 0
            for _ in range(12):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1500)
                new_height = page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            # =========================================================
            # 3) EXTRACT TABLE DATA
            # =========================================================
            tables = soup.find_all("table")
            print(f"[RAKEZ] Tables found in HTML: {len(tables)}")

            rows_data = []

            for table in tables:
                rows = table.find_all("tr")

                for row in rows:
                    cells = row.find_all(["td", "th"])
                    cell_texts = [self._normalize_text(c.get_text(" ", strip=True)) for c in cells]

                    # skip empty rows
                    cell_texts = [x for x in cell_texts if x]
                    if not cell_texts:
                        continue

                    # skip header rows
                    joined = " | ".join(cell_texts).lower()
                    if "activity name" in joined and "activity code" in joined:
                        continue

                    if len(cell_texts) >= 2:
                        rows_data.append(cell_texts)

            # =========================================================
            # 4) FALLBACK IF TABLE PARSING FAILS
            # =========================================================
            if not rows_data:
                print("[RAKEZ] No rows extracted from tables. Trying fallback text parsing...")
                blocks = soup.find_all(["div", "li", "p"])
                for b in blocks:
                    txt = self._normalize_text(b.get_text(" ", strip=True))
                    if not txt:
                        continue

                    low = txt.lower()
                    if any(k in low for k in [
                        "trading", "services", "manufacturing",
                        "consultancy", "repair", "activity"
                    ]):
                        rows_data.append([txt])

            print(f"[RAKEZ] Raw extracted rows: {len(rows_data)}")

            context.close()
            browser.close()

        # =========================================================
        # 5) CLEAN INTO DATAFRAME
        # =========================================================
        cleaned = []

        for row in rows_data:
            row = [self._normalize_text(x) for x in row if self._normalize_text(x)]
            if not row:
                continue

            record = {
                "Activity Code": row[0] if len(row) > 0 else "",
                "Activity Name": row[1] if len(row) > 1 else row[0],
                "Group": row[2] if len(row) > 2 else "",
                "Category": row[3] if len(row) > 3 else "",
            }

            name = str(record["Activity Name"]).strip().lower()
            if not name:
                continue
            if name in {"activity name", "activities", "name"}:
                continue

            cleaned.append(record)

        df = pd.DataFrame(cleaned)

        if df.empty:
            raise Exception("RAKEZ scraper returned no rows after parsing.")

        if "Activity Name" in df.columns:
            df["Activity Name"] = df["Activity Name"].astype(str).str.strip()
            df = df[df["Activity Name"] != ""]
            df.drop_duplicates(subset=["Activity Name"], inplace=True)

        df.reset_index(drop=True, inplace=True)

        print(f"[RAKEZ] Final unique activities: {len(df)}")

        # optional save
        output_dir = "exports"
        os.makedirs(output_dir, exist_ok=True)
        csv_path = os.path.join(output_dir, "rakez_activities.csv")
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"[RAKEZ] CSV saved at: {csv_path}")

        return df