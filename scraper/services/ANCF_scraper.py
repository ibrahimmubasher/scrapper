import json
import time

import requests
import urllib3
import pandas as pd

from scraper.utils.retry import retry_request

urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)


class ANCFScraper:

    def scrape(self):

        print("\n" + "=" * 50)
        print("SCRAPING ANCF")
        print("=" * 50)

        url = (
            "https://eportal.ancfz.ae/business-activities/"
            "aura?r=0&aura.ApexAction.execute=1"
        )

        payload = {
            "message": json.dumps({
                "actions": [{
                    "id": "3;a",
                    "descriptor":
                        "aura://ApexActionController/ACTION$execute",
                    "callingDescriptor": "UNKNOWN",
                    "params": {
                        "namespace":      "",
                        "classname":      "GetActivitiesController",
                        "method":         "getActivities",
                        "cacheable":      False,
                        "isContinuation": False
                    }
                }]
            }),
            "aura.context": json.dumps({
                "mode":  "PROD",
                "fwuid": (
                    "ZkJhOVpLN2NZQkJrd2NWd3pMcnFOdzJEa1N5enhOU3R5QWl2"
                    "VzNveFZTbGcxMy4tMjE0NzQ4MzY0OC4xMzEwNzIwMA"
                ),
                "app": "c:testApplication",
                "loaded": {
                    "APPLICATION@markup://c:testApplication":
                        "898_WU4__0ARNqge7_y3MQ7scA"
                },
                "dn":      [],
                "globals": {},
                "uad":     True
            }),
            "aura.pageURI": "/business-activities/",
            "aura.token":   "null"
        }

        headers = {
            "Accept":       "*/*",
            "Content-Type": (
                "application/x-www-form-urlencoded; charset=UTF-8"
            ),
            "Origin":   "https://eportal.ancfz.ae",
            "Referer":  "https://eportal.ancfz.ae/business-activities/",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/148.0.0.0 Safari/537.36"
            )
        }

        try:

            session = requests.Session()

            # =============================================
            # REQUEST WITH RETRY + EXPONENTIAL BACKOFF
            # =============================================
            response = retry_request(
                lambda: session.post(
                    url,
                    headers=headers,
                    data=payload,
                    timeout=60,
                    verify=False
                )
            )

            response.raise_for_status()

            response_json = response.json()

            # =============================================
            # VALIDATE RESPONSE STRUCTURE
            # =============================================
            if (
                "actions" not in response_json
                or len(response_json["actions"]) == 0
            ):
                raise Exception(
                    "Invalid API response: "
                    "'actions' missing or empty."
                )

            activities = (
                response_json["actions"][0]
                ["returnValue"]
                ["returnValue"]
            )

            if not activities:
                raise Exception(
                    "API returned empty activities list."
                )

            # =============================================
            # BUILD DATAFRAME
            # =============================================
            rows = []

            for activity in activities:

                rows.append({

                    "activity code":
                        str(
                            activity.get(
                                "Activity_Code__c",
                                ""
                            )
                        ).strip(),

                    "activity name":
                        str(
                            activity.get(
                                "Activity_English_Name__c",
                                ""
                            )
                        ).strip(),

                    "activity description":
                        str(
                            activity.get(
                                "Activity_Description__c",
                                ""
                            )
                        ).strip(),

                    "activity group":
                        str(
                            activity.get(
                                "Activity_Category__c",
                                ""
                            )
                        ).strip(),

                    "license type":
                        str(
                            activity.get(
                                "Activity_Category__c",
                                ""
                            )
                        ).strip(),

                    "jurisdiction":
                        "ANCF"
                })

            df = pd.DataFrame(rows)

            df.columns = (
                df.columns
                .str.strip()
                .str.lower()
            )

            print(f"\nFound {len(df)} activities")

            print("\nColumns:")
            print(df.columns.tolist())

            print("\nSample:")
            print(df.head())

            return df

        except Exception as e:

            print("\n❌ ANCF SCRAPER FAILED")
            print(str(e))

            return pd.DataFrame(
                columns=[
                    "activity code",
                    "activity name",
                    "activity description",
                    "activity group",
                    "license type",
                    "jurisdiction"
                ]
            )