import requests
import pandas as pd


def scrape_paginated_api(
    base_url,
    headers,
    columns,
    field_map,
    params=None,
    limit=1000,
    offset_param="offset",
    order_param=None,
    dedupe_column=None,
):
    """
    Generic paginated API scraper.
    Returns a pandas DataFrame.
    """

    data = []

    offset = 0

    base_params = params.copy() if params else {}

    base_params["select"] = base_params.get("select", "*")
    base_params["limit"] = limit

    if order_param:
        base_params["order"] = order_param

    while True:

        request_params = {
            **base_params,
            offset_param: offset
        }

        response = requests.get(
            base_url,
            params=request_params,
            headers=headers,
            timeout=30
        )

        if response.status_code == 401:
            raise Exception("Unauthorized — invalid API credentials.")

        if response.status_code != 200:
            raise Exception(
                f"API error {response.status_code}: {response.text[:300]}"
            )

        items = response.json()

        if not items:
            break

        for item in items:

            row = {
                col: item.get(api_key, "")
                for col, api_key in field_map.items()
            }

            data.append(row)

        if len(items) < limit:
            break

        offset += limit

    if not data:
        raise Exception("No data returned from API.")

    df = pd.DataFrame(data, columns=columns)

    if dedupe_column and dedupe_column in df.columns:
        df.drop_duplicates(
            subset=[dedupe_column],
            inplace=True
        )

    df.reset_index(drop=True, inplace=True)

    return df