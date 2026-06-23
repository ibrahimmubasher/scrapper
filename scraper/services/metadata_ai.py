# ============================================================
# FIX for scraper/services/metadata_ai.py
#
# PROBLEM: MetadataAI.__init__() ignored the file path used
# by ActivityMatcher (which copies the Excel to a temp file)
# and instead always re-read directly from
# scraper/data/Consolidated List of Activities.xlsx
# via os.getcwd().
#
# This meant TWO different processes could be reading /
# writing to / locking the SAME original file at once:
#   - ActivityMatcher._prepare_working_workbook() copying it
#   - MetadataAI._load_isic_activities() reading it directly
#
# On some filesystems (and especially under concurrent access
# patterns Railway's containers can exhibit), this can cause
# pandas/openpyxl to stall indefinitely with no error and no
# output — exactly the symptom we saw.
#
# FIX: Accept an optional file_path argument so MetadataAI
# uses the SAME safe temp-copied file as ISICMatcher and RAG.
# ============================================================

import os
import re
import json
import threading

import numpy as np
import pandas as pd

from openai import OpenAI
from sklearn.metrics.pairwise import cosine_similarity


class MetadataAI:

    def __init__(self, file_path=None):

        self.cache_lock = threading.Lock()

        BASE_DIR = os.getcwd()

        # ── FIX: use passed-in path if provided ──────────
        if file_path:
            self.FILE_PATH = file_path
        else:
            self.FILE_PATH = os.path.join(
                BASE_DIR, "scraper", "data",
                "Consolidated List of Activities.xlsx"
            )

        self.EMBEDDINGS_PATH = os.path.join(
            BASE_DIR, "scraper", "data",
            "embeddings.npy"
        )

        self.NAMES_PATH = os.path.join(
            BASE_DIR, "scraper", "data",
            "activity_names.npy"
        )

        self.CACHE_PATH = os.path.join(
            BASE_DIR, "scraper", "data",
            "gpt_cache.json"
        )

        self.EMBEDDING_MODEL = "text-embedding-3-small"

        print("[MetadataAI] Initializing...")
        print(f"[MetadataAI] Reading from: {self.FILE_PATH}")
        print(f"[MetadataAI] File exists: {os.path.exists(self.FILE_PATH)}")

        # ============================================
        # OPENAI CLIENT
        # ============================================
        self.client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY")
        )

        print("[MetadataAI] OpenAI client created")

        # ============================================
        # LOAD GPT CACHE
        # ============================================
        self.gpt_cache = {}

        if os.path.exists(self.CACHE_PATH):

            with open(self.CACHE_PATH, "r") as f:
                self.gpt_cache = json.load(f)

            print(
                f"[MetadataAI] Loaded "
                f"{len(self.gpt_cache)} cached results"
            )

        # ============================================
        # LOAD ISIC ACTIVITIES ONCE
        # ============================================
        print("[MetadataAI] About to read ISIC sheet...")

        self.isic_activities = self._load_isic_activities()

        print(
            f"[MetadataAI] Loaded "
            f"{len(self.isic_activities)} ISIC activities"
        )

        # ============================================
        # LOAD / CREATE EMBEDDINGS ONCE
        # ============================================
        if (
            os.path.exists(self.EMBEDDINGS_PATH)
            and os.path.exists(self.NAMES_PATH)
        ):
            print("[MetadataAI] Loading saved embeddings...")

            self.embeddings = np.load(self.EMBEDDINGS_PATH)

            self.activity_names = np.load(
                self.NAMES_PATH,
                allow_pickle=True
            ).tolist()

        else:
            print("[MetadataAI] Creating embeddings via OpenAI...")

            self.activity_names = [
                a["activity"]
                for a in self.isic_activities
            ]

            self.embeddings = self._get_embeddings_batch(
                self.activity_names
            )

            np.save(self.EMBEDDINGS_PATH, self.embeddings)

            np.save(
                self.NAMES_PATH,
                np.array(self.activity_names)
            )

            print("[MetadataAI] Embeddings saved locally.")

        print("[MetadataAI] Ready.\n")

    # ==================================================
    # CLEAN ISIC NUMBER
    # ==================================================
    def _clean_isic_number(self, value):

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

    # ==================================================
    # IS EMPTY helper
    # ==================================================
    def _is_empty(self, value):

        return str(value).strip().lower() in (
            "", "nan", "none", "null", "n/a"
        )

    # ==================================================
    # LOAD ISIC ACTIVITIES (once at startup)
    # ==================================================
    def _load_isic_activities(self):

        df = pd.read_excel(
            self.FILE_PATH,
            sheet_name="ISIC"
        )

        df.columns = [
            str(col).strip().lower()
            for col in df.columns
        ]

        df["division"] = df["division"].ffill()
        df["group"]    = df["group"].ffill()
        df["class"]    = df["class"].ffill()

        for col in ["division", "group", "class"]:
            df[col] = df[col].apply(self._clean_isic_number)

        df["activity name"] = (
            df["activity name"]
            .fillna("").astype(str).str.strip()
        )

        df = df[df["activity name"] != ""]

        activities = []

        for _, row in df.iterrows():

            activities.append({
                "activity": str(row["activity name"]).strip(),
                "division": str(row["division"]).strip(),
                "group":    str(row["group"]).strip(),
                "class":    str(row["class"]).strip()
            })

        return activities

    # ==================================================
    # SAVE GPT CACHE  (thread-safe)
    # ==================================================
    def _save_cache(self):

        with open(self.CACHE_PATH, "w") as f:
            json.dump(self.gpt_cache, f, indent=2)

    # ==================================================
    # BATCH EMBED (startup only)
    # ==================================================
    def _get_embeddings_batch(self, texts, batch_size=500):

        all_embeddings = []

        for i in range(0, len(texts), batch_size):

            batch = texts[i: i + batch_size]

            response = self.client.embeddings.create(
                input=batch,
                model=self.EMBEDDING_MODEL
            )

            batch_embeddings = [
                item.embedding
                for item in response.data
            ]

            all_embeddings.extend(batch_embeddings)

            print(
                f"[MetadataAI] Embedded "
                f"{min(i + batch_size, len(texts))}"
                f"/{len(texts)}..."
            )

        return np.array(all_embeddings)

    # ==================================================
    # SINGLE EMBED (per query)
    # ==================================================
    def _get_embedding(self, text):

        response = self.client.embeddings.create(
            input=[text],
            model=self.EMBEDDING_MODEL
        )

        return np.array(
            response.data[0].embedding
        ).reshape(1, -1)

    # ==================================================
    # TOP 20 CANDIDATES via cosine similarity
    # ==================================================
    def _get_top_candidates(self, activity_name, top_n=20):

        query_embedding = self._get_embedding(activity_name)

        similarities = cosine_similarity(
            query_embedding,
            self.embeddings
        )[0]

        top_indices = np.argsort(similarities)[::-1][:top_n]

        candidates = []

        for idx in top_indices:

            activity = self.isic_activities[idx]
            score    = round(float(similarities[idx]) * 100, 2)

            candidates.append({
                "activity": activity["activity"],
                "division": activity["division"],
                "group":    activity["group"],
                "class":    activity["class"],
                "score":    score
            })

        return candidates

    # ==================================================
    # SEMANTIC ISIC MATCH
    # ==================================================
    def semantic_isic_match(self, activity_name):

        cache_key = activity_name.strip().lower()

        with self.cache_lock:

            if cache_key in self.gpt_cache:
                print(f"[CACHE] {activity_name}")
                return self.gpt_cache[cache_key]

        candidates = self._get_top_candidates(
            activity_name, top_n=20
        )

        candidate_lines = "\n".join([
            f"{i+1} | {c['activity']}\n"
            f"   Division: {c['division']} | "
            f"Group: {c['group']} | "
            f"Class: {c['class']}"
            for i, c in enumerate(candidates)
        ])

        prompt = f"""You are an official ISIC Revision 4 classification expert.

Your task is to classify a business activity into the SINGLE most appropriate ISIC activity.

Activity to classify: "{activity_name}"

Top matching ISIC candidates:
{candidate_lines}

Rules:
- Match business purpose, not wording.
- Medical must match medical.
- Dental must match dental.
- Consultancy must match consultancy.
- Manufacturing must match manufacturing.
- Retail must match retail.
- Education must match education.

Return ONLY the number of the best match.

Example:
12
"""

        response = self.client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )

        try:
            index = int(
                response.choices[0].message.content.strip()
            ) - 1

            if index < 0 or index >= len(candidates):
                index = 0

        except Exception:
            index = 0

        selected = candidates[index]

        result = {
            "division":         self._clean_isic_number(selected["division"]),
            "group":            self._clean_isic_number(selected["group"]),
            "class":            self._clean_isic_number(selected["class"]),
            "matched_activity": selected["activity"],
            "confidence":       selected["score"],
            "method":           "OPENAI"
        }

        with self.cache_lock:
            self.gpt_cache[cache_key] = result
            self._save_cache()

        return result

    # ==================================================
    # BATCH DESCRIPTION GENERATION
    # ==================================================
    def generate_descriptions_batch(
        self,
        activities,
        batch_size=20
    ):
        results = {}

        for i in range(0, len(activities), batch_size):

            batch = activities[i: i + batch_size]

            activity_lines = "\n\n".join([
                f"{j+1}. Activity: {a['activity_name']}\n"
                f"   Division: {a['division']} | "
                f"Group: {a['group']} | "
                f"Class: {a['class_code']}"
                for j, a in enumerate(batch)
            ])

            prompt = f"""Generate a one-sentence professional ISIC business description for each activity.

Rules:
- Generate ONE description for EVERY activity listed.
- Never skip an activity.
- Exactly one sentence per activity.
- Professional business wording.
- Do NOT mention division/group/class numbers.
- Explain what the business does based on its name and ISIC context.
- Return a numbered list matching the input order, no blank lines between items.

Example:
1. Engages in the retail sale of clothing and apparel to the general public.
2. Provides general medical consultation and treatment services to outpatients.
3. Manufactures and supplies industrial chemicals for commercial use.

Activities:
{activity_lines}
"""

            try:

                response = self.client.chat.completions.create(
                    model="gpt-4.1-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2
                )

                content = (
                    response.choices[0]
                    .message.content
                    .strip()
                )

                parsed = {}

                for line in content.split("\n"):

                    line = line.strip()

                    if not line:
                        continue

                    m = re.match(
                        r"^(\d+)[\.\)\:\-]\s*(.+)",
                        line
                    )

                    if m:
                        num          = int(m.group(1))
                        desc         = m.group(2).strip()
                        parsed[num]  = desc

                for j, activity in enumerate(batch):

                    description = parsed.get(j + 1, "").strip()

                    if self._is_empty(description):

                        print(
                            f"[DESC FALLBACK] "
                            f"{activity['activity_name']}"
                        )

                        description = self._generate_single_description(
                            activity["activity_name"],
                            activity["division"],
                            activity["group"],
                            activity["class_code"]
                        )

                    results[activity["activity_name"]] = description

            except Exception as e:

                print(f"[DESC BATCH ERROR] {e}")

                for activity in batch:

                    results[activity["activity_name"]] = (
                        self._generate_single_description(
                            activity["activity_name"],
                            activity["division"],
                            activity["group"],
                            activity["class_code"]
                        )
                    )

            print(
                f"[MetadataAI] Descriptions: "
                f"{min(i + batch_size, len(activities))}"
                f"/{len(activities)}"
            )

        return results

    # ==================================================
    # SINGLE DESCRIPTION FALLBACK
    # ==================================================
    def _generate_single_description(
        self,
        activity_name,
        division,
        group,
        class_code
    ):

        prompt = f"""Generate a one-sentence professional business description.

Activity: {activity_name}
Division: {division} | Group: {group} | Class: {class_code}

Rules:
- Exactly 1 sentence.
- Professional wording.
- Do NOT mention division/group/class numbers.
- Explain what the business does.
- Never return empty, null, N/A.

Return only the sentence.
"""

        try:

            response = self.client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )

            desc = response.choices[0].message.content.strip()

            if desc and not self._is_empty(desc):
                return desc

            return (
                f"Provides services related to "
                f"{activity_name}."
            )

        except Exception as e:

            print(f"[DESC SINGLE ERROR] {activity_name}: {e}")

            return (
                f"Provides services related to "
                f"{activity_name}."
            )

    # ==================================================
    # PUBLIC SINGLE DESCRIPTION (compatibility)
    # ==================================================
    def generate_description(
        self,
        activity_name,
        division,
        group_code,
        class_code
    ):

        result = self.generate_descriptions_batch([{
            "activity_name": activity_name,
            "division":      division,
            "group":         group_code,
            "class_code":    class_code
        }])

        return result.get(activity_name, "")