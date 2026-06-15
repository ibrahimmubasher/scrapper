from django.core.management.base import BaseCommand
from scraper.services.csv_exporter import CSVExporter
from scraper.services.activity_matcher import ActivityMatcher
from scraper.services.websites import WEBSITES
from scraper.services.dataframe_utils import filter_by_jurisdiction
import traceback
import sys
import subprocess


class Command(BaseCommand):

    help = "Run all scrapers"

    def add_arguments(self, parser):

        parser.add_argument(
            "--website",
            type=str,
            default="ALL"
        )


        
    def handle(self, *args, **options):

        # Install system dependencies at runtime
        subprocess.run(
            ["apt-get", "update"],
            check=False
        )
        subprocess.run(
            [
                "apt-get", "install", "-y",
                "libglib2.0-0t64",
                "libnss3",
                "libatk1.0-0t64",
                "libatk-bridge2.0-0t64",
                "libcups2t64",
                "libdrm2",
                "libxkbcommon0",
                "libxcomposite1",
                "libxdamage1",
                "libxfixes3",
                "libxrandr2",
                "libgbm1",
                "libasound2t64",
                "libx11-6",
                "libxcb1",
                "libxext6",
            ],
            check=False
        )

        # Install playwright browser
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True
        )

        matcher = ActivityMatcher()

        website = options["website"].upper()

        if website == "ALL":
            websites = WEBSITES.items()
        else:
            if website not in WEBSITES:
                self.stdout.write(self.style.ERROR("Invalid website"))
                return
            websites = [(website, WEBSITES[website])]

        for name, config in websites:

            self.stdout.write(
                self.style.SUCCESS(f"\nRunning {name}...")
            )

            try:

                scraped_df = config["scraper"]()

                master_df = matcher.update_activities(
                    scraped_df,
                    config["jurisdiction"]
                )

                website_df = matcher.get_jurisdiction_dataframe(
                    master_df,
                    config["jurisdiction"]
                )

                CSVExporter.save(website_df, name)

            except Exception as e:

                self.stdout.write(
                    self.style.ERROR(f"{name} Failed : {e}")
                )

                self.stdout.write(
                    self.style.ERROR(traceback.format_exc())
                )

        self.stdout.write(
            self.style.SUCCESS("\nCompleted Successfully")
        )