"""
src/analysis/sentiment.py

Třívrstá sentiment analýza pro mix jazyků.
  Preprocessing: emoji → text, hashtagy → slova, čištění
  Vrstva 1:      Kontextový slovník (context_lexicon.json)
  Vrstva 2:      VADER na přeloženém textu
  Finální skóre: vážený průměr obou vrstev
"""

import json
import re
import time
from pathlib import Path

import emoji
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from langdetect import detect, LangDetectException
from deep_translator import GoogleTranslator

from src.core.database import DatabaseManager


# --- Konfigurace vah ---
LEXICON_WEIGHT = 0.55
VADER_WEIGHT   = 0.45

POSITIVE_THRESHOLD =  0.05
NEGATIVE_THRESHOLD = -0.05

LEXICON_PATH = Path(__file__).parent / "context_lexicon.json"

# Placeholder texty které přeskočíme
PLACEHOLDERS = frozenset({
    "[OBSAHUJE VIDEO]",
    "[OBSAHUJE FOTKU]",
    "[OBSAHUJE MÉDIA/GIF]",
})


class SentimentAnalyzer:
    def __init__(self):
        self.vader = SentimentIntensityAnalyzer()
        self.db = DatabaseManager()
        self.lexicon = self._load_lexicon()
        self._ensure_columns()

    # ------------------------------------------------------------------
    # Načtení kontextového slovníku
    # ------------------------------------------------------------------
    def _load_lexicon(self) -> dict:
        flat = {}
        if not LEXICON_PATH.exists():
            print(f"[SENTIMENT] Varování: Slovník nenalezen ({LEXICON_PATH}). Bude použit pouze VADER.")
            return flat
        try:
            with open(LEXICON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            skipped = 0
            for category, entries in data.items():
                # Přeskočit komentáře (klíče začínající _comment nebo _)
                if category.startswith("_"):
                    continue
                if not isinstance(entries, dict):
                    continue
                for phrase, score in entries.items():
                    # Přeskočit jakoukoliv hodnotu, která není číslo
                    try:
                        flat[phrase.lower().strip()] = float(score)
                    except (ValueError, TypeError):
                        skipped += 1

            if skipped:
                print(f"[SENTIMENT] Varování: Přeskočeno {skipped} nečíselných hodnot ve slovníku.")
            print(f"[SENTIMENT] Slovník načten: {len(flat)} výrazů.")

        except json.JSONDecodeError as e:
            print(f"[SENTIMENT ERROR] Slovník má neplatný JSON formát: {e}")
        except Exception as e:
            print(f"[SENTIMENT ERROR] Načtení slovníku selhalo: {e}")
        return flat

    # ------------------------------------------------------------------
    # DB migrace
    # ------------------------------------------------------------------
    def _ensure_columns(self):
        try:
            self.db.cursor.execute("PRAGMA table_info(comments)")
            existing = [row[1] for row in self.db.cursor.fetchall()]
            for col, col_type in {
                "sentiment_score": "REAL",
                "sentiment_label": "TEXT",
                "sentiment_lang":  "TEXT",
            }.items():
                if col not in existing:
                    self.db.cursor.execute(f"ALTER TABLE comments ADD COLUMN {col} {col_type}")
                    print(f"[SENTIMENT] Přidán sloupec '{col}'.")
            self.db.conn.commit()
        except Exception as e:
            print(f"[SENTIMENT ERROR] Migrace DB selhala: {e}")

    # ------------------------------------------------------------------
    # PREPROCESSING
    # ------------------------------------------------------------------
    def _split_hashtag(self, tag: str) -> str:
        tag = tag.lstrip("#")
        tag = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', tag)
        tag = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', ' ', tag)
        tag = re.sub(r'(?<=\D)(?=\d)|(?<=\d)(?=\D)', ' ', tag)
        return tag.lower().strip()

    def _emojis_to_text(self, text: str) -> str:
        demojized = emoji.demojize(text, delimiters=(" :", ": "))
        demojized = re.sub(r':([^:]+):', lambda m: m.group(1).replace('_', ' '), demojized)
        return demojized

    def preprocess(self, text: str) -> str:
        if not text:
            return ""
        text = self._emojis_to_text(text)
        text = re.sub(r'https?://\S+|www\.\S+', '', text)
        text = re.sub(r'@\w+', '', text)
        text = re.sub(r'#\w+', lambda m: ' ' + self._split_hashtag(m.group(0)) + ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    # ------------------------------------------------------------------
    # Vrstva 1 — kontextový slovník
    # ------------------------------------------------------------------
    def _lexicon_score(self, text: str) -> float | None:
        if not self.lexicon:
            return None

        text_lower = text.lower()
        matches = []

        for phrase, score in self.lexicon.items():
            if phrase in text_lower:
                weight = len(phrase.split())
                matches.append((score, weight))

        if not matches:
            return None

        total_weight = sum(w for _, w in matches)
        weighted_sum = sum(s * w for s, w in matches)
        return weighted_sum / total_weight

    # ------------------------------------------------------------------
    # Detekce jazyka
    # ------------------------------------------------------------------
    def _detect_language(self, text: str) -> str:
        clean = re.sub(r'[^\w\s]', '', text, flags=re.UNICODE).strip()
        if len(clean) < 4:
            return "unknown"
        try:
            return detect(text)
        except LangDetectException:
            return "unknown"

    # ------------------------------------------------------------------
    # Překlad do angličtiny
    # ------------------------------------------------------------------
    def _translate_to_en(self, text: str, source_lang: str) -> str:
        try:
            result = GoogleTranslator(source=source_lang, target="en").translate(text)
            return result if result else text
        except Exception:
            return text

    # ------------------------------------------------------------------
    # Label ze skóre
    # ------------------------------------------------------------------
    def _score_to_label(self, score: float) -> str:
        if score >= POSITIVE_THRESHOLD:
            return "positive"
        elif score <= NEGATIVE_THRESHOLD:
            return "negative"
        return "neutral"

    # ------------------------------------------------------------------
    # Hlavní metoda — analýza jednoho textu
    # ------------------------------------------------------------------
    def analyze_text(self, text: str) -> tuple[float, str, str]:
        """Vrátí (compound_score, label, detected_lang)."""
        if not text or text.strip() in PLACEHOLDERS:
            return 0.0, "neutral", "unknown"

        processed = self.preprocess(text)

        if not processed or len(processed.strip()) < 2:
            return 0.0, "neutral", "unknown"

        lex_score = self._lexicon_score(processed)

        lang = self._detect_language(processed)
        text_for_vader = (
            self._translate_to_en(processed, lang)
            if lang not in ("en", "unknown")
            else processed
        )
        vader_score = self.vader.polarity_scores(text_for_vader)["compound"]

        if lex_score is not None:
            final_score = (lex_score * LEXICON_WEIGHT) + (vader_score * VADER_WEIGHT)
        else:
            final_score = vader_score

        final_score = round(max(-1.0, min(1.0, final_score)), 4)
        return final_score, self._score_to_label(final_score), lang

    # ------------------------------------------------------------------
    # Hromadná analýza čekajících komentářů
    # ------------------------------------------------------------------
    def analyze_pending(self, callback=None) -> int:
        try:
            self.db.cursor.execute(
                "SELECT id, text_content FROM comments WHERE sentiment_score IS NULL"
            )
            rows = self.db.cursor.fetchall()
        except Exception as e:
            print(f"[SENTIMENT ERROR] Nepodařilo se načíst komentáře: {e}")
            return 0

        total = len(rows)
        if total == 0:
            print("[SENTIMENT] Žádné nové komentáře ke zpracování.")
            return 0

        print(f"[SENTIMENT] Zahajuji analýzu {total} komentářů (slovník: {len(self.lexicon)} výrazů)...")
        processed = 0

        for i, (comment_id, text) in enumerate(rows):
            try:
                score, label, lang = self.analyze_text(text or "")

                self.db.cursor.execute(
                    """UPDATE comments
                       SET sentiment_score = ?, sentiment_label = ?, sentiment_lang = ?
                       WHERE id = ?""",
                    (score, label, lang, comment_id)
                )

                if (i + 1) % 50 == 0:
                    self.db.conn.commit()

                processed += 1
                if callback:
                    callback(processed, total)

                if lang not in ("en", "unknown") and i % 10 == 0:
                    time.sleep(0.3)

            except Exception as e:
                print(f"[SENTIMENT ERROR] Chyba u komentáře {comment_id}: {e}")
                continue

        self.db.conn.commit()
        print(f"[SENTIMENT] Hotovo. Zpracováno {processed}/{total} komentářů.")
        return processed

    # ------------------------------------------------------------------
    # Jednorázová analýza po scrape
    # ------------------------------------------------------------------
    def analyze_single(self, comment_id: str, text: str):
        try:
            score, label, lang = self.analyze_text(text or "")
            self.db.cursor.execute(
                """UPDATE comments
                   SET sentiment_score = ?, sentiment_label = ?, sentiment_lang = ?
                   WHERE id = ?""",
                (score, label, lang, comment_id)
            )
            self.db.conn.commit()
        except Exception as e:
            print(f"[SENTIMENT ERROR] analyze_single selhal: {e}")

    # ------------------------------------------------------------------
    # Statistiky per uživatel
    # ------------------------------------------------------------------
    def get_stats_for_user(self, platform: str, username: str) -> dict:
        try:
            self.db.cursor.execute(
                """
                SELECT
                    COUNT(*)                     AS total,
                    AVG(c.sentiment_score)       AS avg_score,
                    SUM(CASE WHEN c.sentiment_label = 'positive' THEN 1 ELSE 0 END) AS positive,
                    SUM(CASE WHEN c.sentiment_label = 'negative' THEN 1 ELSE 0 END) AS negative,
                    SUM(CASE WHEN c.sentiment_label = 'neutral'  THEN 1 ELSE 0 END) AS neutral
                FROM comments c
                JOIN posts p ON c.post_id = p.id
                JOIN users u ON p.user_id = u.id
                WHERE u.platform = ? AND u.username = ?
                  AND c.sentiment_score IS NOT NULL
                """,
                (platform, username)
            )
            row = self.db.cursor.fetchone()
            if not row or row[0] == 0:
                return {}
            return {
                "total":     row[0],
                "avg_score": round(row[1], 3) if row[1] is not None else 0.0,
                "positive":  row[2] or 0,
                "negative":  row[3] or 0,
                "neutral":   row[4] or 0,
            }
        except Exception as e:
            print(f"[SENTIMENT ERROR] get_stats_for_user: {e}")
            return {}

    # ------------------------------------------------------------------
    # Přidání výrazu do slovníku za běhu
    # ------------------------------------------------------------------
    def add_to_lexicon(self, phrase: str, score: float, save: bool = True):
        phrase = phrase.lower().strip()
        self.lexicon[phrase] = float(score)

        if save and LEXICON_PATH.exists():
            try:
                with open(LEXICON_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if "custom" not in data:
                    data["custom"] = {}
                data["custom"][phrase] = score
                with open(LEXICON_PATH, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"[SENTIMENT] Přidáno do slovníku: '{phrase}' = {score}")
            except Exception as e:
                print(f"[SENTIMENT ERROR] Uložení do slovníku selhalo: {e}")