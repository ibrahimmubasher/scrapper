import os
import re
import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from scraper.services.logger import safe_print

print = safe_print


class RAKEZScraper:
    URL = "https://rakez.com/en/start-a-business/license-activity-list"

    def _normalize_text(self, text):
        text = str(text or "")
        text = text.replace("\xa0", " ")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _normalize_zone(self, text):
        return self._normalize_text(text).lower()

    def _extract_rows_from_current_page(self, page):
        """
        Extract rows from the currently visible RAKEZ activity table.
        Expected columns:
        Zone | Activity Code | Activity Name | License Type | Activity Group

        Speed note: we grab only the table's outerHTML via evaluate()
        instead of page.content() (the full page, including the entire
        DNN header/menu/footer markup). Parsing just the table is
        meaningfully faster across ~180 pages.
        """
        try:
            table_html = page.locator("table[id*='gvBusinessActivity']").first.evaluate(
                "el => el.outerHTML"
            )
        except Exception:
            print("[RAKEZ] Could not read activity table HTML on current page.")
            return []

        soup = BeautifulSoup(table_html, "html.parser")
        table = soup.find("table", id=re.compile(r"gvBusinessActivity", re.I))
        if not table:
            print("[RAKEZ] No activity table found on current page.")
            return []

        rows_data = []
        rows = table.find_all("tr")

        for row in rows:
            cells = row.find_all(["td", "th"])
            cell_texts = [self._normalize_text(c.get_text(" ", strip=True)) for c in cells]
            cell_texts = [x for x in cell_texts if x]

            if not cell_texts:
                continue

            joined = " | ".join(cell_texts).lower()

            # skip header row
            if "activity code" in joined and "activity name" in joined:
                continue

            # we expect at least 5 fields:
            # Zone, Activity Code, Activity Name, License Type, Activity Group
            if len(cell_texts) >= 5:
                rows_data.append(cell_texts[:5])

        return rows_data

    def _select_freezone(self, page):
        print("[RAKEZ] Looking for zone dropdown...")

        possible_selectors = [
            "select[name*='zone' i]",
            "select[id*='zone' i]",
            "select.form-select",
            "select",
        ]

        for css in possible_selectors:
            try:
                selects = page.locator(css)
                count = selects.count()

                for i in range(count):
                    sel = selects.nth(i)

                    try:
                        options = sel.locator("option")
                        opt_count = options.count()
                        if opt_count == 0:
                            continue

                        option_texts = []
                        matched = False

                        for j in range(opt_count):
                            raw_text = self._normalize_text(options.nth(j).inner_text())
                            option_texts.append(raw_text)
                            zone_txt = self._normalize_zone(raw_text)

                            print(f"[RAKEZ] Checking zone option: raw='{raw_text}' normalized='{zone_txt}'")

                            if zone_txt in {"freezone", "free zone"}:
                                val = options.nth(j).get_attribute("value")
                                print(f"[RAKEZ] Selecting Free Zone using option: {raw_text}")

                                if val:
                                    sel.select_option(value=val)
                                else:
                                    sel.select_option(label=raw_text)

                                page.wait_for_timeout(4000)
                                matched = True
                                break

                        print(f"[RAKEZ] Dropdown options found: {option_texts[:20]}")

                        if matched:
                            return True

                    except Exception:
                        continue

            except Exception:
                continue

        return False

    def _maximize_records_per_page(self, page):
        """
        Select the highest available "records per page" option (e.g. 40
        instead of the default 20). This directly halves (or better) the
        total number of pages we have to paginate through, which is the
        single biggest lever for speeding up the full scrape.

        Found generically (not via a hardcoded control ID) because RAKEZ's
        DNN control IDs shift between renders/deployments — the same
        reason the pager ID broke earlier. We identify the right <select>
        by the fact that ALL its options are plain numbers (10, 20, 40...),
        which distinguishes it from the Zone dropdown (text options) and
        anything else on the page.
        """
        print("[RAKEZ] Looking for records-per-page dropdown...")

        try:
            selects = page.locator("select")
            count = selects.count()

            best_select = None
            best_value = None
            best_option_texts = None

            for i in range(count):
                sel = selects.nth(i)
                try:
                    options = sel.locator("option")
                    opt_count = options.count()
                    if opt_count == 0:
                        continue

                    option_texts = []
                    all_numeric = True
                    for j in range(opt_count):
                        raw_text = self._normalize_text(options.nth(j).inner_text())
                        option_texts.append(raw_text)
                        if not raw_text.isdigit():
                            all_numeric = False

                    if not all_numeric or len(option_texts) < 2:
                        continue

                    numeric_values = [int(t) for t in option_texts]
                    local_max = max(numeric_values)

                    if best_value is None or local_max > best_value:
                        best_value = local_max
                        best_select = sel
                        best_option_texts = option_texts

                except Exception:
                    continue

            if best_select is None:
                print("[RAKEZ] No records-per-page dropdown found — continuing with default page size.")
                return False

            print(f"[RAKEZ] Records-per-page options found: {best_option_texts}. Selecting max: {best_value}")
            best_select.select_option(label=str(best_value))
            page.wait_for_timeout(4000)

            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            print(f"[RAKEZ] Records per page set to {best_value}.")
            return True

        except Exception as e:
            print(f"[RAKEZ] Could not set records-per-page: {e}")
            return False

    def _go_to_next_page(self, page, current_page_num):
        """
        Move to next page using ASP.NET __doPostBack instead of click.

        Generic version: does NOT depend on a specific DNN control ID
        (IDs like 'dnn_ctr3776_...' can shift between renders/deployments
        depending on module placement, caching, or session state).
        Instead this scans EVERY <a> on the page whose href contains
        '__doPostBack' and matches by visible text, with full diagnostic
        printing so the real pager structure is visible if it changes
        again in the future.

        Returns True if moved, else False.
        """
        next_page = current_page_num + 1

        try:
            # RETRY LOOP: a single slow/missed postback (DNN pages carry
            # heavy ViewState and can occasionally lag — worse now that
            # we're pulling 100 rows/page instead of 20) shouldn't kill
            # the whole run. Try up to 3 times before giving up on this
            # page transition.
            #
            # IMPORTANT: the pager is RE-SCANNED FRESH on every attempt
            # (not cached from before the loop). Caching the target link
            # across retries was the bug that caused a later attempt to
            # click the wrong element (a stale index pointed at '<' after
            # the DOM had already shifted) and, worse, to hang for 120s
            # clicking into a node mid-replacement by an overlapping
            # UpdatePanel response.
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):

                # Let the page settle before clicking — this now applies
                # even on the FIRST attempt. With 100 rows/page instead of
                # 20, the table can still be finishing layout/reflow work
                # right after landing on a page, and clicking too early
                # into that busy period is consistent with the click
                # dispatch itself hanging (pre-click checks pass instantly,
                # but the actual click never completes) — a classic sign
                # of a CPU-constrained browser process, more likely on a
                # smaller/burstable EC2 instance under load.
                try:
                    page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    pass
                page.wait_for_timeout(1200 if attempt == 1 else 1500)

                # First check: did a PREVIOUS attempt actually already
                # succeed, just too slowly for our detection window to
                # catch it in time? If the pager already shows next_page
                # as the active (disabled) page, don't click again —
                # clicking again would move PAST the page we want.
                already_there = False
                try:
                    already_there = page.evaluate(
                        """
                        (nextPage) => {
                            const links = Array.from(document.querySelectorAll("a[href*='__doPostBack']"));
                            return links.some(a => {
                                const txt = (a.textContent || '').trim();
                                const cls = a.className || '';
                                return txt === String(nextPage) && cls.includes('page_disabled');
                            });
                        }
                        """,
                        arg=next_page,
                    )
                except Exception:
                    pass

                if already_there:
                    print(f"[RAKEZ] Page {next_page} already active (caught up from a previous attempt) — skipping click.")
                    page.wait_for_timeout(300)
                    return True

                # Re-scan the pager fresh — do NOT reuse a link reference
                # from an earlier attempt or from before this loop.
                try:
                    candidates = page.evaluate(
                        """
                        () => Array.from(document.querySelectorAll("a[href*='__doPostBack']")).map((a, i) => ({
                            index: i,
                            text: (a.textContent || '').trim(),
                            cls: a.className || ''
                        }))
                        """
                    )
                except Exception as e:
                    print(f"[RAKEZ] Could not scan pager on attempt {attempt}: {e}")
                    continue

                target_index = None
                matched_text = None

                for c in candidates:
                    if c["text"] == str(next_page) and "page_disabled" not in c["cls"]:
                        target_index = c["index"]
                        matched_text = c["text"]
                        break

                if target_index is None:
                    for c in candidates:
                        if c["text"].strip().lower() in {"next", ">", "»", "next »"} and "page_disabled" not in c["cls"]:
                            target_index = c["index"]
                            matched_text = c["text"]
                            break

                if target_index is None:
                    print(f"[RAKEZ] No matching pagination link found for page {next_page} on attempt {attempt}.")
                    print(f"[RAKEZ] Postback link candidates: {[(c['text'], c['cls']) for c in candidates]}")
                    continue

                target_locator = page.locator("a[href*='__doPostBack']").nth(target_index)

                print(f"[RAKEZ] Moving to page {next_page} by clicking link '{matched_text}' (attempt {attempt}/{max_attempts})")

                try:
                    old_first_row = page.locator("table[id*='gvBusinessActivity'] tr").nth(1).inner_text()
                except Exception:
                    old_first_row = ""

                # IMPORTANT: click the element directly instead of invoking
                # __doPostBack via page.evaluate(). Playwright's evaluate()
                # runs JS in strict mode, and ASP.NET's legacy
                # PageRequestManager script uses `arguments.callee`
                # internally, which throws in strict mode. A real click
                # fires the javascript: href in normal page scope, exactly
                # like a human clicking it, so it works fine.
                #
                # NOTE: explicit short timeout here (not the global 120s
                # default). With 100 rows/page the DOM is bigger and can
                # be mid-replacement by an UpdatePanel response — if the
                # click genuinely can't land, we want to know in ~15s and
                # retry with a fresh pager scan, not hang for 2 minutes.
                try:
                    target_locator.scroll_into_view_if_needed(timeout=25000)
                    target_locator.click(timeout=25000)
                except Exception as e:
                    print(f"[RAKEZ] Click attempt {attempt} failed: {e}")
                    continue

                # Let the AJAX postback actually finish before checking
                # anything. With bigger 100-row payloads this can
                # legitimately take longer than before.
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass

                # Primary success signal: the pager's active-page indicator
                # moves. When page N is current, its pager link typically
                # gets 'page_disabled' (i.e. "you are here, not clickable").
                pager_flipped = False
                try:
                    page.wait_for_function(
                        """
                        (nextPage) => {
                            const links = Array.from(document.querySelectorAll("a[href*='__doPostBack']"));
                            return links.some(a => {
                                const txt = (a.textContent || '').trim();
                                const cls = a.className || '';
                                return txt === String(nextPage) && cls.includes('page_disabled');
                            });
                        }
                        """,
                        arg=next_page,
                        timeout=10000,
                    )
                    pager_flipped = True
                except Exception:
                    pass

                # IMPORTANT: the pager's class can flip slightly BEFORE the
                # actual table data finishes updating — they're two separate
                # pieces of the same AJAX response landing in the DOM at
                # slightly different times. Trusting the pager flip alone
                # caused us to scrape stale (previous-page) table data while
                # the pager already said we'd moved on. So we ALWAYS also
                # confirm the row text actually changed, regardless of
                # whether the pager already flipped.
                row_changed = False
                try:
                    page.wait_for_function(
                        """
                        (oldText) => {
                            const row = document.querySelector("table[id*='gvBusinessActivity'] tr:nth-child(2)");
                            return row && row.innerText.trim() !== oldText.trim();
                        }
                        """,
                        arg=old_first_row,
                        timeout=8000,
                    )
                    row_changed = True
                except Exception:
                    pass

                if row_changed:
                    print(f"[RAKEZ] Page {next_page} confirmed loaded (row data changed, pager_flipped={pager_flipped}).")
                    page.wait_for_timeout(200)
                    return True

                print(f"[RAKEZ] Attempt {attempt}/{max_attempts} did not confirm page {next_page} (pager_flipped={pager_flipped}, row_changed=False).")

            print(f"[RAKEZ] Could not confirm navigation to page {next_page} after {max_attempts} attempts. Stopping pagination.")
            return False

        except Exception as e:
            print(f"[RAKEZ] Pagination scan failed: {e}")
            return False

    def scrape(self):
        print("\n[RAKEZ] Starting scraper...")
        all_rows = []

        with sync_playwright() as p:
            # NOTE: switched away from snap Chromium to Playwright's own
            # bundled browser. Snap's confinement (AppArmor/seccomp) adds
            # overhead and has caused unrelated breakage elsewhere (cross-
            # origin iframes on another scraper). Run on the server first:
            #   playwright install chromium --with-deps
            #
            # Also added flags that reduce Chromium's background
            # throttling/backgrounding behavior — these matter more now
            # that we're rendering 100-row pages instead of 20, especially
            # if the EC2 instance is a smaller/burstable type under CPU
            # pressure.
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-setuid-sandbox",
                    "--disable-background-timer-throttling",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding",
                ],
            )

            context = browser.new_context(
                viewport={"width": 1400, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                ),
            )

            page = context.new_page()
            page.set_default_timeout(120000)
            page.set_default_navigation_timeout(120000)

            print(f"[RAKEZ] Opening: {self.URL}")
            page.goto(self.URL, wait_until="domcontentloaded", timeout=120000)
            page.wait_for_timeout(5000)

            # select freezone
            zone_selected = self._select_freezone(page)
            if not zone_selected:
                raise Exception("RAKEZ Freezone option not found in dropdown.")

            print("[RAKEZ] Waiting for activity table after Freezone selection...")
            page.wait_for_timeout(5000)

            # Bump rows-per-page to the max available (e.g. 40 instead of
            # the default 20). This roughly halves the total number of
            # pages we need to paginate through, which is the biggest
            # available speedup for a 180+ page scrape. Non-fatal if it
            # can't be found — we just fall back to the default page size.
            self._maximize_records_per_page(page)

            current_page_num = 1
            seen_page_signatures = set()

            while True:
                print(f"[RAKEZ] Scraping page {current_page_num}...")

                page_rows = self._extract_rows_from_current_page(page)
                print(f"[RAKEZ] Page {current_page_num} rows extracted: {len(page_rows)}")

                # signature to prevent loops
                signature = tuple(tuple(r) for r in page_rows[:5])
                if signature in seen_page_signatures:
                    print("[RAKEZ] Same page content detected again, stopping pagination.")
                    break
                seen_page_signatures.add(signature)

                all_rows.extend(page_rows)

                moved = self._go_to_next_page(page, current_page_num)
                if not moved:
                    print("[RAKEZ] No more pages found.")
                    break

                current_page_num += 1

            context.close()
            browser.close()

        print(f"[RAKEZ] Total raw extracted rows from all pages: {len(all_rows)}")

        # build dataframe
        cleaned = []
        for row in all_rows:
            row = [self._normalize_text(x) for x in row if self._normalize_text(x)]
            if len(row) < 5:
                continue

            record = {
                "Zone": row[0],
                "Activity Code": row[1],
                "Activity Name": row[2],
                "License Type": row[3],
                "Activity Group": row[4],
            }

            if not record["Activity Name"]:
                continue

            cleaned.append(record)

        df = pd.DataFrame(cleaned)

        if df.empty:
            raise Exception("RAKEZ scraper returned no rows after parsing.")

        # keep only freezone
        df["Zone"] = df["Zone"].astype(str).str.strip()
        df = df[df["Zone"].str.lower() == "freezone"]

        # cleanup
        df["Activity Name"] = df["Activity Name"].astype(str).str.strip()
        df = df[df["Activity Name"] != ""]
        df.drop_duplicates(subset=["Activity Code", "Activity Name"], inplace=True)
        df.reset_index(drop=True, inplace=True)

        print(f"[RAKEZ] Final Freezone unique activities: {len(df)}")

        output_dir = "exports"
        os.makedirs(output_dir, exist_ok=True)
        csv_path = os.path.join(output_dir, "rakez_activities.csv")
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"[RAKEZ] CSV saved at: {csv_path}")

        return df