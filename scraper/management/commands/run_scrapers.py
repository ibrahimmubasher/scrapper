import json
import subprocess
import sys
import traceback
from pathlib import Path

from django.core.management.base import BaseCommand

from scraper.services.activity_matcher import ActivityMatcher
from scraper.services.csv_exporter import CSVExporter
from scraper.services.websites import WEBSITES


def safe_console_output(text, stream=None):
    if stream is None:
        stream = sys.stdout

    text = str(text)

    try:
        stream.write(text)
    except UnicodeEncodeError:
        stream.write(text.encode("ascii", "replace").decode("ascii"))


def update_progress_status(progress_file, status, message, percent, current_website=None):
    if progress_file is None:
        return

    progress_path = Path(progress_file)
    progress_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "status": status,
        "message": message,
        "percent": int(percent),
        "current_website": current_website,
    }

    progress_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class Command(BaseCommand):

    help = "Run all scrapers"

    def add_arguments(self, parser):
        parser.add_argument("--website", type=str, default="ALL")
        parser.add_argument("--progress-file", type=str, default=None)

    def handle(self, *args, **options):
        progress_file = options.get("progress_file")

        update_progress_status(progress_file, "starting", "Preparing scraper run", 5)

        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
        )

        update_progress_status(progress_file, "running", "Preparing browser dependencies", 10)

        matcher = ActivityMatcher()

        website = options["website"].upper()

        if website == "ALL":
            websites = list(WEBSITES.items())
        else:
            if website not in WEBSITES:
                update_progress_status(progress_file, "failed", "Invalid website selected", 0, website)
                self.stdout.write(self.style.ERROR("Invalid website"))
                return
            websites = [(website, WEBSITES[website])]

        total = max(len(websites), 1)

        for index, (name, config) in enumerate(websites, start=1):
            current_percent = min(95, int((index / total) * 100))
            update_progress_status(progress_file, "running", f"Running {name}", current_percent, name)

            safe_console_output(
                self.style.SUCCESS(f"\nRunning {name}..."),
                self.stdout,
            )

            try:
                scraped_df = config["scraper"]()

                master_df = matcher.update_activities(
                    scraped_df,
                    config["jurisdiction"],
                )

                website_df = matcher.get_jurisdiction_dataframe(
                    master_df,
                    config["jurisdiction"],
                )

                CSVExporter.save(website_df, name)
                update_progress_status(progress_file, "running", f"Saved {name} results", current_percent, name)
            except Exception as exc:
                update_progress_status(progress_file, "failed", f"{name} failed: {exc}", current_percent, name)

                safe_console_output(
                    self.style.ERROR(f"{name} Failed : {exc}"),
                    self.stdout,
                )

                safe_console_output(
                    self.style.ERROR(traceback.format_exc()),
                    self.stdout,
                )

        update_progress_status(progress_file, "completed", "Scraper run completed successfully", 100)

        safe_console_output(
            self.style.SUCCESS("\nCompleted Successfully"),
            self.stdout,
        )