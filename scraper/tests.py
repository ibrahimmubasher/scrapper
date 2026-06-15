import io
import json
import tempfile
from pathlib import Path

import pandas as pd
from django.test import TestCase

from scraper.management.commands.run_scrapers import safe_console_output, update_progress_status
from scraper.services.activity_matcher import ActivityMatcher


class SafeConsoleOutputTests(TestCase):

    def test_replaces_non_ascii_characters_for_cp1252_stream(self):
        stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")

        safe_console_output("✅ Saved 3 rows.", stream)

        stream.flush()
        stream.seek(0)

        self.assertEqual(stream.read(), "? Saved 3 rows.")


class ActivityMatcherOutputTests(TestCase):

    def test_writes_run_output_to_separate_workbook(self):
        matcher = ActivityMatcher.__new__(ActivityMatcher)

        with tempfile.TemporaryDirectory() as tmpdir:
            df = pd.DataFrame([
                {"activity name": "Test Activity", "jurisdiction": "SHAMS"}
            ])

            output_path = matcher._write_run_output(df, "SHAMS", output_dir=tmpdir)

            self.assertTrue(Path(output_path).exists())

            written_df = pd.read_excel(output_path, sheet_name="Final")
            self.assertEqual(written_df.iloc[0]["activity name"], "Test Activity")


class RunScrapersProgressTests(TestCase):

    def test_update_progress_status_writes_json_payload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            progress_file = Path(tmpdir) / "progress.json"

            update_progress_status(progress_file, "running", "Scraping SHAMS", 25, "SHAMS")

            self.assertTrue(progress_file.exists())

            payload = json.loads(progress_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "running")
            self.assertEqual(payload["message"], "Scraping SHAMS")
            self.assertEqual(payload["percent"], 25)
            self.assertEqual(payload["current_website"], "SHAMS")
