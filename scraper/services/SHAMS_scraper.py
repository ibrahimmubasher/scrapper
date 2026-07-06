import os
import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import requests

from scraper.services.logger import safe_print

print = safe_print


def scrape_SHAMS_activities():
    url = "https://shamsfz.ae/business-setup/business-activities/"
    data = []

    # --- Try API-first approach (faster, avoids browser) ---
    api_base = "https://shamsfz.ae/wp-json/shams-activities/v1/activities"
    print("[SHAMS API] Starting API attempt...")
    print(f"[SHAMS API] Target URL: {api_base}")
    try:
        per_page = 100
        page = 1
        api_items = []
        headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
        }
        print(f"[SHAMS API] Prepared headers: {headers}")

        def extract_list(obj):
            if isinstance(obj, list):
                return obj
            if isinstance(obj, dict):
                # common candidate keys
                for k in ("items", "activities", "data", "results", "rows", "records"):
                    if k in obj and isinstance(obj[k], list):
                        return obj[k]
                # look for the first list-valued entry
                for v in obj.values():
                    if isinstance(v, list):
                        return v
            return []

        while True:
            print(f"[SHAMS API] Fetching page {page}...")
            resp = requests.get(api_base, params={"page": page, "per_page": per_page}, headers=headers, timeout=30)
            print(f"[SHAMS API] Response status: {resp.status_code}")
            if resp.status_code != 200:
                print(f"[SHAMS API] Non-200 status, stopping. Response text: {resp.text[:200]}")
                break
            try:
                parsed = resp.json()
            except Exception as ex:
                print(f"[SHAMS API] JSON parse error: {ex}")
                break

            items = extract_list(parsed)

            # If top-level is a dict mapping numeric keys to items, try to coerce
            if not items and isinstance(parsed, dict):
                numeric_vals = [v for k, v in parsed.items() if k.isdigit() and isinstance(v, dict)]
                if numeric_vals:
                    items = numeric_vals

            if not items:
                break

            api_items.extend(items)

            if len(items) < per_page:
                break

            page += 1

        if api_items:
            print(f"[SHAMS API] Retrieved {len(api_items)} items from API")

            # Helper to pick a field from several candidate keys
            def pick(obj, candidates):
                if not isinstance(obj, dict):
                    return ""
                for k in candidates:
                    if k in obj and obj[k] is not None:
                        return obj[k]
                # check lowercased keys
                for k, v in obj.items():
                    if k.lower() in [c.lower() for c in candidates] and v is not None:
                        return v
                return ""

            for it in api_items:
                # try common key names observed in similar endpoints
                activity_name = pick(it, ["activity_name", "Activity Name", "name", "title", "activity"]) or ""
                code = pick(it, ["activity_code", "code", "Activity Code"]) or ""
                category = pick(it, ["category", "Category"]) or ""
                group = pick(it, ["group", "Group", "subcategory"]) or ""

                # some entries may have nested title objects
                if isinstance(activity_name, dict):
                    activity_name = pick(activity_name, ["rendered", "text"]) or ""

                data.append({
                    "Code": str(code).strip(),
                    "Category": str(category).strip(),
                    "Group": str(group).strip(),
                    "Activity Name": str(activity_name).strip(),
                    "Arabic Name": "",
                    "Third Party": "",
                    "When": "",
                    "Notes": "",
                })

            # Build DataFrame and return early
            df_api = pd.DataFrame(data)
            if not df_api.empty:
                df_api.drop_duplicates(subset=["Activity Name"], inplace=True)
                df_api.reset_index(drop=True, inplace=True)
                return df_api
    except Exception as e:
        import traceback
        print(f"[SHAMS API] API attempt failed with exception: {e}")
        print(f"[SHAMS API] Traceback: {traceback.format_exc()}")
        # fall through to Playwright-based scraping

    

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
            java_script_enabled=True,
        )

        page = context.new_page()
        page.set_default_timeout(120000)
        page.set_default_navigation_timeout(120000)

        print("\nOpening Shams Free Zone website...")
        print(f"URL: {url}")

        page.goto(url, wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(5000)

        # Try to let JS/iframe finish loading
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        # ==========================================
        # FIND ZOHO IFRAME
        # ==========================================
        print("[DEBUG] Checking iframe elements on page...")

        zoho_frame = None

        # Try for up to 60 seconds
        for attempt in range(60):
            print(f"[DEBUG] Attempt {attempt + 1}/60 to find Zoho frame")

            # 1) Print current frames
            frames = page.frames
            print(f"[DEBUG] Current frame count: {len(frames)}")
            for idx, frame in enumerate(frames):
                print(f"[DEBUG]   Frame {idx}: {frame.url}")

            # 2) Try to locate iframe elements in DOM
            iframe_elements = page.locator("iframe")
            iframe_count = iframe_elements.count()
            print(f"[DEBUG] iframe elements found in DOM: {iframe_count}")

            for i in range(iframe_count):
                try:
                    iframe = iframe_elements.nth(i)
                    src = iframe.get_attribute("src")
                    print(f"[DEBUG]   iframe[{i}] src = {src}")

                    if src and "zoho" in src.lower():
                        frame = iframe.content_frame()
                        if frame:
                            zoho_frame = frame
                            print(f"[DEBUG]   FOUND Zoho frame from iframe src: {src}")
                            break
                except Exception as exc:
                    print(f"[DEBUG]   Error reading iframe[{i}]: {exc}")

            if zoho_frame:
                break

            # 3) Fallback: scan Playwright frames directly
            for frame in page.frames:
                frame_url = (frame.url or "").lower()
                if "zoho" in frame_url or "zohopublic" in frame_url:
                    zoho_frame = frame
                    print(f"[DEBUG]   FOUND Zoho frame from page.frames: {frame.url}")
                    break

            if zoho_frame:
                break

            # 4) Fallback: check for htInstance on the top-level page (some sites expose it
            #     without an iframe). If present, use the page as the frame target.
            try:
                has_ht = page.evaluate(
                    "() => { try { return !!(window.htInstance); } catch(e) { return false; } }"
                )
                if has_ht:
                    zoho_frame = page
                    print("[DEBUG]   FOUND htInstance on top-level page (no iframe)")
                    break
            except Exception as exc:
                print(f"[DEBUG]   Error checking top-level htInstance: {exc}")

            page.wait_for_timeout(1000)

        if zoho_frame is None:
            print("[ERROR] Zoho frame not found.")
            print("[ERROR] Dumping iframe HTML for debugging...")

            try:
                html = page.content()
                snippet = html[:10000]
                print(snippet)
            except Exception as exc:
                print(f"[ERROR] Could not dump page HTML: {exc}")

            context.close()
            browser.close()
            raise Exception("Zoho frame not found.")

        print("Zoho frame found.")

        # ==========================================
        # WAIT FOR HANDSONTABLE DATA
        # ==========================================
        print("Loading all rows...")

        count = 0
        for _ in range(30):
            count = zoho_frame.evaluate(
                """
                () => {
                    try {
                        return window.htInstance ? window.htInstance.getData().length : 0;
                    } catch(e) {
                        return 0;
                    }
                }
                """
            )
            print(f"[DEBUG] Initial htInstance row count: {count}")
            if count > 0:
                break
            page.wait_for_timeout(1000)

        if count == 0:
            print("[DEBUG] htInstance still empty, waiting a bit more...")
            page.wait_for_timeout(5000)

        # Scroll to force lazy load
        for i in range(60):
            zoho_frame.evaluate(
                """
                () => {
                    const h = document.querySelector('.wtHolder');
                    if (h) h.scrollTop = h.scrollHeight;
                }
                """
            )
            page.wait_for_timeout(800)

            count = zoho_frame.evaluate(
                """
                () => {
                    try {
                        return window.htInstance ? window.htInstance.getData().length : 0;
                    } catch(e) {
                        return 0;
                    }
                }
                """
            )

            print(f"  scroll {i + 1} | rows: {count}")

            if count >= 900:
                break

        # Final stable check
        prev_count = 0
        stable_streak = 0

        for _ in range(20):
            count = zoho_frame.evaluate(
                """
                () => {
                    try {
                        return window.htInstance ? window.htInstance.getData().length : 0;
                    } catch(e) {
                        return 0;
                    }
                }
                """
            )

            if count == prev_count and count > 0:
                stable_streak += 1
                if stable_streak >= 3:
                    break
            else:
                stable_streak = 0

            prev_count = count
            page.wait_for_timeout(500)

        print("htInstance rows: " + str(count))

        # ==========================================
        # EXTRACT ALL DATA FROM htInstance
        # ==========================================
        raw_rows = zoho_frame.evaluate(
            """
            () => {
                try {
                    const rows = window.htInstance.getData();

                    return rows.map(row => {
                        const cells = row.map(c => {
                            if (c === null || c === undefined) return '';
                            if (typeof c === 'object') return JSON.stringify(c);
                            return String(c);
                        });
                        return cells;
                    });
                } catch(e) {
                    return [{ error: e.toString() }];
                }
            }
            """
        )

        print("First 3 raw rows:")
        for r in raw_rows[:3]:
            print("  " + str(r))

        print("Raw rows extracted: " + str(len(raw_rows)))

        context.close()
        browser.close()

    # ==========================================
    # CLEAN AND BUILD DATA
    # ==========================================
    def clean(val):
        return BeautifulSoup(str(val), "html.parser").get_text(strip=True)

    for row in raw_rows:
        if isinstance(row, dict) and row.get("error"):
            raise Exception("JS error: " + row["error"])

        if not isinstance(row, list):
            continue

        if len(row) < 6:
            continue

        code = clean(row[2] if len(row) > 2 else "")
        category = clean(row[3] if len(row) > 3 else "")
        group = clean(row[4] if len(row) > 4 else "")
        activity_name = clean(row[5] if len(row) > 5 else "")
        arabic_name = clean(row[6] if len(row) > 6 else "")
        third_party = clean(row[7] if len(row) > 7 else "")
        when = clean(row[8] if len(row) > 8 else "")
        notes = clean(row[9] if len(row) > 9 else "")

        if not activity_name or activity_name in ("&nbsp;", "nbsp;", ""):
            continue

        data.append({
            "Code": code,
            "Category": category,
            "Group": group,
            "Activity Name": activity_name,
            "Arabic Name": arabic_name,
            "Third Party": third_party,
            "When": when,
            "Notes": notes,
        })

    if not data:
        raise Exception("No data scraped from Shams.")

    df = pd.DataFrame(data)

    df = df[
        ~df["Activity Name"].str.lower().str.strip()
        .isin(["activity name", "none", "", "nan", "&nbsp;"])
    ]

    df.drop_duplicates(subset=["Activity Name"], inplace=True)
    df.reset_index(drop=True, inplace=True)

    print("Total unique activities: " + str(len(df)))

    output_dir = "exports"
    os.makedirs(output_dir, exist_ok=True)

    csv_path = os.path.join(output_dir, "shams_activities.csv")
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print("CSV saved at: " + csv_path)

    return df