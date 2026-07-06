import os
import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from scraper.services.logger import safe_print

print = safe_print


def scrape_SHAMS_activities():
    url = "https://shamsfz.ae/business-setup/business-activities/"
    data = []

    def clean(val):
        return BeautifulSoup(str(val), "html.parser").get_text(strip=True)

    with sync_playwright() as p:
        # --------------------------------------------------
        # 0) LAUNCH BROWSER
        # Use Playwright's own bundled Chromium, NOT the snap
        # binary. Snap Chromium runs under strict AppArmor/
        # seccomp confinement which has been known to silently
        # break cross-origin iframe embedding (exactly the
        # symptom we're chasing here). Run:
        #   playwright install chromium --with-deps
        # on the server before deploying.
        # --------------------------------------------------
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-setuid-sandbox",
            ],
        )

        context = browser.new_context(
            viewport={"width": 1400, "height": 900},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )

        page = context.new_page()
        page.set_default_timeout(120000)
        page.set_default_navigation_timeout(120000)

        # Surface anything that would otherwise fail silently
        page.on("console", lambda msg: print(f"[CONSOLE] {msg.type}: {msg.text}"))
        page.on("pageerror", lambda exc: print(f"[PAGE ERROR] {exc}"))
        page.on("requestfailed", lambda req: print(f"[REQUEST FAILED] {req.url} - {req.failure}"))

        print("\nOpening Shams Free Zone website...")
        print(f"URL: {url}")

        # --------------------------------------------------
        # 1) LOAD PAGE
        # --------------------------------------------------
        page.goto(url, wait_until="networkidle", timeout=120000)
        page.wait_for_timeout(8000)

        print("[DEBUG] Page loaded, capturing diagnostics...")

        # --------------------------------------------------
        # 2) ALWAYS CAPTURE STATE BEFORE HUNTING FOR THE FRAME
        # This is the single most useful thing when this fails
        # again — pull these two files off the server and look.
        # --------------------------------------------------
        try:
            page.screenshot(path="/tmp/shams_debug_page.png", full_page=True)
            print("[DEBUG] Saved screenshot to /tmp/shams_debug_page.png")
        except Exception as e:
            print(f"[DEBUG] Screenshot failed: {e}")

        html = page.content()
        try:
            with open("/tmp/shams_debug_page.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("[DEBUG] Saved page HTML to /tmp/shams_debug_page.html")
        except Exception as e:
            print(f"[DEBUG] Could not save debug HTML: {e}")

        has_iframe_tag = "<iframe" in html.lower()
        has_zoho_ref = "zoho" in html.lower()
        has_challenge = any(
            marker in html.lower()
            for marker in ["captcha", "cloudflare", "checking your browser", "attention required"]
        )
        print(f"[DEBUG] <iframe> present in HTML: {has_iframe_tag}")
        print(f"[DEBUG] 'zoho' string present in HTML: {has_zoho_ref}")
        print(f"[DEBUG] Bot-challenge markers present: {has_challenge}")

        print(f"[DEBUG] Total frames currently: {len(page.frames)}")
        for idx, f in enumerate(page.frames):
            print(f"[DEBUG] Frame {idx}: {f.url}")

        zoho_frame = None
        iframe_selectors = [
            'iframe[src*="zoho"]',
            'iframe[src*="zohopublic"]',
            'iframe[src*="creatorapp"]',
            'iframe[src*="publish"]',
        ]
        combined_selector = ", ".join(iframe_selectors)

        # --------------------------------------------------
        # 3) PREFERRED: frame_locator waits for attachment
        # instead of racing page.frames in a polling loop.
        # --------------------------------------------------
        try:
            frame_loc = page.frame_locator(combined_selector)
            frame_loc.locator("body").wait_for(state="attached", timeout=20000)
            handle = page.locator(combined_selector).first.element_handle()
            candidate = handle.content_frame() if handle else None
            if candidate:
                zoho_frame = candidate
                print(f"[DEBUG] Got frame via frame_locator: {zoho_frame.url}")
        except PlaywrightTimeoutError:
            print("[DEBUG] frame_locator timed out — iframe never attached")
        except Exception as e:
            print(f"[DEBUG] frame_locator approach failed: {e}")

        # --------------------------------------------------
        # 4) FALLBACK: manual polling loop (selectors + page.frames)
        # --------------------------------------------------
        if zoho_frame is None:
            for attempt in range(30):
                print(f"[DEBUG] Attempt {attempt + 1}/30 to locate Zoho iframe")

                for selector in iframe_selectors:
                    try:
                        iframe_el = page.locator(selector).first
                        if iframe_el.count() > 0:
                            frame = iframe_el.element_handle().content_frame()
                            if frame:
                                zoho_frame = frame
                                print(f"[DEBUG] Found via selector '{selector}': {zoho_frame.url}")
                                break
                    except Exception as e:
                        print(f"[DEBUG] Selector {selector} failed: {e}")

                if zoho_frame:
                    break

                try:
                    iframe_sources = page.evaluate(
                        """
                        () => Array.from(document.querySelectorAll('iframe'))
                                  .map(i => i.src || i.getAttribute('src') || '')
                        """
                    )
                    print(f"[DEBUG] iframe srcs found in DOM: {iframe_sources}")
                except Exception as e:
                    print(f"[DEBUG] Could not inspect iframe DOM: {e}")

                for f in page.frames:
                    if any(key in f.url.lower() for key in ["zoho", "zohopublic", "creatorapp", "publish"]):
                        zoho_frame = f
                        print(f"[DEBUG] Found Zoho frame from page.frames: {f.url}")
                        break

                if zoho_frame:
                    break

                page.wait_for_timeout(2000)

        # --------------------------------------------------
        # 5) STILL NOTHING -> FAIL WITH FULL DIAGNOSTICS SAVED
        # --------------------------------------------------
        if zoho_frame is None:
            context.close()
            browser.close()
            reason = "bot-challenge detected" if has_challenge else "iframe never attached"
            raise Exception(
                f"Zoho frame not found on SHAMS page ({reason}). "
                f"See /tmp/shams_debug_page.png and /tmp/shams_debug_page.html"
            )

        print("[DEBUG] Zoho frame found successfully.")
        print(f"[DEBUG] Zoho frame URL: {zoho_frame.url}")

        # --------------------------------------------------
        # 6) WAIT FOR HANDSONTABLE INSTANCE
        # --------------------------------------------------
        print("[DEBUG] Waiting for htInstance data...")

        count = 0
        for _ in range(40):
            try:
                count = zoho_frame.evaluate(
                    """
                    () => {
                        try {
                            return window.htInstance ? window.htInstance.getData().length : 0;
                        } catch (e) {
                            return 0;
                        }
                    }
                    """
                )
            except Exception:
                count = 0

            print(f"[DEBUG] Current htInstance row count: {count}")

            if count > 0:
                break

            try:
                zoho_frame.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            except Exception:
                pass

            page.wait_for_timeout(1500)

        if count == 0:
            context.close()
            browser.close()
            raise Exception("Zoho frame found, but no table data loaded.")

        # --------------------------------------------------
        # 7) SCROLL TABLE TO FORCE ALL ROWS LOAD
        # --------------------------------------------------
        print("[DEBUG] Loading all rows from Zoho table...")

        last_count = 0
        stable_rounds = 0

        for i in range(60):
            try:
                zoho_frame.evaluate(
                    """
                    () => {
                        const holder = document.querySelector('.wtHolder');
                        if (holder) {
                            holder.scrollTop = holder.scrollHeight;
                        }
                    }
                    """
                )
            except Exception:
                pass

            page.wait_for_timeout(1000)

            try:
                count = zoho_frame.evaluate(
                    """
                    () => {
                        try {
                            return window.htInstance ? window.htInstance.getData().length : 0;
                        } catch (e) {
                            return 0;
                        }
                    }
                    """
                )
            except Exception:
                count = 0

            print(f"[DEBUG] Scroll {i+1}/60 | rows: {count}")

            if count == last_count and count > 0:
                stable_rounds += 1
            else:
                stable_rounds = 0

            last_count = count

            if stable_rounds >= 4:
                break

        print(f"[DEBUG] Final row count before extraction: {last_count}")

        # --------------------------------------------------
        # 8) EXTRACT RAW TABLE DATA
        # --------------------------------------------------
        raw_rows = zoho_frame.evaluate(
            """
            () => {
                try {
                    if (!window.htInstance) {
                        return [];
                    }

                    const rows = window.htInstance.getData();

                    return rows.map(row => {
                        return row.map(cell => {
                            if (cell === null || cell === undefined) return '';
                            if (typeof cell === 'object') return JSON.stringify(cell);
                            return String(cell);
                        });
                    });
                } catch (e) {
                    return [{ error: e.toString() }];
                }
            }
            """
        )

        print(f"[DEBUG] Raw rows extracted: {len(raw_rows)}")
        for r in raw_rows[:3]:
            print(f"[DEBUG] Sample row: {r}")

        context.close()
        browser.close()

    # --------------------------------------------------
    # 9) BUILD DATAFRAME
    # --------------------------------------------------
    for row in raw_rows:
        if isinstance(row, dict) and row.get("error"):
            raise Exception("JS error while extracting SHAMS table: " + row["error"])

        if not isinstance(row, list):
            continue

        if len(row) < 6:
            continue

        code = clean(row[2] if len(row) > 2 else "")
        category = clean(row[3] if len(row) > 3 else "")
        group = clean(row[4] if len(row) > 4 else "")
        activity_name = clean(row[5] if len(row) > 5 else "")
        arabic_name = clean(row[6] if len(row) > 6 else "")
        third_party = clean(row[7] if len(row) > 7 else "")
        when = clean(row[8] if len(row) > 8 else "")
        notes = clean(row[9] if len(row) > 9 else "")

        if not activity_name:
            continue

        if activity_name.lower().strip() in {"activity name", "none", "nan", "&nbsp;"}:
            continue

        data.append({
            "Code": code,
            "Category": category,
            "Group": group,
            "Activity Name": activity_name,
            "Arabic Name": arabic_name,
            "Third Party": third_party,
            "When": when,
            "Notes": notes,
        })

    if not data:
        raise Exception("No data scraped from SHAMS after extraction.")

    df = pd.DataFrame(data)
    df.drop_duplicates(subset=["Activity Name"], inplace=True)
    df.reset_index(drop=True, inplace=True)

    print(f"Total unique SHAMS activities: {len(df)}")
    return df