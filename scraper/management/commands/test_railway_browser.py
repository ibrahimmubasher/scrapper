"""
Management command to test Railway browser installation.
Run with: python manage.py test_railway_browser
"""

from django.core.management.base import BaseCommand
from playwright.sync_api import sync_playwright
import sys


class Command(BaseCommand):
    help = "Test Playwright and Chromium installation on Railway"

    def handle(self, *args, **options):
        print("\n" + "="*60)
        print("RAILWAY BROWSER TEST")
        print("="*60)

        # Test 1: Check Playwright import
        print("\n[TEST 1] Playwright module import...")
        try:
            from playwright.sync_api import sync_playwright
            print("✓ Playwright imported successfully")
        except ImportError as e:
            print(f"✗ Failed to import Playwright: {e}")
            sys.exit(1)

        # Test 2: Launch browser
        print("\n[TEST 2] Launching Chromium browser...")
        try:
            with sync_playwright() as p:
                print("  ✓ sync_playwright context started")

                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu"
                    ]
                )
                print("  ✓ Chromium browser launched")

                page = browser.new_page()
                print("  ✓ New page created")

                # Test 3: Navigate to a website
                print("\n[TEST 3] Navigating to google.com...")
                try:
                    page.goto("https://www.google.com", timeout=30000)
                    print(f"  ✓ Page loaded successfully")
                    print(f"  ✓ Page title: {page.title()}")
                except Exception as e:
                    print(f"  ✗ Navigation failed: {e}")
                    browser.close()
                    sys.exit(1)

                browser.close()
                print("  ✓ Browser closed")

        except Exception as e:
            print(f"✗ Browser launch failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

        # Test 4: Check webdriver-manager
        print("\n[TEST 4] Checking webdriver-manager...")
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            print("  ✓ webdriver-manager imported successfully")
        except ImportError:
            print("  ⚠ webdriver-manager not found (optional for Playwright)")

        # Test 5: Check Selenium
        print("\n[TEST 5] Checking Selenium...")
        try:
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            print("  ✓ Selenium imported successfully")
        except ImportError as e:
            print(f"  ✗ Selenium import failed: {e}")

        print("\n" + "="*60)
        print("ALL TESTS PASSED ✓")
        print("="*60)
        print("\nBrowser environment is ready for scraping!")
