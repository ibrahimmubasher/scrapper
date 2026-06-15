import pandas as pd
from playwright.sync_api import sync_playwright


def scrape_SPC_activities():

    url = "https://www.spcfz.ae/business-activities/"
    data = []

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--single-process",
            ]
        )
        page = browser.new_page()

        page.goto(url, wait_until="networkidle")

        page_num = 1

        while True:

            print(f"Scraping page {page_num}...")

            # Wait for table rows
            page.wait_for_selector(
                "table tbody tr",
                state="visible",
                timeout=15000
            )

            rows = page.locator("table tbody tr")
            row_count = rows.count()

            for i in range(row_count):

                cols = rows.nth(i).locator("td")
                col_count = cols.count()

                if col_count < 4:
                    continue

                cells = [
                    cols.nth(j).inner_text().strip()
                    for j in range(col_count)
                ]

                # ==================================================
                # SPC WEBSITE RETURNS:
                # "4651.69 - Wholesale of ..."
                # inside ONE cell
                # So split manually
                # ==================================================
                full_activity = (
                    cells[3]
                    if len(cells) > 3 else ""
                ).strip()

                if " - " in full_activity:

                    code, activity_name = full_activity.split(
                        " - ",
                        1
                    )

                else:

                    code = ""
                    activity_name = full_activity

                data.append({

                    "Category": (
                        cells[0]
                        if len(cells) > 0 else ""
                    ),

                    "Group": (
                        cells[1]
                        if len(cells) > 1 else ""
                    ),

                    "Code": code.strip(),

                    "Activity Name": activity_name.strip(),

                    "Arabic Name": (
                        cells[4]
                        if len(cells) > 4 else ""
                    ),

                    "Third Party": (
                        cells[5]
                        if len(cells) > 5 else ""
                    ),

                    "Instant License": (
                        cells[6]
                        if len(cells) > 6 else ""
                    ),
                })

            print(
                f"  → {row_count} rows collected from page {page_num}"
            )

            # ==================================================
            # NEXT BUTTON
            # ==================================================
            next_btn = page.locator("button#ftable-next")

            if next_btn.count() == 0:
                print("No Next button found — done.")
                break

            is_disabled = next_btn.first.is_disabled()

            btn_class = (
                next_btn.first.get_attribute("class")
                or ""
            )

            if (
                is_disabled
                or "disabled" in btn_class.lower()
            ):

                print(
                    f"Next button disabled on page {page_num} — done."
                )

                break

            # Detect page change
            first_row_text_before = rows.nth(0).inner_text()

            next_btn.first.click()

            try:

                page.wait_for_function(
                    """(prevText) => {
                        const firstRow =
                            document.querySelector(
                                'table tbody tr'
                            );

                        return (
                            firstRow &&
                            firstRow.innerText !== prevText
                        );
                    }""",
                    arg=first_row_text_before,
                    timeout=15000,
                )

            except Exception as e:

                print(
                    f"⚠ wait_for_function timed out "
                    f"on page {page_num}: {e}"
                )

                page.wait_for_timeout(3000)

            page_num += 1

        browser.close()

    if not data:
        raise Exception("No data scraped")

    # ==================================================
    # CREATE DATAFRAME
    # ==================================================
    df = pd.DataFrame(data)

    # Remove duplicates using activity code
    df.drop_duplicates(
        subset=["Code"],
        inplace=True
    )

    df.reset_index(
        drop=True,
        inplace=True
    )

    print(
        f"\n✅ Done. "
        f"Total unique activities scraped: {len(df)}"
    )

    return df