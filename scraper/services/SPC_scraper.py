import requests
import pandas as pd
import re


def scrape_SPC_activities():

    BASE_URL = (
        "https://www.spcfz.ae/wp-json/spc/v1/activities"
    )

    data = []

    # First request
    first_response = requests.get(BASE_URL)
    first_response.raise_for_status()

    total_pages = int(
        first_response.headers.get(
            "X-WP-TotalPages",
            1
        )
    )

    print(
        f"Found {total_pages} pages"
    )

    # ============================================
    # REGEX: matches a leading code prefix regardless
    # of whether SubCode field matches the text.
    #
    # Two patterns combined:
    #   1. digits + ".xx" suffix + optional dash
    #      e.g. "4773.b8 - ", "1811.10-", "7210.02 -- "
    #   2. 3+ digits + REQUIRED dash
    #      e.g. "9603- ", "100356 - "
    #
    # Deliberately does NOT match a bare leading digit
    # with no dot and no dash (avoids mangling things
    # like "3D Printing Services" -> "D Printing Services").
    # ============================================
    CODE_PREFIX_PATTERN = re.compile(
        r'^\s*\d+(?:\.[a-zA-Z0-9]+)\s*[-–—]{0,2}\s*'
        r'|'
        r'^\s*\d{3,}\s*[-–—]+\s*',
        flags=re.IGNORECASE
    )

    for page in range(1, total_pages + 1):

        print(
            f"Scraping page {page}/{total_pages}"
        )

        response = requests.get(
            BASE_URL,
            params={
                "page": page
            }
        )

        response.raise_for_status()

        records = response.json()

        for item in records:

            full_activity = item.get(
                "Description_EN",
                ""
            ).strip()

            # Code provided directly by API
            code = item.get("SubCode", "").strip()

            activity_name = full_activity

            # =========================================
            # STEP 1: Try exact SubCode match first
            # (works when SubCode matches text exactly)
            # =========================================
            if code:

                escaped_code = re.escape(code)

                stripped = re.sub(
                    rf'^\s*{escaped_code}\s*[-–—]{{0,2}}\s*',
                    '',
                    full_activity,
                    flags=re.IGNORECASE
                ).strip()

                if stripped != full_activity:
                    activity_name = stripped

            # =========================================
            # STEP 2: SubCode didn't match the visible
            # text — fall back to generic pattern that
            # strips ANY leading code-like prefix found
            # in the text itself, regardless of SubCode.
            # =========================================
            if activity_name == full_activity:

                match = CODE_PREFIX_PATTERN.match(full_activity)

                if match:

                    prefix = match.group(0)

                    activity_name = full_activity[len(prefix):].strip()

                    # Extract the code portion for the Code column
                    code_match = re.match(
                        r'^\s*([\d]+(?:\.[a-zA-Z0-9]+)?)',
                        prefix
                    )

                    if code_match and not code:
                        code = code_match.group(1)

            data.append({

                "Category":
                    item.get(
                        "Category",
                        ""
                    ),

                "Group":
                    item.get(
                        "Code",
                        ""
                    ),

                "Code":
                    code,

                "Activity Name":
                    activity_name,

                "Arabic Name":
                    item.get(
                        "Description_AR",
                        ""
                    ),

                "Third Party":
                    item.get(
                        "Authority",
                        ""
                    ),

                "Instant License":
                    item.get(
                        "when",
                        ""
                    ),

                "Fee":
                    item.get(
                        "Fee",
                        ""
                    ),

                "Status":
                    item.get(
                        "Status",
                        ""
                    )
            })

    df = pd.DataFrame(data)

    df.drop_duplicates(
        subset=["Code"],
        inplace=True
    )

    df.reset_index(
        drop=True,
        inplace=True
    )

    print(
        f"\n Total Activities: {len(df)}"
    )

    # DEBUG: flag any rows still starting with what looks
    # like a leftover code, so you can sanity-check results
    still_has_code = df[
        df["Activity Name"].str.match(
            r'^\s*\d+\.[a-zA-Z0-9]+\s*[-–—]', na=False
        )
    ]

    if len(still_has_code) > 0:
        print(
            f"\n[SPC DEBUG] {len(still_has_code)} rows still "
            f"appear to have a code prefix:"
        )
        print(still_has_code["Activity Name"].head(10).tolist())
    else:
        print("\n[SPC DEBUG] No leftover code prefixes detected.")

    return df