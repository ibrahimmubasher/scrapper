import requests
import pandas as pd


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

            full_activity = (
                item.get(
                    "Description_EN",
                    ""
                ).strip()
            )

            if " - " in full_activity:

                code, activity_name = (
                    full_activity.split(
                        " - ",
                        1
                    )
                )

            else:

                code = item.get(
                    "SubCode",
                    ""
                )

                activity_name = (
                    full_activity
                )

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

    return df