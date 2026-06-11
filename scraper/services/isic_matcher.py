import os
import re

import pandas as pd
from rapidfuzz import fuzz


class ISICMatcher:

    def __init__(self):

        BASE_DIR = os.getcwd()

        self.FILE_PATH = os.path.join(
            BASE_DIR, "scraper", "data",
            "Consolidated List of Activities.xlsx"
        )

        print("\n[ISIC] Loading ISIC Sheet...")

        self.df = pd.read_excel(
            self.FILE_PATH,
            sheet_name="ISIC"
        )

        self.df.columns = [
            str(col).strip().lower()
            for col in self.df.columns
        ]

        self.df["division"] = self.df["division"].ffill()
        self.df["group"]    = self.df["group"].ffill()
        self.df["class"]    = self.df["class"].ffill()

        # Clean ISIC numbers at load time — once
        # "Division 42" → "42"  |  "10.0" → "10"
        for col in ["division", "group", "class"]:
            self.df[col] = self.df[col].apply(
                self._clean_isic_number
            )

        self.df["activity name"] = (
            self.df["activity name"]
            .fillna("").astype(str).str.strip()
        )

        self.df = self.df[self.df["activity name"] != ""]

        print(f"[ISIC] Loaded {len(self.df)} activities")

    # ==========================================
    # CLEAN ISIC NUMBER
    # "Division 42" → "42"
    # "10.0"        → "10"
    # ==========================================
    def _clean_isic_number(self, value):

        text = str(value).strip()

        if text.lower() in ("nan", "none", ""):
            return ""

        # Strip word prefix
        text = re.sub(
            r"^(division|group|class|section)\s*",
            "",
            text,
            flags=re.IGNORECASE
        ).strip()

        # Strip float suffix
        try:
            return str(int(float(text)))
        except Exception:
            return text

    # ==========================================
    # NORMALIZE
    # ==========================================
    def normalize(self, text):

        text = str(text).lower().strip()
        text = text.replace("&amp;", "and")
        text = re.sub(r"&", "and", text)
        text = re.sub(r"\s+", " ", text)

        return text

    # ==========================================
    # BUILD RESPONSE
    # ==========================================
    def build_response(self, row, confidence, method):

        return {
            "division":
                str(row.get("division", "")).strip(),
            "group":
                str(row.get("group", "")).strip(),
            "class":
                str(row.get("class", "")).strip(),
            "matched_activity":
                str(row.get("activity name", "")).strip(),
            "confidence":
                confidence,
            "method":
                method
        }

    # ==========================================
    # EXACT MATCH
    # ==========================================
    def exact_match(self, activity_name):

        match = self.df[
            self.df["activity name"].apply(self.normalize)
            == self.normalize(activity_name)
        ]

        if match.empty:
            return None

        return self.build_response(match.iloc[0], 100, "EXACT")

    # ==========================================
    # FUZZY MATCH
    # threshold=95 → only very confident matches
    # below 95     → return None → GPT takes over
    # ==========================================
    def fuzzy_match(self, activity_name, threshold=95):

        target = self.normalize(activity_name)

        best_row   = None
        best_score = 0

        for _, row in self.df.iterrows():

            existing = self.normalize(row["activity name"])

            score = max(
                fuzz.token_sort_ratio(target, existing),
                fuzz.token_set_ratio(target, existing),
                fuzz.partial_ratio(target, existing)
            )

            if score > best_score:
                best_score = score
                best_row   = row

        if best_row is None:
            return None

        if best_score < threshold:
            print(
                f"[ISIC] {best_score}% < {threshold}% "
                f"for '{activity_name}' → GPT"
            )
            return None

        return self.build_response(best_row, best_score, "FUZZY")

    # ==========================================
    # PREDICT
    # ==========================================
    def predict(self, activity_name):

        if not activity_name:
            return None

        activity_name = str(activity_name).strip()

        exact = self.exact_match(activity_name)

        if exact:
            return exact

        return self.fuzzy_match(activity_name, threshold=95)