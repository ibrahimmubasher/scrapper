from scraper.services.maydan_service import scrape_meydan
from scraper.services.SPC_scraper import scrape_SPC_activities
from scraper.services.SHAMS_scraper import scrape_SHAMS_activities
from scraper.services.activity_matcher import ActivityMatcher


class ScraperManager:

    def __init__(self):

        self.matcher = ActivityMatcher()

    # =====================================================
    # MEYDAN
    # =====================================================
    def run_meydan(self):

        print("\n===================================")
        print("STARTING MEYDAN SCRAPER")
        print("===================================\n")

        meydan_df = scrape_meydan()

        self.matcher.update_activities(
            scraped_df=meydan_df,
            jurisdiction="Meydan"
        )

        print("\nMEYDAN COMPLETED\n")

    # =====================================================
    # SPC
    # =====================================================
    def run_spc(self):

        print("\n===================================")
        print("STARTING SPC SCRAPER")
        print("===================================\n")

        spc_df = scrape_SPC_activities()

        self.matcher.update_activities(
            scraped_df=spc_df,
            jurisdiction="SPC"
        )

        print("\nSPC COMPLETED\n")

    # =====================================================
    # SHAMS
    # =====================================================
    def run_shams(self):

        print("\n===================================")
        print("STARTING SHAMS SCRAPER")
        print("===================================\n")

        shams_df = scrape_SHAMS_activities()

        self.matcher.update_activities(
            scraped_df=shams_df,
            jurisdiction="SHAMS"
        )

        print("\nSHAMS COMPLETED\n")

    # =====================================================
    # RUN ALL
    # =====================================================
    def run_all(self):

        self.run_meydan()
        self.run_spc()
        self.run_shams()

        print("\n===================================")
        print("ALL SCRAPERS COMPLETED")
        print("===================================\n")