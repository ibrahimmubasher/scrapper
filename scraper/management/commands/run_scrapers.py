from django.core.management.base import BaseCommand
from scraper.services.csv_exporter import CSVExporter
from scraper.services.activity_matcher import ActivityMatcher
from scraper.services.websites import WEBSITES
from scraper.services.dataframe_utils import filter_by_jurisdiction


class Command(BaseCommand):

    help = "Run all scrapers"

    def add_arguments(self, parser):

        parser.add_argument(
            "--website",
            type=str,
            default="ALL"
        )

    def handle(self, *args, **options):

        matcher = ActivityMatcher()

        website = options["website"].upper()

        # --------------------------
        # RUN ALL
        # --------------------------

        if website == "ALL":

            websites = WEBSITES.items()

        else:

            if website not in WEBSITES:

                self.stdout.write(
                    self.style.ERROR("Invalid website")
                )
                return

            websites = [
                (website, WEBSITES[website])
            ]

        # --------------------------
        # LOOP
        # --------------------------

        for name, config in websites:

            self.stdout.write(
                self.style.SUCCESS(
                    f"\nRunning {name}..."
                )
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

                CSVExporter.save(
                    website_df,
                    name
                )
            except Exception as e:

                self.stdout.write(
                    self.style.ERROR(
                        f"{name} Failed : {e}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                "\nCompleted Successfully"
            )
        )