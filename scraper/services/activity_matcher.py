import os
import re

import numpy as np
import pandas as pd

from rapidfuzz import fuzz, process

from concurrent.futures import ThreadPoolExecutor, as_completed

from scraper.services.activity_rag import ActivityRAG
from scraper.services.metadata_ai import MetadataAI
from scraper.services.isic_matcher import ISICMatcher
from scraper.services.logger import safe_print


class ActivityMatcher:

    # =====================================================
    # INIT
    # =====================================================
    def __init__(self):

        BASE_DIR = os.getcwd()

        self.FILE_PATH = os.path.join(
            BASE_DIR, "scraper", "data",
            "Consolidated List of Activities.xlsx"
        )

        self.isic_matcher = ISICMatcher()
        self.rag          = ActivityRAG(self.FILE_PATH)
        self.metadata_ai  = MetadataAI()

    # =====================================================
    # NORMALIZE
    # =====================================================
    def normalize(self, text):

        text = str(text).strip().lower()
        text = re.sub(r"\s+", " ", text)

        return text

    # =====================================================
    # NORMALIZE STRICT
    # =====================================================
    def normalize_strict(self, text):

        text = str(text).strip().lower()
        text = re.sub(r"[^a-z0-9]", "", text)

        return text

    # =====================================================
    # CLEAN ISIC NUMBER
    # "Division 42" → "42"  |  "10.0" → "10"
    # =====================================================
    def clean_isic_number(self, value):

        text = str(value).strip()

        if text.lower() in ("nan", "none", ""):
            return ""

        text = re.sub(
            r"^(division|group|class|section)\s*",
            "",
            text,
            flags=re.IGNORECASE
        ).strip()

        try:
            return str(int(float(text)))
        except Exception:
            return text

    # =====================================================
    # CLEAN ACTIVITY CODE
    # =====================================================
    def clean_number(self, value):

        if pd.isna(value):
            return ""

        text = str(value).strip()

        if text.lower() in ("nan", "none", ""):
            return ""

        try:
            return str(int(float(text)))
        except Exception:
            return text

    # =====================================================
    # IS EMPTY
    # =====================================================
    def is_empty(self, value):

        return str(value).strip().lower() in (
            "", "nan", "none", "null", "n/a"
        )

    # =====================================================
    # FORMAT JURISDICTION
    # =====================================================
    def format_jurisdiction(self, jurisdiction):

        jurisdiction = str(jurisdiction).strip().lower()

        jurisdiction_map = {
            "afz":             "Ajman",
            "ajman free zone": "Ajman",
            "dmcc":            "Dubai",
            "dafza":           "Dubai",
            "shams":           "SHAMS",
            "shams free zone": "SHAMS",
            "ifza":            "IFZA",
            "ancf":            "ANVC",
            "anvc":            "ANVC"
        }

        return jurisdiction_map.get(
            jurisdiction,
            jurisdiction.title()
        )

    # =====================================================
    # GET JURISDICTION DATAFRAME
    # =====================================================
    def get_jurisdiction_dataframe(
        self,
        master_df,
        jurisdiction
    ):

        jurisdiction = self.format_jurisdiction(jurisdiction)

        return master_df[
            master_df["jurisdiction"]
            .astype(str)
            .str.strip()
            .str.lower()
            ==
            jurisdiction.lower()
        ].copy()

    # =====================================================
    # BUILD NAME LIST
    # =====================================================
    def _build_name_list(self, df):

        records   = df.to_dict("records")
        name_list = [
            self.normalize(str(r.get("activity name", "")))
            for r in records
        ]

        return name_list, records

    # =====================================================
    # BATCH FUZZY MATCH — vectorized via cdist
    # fuzz.ratio only — strict character similarity
    # Returns { normalized_query: (record, score) | None }
    # =====================================================
    def _batch_fuzzy_match(
        self,
        query_names,
        name_list,
        records,
        threshold
    ):

        results = {}

        if not query_names or not name_list:
            return results

        try:
            from rapidfuzz.process import cdist as _cdist

            score_matrix = _cdist(
                query_names,
                name_list,
                scorer=fuzz.ratio
            )

            for i, query in enumerate(query_names):

                row_scores = score_matrix[i]
                best_idx   = int(np.argmax(row_scores))
                best_score = float(row_scores[best_idx])

                if best_score >= threshold:
                    results[query] = (records[best_idx], best_score)
                else:
                    results[query] = None

        except ImportError:

            for query in query_names:

                best_score = 0
                best_idx   = -1

                for i, name in enumerate(name_list):
                    score = fuzz.ratio(query, name)
                    if score > best_score:
                        best_score = score
                        best_idx   = i

                if best_score >= threshold and best_idx >= 0:
                    results[query] = (records[best_idx], best_score)
                else:
                    results[query] = None

        return results

    # =====================================================
    # CLASSIFY ONE ACTIVITY (ISIC → GPT)
    # ALWAYS returns a valid isic dict
    # =====================================================
    def _classify_activity(self, activity_name):

        isic_metadata = self.isic_matcher.predict(activity_name)

        if isic_metadata is None:

            print(f"[GPT] {activity_name}")

            isic_metadata = self.metadata_ai.semantic_isic_match(
                activity_name
            )

        isic_metadata["division"] = self.clean_isic_number(
            isic_metadata.get("division", "")
        )
        isic_metadata["group"] = self.clean_isic_number(
            isic_metadata.get("group", "")
        )
        isic_metadata["class"] = self.clean_isic_number(
            isic_metadata.get("class", "")
        )

        return activity_name, isic_metadata

    # =====================================================
    # ASSIGN CODE via RAG
    # =====================================================
    # def _assign_code(self, activity_name):

    #     try:
    #         code, _, _ = self.rag._assign_code(activity_name)
    #         return self.clean_number(code)
    #     except Exception as e:
    #         print(f"[CODE ERROR] {activity_name}: {e}")
    #         return ""

    # =====================================================
    # FIND CODE BY CLASS + GROUP + DIVISION
    # If another activity in master has same ISIC fields
    # → reuse its activity code
    # =====================================================
    def _find_code_by_isic(self, master_df, division, group, cls):

        if not group:
            return ""

        def clean(val):
            try:
                return str(int(float(str(val).strip())))
            except Exception:
                return str(val).strip()

        grp_clean = clean(group)

        mask = master_df["group"].apply(clean) == grp_clean

        matches = master_df[mask]

        for _, row in matches.iterrows():
            code = self.clean_number(row.get("activity code", ""))
            if code:
                print(f"[CODE BY GROUP] group={grp_clean} -> code={code}")
                return code

        print(f"[CODE NO MATCH] group={grp_clean}")
        return ""

    # =====================================================
    # UPDATE ACTIVITIES — main entry point
    #
    # FLOW PER ACTIVITY:
    #  1. Exact duplicate in same jurisdiction     → SKIP
    #  2. Spelling variant >= 92% same jurisdiction → SKIP
    #  3. Global match >= 90%
    #     → copy division/group/class/isic description
    #  4. Truly new
    #     → ISICMatcher → GPT → generate isic description
    #     → code: match by ISIC fields → fallback RAG
    #
    # ALL descriptions stored in "isic description" column
    # GUARANTEE: no row with empty division/group/class
    #            or empty isic description
    # =====================================================
    def update_activities(self, scraped_df, jurisdiction):

        # =================================================
        # LOAD FINAL SHEET
        # =================================================
        master_df = pd.read_excel(
            self.FILE_PATH,
            sheet_name="Final"
        )

        master_df.columns = [
            str(col).strip().lower()
            for col in master_df.columns
        ]

        # Ensure isic description column exists
        if "isic description" not in master_df.columns:
            master_df["isic description"] = ""

        if "activity description" not in master_df.columns:
            master_df["activity description"] = ""

        if "status" not in master_df.columns:
            master_df["status"] = ""

        if scraped_df.empty:
            print("\n❌ Scraped dataframe is empty.")
            return master_df

        # =================================================
        # CLEAN SCRAPED DF
        # =================================================
        scraped_df = scraped_df.copy()

        scraped_df.columns = [
            str(col).strip().lower()
            for col in scraped_df.columns
        ]

        if "activity name" not in scraped_df.columns:
            print("\n❌ Missing 'activity name' column.")
            return master_df

        scraped_df["activity name"] = (
            scraped_df["activity name"]
            .fillna("")
            .astype(str)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )

        scraped_df = scraped_df[scraped_df["activity name"] != ""]

        scraped_df.drop_duplicates(
            subset=["activity name"],
            inplace=True
        )

        scraped_df.reset_index(drop=True, inplace=True)

        # =================================================
        # FORMAT JURISDICTION
        # =================================================
        jurisdiction = self.format_jurisdiction(jurisdiction)

        print("\n" + "=" * 50)
        print(f"PROCESSING   : {jurisdiction}")
        print(f"Total scraped: {len(scraped_df)}")
        print("=" * 50 + "\n")

        # =================================================
        # PRECOMPUTE NAME LISTS (once)
        # =================================================
        jurisdiction_df = master_df[
            master_df["jurisdiction"]
            .astype(str).str.strip().str.lower()
            == jurisdiction.lower()
        ].copy()

        jurisdiction_name_list, jurisdiction_records = (
            self._build_name_list(jurisdiction_df)
        )

        global_name_list, global_records = (
            self._build_name_list(master_df)
        )

        # =================================================
        # CHECK 1: EXACT DUPLICATES
        # =================================================
        exact_existing = set(
            jurisdiction_df["activity name"]
            .astype(str).str.strip().str.lower()
            .tolist()
        )

        scraped_names = scraped_df["activity name"].tolist()

        non_exact = [
            name for name in scraped_names
            if name.lower().strip() not in exact_existing
        ]

        skipped_exact = len(scraped_names) - len(non_exact)

        if skipped_exact:
            print(
                f"[SKIP] {skipped_exact} exact duplicates "
                f"in {jurisdiction}"
            )

        if not non_exact:
            print("Nothing new to process.")
            return master_df

        # =================================================
        # NORMALIZE QUERIES ONCE
        # =================================================
        normalized_queries = [
            self.normalize(name)
            for name in non_exact
        ]

        # =================================================
        # CHECK 2: SPELLING VARIANTS
        # fuzz.ratio >= 92% in same jurisdiction → SKIP
        # =================================================
        print(
            f"[CHECK] Spelling variants "
            f"({len(non_exact)} activities)..."
        )

        spell_results = self._batch_fuzzy_match(
            normalized_queries,
            jurisdiction_name_list,
            jurisdiction_records,
            threshold=92
        )

        not_spelling      = []
        not_spelling_norm = []

        for name, norm in zip(non_exact, normalized_queries):

            match = spell_results.get(norm)

            if match is not None:
                record, score = match
                safe_print(
                    f"[SKIP SPELLING {score:.0f}%] "
                    f"'{name}' -> "
                    f"'{record.get('activity name', '')}'"
                )
            else:
                not_spelling.append(name)
                not_spelling_norm.append(norm)

        if not not_spelling:
            print("Nothing new after spelling check.")
            return master_df

        # =================================================
        # CHECK 3: GLOBAL MATCH
        # fuzz.ratio >= 90% → copy metadata
        # copies: division, group, class, isic description
        # =================================================
        print(
            f"[CHECK] Global match "
            f"({len(not_spelling)} activities)..."
        )

        global_results = self._batch_fuzzy_match(
            not_spelling_norm,
            global_name_list,
            global_records,
            threshold=90
        )

        # =================================================
        # BUCKET: global_reuse vs to_classify
        # =================================================
        global_reuse = {}
        to_classify  = []

        for name, norm in zip(not_spelling, not_spelling_norm):

            match = global_results.get(norm)

            if match is not None:

                record, score = match

                division         = self.clean_isic_number(
                    record.get("division", "")
                )
                group            = self.clean_isic_number(
                    record.get("group", "")
                )
                class_name       = self.clean_isic_number(
                    record.get("class", "")
                )
                isic_description = str(
                    record.get("isic description", "")
                ).strip()
                code             = self.clean_number(
                    record.get("activity code", "")
                )

                # Reuse only if division/group/class complete
                if division and group and class_name:

                    global_reuse[name] = {
                        "division":         division,
                        "group":            group,
                        "class":            class_name,
                        "isic_description": isic_description,
                        "code":             code
                    }

                    print(
                        f"[GLOBAL {score:.0f}%] "
                        f"'{name}' <- "
                        f"'{record.get('activity name', '')}'"
                    )

                    continue

            to_classify.append(name)

        print(
            f"\n[BUCKETS] "
            f"Global copy: {len(global_reuse)} | "
            f"New (GPT): {len(to_classify)}\n"
        )

        # =================================================
        # PARALLEL CLASSIFICATION (new activities only)
        # =================================================
        classification_results = {}

        if to_classify:

            print(
                f"[CLASSIFYING] {len(to_classify)} "
                f"in parallel...\n"
            )

            with ThreadPoolExecutor(max_workers=10) as executor:

                futures = {
                    executor.submit(
                        self._classify_activity, name
                    ): name
                    for name in to_classify
                }

                for future in as_completed(futures):

                    try:
                        name, result = future.result()
                        classification_results[name] = result

                    except Exception as e:
                        name = futures[future]
                        print(f"[CLASSIFY ERROR] {name}: {e}")
                        classification_results[name] = {
                            "division": "",
                            "group":    "",
                            "class":    ""
                        }

        # =================================================
        # COLLECT ALL ACTIVITIES NEEDING isic description
        # =================================================
        needs_description = []

        for name in to_classify:

            isic = classification_results.get(name, {})

            needs_description.append({
                "activity_name": name,
                "division":      isic.get("division", ""),
                "group":         isic.get("group", ""),
                "class_code":    isic.get("class", "")
            })

        global_needs_desc = []

        for name, meta in global_reuse.items():

            if self.is_empty(meta["isic_description"]):

                global_needs_desc.append(name)

                needs_description.append({
                    "activity_name": name,
                    "division":      meta["division"],
                    "group":         meta["group"],
                    "class_code":    meta["class"]
                })

        # =================================================
        # BATCH DESCRIPTION GENERATION
        # =================================================
        description_map = {}

        if needs_description:

            print(
                f"[DESCRIPTIONS] Generating "
                f"{len(needs_description)} isic descriptions "
                f"in batches of 20...\n"
            )

            description_map = (
                self.metadata_ai.generate_descriptions_batch(
                    needs_description,
                    batch_size=20
                )
            )

        # =================================================
        # PARALLEL CODE ASSIGNMENT
        # First try: match by division+group+class in master
        # Fallback:  RAG assignment
        # =================================================
        code_map = {}

        if to_classify:

            def assign_code_smart(name):

                isic     = classification_results.get(name, {})
                division = self.clean_isic_number(
                    isic.get("division", "")
                )
                group    = self.clean_isic_number(
                    isic.get("group", "")
                )
                cls      = self.clean_isic_number(
                    isic.get("class", "")
                )

                # Try to copy code from existing activity
                # with same ISIC fields
                code = self._find_code_by_isic(
                    master_df, division, group, cls
                )

                if code:
                    print(f"[CODE ISIC MATCH] {name} -> {code}")
                    return name, code

                # Fallback to RAG
                code = (
                    meta["code"]
                    or self._find_code_by_isic(master_df, meta["division"], meta["group"], meta["class"])
                    or self._assign_code(name)
                )
                return name, code

            with ThreadPoolExecutor(max_workers=10) as executor:

                futures = {
                    executor.submit(assign_code_smart, name): name
                    for name in to_classify
                }

                for future in as_completed(futures):

                    try:
                        name, code     = future.result()
                        code_map[name] = code
                    except Exception as e:
                        name = futures[future]
                        print(f"[CODE ERROR] {name}: {e}")
                        code_map[name] = ""

        # =================================================
        # BUILD ALL NEW ROWS
        # =================================================
        new_rows = []

        # --- GLOBAL COPY rows ---
        for name, meta in global_reuse.items():

            code     = meta["code"] or self._assign_code(name)
            division = meta["division"]
            group    = meta["group"]
            cls      = meta["class"]

            isic_desc = meta["isic_description"]

            if self.is_empty(isic_desc):
                isic_desc = description_map.get(name, "")

            # Safety net: ISIC fields empty
            if not division or not group or not cls:

                print(f"[FIX ISIC] {name}")

                isic = self.metadata_ai.semantic_isic_match(name)

                division = self.clean_isic_number(
                    isic.get("division", "")
                )
                group    = self.clean_isic_number(
                    isic.get("group", "")
                )
                cls      = self.clean_isic_number(
                    isic.get("class", "")
                )

            # Safety net: description still empty
            if self.is_empty(isic_desc):

                print(f"[FIX DESC] {name}")

                isic_desc = self.metadata_ai.generate_description(
                    name, division, group, cls
                )

            new_rows.append({
                "activity name":        name,
                "activity code":        self.clean_number(code),
                "jurisdiction":         jurisdiction,
                "division":             division,
                "group":                group,
                "class":                cls,
                "isic description":     isic_desc,
                "activity description": "",
                "status":               "Draft"
            })

            print(f"[APPENDED GLOBAL] {name}")

        # --- NEW classified rows ---
        for name in to_classify:

            isic      = classification_results.get(name, {})
            division  = self.clean_isic_number(isic.get("division", ""))
            group     = self.clean_isic_number(isic.get("group", ""))
            cls       = self.clean_isic_number(isic.get("class", ""))
            isic_desc = description_map.get(name, "").strip()
            code      = self.clean_number(code_map.get(name, ""))

            # Safety net: ISIC fields empty
            if not division or not group or not cls:

                print(f"[FIX ISIC] {name}")

                isic2 = self.metadata_ai.semantic_isic_match(name)

                division = self.clean_isic_number(
                    isic2.get("division", "")
                )
                group    = self.clean_isic_number(
                    isic2.get("group", "")
                )
                cls      = self.clean_isic_number(
                    isic2.get("class", "")
                )

            # Safety net: description still empty
            if self.is_empty(isic_desc):

                print(f"[FIX DESC] {name}")

                isic_desc = self.metadata_ai.generate_description(
                    name, division, group, cls
                )

            new_rows.append({
                "activity name":        name,
                "activity code":        code,
                "jurisdiction":         jurisdiction,
                "division":             division,
                "group":                group,
                "class":                cls,
                "isic description":     isic_desc,
                "activity description": "",
                "status":               "Draft"
            })

            print(
                f"[APPENDED NEW] {name} -> "
                f"{isic.get('matched_activity', 'N/A')} "
                f"[{isic.get('method', 'N/A')}]"
            )

        # =================================================
        # WRITE FINAL SHEET ONCE
        # =================================================
        if new_rows:

            master_df = pd.concat(
                [master_df, pd.DataFrame(new_rows)],
                ignore_index=True
            )

            with pd.ExcelWriter(
                self.FILE_PATH,
                engine="openpyxl",
                mode="a",
                if_sheet_exists="replace"
            ) as writer:

                master_df.to_excel(
                    writer,
                    sheet_name="Final",
                    index=False
                )

            print(f"\n✅ Saved {len(new_rows)} new rows.")

        # =================================================
        # SUMMARY
        # =================================================
        print(f"\n{'='*50}")
        print("COMPLETE")
        print(f"Jurisdiction   : {jurisdiction}")
        print(f"New rows added : {len(new_rows)}")
        print(f"Total rows     : {len(master_df)}")
        print(f"{'='*50}\n")

        website_df = master_df[
            master_df["jurisdiction"]
            .astype(str)
            .str.lower()
            ==
            jurisdiction.lower()
        ].copy()

        return website_df