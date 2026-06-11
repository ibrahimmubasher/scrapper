import os
import re
import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


def scrape_SHAMS_activities():

    url  = "https://shamsfz.ae/business-setup/business-activities/"
    data = []

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)
        page    = browser.new_page()

        print("\nOpening Shams Free Zone website...")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        # ==========================================
        # GET ZOHO FRAME
        # ==========================================

        zoho_frame = None
        for _ in range(30):
            for f in page.frames:
                if "zohopublic" in f.url:
                    zoho_frame = f
                    break
            if zoho_frame:
                break
            page.wait_for_timeout(1000)

        if zoho_frame is None:
            raise Exception("Zoho frame not found.")

        print("Zoho frame found.")

        # Scroll wtHolder to force Zoho to load all rows,
        # then wait for count to stabilize.
        print("Loading all rows...")

        # First wait for initial data
        for _ in range(20):
            c = zoho_frame.evaluate(
                "() => { try { return window.htInstance ? window.htInstance.getData().length : 0; } catch(e) { return 0; } }"
            )
            if c > 0:
                break
            page.wait_for_timeout(1000)

        # Now scroll to bottom repeatedly to trigger full load
        for i in range(50):
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
                "() => { try { return window.htInstance ? window.htInstance.getData().length : 0; } catch(e) { return 0; } }"
            )
            print("  scroll " + str(i+1) + " | rows: " + str(count))

            if count >= 900:
                break

        # Final stable check
        prev_count    = 0
        stable_streak = 0

        for _ in range(20):
            count = zoho_frame.evaluate(
                "() => { try { return window.htInstance ? window.htInstance.getData().length : 0; } catch(e) { return 0; } }"
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
        # Column order from sample:
        # [0] checkbox/nbsp  [1] record obj
        # [2] Code           [3] Category
        # [4] Group          [5] Activity Name (HTML)
        # [6] Arabic Name    [7] Third Party
        # [8] When           [9] Notes
        # ==========================================

        raw_rows = zoho_frame.evaluate(
            """
            () => {
                try {
                    // Use getData() — returns what is visible in cells
                    const rows = window.htInstance.getData();

                    // Print first row to console for debugging
                    if (rows.length > 0) {
                        console.log('ROW0:', JSON.stringify(rows[0]));
                        console.log('ROW1:', JSON.stringify(rows[1]));
                    }

                    return rows.map(row => {
                        // Convert row to plain strings
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

        # Print first 3 raw rows to see structure
        print("First 3 raw rows:")
        for r in raw_rows[:3]:
            print("  " + str(r))

        print("Raw rows extracted: " + str(len(raw_rows)))

        browser.close()

    # ==========================================
    # CLEAN AND BUILD DATA
    # ==========================================

    def clean(val):
        """Strip HTML tags and whitespace from a value."""
        return BeautifulSoup(str(val), "html.parser").get_text(strip=True)

    for row in raw_rows:

        # Error row from JS
        if isinstance(row, dict) and row.get("error"):
            raise Exception("JS error: " + row["error"])

        # Must be a list
        if not isinstance(row, list):
            continue

        # Need at least 6 columns
        if len(row) < 6:
            continue

        # Column positions confirmed from debug:
        # [0]=nbsp [1]=record obj [2]=Code [3]=Category
        # [4]=Group [5]=Activity Name [6]=Arabic [7]=Third Party
        # [8]=When [9]=Notes
        code          = clean(row[2] if len(row) > 2 else "")
        category      = clean(row[3] if len(row) > 3 else "")
        group         = clean(row[4] if len(row) > 4 else "")
        activity_name = clean(row[5] if len(row) > 5 else "")
        arabic_name   = clean(row[6] if len(row) > 6 else "")
        third_party   = clean(row[7] if len(row) > 7 else "")
        when          = clean(row[8] if len(row) > 8 else "")
        notes         = clean(row[9] if len(row) > 9 else "")

        if not activity_name or activity_name in ("&nbsp;", "nbsp;", ""):
            continue

        data.append({
            "Code":          code,
            "Category":      category,
            "Group":         group,
            "Activity Name": activity_name,
            "Arabic Name":   arabic_name,
            "Third Party":   third_party,
            "When":          when,
            "Notes":         notes,
        })

    # ==========================================
    # VALIDATE
    # ==========================================

    if not data:
        raise Exception("No data scraped from Shams.")

    # ==========================================
    # DATAFRAME
    # ==========================================

    df = pd.DataFrame(data)

    df = df[
        ~df["Activity Name"].str.lower().str.strip()
        .isin(["activity name", "none", "", "nan", "&nbsp;"])
    ]

    df.drop_duplicates(subset=["Activity Name"], inplace=True)
    df.reset_index(drop=True, inplace=True)

    print("Total unique activities: " + str(len(df)))

    # ==========================================
    # CSV SAVE
    # ==========================================

    output_dir = "exports"
    os.makedirs(output_dir, exist_ok=True)

    csv_path = os.path.join(output_dir, "shams_activities.csv")
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print("CSV saved at: " + csv_path)

    return df