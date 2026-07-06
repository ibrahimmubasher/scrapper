import os
import time
import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from scraper.services.logger import safe_print

print = safe_print


def scrape_SHAMS_activities():
    url = "https://shamsfz.ae/business-setup/business-activities/"
    data = []

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

        print("\nOpening Shams Free Zone website...")
        print(f"URL: {url}")

        page.goto(url, wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(5000)

        # =========================================================
        # STEP 1: WAIT FOR THE ZOHO IFRAME ELEMENT TO APPEAR
        # =========================================================
        print("[DEBUG] Looking for Zoho iframe element in page DOM...")

        iframe_locator = None
        iframe_selectors = [
            "iframe[src*='zohopublic']",
            "iframe[src*='zoho']",
            "iframe[src*='creatorapp']",
            "iframe",
        ]

        for selector in iframe_selectors:
            try:
                page.wait_for_selector(selector, timeout=15000)
                count = page.locator(selector).count()
                print(f"[DEBUG] Selector matched: {selector} | count={count}")
                if count > 0:
                    iframe_locator = page.locator(selector).first
                    break
            except Exception:
                continue

        if iframe_locator is None:
            # dump all iframes for debugging
            frames_info = page.locator("iframe").evaluate_all(
                """
                els => els.map(el => ({
                    src: el.getAttribute('src'),
                    id: el.getAttribute('id'),
                    cls: el.getAttribute('class')
                }))
                """
            ) if page.locator("iframe").count() > 0 else []

            print("[ERROR] No iframe found on page.")
            print(f"[ERROR] iframe info: {frames_info}")
            raise Exception("Zoho iframe not found in DOM.")

        # Print iframe src for confirmation
        try:
            iframe_src = iframe_locator.get_attribute("src")
            print(f"[DEBUG] iframe src found: {iframe_src}")
        except Exception:
            iframe_src = None
            print("[DEBUG] iframe found but src could not be read")

        # =========================================================
        # STEP 2: GET FRAME OBJECT FROM IFRAME ELEMENT
        # =========================================================
        print("[DEBUG] Waiting for iframe content frame...")

        zoho_frame = None
        for attempt in range(30):
            try:
                zoho_frame = iframe_locator.content_frame()
                if zoho_frame is not None:
                    print(f"[DEBUG] Zoho frame attached on attempt {attempt + 1}")
                    break
            except Exception:
                pass

            page.wait_for_timeout(1000)

        if zoho_frame is None:
            print("[ERROR] iframe exists but content_frame() never attached.")
            raise Exception("Zoho frame found in DOM but could not attach to content frame.")

        # =========================================================
        # STEP 3: WAIT FOR TABLE / HANDSONTABLE TO LOAD
        # =========================================================
        print("[DEBUG] Waiting for Zoho content to load...")

        loaded = False
        for attempt in range(60):
            try:
                row_count = zoho_frame.evaluate(
                    """
                    () => {
                        try {
                            if (window.htInstance) {
                                return window.htInstance.getData().length;
                            }
                            return 0;
                        } catch (e) {
                            return 0;
                        }
                    }
                    """
                )

                if row_count > 0:
                    print(f"[DEBUG] htInstance detected with {row_count} rows")
                    loaded = True
                    break

                # Sometimes table HTML appears before htInstance
                table_exists = zoho_frame.locator("table").count()
                print(f"[DEBUG] Attempt {attempt+1}/60 | rows={row_count} | tables={table_exists}")

            except Exception as exc:
                print(f"[DEBUG] Waiting for Zoho content... attempt {attempt+1} | {exc}")

            page.wait_for_timeout(1000)

        if not loaded:
            # Dump a small portion of HTML for debugging
            try:
                html = zoho_frame.content()
                print("[ERROR] Zoho frame loaded but htInstance not available.")
                print(html[:3000])
            except Exception:
                pass
            raise Exception("Zoho table did not load / htInstance not found.")

        # =========================================================
        # STEP 4: SCROLL TO LOAD ALL ROWS
        # =========================================================
        print("[DEBUG] Loading all rows from Zoho table...")

        previous_count = 0
        stable_rounds = 0

        for i in range(60):
            try:
                zoho_frame.evaluate(
                    """
                    () => {
                        const holder = document.querySelector('.wtHolder');
                        if (holder) {
                            holder.scrollTop = holder.scrollHeight;
                        }
                    }
                    """
                )
            except Exception:
                pass

            page.wait_for_timeout(1000)

            try:
                current_count = zoho_frame.evaluate(
                    """
                    () => {
                        try {
                            return window.htInstance ? window.htInstance.getData().length : 0;
                        } catch (e) {
                            return 0;
                        }
                    }
                    """
                )
            except Exception:
                current_count = 0

            print(f"[DEBUG] Scroll {i+1}/60 | rows={current_count}")

            if current_count == previous_count and current_count > 0:
                stable_rounds += 1
            else:
                stable_rounds = 0

            previous_count = current_count

            if stable_rounds >= 4:
                print("[DEBUG] Row count stabilized.")
                break

        # =========================================================
        # STEP 5: EXTRACT RAW ROWS FROM HANDSONTABLE
        # =========================================================
        print("[DEBUG] Extracting rows from htInstance...")

        raw_rows = zoho_frame.evaluate(
            """
            () => {
                try {
                    if (!window.htInstance) {
                        return [];
                    }

                    const rows = window.htInstance.getData();

                    return rows.map(row =>
                        row.map(cell => {
                            if (cell === null || cell === undefined) return '';
                            if (typeof cell === 'object') return JSON.stringify(cell);
                            return String(cell);
                        })
                    );
                } catch (e) {
                    return [{ error: e.toString() }];
                }
            }
            """
        )

        print(f"[DEBUG] Raw rows extracted: {len(raw_rows)}")
        for idx, row in enumerate(raw_rows[:3]):
            print(f"[DEBUG] Sample row {idx + 1}: {row}")

        context.close()
        browser.close()

    # =========================================================
    # STEP 6: CLEAN DATA
    # =========================================================
    def clean(val):
        return BeautifulSoup(str(val), "html.parser").get_text(strip=True)

    for row in raw_rows:
        if isinstance(row, dict) and row.get("error"):
            raise Exception("JavaScript extraction error: " + row["error"])

        if not isinstance(row, list):
            continue

        # Expected columns:
        # [0] blank / checkbox
        # [1] record object
        # [2] Code
        # [3] Category
        # [4] Group
        # [5] Activity Name
        # [6] Arabic Name
        # [7] Third Party
        # [8] When
        # [9] Notes

        if len(row) < 6:
            continue

        code = clean(row[2]) if len(row) > 2 else ""
        category = clean(row[3]) if len(row) > 3 else ""
        group = clean(row[4]) if len(row) > 4 else ""
        activity_name = clean(row[5]) if len(row) > 5 else ""
        arabic_name = clean(row[6]) if len(row) > 6 else ""
        third_party = clean(row[7]) if len(row) > 7 else ""
        when = clean(row[8]) if len(row) > 8 else ""
        notes = clean(row[9]) if len(row) > 9 else ""

        if not activity_name:
            continue

        lower_name = activity_name.strip().lower()
        if lower_name in {"activity name", "none", "nan", "&nbsp;"}:
            continue

        data.append(
            {
                "Code": code,
                "Category": category,
                "Group": group,
                "Activity Name": activity_name,
                "Arabic Name": arabic_name,
                "Third Party": third_party,
                "When": when,
                "Notes": notes,
            }
        )

    if not data:
        raise Exception("No data scraped from SHAMS.")

    df = pd.DataFrame(data)

    df.drop_duplicates(subset=["Activity Name"], inplace=True)
    df.reset_index(drop=True, inplace=True)

    print(f"Total unique activities: {len(df)}")

    return df