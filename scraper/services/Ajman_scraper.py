import os
import pandas as pd
from playwright.sync_api import sync_playwright

from scraper.services.logger import safe_print

print = safe_print


def scrape_AFZ_activities():

    url = "https://afz.gov.ae/activity-list/"

    data = []

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page()

        print("\nOpening AFZ website...")

        page.goto(
            url,
            wait_until="networkidle",
            timeout=60000
        )

        page_num = 1

        while True:

            print(f"\nScraping page {page_num}...")

            # ==========================================
            # WAIT FOR TABLE
            # ==========================================

            page.wait_for_selector(
                "table tbody tr",
                state="visible",
                timeout=20000
            )

            rows = page.locator(
                "table tbody tr"
            )

            row_count = rows.count()

            print(
                f"Found {row_count} rows"
            )

            # ==========================================
            # EXTRACT ROWS
            # ==========================================

            for i in range(row_count):

                cols = rows.nth(i).locator("td")

                col_count = cols.count()

                if col_count == 0:
                    continue

                cells = [
                    cols.nth(j)
                    .inner_text()
                    .strip()
                    for j in range(col_count)
                ]

                data.append({

                    "Activity Number": (
                        cells[0]
                        if len(cells) > 0 else ""
                    ),

                    "ISIC Code": (
                        cells[1]
                        if len(cells) > 1 else ""
                    ),

                    "License Type": (
                        cells[2]
                        if len(cells) > 2 else ""
                    ),

                    "Activity Name": (
                        cells[3]
                        if len(cells) > 3 else ""
                    ),

                    "Description": (
                        cells[4]
                        if len(cells) > 4 else ""
                    ),
                })

            print(
                f"→ {row_count} rows collected "
                f"from page {page_num}"
            )

            # ==========================================
            # PAGINATION
            # ==========================================

            next_btn = page.locator(
                "button[aria-label='Next']"
            )

            if next_btn.count() == 0:

                next_btn = page.locator(
                    "button[aria-label='Next page']"
                )

            if next_btn.count() == 0:

                next_btn = page.locator(
                    "button:has-text('Next')"
                )

            if next_btn.count() == 0:

                next_btn = page.locator(
                    "li.pagination-next button"
                )

            # No next button
            if next_btn.count() == 0:

                print(
                    "\nNo next button found."
                )

                break

            # Disabled check
            is_disabled = (
                next_btn.first.is_disabled()
            )

            btn_class = (
                next_btn.first.get_attribute(
                    "class"
                ) or ""
            )

            if (
                is_disabled
                or "disabled" in btn_class.lower()
            ):

                print(
                    f"\nPagination ended "
                    f"on page {page_num}"
                )

                break

            # Detect table change
            first_row_before = (
                rows.nth(0)
                .inner_text()
                .strip()
            )

            print(
                f"Moving to page "
                f"{page_num + 1}..."
            )

            next_btn.first.click()

            page.wait_for_timeout(2000)

            try:

                page.wait_for_function(
                    """
                    (prevText) => {

                        const firstRow =
                            document.querySelector(
                                'table tbody tr'
                            );

                        return (
                            firstRow &&
                            firstRow.innerText !== prevText
                        );
                    }
                    """,
                    arg=first_row_before,
                    timeout=15000
                )

            except Exception:

                page.wait_for_timeout(3000)

            page_num += 1

        browser.close()

    # ==========================================
    # VALIDATE
    # ==========================================

    if not data:

        raise Exception(
            "No data scraped from AFZ."
        )

    # ==========================================
    # DATAFRAME
    # ==========================================

    df = pd.DataFrame(data)

    # Remove duplicates
    df.drop_duplicates(
        subset=["Activity Number"],
        inplace=True
    )

    df.reset_index(
        drop=True,
        inplace=True
    )

    print(
        f"\n✅ Total unique activities: "
        f"{len(df)}"
    )

    # ==========================================
    # OPTIONAL CSV SAVE
    # ==========================================

    output_dir = "exports"

    os.makedirs(
        output_dir,
        exist_ok=True
    )

    csv_path = os.path.join(
        output_dir,
        "afz_activities.csv"
    )

    df.to_csv(
        csv_path,
        index=False,
        encoding="utf-8-sig"
    )

    print(
        f"\n✅ CSV saved at:\n{csv_path}"
    )

    # ==========================================
    # RETURN DATAFRAME
    # ==========================================

    return df