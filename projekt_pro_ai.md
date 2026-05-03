## Soubor: requirements.txt
```txt
DrissionPage
customtkinter
keyboard
pillow
requests
playwright-stealth
playwright
vaderSentiment
langdetect
deep-translator
emoji
pytesseract
wordcloud
matplotlib
psutil
```

## Soubor: social_bot\main.py
```py
from src.gui.app import App

if __name__ == "__main__":
    try:
        app = App()
        app.update()
        app.mainloop()
    except KeyboardInterrupt:
        print("\n[INFO] Aplikace byla ukončena uživatelem (CTRL+C).")
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Aplikace spadla: {e}")
```

## Soubor: social_bot\src\analysis\image_ocr.py
```py
"""
src/analysis/image_ocr.py

OCR analýza obrázků z příspěvků a komentářů.
  1. Stažení obrázku z media_url
  2. Preprocessing (kontrast, převod na šedou) pro lepší OCR
  3. Tesseract OCR s automatickou detekcí jazyka
  4. Předání extrahovaného textu do SentimentAnalyzer
  5. Uložení výsledků do DB (media_text, media_sentiment_score, media_sentiment_label)
"""

import re
import time
import pytesseract
import requests
from io import BytesIO
from PIL import Image, ImageFilter, ImageEnhance
from pathlib import Path
from src.core.database import DatabaseManager
from src.analysis.sentiment import SentimentAnalyzer

# Cesta k tesseract.exe — standardní Windows instalace
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Jazyky pro OCR — podle dostupných .traineddata souborů
# Tesseract formát: "eng+ces+slk+spa"
OCR_LANGUAGES = "eng+ces+slk+spa"

# Minimální délka extrahovaného textu aby mělo smysl ho analyzovat
MIN_TEXT_LENGTH = 8

# Timeout pro stahování obrázků (sekundy)
DOWNLOAD_TIMEOUT = 10


class ImageOCRAnalyzer:
    def __init__(self):
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
        self.db = DatabaseManager()
        self.sentiment = SentimentAnalyzer()
        self._ensure_columns()
        self._verify_tesseract()

    # ------------------------------------------------------------------
    # Ověření Tesseract instalace
    # ------------------------------------------------------------------
    def _verify_tesseract(self):
        try:
            version = pytesseract.get_tesseract_version()
            print(f"[OCR] Tesseract nalezen: v{version}")
        except Exception as e:
            print(f"[OCR ERROR] Tesseract nenalezen: {e}")
            print(f"[OCR] Zkontroluj cestu: {TESSERACT_CMD}")

    # ------------------------------------------------------------------
    # DB migrace
    # ------------------------------------------------------------------
    def _ensure_columns(self):
        migrations = {
            "posts": [
                ("media_text",              "TEXT"),
                ("media_sentiment_score",   "REAL"),
                ("media_sentiment_label",   "TEXT"),
            ],
            "comments": [
                ("media_text",              "TEXT"),
                ("media_sentiment_score",   "REAL"),
                ("media_sentiment_label",   "TEXT"),
            ],
        }

        for table, columns in migrations.items():
            try:
                self.db.cursor.execute(f"PRAGMA table_info({table})")
                existing = [row[1] for row in self.db.cursor.fetchall()]
                for col, col_type in columns:
                    if col not in existing:
                        self.db.cursor.execute(
                            f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"
                        )
                        print(f"[OCR] Přidán sloupec '{col}' do tabulky {table}.")
                self.db.conn.commit()
            except Exception as e:
                print(f"[OCR ERROR] Migrace tabulky {table} selhala: {e}")

    # ------------------------------------------------------------------
    # Stažení obrázku
    # ------------------------------------------------------------------
    def _download_image(self, url: str) -> Image.Image | None:
        """Stáhne obrázek z URL a vrátí PIL Image objekt."""
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }
            response = requests.get(url, timeout=DOWNLOAD_TIMEOUT, headers=headers)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if "image" not in content_type and not url.lower().endswith(
                (".jpg", ".jpeg", ".png", ".webp", ".gif")
            ):
                return None

            img = Image.open(BytesIO(response.content))
            return img

        except requests.exceptions.Timeout:
            print(f"  -> [OCR] Timeout při stahování: {url[:60]}...")
            return None
        except Exception as e:
            print(f"  -> [OCR] Chyba stahování: {e}")
            return None

    # ------------------------------------------------------------------
    # Preprocessing obrázku pro lepší OCR
    # ------------------------------------------------------------------
    def _preprocess_image(self, img: Image.Image) -> Image.Image:
        """
        Série úprav které zlepšují přesnost Tesseractu:
          1. Převod na RGB (některé PNG jsou RGBA nebo P mode)
          2. Zvětšení pokud je příliš malý
          3. Převod na šedou
          4. Zvýšení kontrastu
          5. Zostření hran
        """
        # 1. Normalizace barevného módu
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        # 2. Zvětšení malých obrázků — Tesseract potřebuje min ~300 DPI ekvivalent
        w, h = img.size
        if w < 600 or h < 600:
            scale = max(600 / w, 600 / h)
            new_w = int(w * scale)
            new_h = int(h * scale)
            img = img.resize((new_w, new_h), Image.LANCZOS)

        # 3. Šedá
        img = img.convert("L")

        # 4. Kontrast
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)

        # 5. Zostření
        img = img.filter(ImageFilter.SHARPEN)

        return img

    # ------------------------------------------------------------------
    # OCR jednoho obrázku
    # ------------------------------------------------------------------
    def extract_text(self, url: str) -> str | None:
        """
        Stáhne obrázek a provede OCR.
        Vrátí extrahovaný text nebo None pokud se nezdaří / text je příliš krátký.
        """
        if not url or url.startswith("blob:"):
            return None

        # Přeskočit video thumbnail URL — ty neobsahují čitelný text
        if any(x in url for x in ["video_thumb", "ext_tw_video", ".mp4", ".m3u8"]):
            return None

        img = self._download_image(url)
        if img is None:
            return None

        try:
            processed = self._preprocess_image(img)

            # Konfigurace Tesseractu:
            # --psm 3 = automatická detekce layoutu stránky (default, vhodné pro obecné obrázky)
            # --oem 3 = LSTM neural net (nejpřesnější)
            config = "--psm 3 --oem 3"

            raw_text = pytesseract.image_to_string(
                processed,
                lang=OCR_LANGUAGES,
                config=config
            )

            # Čištění výstupu
            cleaned = self._clean_ocr_text(raw_text)

            if len(cleaned) < MIN_TEXT_LENGTH:
                return None

            return cleaned

        except Exception as e:
            print(f"  -> [OCR] Tesseract selhal: {e}")
            return None

    # ------------------------------------------------------------------
    # Čištění OCR textu
    # ------------------------------------------------------------------
    def _clean_ocr_text(self, text: str) -> str:
        """
        Odstraní artefakty typické pro OCR výstup:
          - Osamělé znaky a šum
          - Nadbytečné prázdné řádky
          - Speciální znaky které Tesseract generuje jako šum
        """
        if not text:
            return ""

        # Odstranění běžných OCR artefaktů
        text = re.sub(r'[|}{\\]', '', text)

        # Řádky s méně než 2 smysluplnými znaky jsou šum
        lines = text.split('\n')
        clean_lines = []
        for line in lines:
            stripped = line.strip()
            # Zachovat řádky s alespoň 2 alfa-numerickými znaky
            if len(re.findall(r'[a-zA-Z0-9\u00C0-\u024F]', stripped)) >= 2:
                clean_lines.append(stripped)

        result = ' '.join(clean_lines)
        result = re.sub(r'\s+', ' ', result).strip()
        return result

    # ------------------------------------------------------------------
    # Hromadné zpracování příspěvků
    # ------------------------------------------------------------------
    def analyze_pending_posts(self, callback=None) -> int:
        """Zpracuje všechny příspěvky s media_url kde media_text IS NULL."""
        try:
            self.db.cursor.execute("""
                SELECT id, media_url FROM posts
                WHERE media_url IS NOT NULL
                  AND media_url != ''
                  AND media_text IS NULL
                  AND (
                    media_url LIKE '%.jpg%'
                    OR media_url LIKE '%.jpeg%'
                    OR media_url LIKE '%.png%'
                    OR media_url LIKE '%.webp%'
                    OR media_url LIKE '%pbs.twimg%'
                    OR media_url LIKE '%cdninstagram%'
                    OR media_url LIKE '%fbcdn%'
                  )
            """)
            rows = self.db.cursor.fetchall()
        except Exception as e:
            print(f"[OCR ERROR] Načtení příspěvků selhalo: {e}")
            return 0

        return self._process_rows(rows, "posts", callback)

    # ------------------------------------------------------------------
    # Hromadné zpracování komentářů
    # ------------------------------------------------------------------
    def analyze_pending_comments(self, callback=None) -> int:
        """Zpracuje všechny komentáře s media_url kde media_text IS NULL."""
        try:
            self.db.cursor.execute("""
                SELECT id, media_url FROM comments
                WHERE media_url IS NOT NULL
                  AND media_url != ''
                  AND media_text IS NULL
                  AND (
                    media_url LIKE '%.jpg%'
                    OR media_url LIKE '%.jpeg%'
                    OR media_url LIKE '%.png%'
                    OR media_url LIKE '%.webp%'
                    OR media_url LIKE '%pbs.twimg%'
                    OR media_url LIKE '%cdninstagram%'
                    OR media_url LIKE '%fbcdn%'
                  )
            """)
            rows = self.db.cursor.fetchall()
        except Exception as e:
            print(f"[OCR ERROR] Načtení komentářů selhalo: {e}")
            return 0

        return self._process_rows(rows, "comments", callback)

    # ------------------------------------------------------------------
    # Společná logika zpracování
    # ------------------------------------------------------------------
    def _process_rows(self, rows: list, table: str, callback=None) -> int:
        total = len(rows)
        if total == 0:
            print(f"[OCR] Žádné nové obrázky v tabulce {table}.")
            return 0

        print(f"[OCR] Zahajuji OCR analýzu {total} obrázků ({table})...")
        processed = 0
        found_text = 0

        for i, (row_id, media_url) in enumerate(rows):
            # Některé záznamy mají více URL oddělených středníkem (Instagram kolotoče)
            urls = media_url.split(";")
            all_texts = []

            for url in urls:
                url = url.strip()
                if not url:
                    continue

                text = self.extract_text(url)
                if text:
                    all_texts.append(text)
                    print(f"  -> [OCR] Text nalezen ({len(text)} znaků): {text[:60]}...")

                # Krátká pauza aby nedošlo k rate-limit blokaci při stahování
                time.sleep(0.2)

            combined_text = " | ".join(all_texts) if all_texts else None

            # Sentiment extrahovaného textu
            media_score = None
            media_label = None
            if combined_text:
                media_score, media_label, _ = self.sentiment.analyze_text(combined_text)
                found_text += 1

            # Uložit výsledek — i None (abychom příště přeskočili)
            # Používáme sentinel hodnotu "" pro "zpracováno ale nic nenalezeno"
            self.db.cursor.execute(
                f"""UPDATE {table}
                    SET media_text = ?,
                        media_sentiment_score = ?,
                        media_sentiment_label = ?
                    WHERE id = ?""",
                (combined_text or "", media_score, media_label, row_id)
            )

            if (i + 1) % 20 == 0:
                self.db.conn.commit()

            processed += 1
            if callback:
                callback(processed, total)

        self.db.conn.commit()
        print(
            f"[OCR] Hotovo. Zpracováno: {processed} | "
            f"Text nalezen: {found_text} | Bez textu: {processed - found_text}"
        )
        return processed


    def analyze_pending_both(self, callback=None) -> tuple:
        """
        Spustí OCR nad příspěvky i komentáři.
        callback(current, total, phase) — volitelné; phase='posts'|'comments'.
        Vrátí (n_posts, n_comments).
        """
        print("[OCR] === Fáze A: příspěvky ===")
        posts_cb = (lambda c, t: callback(c, t, "posts")) if callback else None
        n_posts = self.analyze_pending_posts(callback=posts_cb)

        print("[OCR] === Fáze B: komentáře ===")
        comments_cb = (lambda c, t: callback(c, t, "comments")) if callback else None
        n_comments = self.analyze_pending_comments(callback=comments_cb)

        print(f"[OCR] Celkem — příspěvky: {n_posts} | komentáře: {n_comments}")
        return n_posts, n_comments
```

## Soubor: social_bot\src\analysis\sentiment.py
```py
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
```

## Soubor: social_bot\src\analysis\text_stats.py
```py
"""
src/analysis/text_stats.py

Textová statistická analýza příspěvků a komentářů profilu.
  - Nejpoužívanější hashtagy (#tag)
  - Nejčastější zmínky (@handle)
  - Top slova (tokenizace + stop-slova)
  - Word cloud jako PIL Image (pro zobrazení v GUI)

Data jsou rozdělena na dva zdroje:
  - owner:      texty vlastních příspěvků sledovaného profilu
  - commenters: texty komentářů pod jeho příspěvky (bez limitu)
"""

import re
from collections import Counter
from io import BytesIO
from src.core.database import DatabaseManager

# Stop-slova — vícejazyčná sada pro EN/CS/SK/ES
STOP_WORDS = {
    # Angličtina
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "not", "no", "so",
    "if", "as", "it", "its", "this", "that", "these", "those", "i", "you",
    "he", "she", "we", "they", "my", "your", "his", "her", "our", "their",
    "what", "which", "who", "when", "where", "why", "how", "all", "just",
    "more", "also", "about", "than", "then", "there", "here", "up", "out",
    "very", "too", "now", "new", "get", "got", "like", "go", "one", "time",
    "people", "into", "see", "him", "her", "them", "us", "me", "s", "t",
    "re", "ve", "ll", "d", "rt",
    # Čeština / Slovenština
    "je", "se", "to", "na", "ve", "že", "ale", "do", "za", "po", "při",
    "pro", "byl", "byla", "bylo", "jsou", "jsem", "jsi", "jsme", "jste",
    "ten", "ta", "ti", "ty", "co", "jak", "kdy", "kde", "kdo", "nebo",
    "také", "tak", "jako", "jeho", "její", "jejich", "tohoto", "této",
    "tento", "tato", "toto", "mezi", "které", "který", "která", "více",
    "si", "mi", "ho", "mu", "ji", "ze", "aby", "jen", "už", "ještě",
    "bude", "být", "tam", "zde", "tady", "mám", "má", "mít", "vše",
    "svou", "své", "svůj", "není", "ani", "když", "pak", "proto", "tedy",
    "přes", "před", "nad", "pod", "bez", "celý", "celá", "celé",
    # Španělština
    "el", "la", "los", "las", "un", "una", "y", "en", "de", "que", "es",
    "con", "por", "su", "sus", "del", "al", "se", "lo", "le", "les",
    "me", "mi", "nos", "te", "tu", "yo", "él", "ella", "pero", "no",
    "si", "más", "ya", "todo", "como", "muy", "fue", "son", "tiene",
    # Obecné
    "rt", "via", "amp", "gt", "lt", "http", "https", "www",
}


class TextStatsAnalyzer:
    def __init__(self):
        self.db = DatabaseManager()

    # ------------------------------------------------------------------
    # Hlavní metoda — vrátí statistiky rozdělené na vlastníka a komentující
    # ------------------------------------------------------------------
    def get_profile_stats(
        self,
        user_id: str,
        posts_limit: int = 100,
        top_n: int = 10,
    ) -> dict:
        """
        Vrátí slovník se statistikami rozdělenými na dvě sekce:
        {
            "owner": {
                "top_hashtags": [...], "top_mentions": [...], "top_words": [...],
                "total_posts": int,
            },
            "commenters": {
                "top_hashtags": [...], "top_mentions": [...], "top_words": [...],
                "total_comments": int,
            },
        }
        """
        texts_posts    = self._fetch_post_texts(user_id, posts_limit)
        texts_comments = self._fetch_comment_texts(user_id)   # bez limitu

        return {
            "owner": {
                "top_hashtags": self._extract_hashtags(texts_posts, top_n),
                "top_mentions": self._extract_mentions(texts_posts, top_n),
                "top_words":    self._extract_top_words(texts_posts, top_n),
                "total_posts":  len(texts_posts),
            },
            "commenters": {
                "top_hashtags": self._extract_hashtags(texts_comments, top_n),
                "top_mentions": self._extract_mentions(texts_comments, top_n),
                "top_words":    self._extract_top_words(texts_comments, top_n),
                "total_comments": len(texts_comments),
            },
        }

    # ------------------------------------------------------------------
    # Načtení textů z DB
    # ------------------------------------------------------------------
    def _fetch_post_texts(self, user_id: str, limit: int) -> list[str]:
        try:
            self.db.cursor.execute(
                """SELECT text_content FROM posts
                   WHERE user_id = ? AND text_content IS NOT NULL
                     AND text_content NOT IN (
                         '[OBSAHUJE VIDEO]','[OBSAHUJE FOTKU]','[OBSAHUJE MÉDIA/GIF]'
                     )
                   ORDER BY timestamp_posted DESC
                   LIMIT ?""",
                (user_id, limit),
            )
            return [row[0] for row in self.db.cursor.fetchall()]
        except Exception as e:
            print(f"[TEXT-STATS ERROR] Načtení příspěvků selhalo: {e}")
            return []

    def _fetch_comment_texts(self, user_id: str) -> list[str]:
        """Načte všechny komentáře pod příspěvky daného profilu — bez limitu."""
        try:
            self.db.cursor.execute(
                """SELECT c.text_content FROM comments c
                   JOIN posts p ON c.post_id = p.id
                   WHERE p.user_id = ? AND c.text_content IS NOT NULL
                     AND c.text_content NOT IN (
                         '[OBSAHUJE VIDEO]','[OBSAHUJE FOTKU]','[OBSAHUJE MÉDIA/GIF]'
                     )
                   ORDER BY c.timestamp_posted DESC""",
                (user_id,),
            )
            return [row[0] for row in self.db.cursor.fetchall()]
        except Exception as e:
            print(f"[TEXT-STATS ERROR] Načtení komentářů selhalo: {e}")
            return []

    # ------------------------------------------------------------------
    # Extrakce hashtagů
    # ------------------------------------------------------------------
    def _extract_hashtags(self, texts: list[str], top_n: int) -> list[tuple]:
        counter = Counter()
        for text in texts:
            tags = re.findall(r'#(\w+)', text, re.UNICODE)
            counter.update(t.lower() for t in tags if len(t) > 1)
        return [(f"#{tag}", count) for tag, count in counter.most_common(top_n)]

    # ------------------------------------------------------------------
    # Extrakce zmínek
    # ------------------------------------------------------------------
    def _extract_mentions(self, texts: list[str], top_n: int) -> list[tuple]:
        counter = Counter()
        for text in texts:
            mentions = re.findall(r'@(\w+)', text, re.UNICODE)
            counter.update(m.lower() for m in mentions if len(m) > 1)
        return [(f"@{mention}", count) for mention, count in counter.most_common(top_n)]

    # ------------------------------------------------------------------
    # Extrakce top slov
    # ------------------------------------------------------------------
    def _extract_top_words(self, texts: list[str], top_n: int) -> list[tuple]:
        counter = Counter()
        for text in texts:
            clean = re.sub(r'https?://\S+', '', text)
            clean = re.sub(r'[@#]\w+', '', clean)
            words = re.findall(r'\b\w{3,}\b', clean, re.UNICODE)
            filtered = [
                w.lower() for w in words
                if w.lower() not in STOP_WORDS
                and not w.isdigit()
                and len(w) >= 3
            ]
            counter.update(filtered)
        return counter.most_common(top_n)

    # ------------------------------------------------------------------
    # Generování Word Cloud jako PNG bytes
    # ------------------------------------------------------------------
    def generate_word_cloud(
        self,
        user_id: str,
        source: str = "commenters",   # "owner" | "commenters" | "both"
        posts_limit: int = 100,
        width: int = 600,
        height: int = 260,
    ) -> bytes | None:
        """
        Vygeneruje word cloud.
        source:
          "owner"      — pouze příspěvky vlastníka
          "commenters" — pouze komentáře (bez limitu)
          "both"       — obojí dohromady
        """
        try:
            from wordcloud import WordCloud
        except ImportError:
            print("[TEXT-STATS] Knihovna 'wordcloud' není nainstalována. "
                  "Spusť: pip install wordcloud matplotlib")
            return None

        texts = []
        if source in ("owner", "both"):
            texts += self._fetch_post_texts(user_id, posts_limit)
        if source in ("commenters", "both"):
            texts += self._fetch_comment_texts(user_id)

        if not texts:
            return None

        combined = " ".join(texts)
        combined = re.sub(r'https?://\S+', '', combined)
        combined = re.sub(r'[@#]\w+', '', combined)
        combined = re.sub(r'\b\w{1,2}\b', '', combined)

        if len(combined.strip()) < 20:
            return None

        try:
            wc = WordCloud(
                width=width,
                height=height,
                background_color="#2c3035",
                color_func=_dark_theme_color,
                stopwords=STOP_WORDS,
                max_words=80,
                prefer_horizontal=0.85,
                min_font_size=10,
                max_font_size=60,
                collocations=False,
            ).generate(combined)

            img = wc.to_image()
            buf = BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()

        except Exception as e:
            print(f"[TEXT-STATS ERROR] Generování word cloud selhalo: {e}")
            return None


# ------------------------------------------------------------------
# Barevná funkce pro dark theme word cloud
# ------------------------------------------------------------------
def _dark_theme_color(word, font_size, position, orientation, random_state=None, **kwargs):
    import random
    palettes = [
        "hsl(210, 80%, 70%)",
        "hsl(210, 60%, 85%)",
        "hsl(0, 0%, 90%)",
        "hsl(210, 40%, 60%)",
        "hsl(0, 0%, 70%)",
        "hsl(195, 70%, 65%)",
    ]
    return random.choice(palettes)
```

## Soubor: social_bot\src\bots\instagram\auth.py
```py
from src.utils.human_input import delay

class InstagramAuthenticator:
    def __init__(self, bot):
        self.bot = bot

    def login(self):
        self.bot.open_url(self.bot.base_url)
        
        print("[IG] Kontroluji stav přihlášení...")
        try:
            home_icon = self.bot.page.locator('svg[aria-label="Domů"], svg[aria-label="Home"]').first
            if home_icon.is_visible(timeout=3000):
                print("[IG] Již přihlášeno (ze session). Přeskakuji login a cookies.")
                return
        except:
            pass

        print("[IG] Kontroluji Cookies okna...")
        cookie_keywords = [
            'Povolit', 'Odmítnout', 'Allow', 'Decline', 
            'Pustit se do toho', 'Get started', 'Přijmout', 'Accept'
        ]
        for word in cookie_keywords:
            try:
                btn = self.bot.page.get_by_text(word, exact=False).first
                if btn.is_visible(timeout=500):
                    btn.click(force=True)
                    print(f"[IG] Odkliknuto cookie tlačítko: '{word}'")
                    delay(1.5)
                    break
            except:
                pass

        all_login_inputs = self.bot.page.locator('input[name="email"], input[name="username"]').all()
        all_pass_inputs = self.bot.page.locator('input[name="pass"], input[name="password"]').all()
        
        login_input = None
        for inp in all_login_inputs:
            if inp.is_visible():
                login_input = inp
                break
                
        pass_input = None
        for inp in all_pass_inputs:
            if inp.is_visible():
                pass_input = inp
                break

        if not login_input:
            print("[IG] Nevidím viditelný login formulář, ale ani znaky přihlášení.")
            return

        print("[IG] Zadávám přihlašovací údaje...")
        login_input.fill("")
        login_input.press_sequentially(self.bot.username, delay=150)
        delay(0.5, 1)
        
        if pass_input:
            pass_input.fill("")
            pass_input.press_sequentially(self.bot.password, delay=150)
        delay(1, 2)
        
        submit_btn = self.bot.page.locator('button[type="submit"]').first
        if submit_btn.is_visible(timeout=2000):
            submit_btn.click(force=True)
        else:
            try:
                login_btn = self.bot.page.get_by_text('Přihlásit', exact=False).first
                if not login_btn.is_visible():
                    login_btn = self.bot.page.get_by_text('Log in', exact=False).first
                if login_btn.is_visible():
                    login_btn.click(force=True)
            except:
                pass
            
        delay(5, 8)
        
        print("[IG] Provádím úklid po přihlášení...")
        self.bot.handle_popups([
            'Nyní ne', 'Not Now', 'Uložit', 'Save', 
            'Pustit se do toho', 'Get started'
        ])
        print("[IG] Přihlašovací proces dokončen.")
```

## Soubor: social_bot\src\bots\instagram\bot.py
```py
from src.core.base_bot import BaseBot
from .auth import InstagramAuthenticator
from .scraper import InstagramScraper

class InstagramBot(BaseBot):
    def __init__(self, username, password, user_id="default", headless=True):
        super().__init__(user_id=user_id, platform="ig", headless=headless)
        self.username = username
        self.password = password
        
        self.base_url = "https://www.instagram.com/"
        
        self.auth = InstagramAuthenticator(self)
        self.scraper = InstagramScraper(self)

    def login(self):
        self.auth.login()
```

## Soubor: social_bot\src\bots\instagram\scraper.py
```py
from src.utils.human_input import delay
from src.core.database import DatabaseManager
import re
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

class InstagramScraper:
    def __init__(self, bot):
        self.bot = bot
        self.db = DatabaseManager()

    def parse_number(self, text):
        if not text: 
            return 0
        
        # Odstranění nedělitelných mezer (\xa0) a všech dalších whitespace znaků
        text = str(text).upper().replace('\xa0', '').replace('&NBSP;', '')
        text = re.sub(r'\s+', '', text)
        
        if 'TIS' in text:
            text = text.replace('TIS.', 'K').replace('TIS', 'K')
            
        text = text.replace('TOSEMILÍBÍ', '').replace('LIKES', '')
        text = text.replace(',', '.')
        
        match = re.search(r'([\d\.]+)([KMB]?)', text)
        if not match: 
            return 0
            
        num_str, suffix = match.groups()
        try:
            num = float(num_str)
        except:
            return 0
        
        if suffix == 'K': num *= 1000
        elif suffix == 'M': num *= 1000000
        elif suffix == 'B': num *= 1000000000
        
        return int(num)

    def scrape_post_and_comments(self, db_user_id, post_url, comments_limit=50):
        print(f"\n  -> [IG-SCRAPER] Otevírám příspěvek: {post_url}")
        post_id = post_url.rstrip("/").split("/")[-1]
        if self.db.post_exists(post_id):
            print(f"  -> [SKIP] Příspěvek {post_id} již existuje, přeskakuji.")
            return
        self.bot.open_url(post_url)
        delay(3, 5)

        platform_post_id = post_url.rstrip('/').split('/')[-1]
        
        current_url = self.bot.page.url
        try:
            actual_username = current_url.split('instagram.com/')[-1].split('/')[0].split('?')[0]
        except:
            actual_username = ""

        post_container = self.bot.page.locator('main, article, [role="dialog"]').first
        
        # 1. Extrakce textu příspěvku
        post_text = ""
        h1_els = post_container.locator('h1[dir="auto"]').all()
        for h1 in h1_els:
            txt = h1.inner_text()
            if txt and txt != actual_username:
                post_text += txt + "\n"
                
        if not post_text.strip():
            span_els = post_container.locator('span[dir="auto"]').all()
            for sp in span_els[:5]:
                txt = sp.inner_text()
                if txt and txt != actual_username and len(txt) > 5 and not re.match(r'^\d+\s+[hdwmsčty]$', txt, re.IGNORECASE):
                    post_text = txt
                    break
        post_text = post_text.strip()

        # 2. Extrakce média (Podpora kolotočů s využitím JS evaluace pro ignorování mřížky)
        media_urls = []
        is_video = False
        
        for _ in range(15):
            # Videa
            for v in post_container.locator('video').all():
                try:
                    if v.evaluate("el => el.closest('a') !== null"):
                        continue
                        
                    src = v.get_attribute('src') or v.get_attribute('poster')
                    if src and not src.startswith('blob:'):
                        src = src.replace('&amp;', '&')
                        if src not in media_urls:
                            media_urls.append(src)
                            is_video = True
                except:
                    pass
            
            # Fotky
            for img in post_container.locator('div._aagv img, ul li img').all():
                try:
                    if img.evaluate("el => el.closest('a') !== null"):
                        continue
                        
                    alt = (img.get_attribute('alt') or "").lower()
                    src = img.get_attribute('src') or ""
                    
                    if "profile" not in alt and "profilov" not in alt and "data:image" not in src:
                        src = src.replace('&amp;', '&')
                        if src and src not in media_urls:
                            media_urls.append(src)
                except:
                    pass
            
            # Pokus o posun kolotoče na další fotku
            try:
                next_btn = post_container.locator('button[aria-label="Další"], button[aria-label="Next"]').first
                if next_btn.is_visible(timeout=500):
                    next_btn.click(force=True)
                    self.bot.page.wait_for_timeout(800)
                else:
                    break
            except:
                break

        if not post_text:
            if is_video:
                post_text = "[OBSAHUJE VIDEO]"
            elif media_urls:
                post_text = "[OBSAHUJE FOTKU]"

        final_media_url = ";".join(media_urls) if media_urls else None

        # 3. Extrakce statistik
        stats_js = """
        (container) => {
            let likes = "0";
            let comments = "0";
            if(!container) container = document;
            
            let svgs = container.querySelectorAll('svg');
            for(let svg of svgs) {
                let label = svg.getAttribute('aria-label');
                if (label === 'To se mi líbí' || label === 'Like') {
                    let btn = svg.closest('div[role="button"], a');
                    if (btn && btn.innerText.match(/\\d/)) {
                        likes = btn.innerText;
                    }
                } else if (label === 'Komentář' || label === 'Comment') {
                    let btn = svg.closest('div[role="button"], a');
                    if (btn && btn.innerText.match(/\\d/)) {
                        comments = btn.innerText;
                    }
                }
            }
            return {likes, comments};
        }
        """
        try:
            post_element_handle = post_container.element_handle()
            stats_data = self.bot.page.evaluate(stats_js, post_element_handle)
            likes_count = self.parse_number(stats_data.get('likes', '0'))
            comments_count = self.parse_number(stats_data.get('comments', '0'))
        except:
            likes_count, comments_count = 0, 0

        time_loc = post_container.locator('time').first
        timestamp = time_loc.get_attribute('datetime') if time_loc.count() > 0 else ""

        db_post_id = self.db.upsert_post(
            user_id=db_user_id,
            platform="IG",
            platform_post_id=platform_post_id,
            text_content=post_text,
            timestamp_posted=timestamp,
            likes_count=likes_count,
            shares_count=0, 
            comments_count=comments_count, 
            url=post_url,
            media_url=final_media_url
        )
        print(f"  -> [IG-SCRAPER] Uložen příspěvek ID: {platform_post_id} | Lajky: {likes_count} | Komentáře: {comments_count} | Média: {len(media_urls)}")

        # --- Těžba komentářů ---
        print(f"  -> [IG-SCRAPER] Těžím komentáře k tomuto příspěvku (Limit: {comments_limit})...")
        comments_collected = 0
        processed_comment_ids = set()
        
        max_comments = comments_limit

        # OPRAVENÝ SKRIPT PRO KOMENTÁŘE
        js_extract_comments = """
        () => {
            var results = [];
            var times = document.querySelectorAll('time');
            for (var i = 0; i < times.length; i++) {
                var timeEl = times[i];
                var timestamp = timeEl.getAttribute('datetime');
                if (!timestamp) continue;
                
                var block = timeEl;
                for(var j=0; j<8; j++) {
                    if(block.parentElement) block = block.parentElement;
                }
                
                var author = "";
                var links = block.querySelectorAll('a');
                for (var k = 0; k < links.length; k++) {
                    var href = links[k].getAttribute('href');
                    var txt = links[k].innerText.trim();
                    if (href && href.startsWith('/') && txt) {
                        author = txt;
                        break;
                    }
                }
                
                var textContent = "";
                var dirEls = block.querySelectorAll('span[dir="auto"], div[dir="auto"], span');
                for (var k = 0; k < dirEls.length; k++) {
                    var txt = dirEls[k].innerText.trim();
                    var ignoreWords = ['Odpovědět', 'Reply', 'Zobrazit překlad', 'See translation', 'Skrýt odpovědi', 'Hide replies'];
                    
                    var isTimeStr = /^\\d+\\s*[hdwmsčty]$/i.test(txt) || /^před\\s+\\d+/i.test(txt);
                    // Nový filtr pro skrytí textů "Zobrazit odpovědi"
                    var isReplyStr = /zobrazit\\s+všech/i.test(txt) || /view\\s+all/i.test(txt) || /odpovědí/i.test(txt) || /replies/i.test(txt);
                    
                    if (txt && txt !== author && !ignoreWords.includes(txt) && !txt.includes('To se mi líbí') && !txt.includes(' like') && !isTimeStr && !isReplyStr) {
                        // Zabráníme čtení textu z obrovských rodičovských divů
                        if (author && txt.includes(author) && txt.length > author.length + 5) continue;
                        
                        if (!textContent.includes(txt) && txt.length > 1) {
                            textContent += txt + " ";
                        }
                    }
                }
                
                var likesStr = "0";
                var allTextEls = block.querySelectorAll('span, div');
                for (var k = 0; k < allTextEls.length; k++) {
                    var txt = allTextEls[k].innerText.trim();
                    if ((txt.includes('To se mi líbí') || txt.includes(' like') || txt.includes('Likes') || txt.includes('likes')) && /\\d/.test(txt)) {
                        // KLÍČOVÁ OCHRANA: List lajků má pár znaků, rodičovský div s celým komentářem jich má spoustu.
                        // Omezíme to na 40 znaků, takže se uloží jen konkrétní element "33 To se mi líbí".
                        if (txt.length < 40) {
                            likesStr = txt;
                            break;
                        }
                    }
                }
                
                results.push({
                    timestamp: timestamp,
                    author: author,
                    text: textContent.trim(),
                    likesStr: likesStr
                });
            }
            return results;
        }
        """

        js_scroll_comments = """
        () => {
            var times = document.querySelectorAll('time');
            if (times.length > 1) {
                var el = times[times.length - 1]; 
                for (var i = 0; i < 15; i++) {
                    if (!el.parentElement || el.tagName === 'BODY' || el.tagName === 'HTML') break;
                    el = el.parentElement;
                    var style = window.getComputedStyle(el);
                    if (style.overflowY === 'auto' || style.overflowY === 'scroll' || style.overflowY === 'hidden') {
                        if (el.scrollHeight > el.clientHeight + 10) {
                            el.scrollTop = el.scrollHeight;
                            return true;
                        }
                    }
                }
            }
            var divs = document.querySelectorAll('div, ul');
            for (var i=0; i<divs.length; i++) {
                var style = window.getComputedStyle(divs[i]);
                if ((style.overflowY === 'auto' || style.overflowY === 'scroll') && divs[i].scrollHeight > divs[i].clientHeight) {
                    divs[i].scrollTop = divs[i].scrollHeight;
                }
            }
            return false;
        }
        """

        for scroll_attempt in range(12):
            try:
                load_more = self.bot.page.locator('svg[aria-label="Načíst další komentáře"], svg[aria-label="Load more comments"]').first
                if load_more.is_visible(timeout=500):
                    load_more.locator('xpath=./ancestor::button | ./ancestor::div[@role="button"]').first.click(force=True)
                    delay(1.5, 2.5)
            except: pass

            extracted_data = self.bot.page.evaluate(js_extract_comments)
            
            if extracted_data:
                for data in extracted_data:
                    if comments_collected >= max_comments: break
                    
                    c_timestamp = data.get('timestamp')
                    author_username = data.get('author')
                    c_text = data.get('text')
                    likes_str = data.get('likesStr', "0")
                    
                    if not c_timestamp or c_timestamp == timestamp: continue
                    if not author_username: continue
                        
                    platform_comment_id = f"{platform_post_id}_{author_username}_{c_timestamp}"
                    
                    if platform_comment_id in processed_comment_ids: continue
                    processed_comment_ids.add(platform_comment_id)
                    
                    if not c_text: c_text = "[OBSAHUJE MÉDIA/GIF]"
                    c_likes = self.parse_number(likes_str)
                    
                    self.db.upsert_comment(
                        post_id=db_post_id,
                        platform="IG",
                        platform_comment_id=platform_comment_id,
                        author_username=author_username,
                        author_display_name="",
                        text_content=c_text,
                        timestamp_posted=c_timestamp,
                        likes_count=c_likes,
                        shares_count=0,
                        replies_count=0,
                        media_url=None
                    )
                    comments_collected += 1

            if comments_collected >= max_comments: break
            try:
                self.bot.page.evaluate(js_scroll_comments)
            except: pass
            delay(1.5, 2.5)

    def scrape_profile(self, target_query, limit=10, comments_limit=50, followers_limit=50, following_limit=50):
        limit_text = "NEOMEZENO" if limit == -1 else str(limit)
        print(f"[IG-SCRAPER] Zahajuji simulaci lidského vyhledávání: '{target_query}' (Limit: {limit_text} P / {comments_limit} K / {followers_limit} S / {following_limit} S)")

        if "instagram.com" not in self.bot.page.url:
            self.bot.open_url(self.bot.base_url)
            delay(2, 4)

        search_icon = self.bot.page.locator('svg[aria-label="Hledat"]').first
        if search_icon.count() == 0:
            search_icon = self.bot.page.locator('svg[aria-label="Search"]').first

        if search_icon.count() > 0:
            print("[IG-SCRAPER] Klikám na záložku Hledání (Lupa)...")
            try:
                search_icon.locator('xpath=./ancestor::a').first.click(force=True)
            except:
                search_icon.click(force=True)
            delay(2, 4)

            search_box = self.bot.page.locator('input').first
            
            if search_box.count() > 0:
                print("[IG-SCRAPER] Vyhledávací pole nalezeno, simuluji psaní...")
                search_box.click()
                delay(0.5, 1.5)
                
                search_box.fill("")
                search_box.press_sequentially(target_query, delay=150)
                print("[IG-SCRAPER] Dopsáno, čekám na dynamické výsledky...")
                delay(4, 6)
                
                found_profile = False
                ignore_list = ['explore', 'reels', 'direct', 'stories', 'tags', 'locations', 'p', 'your_activity', 'saved', 'settings', 'accounts', 'language']
                
                current_links = self.bot.page.locator('a').all()
                for link in current_links:
                    if link.is_visible():
                        href = link.get_attribute('href')
                        if href and (href.startswith('https://www.instagram.com/') or href.startswith('/')):
                            path = href.replace('https://www.instagram.com', '').split('?')[0].strip('/')
                            
                            if path and '/' not in path:
                                if path not in ignore_list and path != self.bot.username:
                                    if link.inner_text().strip():
                                        print(f"[IG-SCRAPER] Nalezen profil (/{path}/), přecházím na něj.")
                                        link.click(force=True)
                                        found_profile = True
                                        delay(4, 6)
                                        break 
                
                if not found_profile:
                    print("[WARNING] Profil nenalezen v našeptávači, zkouším Direct URL.")
                    clean_target = target_query.replace('@', '').replace(' ', '')
                    self.bot.open_url(f"{self.bot.base_url}{clean_target}/")
                    delay(4, 6)
            else:
                self.bot.open_url(f"{self.bot.base_url}{target_query.replace('@', '').replace(' ', '')}/")
        else:
            self.bot.open_url(f"{self.bot.base_url}{target_query.replace('@', '').replace(' ', '')}/")
            delay(4, 6)

        current_url = self.bot.page.url
        try:
            actual_username = current_url.split('instagram.com/')[-1].split('/')[0].split('?')[0]
        except:
            actual_username = target_query.replace('@', '').replace(' ', '')

        print("[IG-SCRAPER] Stahuji data o uživateli...")
        
        # Komplexní extrakce profilu přes Javascript s lepším filtrováním
        profile_js = """
        () => {
            let header = document.querySelector('header');
            if (!header) return {};
            
            let data = {
                followers: "0",
                following: "0",
                bio: "",
                display_name: "",
                website: "",
                profile_pic_url: "",
                is_verified: 0,
                texts: []
            };
            
            // Followers
            let flw_link = header.querySelector('a[href*="/followers/"]');
            if (flw_link) {
                let span = flw_link.querySelector('span[title]');
                if (span) data.followers = span.getAttribute('title');
                else data.followers = flw_link.innerText;
            }
            
            // Following
            let flg_link = header.querySelector('a[href*="/following/"]');
            if (flg_link) {
                let span = flg_link.querySelector('span:not([dir])');
                if (span) data.following = span.innerText;
                else data.following = flg_link.innerText;
            }
            
            // Verifikace
            if (header.querySelector('svg[aria-label="Ověřeno"], svg[aria-label="Verified"]')) {
                data.is_verified = 1;
            }
            
            // Web
            let web_link = header.querySelector('a[target="_blank"]');
            if (web_link) {
                data.website = web_link.innerText.trim();
            }
            
            // Profilovka
            let img = header.querySelector('img');
            if (img) data.profile_pic_url = img.getAttribute('src');
            
            // Extrakce všech textových elementů pro jméno a bio
            let dirEls = Array.from(header.querySelectorAll('span[dir="auto"], h1[dir="auto"], h2[dir="auto"], div[dir="auto"]'));
            
            for(let el of dirEls) {
                let t = el.innerText.trim();
                if(!t) continue;
                
                let tLow = t.toLowerCase();
                
                // Opravené a přísnější filtrování tlačítek a statistik (zachytí i "Sleduji (47)")
                let isStat = tLow.includes('příspěvky') || tLow.includes('sledující') || tLow.includes('sleduji') ||
                             tLow.includes('posts') || tLow.includes('followers') || tLow.includes('following');
                
                let isBtn = ['sledovat', 'zpráva', 'follow', 'message', 'přidat do příběhu', 'add to story'].includes(tLow);
                
                if (isStat || isBtn) continue;
                
                if (!data.texts.includes(t)) {
                    data.texts.push(t);
                }
            }
            
            return data;
        }
        """
        
        try:
            profile_data = self.bot.page.evaluate(profile_js)
            
            followers_count = self.parse_number(profile_data.get('followers', '0'))
            following_count = self.parse_number(profile_data.get('following', '0'))
            
            display_name = actual_username
            bio = ""
            website = profile_data.get('website', None)
            
            # Očištění posbíraných textů a jejich přiřazení
            texts = profile_data.get('texts', [])
            clean_texts = []
            for t in texts:
                if t.lower() == actual_username.lower(): continue # Vynecháme username
                if website and t == website: continue             # Vynecháme web
                if re.match(r'^[\d\s,]+(?:mil\.|tis\.|m|k)?$', t.lower().replace('\xa0', ' ')): continue # Zbloudilá čísla
                clean_texts.append(t)
                
            # Pokud zbyly texty: první je obvykle jméno (display name), druhý a další je bio
            if len(clean_texts) > 0:
                display_name = clean_texts[0]
                if len(clean_texts) > 1:
                    bio = "\n".join(clean_texts[1:])
            
            is_verified = profile_data.get('is_verified', 0)
            profile_pic_url = profile_data.get('profile_pic_url', None)

        except Exception as e:
            print(f"[ERROR] Selhala extrakce metadat profilu: {e}")
            followers_count, following_count, is_verified = 0, 0, 0
            display_name = actual_username
            bio, website, profile_pic_url = "", None, None

        # Uložení rozšířených dat do DB
        user_id = self.db.upsert_user(
            platform="IG",
            username=actual_username,
            display_name=display_name,
            bio=bio,
            followers_count=followers_count,
            following_count=following_count,
            website=website,
            is_verified=is_verified,
            profile_pic_url=profile_pic_url
        )
        print(f"[IG-SCRAPER] Profil uložen do DB (Sledujících: {followers_count}). Interní ID: {user_id}")

        print("[IG-SCRAPER] Skenuji zeď a sbírám URL příspěvků...")
        
        urls_to_scrape = []
        scroll_attempts_without_new = 0
        max_scroll_loops = 500 if limit == -1 else 100 
        
        loop_counter = 0
        while True:
            all_links = self.bot.page.locator('a').all()
            new_found = False
            
            for link in all_links:
                href = link.get_attribute('href')
                if href and ('/p/' in href or '/reel/' in href):
                    clean_href = href.split('?')[0]
                    full_url = f"https://www.instagram.com{clean_href}" if clean_href.startswith('/') else clean_href
                    
                    if full_url not in urls_to_scrape:
                        urls_to_scrape.append(full_url)
                        new_found = True
                        
                        if limit != -1 and len(urls_to_scrape) >= limit:
                            break
            
            print(f"  -> Nalezeno {len(urls_to_scrape)} unikátních příspěvků...")

            if limit != -1 and len(urls_to_scrape) >= limit:
                print(f"[IG-SCRAPER] Dosažen požadovaný limit {limit}.")
                break
            
            if not new_found:
                scroll_attempts_without_new += 1
                if scroll_attempts_without_new >= 4:
                    print("[IG-SCRAPER] Zdá se, že jsme na konci profilu (žádné nové příspěvky).")
                    break
            else:
                scroll_attempts_without_new = 0

            loop_counter += 1
            if limit == -1 and loop_counter > max_scroll_loops:
                print("[WARNING] Dosažen interní bezpečnostní limit scrollu.")
                break

            self.bot.page.evaluate("window.scrollBy(0, 800)")
            delay(1.5, 3.0)

        final_urls = urls_to_scrape[:limit] if limit != -1 else urls_to_scrape
        
        if not final_urls:
            print("[IG-SCRAPER] Nebyly nalezeny žádné příspěvky (profil je soukromý nebo prázdný).")
            return
            
        if followers_limit > 0:
            self._scrape_network(actual_username, followers_limit, "followers")
        if following_limit > 0:
            self._scrape_network(actual_username, following_limit, "following")

        print(f"\n[IG-SCRAPER] Zahajuji hloubkovou těžbu {len(final_urls)} příspěvků...")
        for i, url in enumerate(final_urls):
            print(f"--- Zpracovávám {i+1} z {len(final_urls)} ---")
            try:
                self.scrape_post_and_comments(user_id, url, comments_limit)
            except Exception as e:
                print(f"[IG-SCRAPER] Chyba při těžbě příspěvku {url}: {e}")

        print("\n[IG-SCRAPER] Kompletní těžba cílového IG profilu a komentářů byla úspěšně dokončena.")

    def _scrape_network(self, username, limit, mode):
        if limit <= 0: return

        conn_type = "follower" if mode == "followers" else "following"
        type_cs = "Sledujících" if mode == "followers" else "Sledovaných"
        print(f"\n[IG-NETWORK] --- Těžba {type_cs} pro @{username} (Limit: {limit}) ---")

        try:
            if f"/{username}/" not in self.bot.page.url:
                self.bot.open_url(f"{self.bot.base_url}{username}/")
                delay(2, 4)

            # Zavři případný zbývající dialog
            try:
                if self.bot.page.locator('div[role="dialog"]').is_visible(timeout=1000):
                    self.bot.page.keyboard.press("Escape")
                    self.bot.page.locator('div[role="dialog"]').wait_for(state="hidden", timeout=4000)
                    delay(1, 2)
            except:
                pass

            # Scrollni na vrchol stránky
            self.bot.page.evaluate("window.scrollTo(0, 0)")
            delay(0.5, 1)

            link = self.bot.page.locator(f'header a[href*="/{mode}/"]').first
            if link.is_visible(timeout=5000):
                link.evaluate("el => el.click()")  # JS klik — obchází intercept
            else:
                print(f"[IG-NETWORK] Tlačítko {type_cs} nebylo nalezeno.")
                return

            dialog = self.bot.page.locator('div[role="dialog"]').first
            dialog.wait_for(state="visible", timeout=8000)
            delay(2, 4)

        except Exception as e:
            print(f"[IG-NETWORK] Nelze otevřít seznam {type_cs}: {e}")
            return

        collected = 0
        processed = set()
        no_new_streak = 0
        MAX_NO_NEW = 6  # kolik kol bez nových uživatelů než skončíme
        max_loops = max(limit * 3, 60)  # bezpečnostní strop

        # JS: extrahuje usernames a scrolluje NEJVĚTŠÍ scrollovatelný div v dialogu
        js_extract = """
        () => {
            let dialog = document.querySelector('div[role="dialog"]');
            if (!dialog) return {users: [], scrolled: false};

            let users = [];
            let links = dialog.querySelectorAll('a[href]');
            for (let a of links) {
                let href = a.getAttribute('href');
                if (href && href.startsWith('/') && href.split('/').filter(Boolean).length === 1) {
                    let un = href.replace(/\\//g, '');
                    if (un && !['explore','reels','direct','stories','p','tv'].includes(un)) {
                        users.push(un);
                    }
                }
            }

            // Najdi scrollovatelný div s NEJVĚTŠÍM scrollHeight (= seznam uživatelů)
            let bestDiv = null;
            let bestScrollHeight = 0;
            let divs = dialog.querySelectorAll('div');
            for (let d of divs) {
                let style = window.getComputedStyle(d);
                if ((style.overflowY === 'auto' || style.overflowY === 'scroll')
                    && d.scrollHeight > d.clientHeight + 10
                    && d.scrollHeight > bestScrollHeight) {
                    bestScrollHeight = d.scrollHeight;
                    bestDiv = d;
                }
            }

            let scrolled = false;
            if (bestDiv) {
                bestDiv.scrollTop += 600;
                scrolled = true;
            }

            return {users: [...new Set(users)], scrolled: scrolled};
        }
        """

        loop = 0
        while collected < limit and no_new_streak < MAX_NO_NEW and loop < max_loops:
            loop += 1
            try:
                data = self.bot.page.evaluate(js_extract)
                new_found = False

                for target_user in data.get('users', []):
                    if target_user == username: continue
                    if collected >= limit: break
                    if target_user not in processed:
                        processed.add(target_user)
                        new_found = True
                        self.db.upsert_connection("IG", username, target_user, conn_type)
                        collected += 1
                        print(f"  -> ({conn_type}): @{target_user} ({collected}/{limit})")

                if not new_found:
                    no_new_streak += 1
                else:
                    no_new_streak = 0

                delay(1.5, 3.0)

            except Exception as e:
                print(f"[IG-NETWORK] Chyba při těžbě modal okna: {e}")
                break

        print(f"[IG-NETWORK] Těžba {type_cs} dokončena. Sesbíráno: {collected}/{limit}")

        try:
            self.bot.page.keyboard.press("Escape")
            delay(1.5, 2.5)
            # Počkej až dialog zmizí
            self.bot.page.locator('div[role="dialog"]').wait_for(state="hidden", timeout=5000)
        except:
            pass
```

## Soubor: social_bot\src\bots\x\auth.py
```py
from src.utils.human_input import delay

class XAuthenticator:
    def __init__(self, bot):
        self.bot = bot
        self.base_url = "https://x.com/"

    def login(self):
        print("[X] Kontroluji session na hlavní stránce...")
        
        # Playwright využívá metodu goto s nastavením chování při načítání
        try:
            self.bot.page.goto(self.base_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"[X] Varování při načítání úvodní stránky: {e}")
            
        delay(4, 6) 

        is_logged_in = False
        
        try:
            # Selektory přepsány do standardního formátu pro Playwright
            if self.bot.page.locator('[aria-label="Timeline: Your Home Timeline"]').is_visible(timeout=5000):
                is_logged_in = True
            elif self.bot.page.locator('[aria-label="Profile"]').is_visible(timeout=2000):
                 is_logged_in = True
            elif "/home" in self.bot.page.url:
                 is_logged_in = True
        except:
            pass

        if is_logged_in:
            print("[X] Úspěšně ověřeno: Již přihlášeno (ze session).")
            return
        
        print("[X] Session nenalezena, jdu se přihlásit...")
        try:
            self.bot.page.goto(self.base_url + "i/flow/login", wait_until="domcontentloaded", timeout=30000)
        except:
            pass
        delay(3)
        
        username_input = self.bot.page.locator('[autocomplete="username"]').first
        try:
            # Playwright vyžaduje explicitní čekání na stav elementu, pokud nevyužíváme auto-waiting akce
            username_input.wait_for(state="visible", timeout=10000)
            print("[X] Zadávám uživatelské jméno...")
            
            # press_sequentially nahrazuje původní iterativní human_typing
            username_input.press_sequentially(self.bot.username, delay=150)
            delay(1, 2)
            
            next_xpath = "//span[text()='Next' or text()='Další']"
            self.bot.click_smart(next_xpath, "Tlačítko Další")
            delay(2, 3)
        except Exception as e:
            print(f"[X] Pole pro username nebylo včas nalezeno: {e}")

        password_input = self.bot.page.locator('[name="password"]').first
        try:
            password_input.wait_for(state="visible", timeout=10000)
            print("[X] Zadávám heslo...")
            
            password_input.press_sequentially(self.bot.password, delay=150)
            delay(1, 2)
            
            login_xpath = "//span[text()='Log in' or text()='Přihlásit se']"
            self.bot.click_smart(login_xpath, "Tlačítko Login")
            delay(5, 8)
            
            self.bot.handle_popups(['Refuse', 'Odmítnout', 'Accept all', 'Povolit'])
            
            print("[X] Přihlášení dokončeno, ukládám session...")
            delay(3)
        except Exception as e:
            print(f"[X] Pole pro heslo nebylo včas nalezeno: {e}")
```

## Soubor: social_bot\src\bots\x\bot.py
```py
from src.core.base_bot import BaseBot
from .auth import XAuthenticator
from .scraper import XScraper

class XBot(BaseBot):
    def __init__(self, username, password, user_id="default", headless=True):
        super().__init__(user_id=user_id, platform="x", headless=headless)
        self.username = username
        self.password = password
        self.base_url = "https://x.com/"
        
        self.auth = XAuthenticator(self)
        self.scraper = XScraper(self)

    def login(self):
        self.auth.login()
```

## Soubor: social_bot\src\bots\x\scraper.py
```py
from src.core.database import DatabaseManager
from .modules.search import XSearchModule
from .modules.profile import XProfileModule
from .modules.posts import XPostsModule
from .modules.comments import XCommentsModule
from .modules.network import XNetworkModule
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

class XScraper:
    def __init__(self, bot):
        self.bot = bot
        self.db = DatabaseManager()
        
        self.search_module   = XSearchModule(bot, self.db)
        self.profile_module  = XProfileModule(bot, self.db)
        self.posts_module    = XPostsModule(bot, self.db)
        self.comments_module = XCommentsModule(bot, self.db)
        self.network_module  = XNetworkModule(bot, self.db)

        # Callback pro GUI progress bary.
        # Formát: progress_callback(key, current, total)
        # Nastavuje se z app.py před spuštěním scrape.
        self.progress_callback = None

    def _report(self, key: str, current: int, total: int):
        """Bezpečné volání progress_callback — nevyhodí výjimku."""
        if self.progress_callback:
            try:
                self.progress_callback(key, current, total)
            except Exception:
                pass

    def scrape_profile(self, target_query, limit=10, comments_limit=50,
                       followers_limit=50, following_limit=50):
        limit_text = "NEOMEZENO" if limit == -1 else str(limit)
        print(f"[X-SCRAPER] Cíl: '{target_query}' (Limit: {limit_text} P / {comments_limit} K / {followers_limit} S)")
        
        if not self.search_module.find_profile(target_query):
            print(f"[ERROR] Profil '{target_query}' nebyl nalezen ani přes Google.")
            return

        try:
            current_url = self.bot.page.url
            if "x.com/" in current_url:
                actual_username = current_url.split('x.com/')[-1].split('?')[0].split('/')[0]
            else:
                actual_username = target_query.replace('@', '').replace(' ', '')
        except:
            actual_username = target_query.replace('@', '').replace(' ', '')

        user_id = self.profile_module.scrape_metadata(actual_username)

        # ── Příspěvky ────────────────────────────────────────────────────
        videos_queue, comments_queue = self.posts_module.scrape_timeline(
            user_id, limit,
            progress_cb=lambda c, t: self._report("posts", c, t)
        )

        if videos_queue:
            self.posts_module.process_videos(videos_queue)

        # ── Komentáře ────────────────────────────────────────────────────
        if comments_queue:
            self.comments_module.scrape_for_queue(
                comments_queue, limit=comments_limit,
                progress_cb=lambda c, t: self._report("comments", c, t)
            )
        else:
            print("[X-SCRAPER] Žádné příspěvky ke zpracování komentářů.")
            self._report("comments", 0, 0)

        # ── Síť ──────────────────────────────────────────────────────────
        if followers_limit > 0:
            self.network_module.scrape_followers(
                actual_username, limit=followers_limit,
                progress_cb=lambda c, t: self._report("followers", c, t)
            )

        if following_limit > 0:
            self.network_module.scrape_following(
                actual_username, limit=following_limit,
                progress_cb=lambda c, t: self._report("following", c, t)
            )

        print("\n[X-SCRAPER] Hotovo.")

    def scrape_trending(self):
        print("[X-SCRAPER] Těžba trendů...")
        try:
            self.bot.page.goto("https://x.com/explore/tabs/trending",
                               wait_until="domcontentloaded", timeout=30000)
        except PlaywrightTimeoutError:
            print("[X-SCRAPER] Varování: Timeout při načítání stránky trendů.")

        trends_locator = self.bot.page.locator('[data-testid="trend"]')
        try:
            trends_locator.first.wait_for(state="visible", timeout=6000)
        except PlaywrightTimeoutError:
            print("[X-SCRAPER] Trendy se nenačetly.")
            return
            
        trends = trends_locator.all()
        print(f"[X-SCRAPER] Nalezeno {len(trends)} trendů.")
        
        for index, trend in enumerate(trends):
            try:
                text_content = trend.inner_text()
                if not text_content: continue
                text  = text_content.split('\n')
                topic = text[1] if len(text) > 1 else text[0]
                count = text[-1] if "posts" in text[-1] else "N/A"
                self.db.upsert_trend("X", index+1, "General", topic, count)
                print(f"  -> #{index+1} {topic}")
            except Exception:
                pass
```

## Soubor: social_bot\src\bots\x\modules\comments.py
```py
from src.utils.human_input import delay
from .utils import XUtils
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
import time
import re

class XCommentsModule:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    def scrape_for_queue(self, queue, limit=20, progress_cb=None):
        if not queue: return
        
        post_count = len(queue)
        print(f"\n[X-COMMENTS] --- Těžba komentářů ({post_count} příspěvků) ---")
        
        comment_videos_queue = []
        total_comments = 0

        for i, post_data in enumerate(queue):
            print(f"[X-COMMENTS] Komentáře pro {post_data['platform_id']} ({i+1}/{post_count})...")
            try:
                collected = self._scrape_single_post(
                    post_data['db_id'],
                    post_data['platform_id'],
                    post_data['url'],
                    limit,
                    comment_videos_queue
                )
                total_comments += collected

                # Po každém příspěvku reportujeme: kolik příspěvků hotovo / celkem
                if progress_cb:
                    progress_cb(i + 1, post_count)

            except Exception as e:
                print(f"[ERROR] Chyba u komentářů: {e}")

        if comment_videos_queue:
            self._process_comment_videos(comment_videos_queue)

    def _scrape_single_post(self, db_post_id, platform_post_id, post_url,
                            max_comments, video_queue) -> int:
        """Vrátí počet sebraných komentářů pro tento příspěvek."""
        try:
            self.bot.page.goto(post_url, wait_until="domcontentloaded", timeout=20000)
            main_article = self.bot.page.locator('article').first
            main_article.wait_for(state="visible", timeout=10000)
            self.bot.page.wait_for_timeout(2000)
        except PlaywrightTimeoutError:
            print(f"  -> [WARNING] Timeout při načítání příspěvku {platform_post_id}.")
            return 0
        except Exception as e:
            print(f"  -> [ERROR] Nelze načíst příspěvek {platform_post_id}: {e}")
            return 0

        comments_collected = 0
        processed_ids = set()
        
        for attempt in range(6):
            if comments_collected >= max_comments: break
            
            articles = self.bot.page.locator('article').all()
            
            for article in articles:
                if comments_collected >= max_comments: break
                try:
                    time_ele = article.locator('time').first
                    if time_ele.count() == 0: continue
                    
                    link_ele = article.locator('a:has(time)').first
                    raw_href = link_ele.get_attribute('href')
                    if not raw_href: continue
                    
                    cid = raw_href.split('/')[-1]
                    if not cid or cid == platform_post_id or cid in processed_ids:
                        continue
                    processed_ids.add(cid)

                    user_name_ele = article.locator('[data-testid="User-Name"]').first
                    author_user = (
                        user_name_ele.inner_text().split('\n')[1].replace('@', '')
                        if user_name_ele.count() > 0 else ""
                    )
                    
                    text_ele = article.locator('[data-testid="tweetText"]').first
                    text_content = text_ele.inner_text() if text_ele.count() > 0 else ""
                    text_content, media_url, is_video = XUtils.extract_media(article, text_content)

                    comment_db_id = self.db.upsert_comment(
                        post_id=db_post_id,
                        platform="X",
                        platform_comment_id=cid,
                        author_username=author_user,
                        author_display_name="",
                        text_content=text_content,
                        timestamp_posted=time_ele.get_attribute('datetime'),
                        likes_count=0, shares_count=0, replies_count=0,
                        media_url=media_url
                    )
                    comments_collected += 1
                    print(f"  -> Uložen komentář: {cid} | Video: {is_video}")

                    if is_video:
                        comment_url = f"https://x.com/{author_user}/status/{cid}"
                        video_queue.append({
                            'db_id': comment_db_id,
                            'url': comment_url,
                            'platform_id': cid
                        })
                        
                except Exception:
                    continue

            self.bot.page.evaluate("window.scrollBy(0, 800)")
            delay(2.0, 3.5)

        return comments_collected

    def _process_comment_videos(self, video_queue):
        count = len(video_queue)
        print(f"\n[X-COMMENTS-VIDEO] --- FÁZE 4: Těžba MP4 z komentářů ({count} položek) ---")
        
        for i, item in enumerate(video_queue):
            print(f"[X-COMMENTS-VIDEO] Zpracovávám komentář {i+1}/{count} (ID: {item['platform_id']})...")
            try:
                stream_url = self._get_video_stream(item['url'])
                if stream_url:
                    self.db.cursor.execute(
                        "UPDATE comments SET media_url = ? WHERE id = ?",
                        (stream_url, item['db_id'])
                    )
                    self.db.conn.commit()
                    print(f"  -> [DB] Video aktualizováno pro komentář.")
                else:
                    print(f"  -> [WARNING] Stream nenalezen.")
                delay(2, 4)
            except Exception as e:
                print(f"  -> [ERROR] {e}")

    def _get_video_stream(self, post_url):
        video_url = None
        
        def handle_response(response):
            nonlocal video_url
            try:
                if "graphql" in response.url:
                    text_body = response.text().replace('\\/', '/')
                    links = re.findall(
                        r'(https://video\.twimg\.com/[^"\'\s]+\.(?:mp4|m3u8))', text_body
                    )
                    if links:
                        mp4s = [l for l in links if l.endswith('.mp4')]
                        video_url = mp4s[0] if mp4s else links[0]
                elif not video_url and "video.twimg.com" in response.url:
                    if ".mp4" in response.url or ".m3u8" in response.url:
                        video_url = response.url
            except:
                pass

        self.bot.page.on("response", handle_response)
        try:
            self.bot.page.goto(post_url, wait_until="domcontentloaded", timeout=15000)
            video_ele = self.bot.page.locator('[data-testid="videoPlayer"]').first
            if video_ele.is_visible(timeout=5000):
                video_ele.click(force=True)
            start_time = time.time()
            while time.time() - start_time < 8:
                if video_url:
                    print(f"  -> [SNIFFER] ÚSPĚCH! URL zachycena.")
                    break
                self.bot.page.wait_for_timeout(500)
        except Exception as e:
            print(f"  -> [SNIFFER ERROR] {e}")
        finally:
            self.bot.page.remove_listener("response", handle_response)
            
        return video_url
```

## Soubor: social_bot\src\bots\x\modules\network.py
```py
from src.utils.human_input import delay
import re

class XNetworkModule:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    def scrape_followers(self, username, limit=50, progress_cb=None):
        self._scrape_users_list(username, "followers", "follower", limit, progress_cb)

    def scrape_following(self, username, limit=50, progress_cb=None):
        self._scrape_users_list(username, "following", "following", limit, progress_cb)

    def _scrape_users_list(self, username, endpoint, conn_type, limit, progress_cb=None):
        if limit <= 0: return
        
        type_cs = "Sledujících" if conn_type == "follower" else "Sledovaných"
        print(f"\n[X-NETWORK] --- Těžba {type_cs} pro @{username} (Limit: {limit}) ---")
        
        try:
            self.bot.page.goto(
                f"https://x.com/{username}/{endpoint}",
                wait_until="domcontentloaded", timeout=15000
            )
            self.bot.page.locator('[data-testid="primaryColumn"]').first.wait_for(
                state="visible", timeout=10000
            )
            delay(2, 4)
        except Exception as e:
            print(f"[X-NETWORK] Nelze načíst seznam {type_cs}: {e}")
            return

        collected = 0
        processed = set()
        scroll_attempts = 0

        while collected < limit and scroll_attempts < 15:
            cells = self.bot.page.locator('[data-testid="UserCell"]').all()
            new_found = False

            for cell in cells:
                if collected >= limit: break
                try:
                    text_content = cell.inner_text()
                    match = re.search(r'@([a-zA-Z0-9_]+)', text_content)
                    
                    if match:
                        target_user = match.group(1).strip()
                        if (target_user
                                and target_user.lower() != username.lower()
                                and target_user not in processed):
                            processed.add(target_user)
                            new_found = True
                            self.db.upsert_connection("X", username, target_user, conn_type)
                            collected += 1
                            print(f"  -> Uložen záznam ({conn_type}): @{target_user} ({collected}/{limit})")

                            # Progress po každém záznamu
                            if progress_cb:
                                progress_cb(collected, limit)

                except Exception:
                    continue

            if not new_found:
                scroll_attempts += 1
            else:
                scroll_attempts = 0

            if collected < limit:
                self.bot.page.evaluate("window.scrollBy(0, 1000)")
                delay(1.5, 3.0)

        print(f"[X-NETWORK] Těžba {type_cs} dokončena.")
```

## Soubor: social_bot\src\bots\x\modules\posts.py
```py
import time
from src.utils.human_input import delay
from .utils import XUtils
import re

class XPostsModule:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    def scrape_timeline(self, user_id, limit, progress_cb=None):
        print("[X-POSTS] Sbírám příspěvky...")
        posts_collected = 0
        processed_post_ids = set()
        
        posts_to_process_video = []
        posts_for_comments = []
        scroll_attempts_without_new = 0

        # Celkový limit pro progress bar (použijeme limit nebo odhad)
        total_estimate = limit if (limit and limit != -1) else 0
        
        while True:
            if limit != -1 and posts_collected >= limit: break
            
            self.bot.page.wait_for_timeout(1000)
            articles = self.bot.page.locator('article').all()
            new_in_batch = False

            for article in articles:
                if limit != -1 and posts_collected >= limit: break
                try:
                    time_ele = article.locator('time').first
                    if time_ele.count() == 0: continue 
                    
                    link_ele = article.locator('a:has(time)').first
                    raw_href = link_ele.get_attribute('href')
                    if not raw_href: continue
                    
                    full_url = raw_href if raw_href.startswith("http") else f"https://x.com{raw_href}"
                    platform_post_id = raw_href.split('/')[-1]
                    
                    if not platform_post_id or platform_post_id in processed_post_ids: continue
                    processed_post_ids.add(platform_post_id)
                    new_in_batch = True
                    
                    text_ele = article.locator('[data-testid="tweetText"]').first
                    post_text = text_ele.inner_text() if text_ele.count() > 0 else ""
                    post_text, media_url, is_video = XUtils.extract_media(article, post_text)
                    
                    timestamp = time_ele.get_attribute('datetime')
                    
                    likes, shares, comments = 0, 0, 0
                    try:
                        re_el = article.locator('[data-testid="reply"]').first
                        comments = XUtils.parse_number(re_el.inner_text()) if re_el.count() > 0 else 0
                        rt_el = article.locator('[data-testid="retweet"]').first
                        shares = XUtils.parse_number(rt_el.inner_text()) if rt_el.count() > 0 else 0
                        li_el = article.locator('[data-testid="like"]').first
                        likes = XUtils.parse_number(li_el.inner_text()) if li_el.count() > 0 else 0
                    except: pass

                    db_post_id = self.db.upsert_post(
                        user_id, "X", platform_post_id, post_text,
                        timestamp, likes, shares, comments, full_url, media_url
                    )
                    posts_collected += 1
                    print(f"[X-POSTS] ({posts_collected}) Tweet: {platform_post_id} | Video: {is_video}")
                    
                    # Progress report
                    if progress_cb and total_estimate > 0:
                        progress_cb(posts_collected, total_estimate)
                    
                    posts_for_comments.append({
                        'db_id': db_post_id,
                        'platform_id': platform_post_id,
                        'url': full_url
                    })

                    if is_video:
                        posts_to_process_video.append({
                            'db_id': db_post_id,
                            'url': full_url,
                            'platform_id': platform_post_id
                        })
                    
                except Exception: 
                    pass

            if not new_in_batch:
                scroll_attempts_without_new += 1
                if scroll_attempts_without_new >= 4:
                    print("[X-POSTS] Dosažen konec profilu nebo účet nemá (další) příspěvky.")
                    # Finální report — sebrali jsme vše co bylo
                    if progress_cb and posts_collected > 0:
                        progress_cb(posts_collected, posts_collected)
                    break
                self.bot.page.evaluate("window.scrollBy(0, 400)")
                delay(1)
            else:
                scroll_attempts_without_new = 0

            self.bot.page.evaluate("window.scrollBy(0, 700)")
            delay(0.8, 1.5)
            
        return posts_to_process_video, posts_for_comments

    def process_videos(self, video_queue):
        if not video_queue: return

        count = len(video_queue)
        print(f"\n[X-VIDEO] --- FÁZE 2: Těžba odkazů videí ({count} položek) ---")
        
        for i, item in enumerate(video_queue):
            print(f"[X-VIDEO] Zpracovávám video {i+1}/{count}...")
            try:
                stream_url = self._get_video_stream(item['url'])
                if stream_url:
                    self.db.cursor.execute(
                        "UPDATE posts SET media_url = ? WHERE id = ?",
                        (stream_url, item['db_id'])
                    )
                    self.db.conn.commit()
                    print(f"  -> [DB] Video aktualizováno.")
                else:
                    print(f"  -> [WARNING] Stream nenalezen.")
                delay(2, 4)
            except Exception as e:
                print(f"  -> [ERROR] {e}")

    def _get_video_stream(self, post_url):
        print(f"  -> [SNIFFER] Jdu pro video: {post_url}")
        video_url = None
        
        def handle_response(response):
            nonlocal video_url
            try:
                if "graphql" in response.url:
                    text_body = response.text().replace('\\/', '/')
                    links = re.findall(
                        r'(https://video\.twimg\.com/[^"\'\s]+\.(?:mp4|m3u8))', text_body
                    )
                    if links:
                        mp4s = [l for l in links if l.endswith('.mp4')]
                        video_url = mp4s[0] if mp4s else links[0]
                elif not video_url and "video.twimg.com" in response.url:
                    if ".mp4" in response.url or ".m3u8" in response.url:
                        video_url = response.url
            except:
                pass

        self.bot.page.on("response", handle_response)
        try:
            self.bot.page.goto(post_url, wait_until="domcontentloaded", timeout=15000)
            video_ele = self.bot.page.locator('[data-testid="videoPlayer"]').first
            if video_ele.is_visible(timeout=5000):
                video_ele.click(force=True)
            start_time = time.time()
            while time.time() - start_time < 8:
                if video_url:
                    print(f"  -> [SNIFFER] ÚSPĚCH! URL zachycena.")
                    break
                self.bot.page.wait_for_timeout(500)
        except Exception as e:
            print(f"  -> [SNIFFER ERROR] {e}")
        finally:
            self.bot.page.remove_listener("response", handle_response)
            
        return video_url
```

## Soubor: social_bot\src\bots\x\modules\profile.py
```py
from src.utils.human_input import delay
from .utils import XUtils

class XProfileModule:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    def scrape_metadata(self, actual_username):
        print(f"[X-PROFILE] Těžím metadata pro @{actual_username}...")
        
        try:
            display_name_loc = self.bot.page.locator('[data-testid="UserName"]').first
            if display_name_loc.count() > 0:
                display_name = display_name_loc.inner_text().split('\n')[0]
                is_verified = 1 if display_name_loc.locator('svg[aria-label="Verified account"]').count() > 0 else 0
            else:
                display_name = actual_username
                is_verified = 0

            bio_loc = self.bot.page.locator('[data-testid="UserDescription"]').first
            bio = bio_loc.inner_text() if bio_loc.count() > 0 else ""
            
            loc_ele = self.bot.page.locator('[data-testid="UserLocation"]').first
            location = loc_ele.inner_text() if loc_ele.count() > 0 else None

            web_ele = self.bot.page.locator('[data-testid="UserUrl"]').first
            website = web_ele.inner_text() if web_ele.count() > 0 else None

            join_ele = self.bot.page.locator('[data-testid="UserJoinDate"]').first
            joined_date = join_ele.inner_text() if join_ele.count() > 0 else None

            followers_ele = self.bot.page.locator('xpath=//a[contains(@href, "/followers")]/span[1] | //a[contains(@href, "/verified_followers")]/span[1]').first
            followers_count = XUtils.parse_number(followers_ele.inner_text() if followers_ele.count() > 0 else "0")

            following_ele = self.bot.page.locator('xpath=//a[contains(@href, "/following")]/span[1]').first
            following_count = XUtils.parse_number(following_ele.inner_text() if following_ele.count() > 0 else "0")

            banner_url = None
            try:
                banner_link = self.bot.page.locator('xpath=//a[contains(@href, "/header_photo")]//img').first
                if banner_link.count() > 0:
                    banner_url = banner_link.get_attribute('src')
            except: pass

            profile_pic_url = self._get_hd_profile_pic()

        except Exception as e:
            print(f"[ERROR] Chyba čtení metadat: {e}")
            display_name = actual_username; bio = ""; followers_count = 0; following_count = 0
            location = None; website = None; joined_date = None; is_verified = 0; banner_url = None; profile_pic_url = None

        user_id = self.db.upsert_user(
            platform="X", 
            username=actual_username, 
            display_name=display_name, 
            bio=bio, 
            followers_count=followers_count, 
            following_count=following_count,
            joined_date=joined_date,
            location=location,
            website=website,
            is_verified=is_verified,
            profile_pic_url=profile_pic_url,
            banner_url=banner_url
        )
        print(f"[X-PROFILE] Uloženo. Verifikace: {is_verified} | Lokace: {location}")
        return user_id

    def _get_hd_profile_pic(self):
        profile_pic_url = None
        try:
            avatar_img = self.bot.page.locator('img[alt="Opens profile photo"]').first
            if avatar_img.count() == 0: 
                avatar_img = self.bot.page.locator('img[alt="Square profile picture and Opens profile photo"]').first
            if avatar_img.count() == 0: 
                avatar_img = self.bot.page.locator('xpath=//div[contains(@data-testid, "UserAvatar-Container")]//img').first
            
            if avatar_img.count() > 0:
                profile_pic_url = avatar_img.get_attribute('src')
                if profile_pic_url and any(x in profile_pic_url for x in ['_bigger', '_mini', '_normal']):
                    photo_link = self.bot.page.locator('xpath=//div[contains(@data-testid, "UserAvatar-Container")]//a[contains(@href, "/photo")]').first
                    if photo_link.count() > 0:
                        photo_link.click()
                        large_img = self.bot.page.locator('xpath=//div[@data-testid="swipe-to-dismiss"]//img').first
                        large_img.wait_for(state="visible", timeout=3000)
                        if large_img.count() > 0:
                            profile_pic_url = large_img.get_attribute('src')
                        
                        close_btn = self.bot.page.locator('div[aria-label="Close"], div[aria-label="Zavřít"]').first
                        if close_btn.count() > 0: 
                            close_btn.click()
                        else: 
                            self.bot.page.go_back()
                        delay(0.5)
        except: pass
        return profile_pic_url
```

## Soubor: social_bot\src\bots\x\modules\search.py
```py
# src/bots/x/modules/search.py
from src.utils.human_input import delay
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
import re


class XSearchModule:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    def find_profile(self, target_query):
        # --- Krok 1: DB cache ---
        print("[X-SEARCH] 1. Krok: Kontrola lokální databáze...")
        known_handle = self.db.get_known_handle(target_query)
        if known_handle:
            print(f"[DATABASE] Nalezen uložený handle: @{known_handle}. Jdu na jistotu.")
            self.bot.open_url(f"{self.bot.base_url}{known_handle}")
            delay(2, 4)
            try:
                if self.bot.page.locator('[data-testid="UserName"]').first.is_visible(timeout=5000):
                    return True
            except Exception:
                pass

        # --- Krok 2: Interní vyhledávání — People záložka ---
        print("[X-SEARCH] 2. Krok: Interní vyhledávání — záložka People...")
        people_result = self._search_in_tab(target_query, tab="people")
        if people_result:
            if self._verify_profile_match(target_query):
                print("[X-SEARCH] Profil ověřen — shoda s dotazem.")
                return True
            else:
                print("[X-SEARCH] Výsledek People záložky neodpovídá dotazu. Zkouším záložku All...")

        # --- Krok 3: Záložka All (vše) ---
        print("[X-SEARCH] 3. Krok: Interní vyhledávání — záložka All...")
        all_result = self._search_in_tab(target_query, tab="all")
        if all_result:
            if self._verify_profile_match(target_query):
                print("[X-SEARCH] Profil ověřen přes záložku All.")
                return True
            else:
                print("[X-SEARCH] Ani záložka All nevrátila shodu. Zkouším Direct URL...")

        # --- Krok 4: Direct URL ---
        print("[X-SEARCH] 4. Krok: Pokus o přímou URL...")
        if self._direct_url(target_query):
            return True

        # --- Krok 5: Google fallback ---
        print("[X-SEARCH] 5. Krok: Google Search fallback...")
        if self._google_search_fallback(target_query):
            try:
                self.bot.page.locator('[data-testid="UserName"]').first.wait_for(
                    state="visible", timeout=8000
                )
                return True
            except Exception:
                pass

        return False

    # ------------------------------------------------------------------
    # Vyhledávání v konkrétní záložce (people / all)
    # ------------------------------------------------------------------
    def _search_in_tab(self, target_query: str, tab: str) -> bool:
        try:
            if "search" not in self.bot.page.url and "explore" not in self.bot.page.url:
                self.bot.open_url(self.bot.base_url + "explore")
                delay(1.5, 2.5)

            search_box = self.bot.page.locator('[data-testid="SearchBox_Search_Input"]').first
            search_box.wait_for(state="visible", timeout=5000)

            search_box.click()
            search_box.fill("")
            search_box.press_sequentially(target_query, delay=100)
            delay(0.5)
            search_box.press("Enter")
            delay(1.5, 2.5)

            if tab == "people":
                tab_xpath = "//span[text()='People' or text()='Lidé']"
            else:
                tab_xpath = "//span[text()='Top' or text()='Vše' or text()='All']"

            try:
                tab_locator = self.bot.page.locator(f"xpath={tab_xpath}").first
                tab_locator.wait_for(state="visible", timeout=4000)
                tab_locator.click()
                delay(1.5, 2.5)
            except PlaywrightTimeoutError:
                print(f"[X-SEARCH] Záložka '{tab}' nenalezena, pokračuji bez přepnutí.")

            first_user = self.bot.page.locator('[data-testid="UserCell"]').first
            first_user.wait_for(state="visible", timeout=4000)
            first_user.click()

            self.bot.page.locator('[data-testid="UserName"]').first.wait_for(
                state="visible", timeout=6000
            )
            return True

        except Exception:
            return False

    # ------------------------------------------------------------------
    # Ověření shody výsledku s původním dotazem
    # ------------------------------------------------------------------
    def _verify_profile_match(self, target_query: str) -> bool:
        try:
            current_url = self.bot.page.url
            url_username = ""
            if "x.com/" in current_url:
                url_username = current_url.split("x.com/")[-1].split("?")[0].split("/")[0].lower()

            username_loc = self.bot.page.locator('[data-testid="UserName"]').first
            full_text = username_loc.inner_text().lower() if username_loc.count() > 0 else ""

            query_clean = re.sub(r'[^a-z0-9]', '', target_query.lower())

            url_clean = re.sub(r'[^a-z0-9]', '', url_username)
            if query_clean and url_clean and (
                query_clean in url_clean or url_clean in query_clean
            ):
                return True

            full_clean = re.sub(r'[^a-z0-9]', '', full_text)
            if query_clean and full_clean and query_clean in full_clean:
                return True

            return False

        except Exception:
            return True

    # ------------------------------------------------------------------
    # Direct URL pokus
    # ------------------------------------------------------------------
    def _direct_url(self, target_query: str) -> bool:
        handle = re.sub(r'[^a-zA-Z0-9_]', '', target_query.replace('@', ''))
        if not handle:
            return False

        try:
            print(f"[X-SEARCH] Zkouším přímou URL: x.com/{handle}")
            self.bot.open_url(f"{self.bot.base_url}{handle}")
            delay(2, 4)

            user_name = self.bot.page.locator('[data-testid="UserName"]').first
            if user_name.is_visible(timeout=5000):
                print(f"[X-SEARCH] Direct URL úspěch: x.com/{handle}")
                return True

            return False

        except Exception:
            return False

    # ------------------------------------------------------------------
    # Google fallback
    # ------------------------------------------------------------------
    def _google_search_fallback(self, target_query: str) -> bool:
        print(f"[GOOGLE] Spouštím záchranné vyhledávání pro: '{target_query}'")
        try:
            self.bot.open_url("https://www.google.com")

            # Odkliknutí cookie dialogu — čekáme až zmizí před dalším krokem
            self.bot.handle_popups(['Přijmout vše', 'Accept all', 'Souhlasím', 'I agree'])

            # Explicitně počkáme na search input — dialog musí být pryč
            # než začneme psát (jinak fill() trefí schovaný input pod overlayem)
            search_input = self.bot.page.locator('textarea[name="q"], input[name="q"]').first
            try:
                search_input.wait_for(state="visible", timeout=6000)
            except PlaywrightTimeoutError:
                print("[GOOGLE] Search input není viditelný — dialog se možná nezavřel.")
                return False

            search_input.click()
            search_input.fill(f"{target_query} twitter")
            delay(0.5)
            search_input.press("Enter")

            print("[GOOGLE] Čekám na výsledky...")
            delay(2, 3)

            results = self.bot.page.locator('a').all()
            for res in results:
                href = res.get_attribute('href')
                if href and (
                    "twitter.com/" in href or "x.com/" in href
                ) and "status" not in href and "search" not in href:
                    print(f"[GOOGLE] Nalezen profil: {href}")
                    res.click()
                    delay(3, 5)
                    return True

            return False

        except Exception as e:
            print(f"[GOOGLE ERROR] {e}")
            return False
```

## Soubor: social_bot\src\bots\x\modules\utils.py
```py
import re

class XUtils:
    @staticmethod
    def parse_number(text):
        if not text: 
            return 0
        text = text.upper().replace(',', '').replace(' ', '').replace('.', '')
        match = re.search(r'([\d\.]+)([KMB]?)', text)
        if not match: 
            return 0
            
        num_str, suffix = match.groups()
        num = float(num_str)
        
        if suffix == 'K': num *= 1000
        elif suffix == 'M': num *= 1000000
        elif suffix == 'B': num *= 1000000000
        
        return int(num)

    @staticmethod
    def extract_media(article_locator, current_text):
        """Vrátí tuple (updated_text, media_url, is_video)"""
        media_url = None
        is_video = False
        
        try:
            # 1. Hledáme primárně explicitní video přehrávač nebo tag video
            video_loc = article_locator.locator('[data-testid="videoPlayer"], video').first
            photo_loc = article_locator.locator('[data-testid="tweetPhoto"]').first
            
            if video_loc.count() > 0:
                is_video = True
                
                # Zjištění, zda je nalezený element přímo video tag
                is_video_tag = video_loc.evaluate("el => el.tagName.toLowerCase() === 'video'")
                if is_video_tag:
                    media_url = video_loc.get_attribute('poster')
                else:
                    poster_video = video_loc.locator('video').first
                    if poster_video.count() > 0:
                        media_url = poster_video.get_attribute('poster')
                
                if not current_text.strip():
                    current_text = "[OBSAHUJE VIDEO]"
                    
            # 2. Pokud se tváří jako fotka, zkontrolujeme ji
            elif photo_loc.count() > 0:
                img_loc = photo_loc.locator('img').first
                if img_loc.count() > 0:
                    media_url = img_loc.get_attribute('src')
                    
                    # Záchranná detekce: X často lazy-loaduje videa jako statické obrázky
                    # Pokud URL obsahuje text indikující náhled videa, přehodnotíme to
                    if media_url and ('video_thumb' in media_url or 'ext_tw_video' in media_url):
                        is_video = True
                        if not current_text.strip():
                            current_text = "[OBSAHUJE VIDEO]"
                            
                # Pokud to video opravdu není, potvrdíme fotku
                if not is_video and not current_text.strip():
                    current_text = "[OBSAHUJE FOTKU]"
                    
        except Exception:
            pass
                
        return current_text, media_url, is_video
```

## Soubor: social_bot\src\bots\youtube\bot.py
```py
from src.core.base_bot import BaseBot
from .scraper import YouTubeScraper

class YouTubeBot(BaseBot):
    def __init__(self, username=None, password=None, user_id="default", headless=True):
        super().__init__(user_id=user_id, platform="youtube", headless=headless)
        
        # Uložíme i když je nevyužijeme (pro zachování stejného rozhraní jako XBot/IGBot)
        self.username = username
        self.password = password
        
        self.base_url = "https://www.youtube.com/"
        
        # Pro YT nepoužíváme Authenticator, jelikož těžíme veřejná data bez přihlášení
        self.scraper = YouTubeScraper(self)

    def login(self):
        # Přepíšeme metodu login, aby nepadala chyba, ale jen bot oznámil přeskočení
        print("[YT] Přihlašování přeskočeno (veřejná data).")
        pass
```

## Soubor: social_bot\src\bots\youtube\scraper.py
```py
from src.utils.human_input import delay
from src.core.database import DatabaseManager
import re
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

class YouTubeScraper:
    def __init__(self, bot):
        self.bot = bot
        self.db = DatabaseManager()
        self.progress_callback = None

    def _report(self, key: str, current: int, total: int):
        if self.progress_callback:
            try:
                self.progress_callback(key, current, total)
            except Exception:
                pass

    def parse_number(self, text):
        if not text: 
            return 0
        text = str(text).upper().replace('\xa0', '').replace(' ', '').replace(',', '.')
        text = re.sub(r'[A-Z-A-ZÁ-Ž]', '', text) 
        
        match = re.search(r'([\d\.]+)([KMB]?)', text)
        if not match: 
            return 0
            
        num_str, suffix = match.groups()
        try:
            num = float(num_str)
        except:
            return 0
        
        if suffix == 'K' or 'TIS' in text: num *= 1000
        elif suffix == 'M' or 'MIL' in text: num *= 1000000
        elif suffix == 'B': num *= 1000000000
        
        return int(num)

    def accept_cookies(self):
        self.bot.handle_popups(['Přijmout vše', 'Accept all', 'Souhlasím', 'I agree'])
        delay(1, 2)

    def _resolve_channel_url(self, target_query):
        """Vyřeší, zda jít na direct URL, vzít to z DB, nebo použít vyhledávání."""
        
        # 1. Je to přímá URL?
        if target_query.startswith("http"):
            if not target_query.endswith("/videos"):
                return target_query.rstrip("/") + "/videos"
            return target_query

        # 2. Hledáme v naší lokální DB (shoda username nebo display_name)
        clean_q = target_query.replace('@', '').strip().lower()
        try:
            self.db.cursor.execute('''
                SELECT username FROM users 
                WHERE platform = 'YT' AND (LOWER(username) = ? OR LOWER(display_name) = ?)
                LIMIT 1
            ''', (clean_q, clean_q))
            row = self.db.cursor.fetchone()
            if row:
                print(f"  -> [YT-SEARCH] Účet nalezen v lokální DB: @{row[0]}")
                return f"https://www.youtube.com/@{row[0]}/videos"
        except Exception as e:
            print(f"  -> [YT-SEARCH] Chyba při čtení DB: {e}")

        # 3. Explicitní @handle (jdu naslepo rovnou na URL)
        if target_query.startswith("@"):
            return f"https://www.youtube.com/{target_query}/videos"

        # 4. Fallback na vyhledávání přímo na YouTube
        print(f"  -> [YT-SEARCH] Kanál nenalezen v DB. Vyhledávám na YouTube...")
        search_url = f"https://www.youtube.com/results?search_query={target_query.replace(' ', '+')}"
        self.bot.open_url(search_url)
        self.accept_cookies()

        try:
            # Počkáme max 8 vteřin na kontejner pro kanál ve výsledcích vyhledávání
            self.bot.page.wait_for_selector('ytd-channel-renderer', timeout=8000)
            channel_link = self.bot.page.locator('ytd-channel-renderer a#main-link').first
            href = channel_link.get_attribute('href')
            if href:
                found_url = f"https://www.youtube.com{href}/videos"
                print(f"  -> [YT-SEARCH] Nalezen kanál ve vyhledávání: {found_url}")
                return found_url
        except PlaywrightTimeoutError:
            print(f"  -> [YT-SEARCH] Ve výsledcích hledání nebyl nalezen žádný kanál.")
            
        return None

    def scrape_profile(self, target_query, limit=10, comments_limit=50):
        limit_text = "NEOMEZENO" if limit == -1 else str(limit)
        print(f"[YT-SCRAPER] Zahajuji těžbu: '{target_query}' (Limit videí: {limit_text})")

        channel_url = self._resolve_channel_url(target_query)
        
        if not channel_url:
            print(f"[ERROR] Nepodařilo se najít platnou URL pro kanál '{target_query}'.")
            return

        self.bot.open_url(channel_url)
        self.accept_cookies()

        print("[YT-SCRAPER] Těžím metadata kanálu...")
        try:
            self.bot.page.wait_for_selector('yt-page-header-view-model', timeout=10000)
            
            channel_data = self.bot.page.evaluate("""
            () => {
                let name = document.querySelector('yt-page-header-view-model h1, #channel-name .ytd-channel-name')?.innerText || "";
                let handle = document.querySelector('yt-page-header-view-model span.yt-core-attributed-string')?.innerText || "";
                let subs = "0";
                
                let textElements = document.querySelectorAll('yt-page-header-view-model span');
                for(let el of textElements) {
                    if(el.innerText.includes('odběr') || el.innerText.includes('subscriber')) {
                        subs = el.innerText;
                        break;
                    }
                }
                return {name: name, handle: handle, subs: subs};
            }
            """)
            
            display_name = channel_data['name']
            actual_username = channel_data['handle'].replace('@', '') or target_query.replace('@', '')
            subs_count = self.parse_number(channel_data['subs'])

        except Exception as e:
            print(f"[ERROR] Nelze načíst metadata kanálu: {e}")
            display_name = target_query
            actual_username = target_query.replace('@', '')
            subs_count = 0

        user_id = self.db.upsert_user(
            platform="YT",
            username=actual_username,
            display_name=display_name,
            followers_count=subs_count
        )
        print(f"[YT-SCRAPER] Kanál uložen. Odběratelé: {subs_count}")

        print("[YT-SCRAPER] Sbírám odkazy na videa...")
        video_urls = []
        scroll_attempts = 0
        
        while True:
            elements = self.bot.page.locator('a#video-title-link, a.ytd-rich-grid-media').all()
            new_found = False
            
            for el in elements:
                href = el.get_attribute('href')
                if href and '/watch?v=' in href:
                    full_url = f"https://www.youtube.com{href.split('&')[0]}"
                    if full_url not in video_urls:
                        video_urls.append(full_url)
                        new_found = True
                        if limit != -1 and len(video_urls) >= limit:
                            break

            if limit != -1 and len(video_urls) >= limit:
                break
                
            if not new_found:
                scroll_attempts += 1
                if scroll_attempts >= 3:
                    break
            else:
                scroll_attempts = 0

            self.bot.page.evaluate("window.scrollBy(0, 1000)")
            delay(1.5, 3)

        final_urls = video_urls[:limit] if limit != -1 else video_urls
        print(f"[YT-SCRAPER] Nalezeno {len(final_urls)} videí.")

        for i, url in enumerate(final_urls):
            self._report("posts", i+1, len(final_urls))
            self.scrape_video(user_id, url, comments_limit)

    def scrape_video(self, db_user_id, video_url, comments_limit=50):
        print(f"\n  -> [YT-SCRAPER] Zpracovávám video: {video_url}")
        
        platform_post_id = video_url.split('v=')[-1].split('&')[0]
        if 'shorts/' in video_url:
            platform_post_id = video_url.split('shorts/')[-1].split('?')[0]

        if self.db.post_exists(platform_post_id):
            print(f"  -> [SKIP] Video {platform_post_id} již existuje.")
            return

        self.bot.open_url(video_url)
        delay(2, 4)

        try:
            more_btn = self.bot.page.locator('tp-yt-paper-button#expand').first
            if more_btn.is_visible(timeout=3000):
                more_btn.click()
                delay(1)
        except: pass

        try:
            title = self.bot.page.locator('h1.ytd-watch-metadata').first.inner_text()
            desc = self.bot.page.locator('#description-inline-expander').first.inner_text()
            text_content = f"{title}\n\n{desc}"
            
            likes_str = "0"
            like_btn = self.bot.page.locator('like-button-view-model button').first
            if like_btn.count() > 0:
                aria = like_btn.get_attribute('aria-label') or ""
                likes_str = re.sub(r'[^\d]', '', aria)
                
            likes_count = int(likes_str) if likes_str.isdigit() else 0

        except Exception as e:
            print(f"  -> [ERROR] Extrakce videa selhala: {e}")
            return

        db_post_id = self.db.upsert_post(
            user_id=db_user_id,
            platform="YT",
            platform_post_id=platform_post_id,
            text_content=text_content,
            timestamp_posted=None, 
            likes_count=likes_count,
            url=video_url
        )

        self._scrape_comments(db_post_id, platform_post_id, comments_limit)

    def _scrape_comments(self, db_post_id, platform_post_id, comments_limit):
        print(f"  -> [YT-SCRAPER] Těžím komentáře (Limit: {comments_limit})...")
        
        # 1. Spolehlivá aktivace (Lazy Load)
        # Scrollujeme 3x za sebou dolů, abychom bezpečně přeskočili i dlouhé popisky videa
        for _ in range(3):
            self.bot.page.evaluate("window.scrollBy(0, 800)")
            delay(1, 2)
        
        try:
            self.bot.page.wait_for_selector('ytd-comment-thread-renderer', timeout=10000)
        except:
            print("  -> [YT-SCRAPER] Komentáře nenalezeny (časový limit, nebo jsou u videa vypnuté).")
            return

        comments_collected = 0
        scroll_attempts = 0
        processed_texts = set()

        # 2. Extrakce přes Playwright lokátory (nativně prorazí i YouTube Shadow DOM)
        while comments_collected < comments_limit:
            # Získáme všechny bloky komentářů, které jsou momentálně vyrenderované na obrazovce
            elements = self.bot.page.locator('ytd-comment-thread-renderer').all()
            new_found = False

            for el in elements:
                if comments_collected >= comments_limit: break
                
                try:
                    # Krátký timeout zabrání zamrznutí, pokud se nějaký element nestihne vykreslit
                    text = el.locator('#content-text').inner_text(timeout=500).strip()
                    if not text or text in processed_texts:
                        continue
                        
                    author = el.locator('#author-text').inner_text(timeout=500).strip()
                    
                    likes_str = "0"
                    vote_el = el.locator('#vote-count-middle')
                    if vote_el.count() > 0:
                        likes_str = vote_el.inner_text().strip()

                    processed_texts.add(text)
                    new_found = True
                    
                    c_likes = self.parse_number(likes_str)
                    c_id = f"{platform_post_id}_{comments_collected}"
                    
                    self.db.upsert_comment(
                        post_id=db_post_id,
                        platform="YT",
                        platform_comment_id=c_id,
                        author_username=author,
                        author_display_name=author,
                        text_content=text,
                        timestamp_posted=None,
                        likes_count=c_likes
                    )
                    comments_collected += 1
                    
                except Exception:
                    # Při scrollování může YouTube staré komentáře smazat (Detached from DOM)
                    # To je běžný jev, proto chybu ignorujeme a jedeme na další element
                    continue

            if not new_found:
                scroll_attempts += 1
                if scroll_attempts >= 4:
                    print("  -> [YT-SCRAPER] Dosažen konec dostupných komentářů.")
                    break
            else:
                scroll_attempts = 0

            # Scroll pro načtení další várky
            self.bot.page.evaluate("window.scrollBy(0, 1500)")
            delay(1.5, 3)

        print(f"  -> [YT-SCRAPER] Dokončeno. Uloženo {comments_collected} komentářů.")
```

## Soubor: social_bot\src\core\base_bot.py
```py
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from src.utils.human_input import delay

class BaseBot:
    def __init__(self, headless=True, user_id="default", platform="general"):
        self.user_id = str(user_id)
        self.platform = platform
        
        self.playwright = sync_playwright().start()
        self.context = None
        self.page = self._setup_driver(headless)

    def _setup_driver(self, headless):
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        
        profile_folder = f"{self.user_id}_{self.platform}"
        profile_path = project_root / 'profiles' / profile_folder
        os.makedirs(profile_path, exist_ok=True)
        
        print(f"[BOT] Nastavuji izolovaný profil (Playwright): {profile_path}")
        
        args = [
            '--disable-blink-features=AutomationControlled',
            '--window-position=0,0',
            '--disable-infobars',
            '--disable-extensions'
        ]

        try:
            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_path),
                headless=headless,
                args=args,
                no_viewport=True,
                channel="chrome",
                accept_downloads=True
            )
            
            page = self.context.pages[0] if self.context.pages else self.context.new_page()
            self._apply_stealth_scripts(page)
            return page
            
        except Exception as e:
            print(f"[CRITICAL ERROR] Nelze spustit Playwright prohlížeč: {e}")
            if self.playwright:
                self.playwright.stop()
            raise e

    def _apply_stealth_scripts(self, page):
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page.add_init_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]})")
        page.add_init_script("Object.defineProperty(navigator, 'languages', {get: () => ['cs-CZ', 'cs', 'en-US', 'en']})")

    def open_url(self, url):
        print(f"[BOT] Otevírám {url}")
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            delay(3, 5)
        except Exception as e:
            print(f"[ERROR] Chyba při otevírání URL: {e}")

    def find_element_smart(self, selector, description="prvek", timeout=10):
        try:
            locator = self.page.locator(selector).first
            locator.wait_for(state="attached", timeout=timeout * 1000)
            return locator
        except PlaywrightTimeoutError:
            return None
        except Exception as e:
            print(f"[DEBUG] Chyba hledání prvku '{description}': {e}")
            return None

    def click_smart(self, selector, description="tlačítko", timeout=5):
        locator = self.find_element_smart(selector, description, timeout)
        if locator:
            try:
                locator.click(timeout=timeout * 1000)
                return True
            except:
                try:
                    locator.click(force=True, timeout=timeout * 1000)
                    return True
                except:
                    pass
        return False

    def handle_popups(self, triggers):
        """
        Klikne na první viditelné tlačítko/odkaz jehož text přesně odpovídá
        některému z řetězců v `triggers`.

        Rozdíl oproti původní verzi:
          - Hledáme konkrétně <button> nebo <a> elementy (ne libovolný text na stránce),
            čímž se vyhneme trefení textu v dropdownech nebo popisných odstavcích.
          - Po úspěšném kliknutí čekáme až dialog zmizí z DOM (max 5 s),
            teprve pak vrátíme True — volající kód tak dostane stránku bez překrytí.
        """
        # CSS selektor omezený na interaktivní prvky
        BUTTON_SELECTOR = "button, a[role='button'], a"

        for text in triggers:
            try:
                # Filtrujeme: interaktivní prvek, jehož viditelný text obsahuje hledaný řetězec
                locator = self.page.locator(BUTTON_SELECTOR).filter(has_text=text).first
                if not locator.is_visible(timeout=1500):
                    continue

                # Ověříme že jde skutečně o tlačítko (ne náhodný odkaz s podobným textem)
                tag = locator.evaluate("el => el.tagName.toLowerCase()")
                role = locator.get_attribute("role") or ""
                el_text = (locator.inner_text() or "").strip()

                # Přijmeme pouze pokud text odpovídá celému tlačítku (ne jen části dlouhého textu)
                if len(el_text) > len(text) * 3:
                    continue  # příliš dlouhý text → pravděpodobně špatný element

                locator.click(force=True)
                print(f"[BOT] Odkliknuto vyskakovací okno: '{text}'")

                # Počkáme až element zmizí (dialog se zavřel)
                try:
                    locator.wait_for(state="hidden", timeout=5000)
                except Exception:
                    pass  # nevadí — pokud už zmizel, timeout je OK

                delay(1.5, 2.5)  # extra pauza pro překreslení stránky
                return True

            except Exception:
                continue

        return False

    def close(self):
        if getattr(self, 'context', None) is None:
            return
            
        print(f"[BOT] Ukládám profil {self.user_id}_{self.platform} a zavírám (Playwright)...")
        try:
            self.context.close()
            if self.playwright:
                self.playwright.stop()
            self.context = None
            self.page = None
            print("[BOT] Uloženo.")
        except Exception:
            pass
```

## Soubor: social_bot\src\core\database.py
```py
import sqlite3
import os
import uuid
from pathlib import Path
from datetime import datetime, timezone

class DatabaseManager:
    def __init__(self, db_name="osint.db"):
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        self.data_dir = project_root / 'data'
        
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.db_path = self.data_dir / db_name
        self.conn = None
        self.cursor = None
        
        self._connect()
        self._create_tables()
        self._migrate_db() # Důležité: Přidá nové sloupce do existující DB

    def _connect(self):
        self.conn = sqlite3.connect(str(self.db_path), timeout=10, check_same_thread=False)
        self.cursor = self.conn.cursor()

    def _create_tables(self):
        # TABULKA USERS - Rozšířená o metadata
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                platform_user_id TEXT,
                username TEXT NOT NULL,
                display_name TEXT,
                bio TEXT,
                followers_count INTEGER,
                following_count INTEGER,
                joined_date TEXT,
                location TEXT,
                website TEXT, 
                is_verified INTEGER DEFAULT 0,
                profile_pic_url TEXT, 
                banner_url TEXT,
                last_scraped TIMESTAMP,
                UNIQUE(platform, username)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                platform_post_id TEXT NOT NULL,
                text_content TEXT,
                media_url TEXT,
                timestamp_posted TIMESTAMP,
                likes_count INTEGER DEFAULT 0,
                shares_count INTEGER DEFAULT 0,
                comments_count INTEGER DEFAULT 0,
                url TEXT,
                scraped_at TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id),
                UNIQUE(platform_post_id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS comments (
                id TEXT PRIMARY KEY,
                post_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                platform_comment_id TEXT NOT NULL,
                author_username TEXT,
                author_display_name TEXT,
                text_content TEXT,
                media_url TEXT,
                timestamp_posted TIMESTAMP,
                likes_count INTEGER DEFAULT 0,
                shares_count INTEGER DEFAULT 0,
                replies_count INTEGER DEFAULT 0,
                scraped_at TIMESTAMP,
                FOREIGN KEY(post_id) REFERENCES posts(id),
                UNIQUE(platform_comment_id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS trending (
                id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                rank INTEGER,
                category TEXT,
                topic_name TEXT NOT NULL,
                post_count TEXT,
                scraped_at TIMESTAMP,
                UNIQUE(platform, topic_name)
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS connections (
                id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                source_username TEXT NOT NULL,
                target_username TEXT NOT NULL,
                connection_type TEXT NOT NULL,
                scraped_at TIMESTAMP,
                UNIQUE(platform, source_username, target_username, connection_type)
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS watchlist (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                platform        TEXT    NOT NULL DEFAULT 'IG',
                username        TEXT    NOT NULL,
                interval_min    INTEGER NOT NULL DEFAULT 20,
                limit_posts     INTEGER NOT NULL DEFAULT 10,
                limit_comments  INTEGER NOT NULL DEFAULT 50,
                limit_followers INTEGER NOT NULL DEFAULT 0,
                limit_following INTEGER NOT NULL DEFAULT 0,
                enabled         INTEGER NOT NULL DEFAULT 1,
                last_scraped_at TEXT,
                next_scrape_at  TEXT,
                added_at        TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE(platform, username)
            )
        ''')
        self.conn.commit()

    def _migrate_db(self):
        """Zkontroluje a přidá chybějící sloupce."""
        required_columns = {
            "following_count": "INTEGER",
            "joined_date": "TEXT",
            "location": "TEXT",
            "website": "TEXT",
            "is_verified": "INTEGER DEFAULT 0",
            "banner_url": "TEXT",
            "profile_pic_url": "TEXT"
        }

        try:
            self.cursor.execute("PRAGMA table_info(users)")
            existing = [row[1] for row in self.cursor.fetchall()]

            for col, type_ in required_columns.items():
                if col not in existing:
                    print(f"[DB] Migrace: Přidávám sloupec '{col}'...")
                    try: self.cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {type_}")
                    except: pass
            self.conn.commit()
        except Exception as e:
            print(f"[DB ERROR] Migrace selhala: {e}")

    def upsert_user(self, platform, username, platform_user_id=None, display_name=None, 
                    bio=None, followers_count=None, following_count=None, 
                    joined_date=None, location=None, website=None, is_verified=0,
                    profile_pic_url=None, banner_url=None):
        
        now = datetime.now(timezone.utc).isoformat()
        
        self.cursor.execute('SELECT id FROM users WHERE platform = ? AND username = ?', (platform, username))
        row = self.cursor.fetchone()
        
        if row:
            user_id = row[0]
            self.cursor.execute('''
                UPDATE users SET
                    platform_user_id = COALESCE(?, platform_user_id),
                    display_name = COALESCE(?, display_name),
                    bio = COALESCE(?, bio),
                    followers_count = COALESCE(?, followers_count),
                    following_count = COALESCE(?, following_count),
                    joined_date = COALESCE(?, joined_date),
                    location = COALESCE(?, location),
                    website = COALESCE(?, website),
                    is_verified = ?,
                    profile_pic_url = COALESCE(?, profile_pic_url),
                    banner_url = COALESCE(?, banner_url),
                    last_scraped = ?
                WHERE id = ?
            ''', (platform_user_id, display_name, bio, followers_count, following_count, 
                  joined_date, location, website, is_verified, profile_pic_url, banner_url, now, user_id))
        else:
            user_id = str(uuid.uuid4())
            self.cursor.execute('''
                INSERT INTO users (
                    id, platform, platform_user_id, username, display_name, bio, 
                    followers_count, following_count, joined_date, location, website, is_verified,
                    profile_pic_url, banner_url, last_scraped
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, platform, platform_user_id, username, display_name, bio, 
                  followers_count, following_count, joined_date, location, website, is_verified,
                  profile_pic_url, banner_url, now))
        
        self.conn.commit()
        return user_id
    
    def post_exists(self, platform_post_id: str) -> bool:
        self.cursor.execute(
            "SELECT 1 FROM posts WHERE platform_post_id = ?",
            (platform_post_id,)
        )
        return self.cursor.fetchone() is not None

    def upsert_post(self, user_id, platform, platform_post_id, text_content, timestamp_posted, likes_count=0, shares_count=0, comments_count=0, url=None, media_url=None):
        now = datetime.now(timezone.utc).isoformat()
        self.cursor.execute('SELECT id FROM posts WHERE platform_post_id = ?', (platform_post_id,))
        row = self.cursor.fetchone()
        if row:
            post_id = row[0]
            self.cursor.execute('''UPDATE posts SET media_url=?, likes_count=?, shares_count=?, comments_count=?, scraped_at=? WHERE id=?''', (media_url, likes_count, shares_count, comments_count, now, post_id))
        else:
            post_id = str(uuid.uuid4())
            self.cursor.execute('''INSERT INTO posts (id, user_id, platform, platform_post_id, text_content, media_url, timestamp_posted, likes_count, shares_count, comments_count, url, scraped_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (post_id, user_id, platform, platform_post_id, text_content, media_url, timestamp_posted, likes_count, shares_count, comments_count, url, now))
        self.conn.commit()
        return post_id

    def upsert_comment(self, post_id, platform, platform_comment_id, author_username, author_display_name, text_content, timestamp_posted, likes_count=0, shares_count=0, replies_count=0, media_url=None):
        now = datetime.now(timezone.utc).isoformat()
        self.cursor.execute('SELECT id FROM comments WHERE platform_comment_id = ?', (platform_comment_id,))
        row = self.cursor.fetchone()
        if row:
            comment_id = row[0]
            self.cursor.execute('''UPDATE comments SET media_url=?, likes_count=?, shares_count=?, replies_count=?, scraped_at=? WHERE id=?''', (media_url, likes_count, shares_count, replies_count, now, comment_id))
        else:
            comment_id = str(uuid.uuid4())
            self.cursor.execute('''INSERT INTO comments (id, post_id, platform, platform_comment_id, author_username, author_display_name, text_content, media_url, timestamp_posted, likes_count, shares_count, replies_count, scraped_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (comment_id, post_id, platform, platform_comment_id, author_username, author_display_name, text_content, media_url, timestamp_posted, likes_count, shares_count, replies_count, now))
        self.conn.commit()
        return comment_id

    def upsert_trend(self, platform, rank, category, topic_name, post_count):
        now = datetime.now(timezone.utc).isoformat()
        self.cursor.execute('SELECT id FROM trending WHERE platform = ? AND topic_name = ?', (platform, topic_name))
        row = self.cursor.fetchone()
        if row:
            trend_id = row[0]
            self.cursor.execute('''UPDATE trending SET rank=?, category=?, post_count=?, scraped_at=? WHERE id=?''', (rank, category, post_count, now, trend_id))
        else:
            trend_id = str(uuid.uuid4())
            self.cursor.execute('''INSERT INTO trending (id, platform, rank, category, topic_name, post_count, scraped_at) VALUES (?, ?, ?, ?, ?, ?, ?)''', (trend_id, platform, rank, category, topic_name, post_count, now))
        self.conn.commit()
        return trend_id
    
    def get_known_handle(self, query):
        """
        Pokusí se najít username v DB na základě query (shoda s username nebo display_name).
        Vrací username (str) nebo None.
        """
        clean_q = query.replace('@', '').strip()
        
        try:
            self.cursor.execute('''
                SELECT username FROM users 
                WHERE platform = 'X' AND (LOWER(username) = LOWER(?) OR LOWER(display_name) = LOWER(?))
                LIMIT 1
            ''', (clean_q, clean_q))
            row = self.cursor.fetchone()
            
            if row:
                return row[0]
            return None
            
        except Exception as e:
            print(f"[DB ERROR] Chyba při hledání handle: {e}")
            return None
        
    def upsert_connection(self, platform, source_username, target_username, connection_type="follower"):
        now = datetime.now(timezone.utc).isoformat()
        self.cursor.execute('''
            SELECT id FROM connections 
            WHERE platform = ? AND source_username = ? AND target_username = ? AND connection_type = ?
        ''', (platform, source_username, target_username, connection_type))
        row = self.cursor.fetchone()
        
        if row:
            conn_id = row[0]
            self.cursor.execute('UPDATE connections SET scraped_at = ? WHERE id = ?', (now, conn_id))
        else:
            conn_id = str(uuid.uuid4())
            self.cursor.execute('''
                INSERT INTO connections (id, platform, source_username, target_username, connection_type, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (conn_id, platform, source_username, target_username, connection_type, now))
        self.conn.commit()
        return conn_id

    def close(self):
        if self.conn:
            self.cursor.close()
            self.conn.close()
```

## Soubor: social_bot\src\core\session_logger.py
```py
# src/core/session_logger.py
"""
SessionLogger — zaznamenává statistiky každého běhu scrapingu do SQLite.

Co se ukládá (tabulka scrape_sessions):
  Identifikace:
    - session_id       UUID každého běhu
    - platform         instagram / X
    - bot_identity     jméno identity bota (např. "0 - Petr")
    - target_username  cílový profil
    - started_at       čas spuštění
    - finished_at      čas dokončení
    - duration_s       délka v sekundách

  Výsledky scrapingu:
    - posts_scraped        počet příspěvků
    - comments_scraped     počet komentářů
    - followers_scraped    počet sledujících
    - following_scraped    počet sledovaných
    - profiles_found       počet nalezených profilů (při batch)

  Rychlost (vypočteno automaticky):
    - posts_per_min        příspěvky / minutu
    - comments_per_min     komentáře / minutu
    - followers_per_min    sledující / minutu

  Síťový provoz (pouze bot, přes Playwright listener):
    - rx_bytes_total       staženo (bytes)
    - tx_bytes_total       odesláno (bytes)
    - rx_bytes_per_post    průměr staženo / příspěvek
    - bytes_per_comment    průměr staženo / komentář

  Kvalita dat:
    - search_method        jak byl profil nalezen (db_cache / x_search / google_fallback)
    - profile_found        0/1 — byl profil nalezen?
    - error_count          počet zachycených chyb během běhu
    - was_interrupted      0/1 — byl běh přerušen uživatelem?

  Kontext (pro srovnání v diplomce):
    - headless             0/1
    - limit_posts          nastavený limit příspěvků (-1 = vše)
    - limit_comments       nastavený limit komentářů
    - limit_followers      nastavený limit sledujících
    - limit_following      nastavený limit sledovaných
    - notes                volitelná poznámka (např. "test bez VPN")

Použití:
    from src.core.session_logger import SessionLogger

    sl = SessionLogger()
    session_id = sl.start_session(
        platform="X", bot_identity="0 - Petr",
        target_username="realDonaldTrump",
        limit_posts=10, limit_comments=50,
        limit_followers=50, limit_following=50
    )

    # ... scraping ...
    sl.set_counts(posts=10, comments=45, followers=50, following=30)
    sl.set_traffic(rx_bytes=1_200_000, tx_bytes=80_000)
    sl.set_search_method("x_search")
    sl.log_error()   # při každé zachycené výjimce

    sl.finish_session()   # vypočte rychlosti, uloží do DB
    sl.finish_session(interrupted=True)   # při UKONČIT OPERACI
"""

import uuid
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path


class SessionLogger:

    def __init__(self, db_name: str = "osint.db"):
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        data_dir     = project_root / "data"
        data_dir.mkdir(exist_ok=True)
        self.db_path = data_dir / db_name

        self._conn   = sqlite3.connect(str(self.db_path), timeout=10,
                                       check_same_thread=False)
        self._cur    = self._conn.cursor()
        self._create_table()

        # Aktuální session (reset při každém start_session)
        self._session_id    : str | None = None
        self._start_time    : float      = 0.0
        self._counts        : dict       = {}
        self._traffic       : dict       = {}
        self._search_method : str        = "unknown"
        self._error_count   : int        = 0
        self._meta          : dict       = {}

    # ------------------------------------------------------------------
    # Tabulka
    # ------------------------------------------------------------------
    def _create_table(self):
        self._cur.execute("""
            CREATE TABLE IF NOT EXISTS scrape_sessions (
                session_id          TEXT PRIMARY KEY,
                platform            TEXT,
                bot_identity        TEXT,
                target_username     TEXT,
                started_at          TEXT,
                finished_at         TEXT,
                duration_s          REAL,

                posts_scraped       INTEGER DEFAULT 0,
                comments_scraped    INTEGER DEFAULT 0,
                followers_scraped   INTEGER DEFAULT 0,
                following_scraped   INTEGER DEFAULT 0,

                posts_per_min       REAL DEFAULT 0,
                comments_per_min    REAL DEFAULT 0,
                followers_per_min   REAL DEFAULT 0,

                rx_bytes_total      INTEGER DEFAULT 0,
                tx_bytes_total      INTEGER DEFAULT 0,
                rx_bytes_per_post   REAL DEFAULT 0,
                bytes_per_comment   REAL DEFAULT 0,

                search_method       TEXT,
                profile_found       INTEGER DEFAULT 1,
                error_count         INTEGER DEFAULT 0,
                was_interrupted     INTEGER DEFAULT 0,

                headless            INTEGER DEFAULT 1,
                limit_posts         INTEGER,
                limit_comments      INTEGER,
                limit_followers     INTEGER,
                limit_following     INTEGER,
                notes               TEXT
            )
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Veřejné API
    # ------------------------------------------------------------------
    def start_session(self, platform: str, bot_identity: str,
                      target_username: str,
                      limit_posts: int = 10,
                      limit_comments: int = 50,
                      limit_followers: int = 50,
                      limit_following: int = 50,
                      headless: bool = True,
                      notes: str = "") -> str:
        """Zahájí novou session. Vrátí session_id."""
        self._session_id  = str(uuid.uuid4())
        self._start_time  = time.time()
        self._counts      = {"posts": 0, "comments": 0,
                             "followers": 0, "following": 0}
        self._traffic     = {"rx": 0, "tx": 0}
        self._search_method = "unknown"
        self._error_count = 0
        self._meta        = {
            "platform":        platform,
            "bot_identity":    bot_identity,
            "target_username": target_username,
            "limit_posts":     limit_posts,
            "limit_comments":  limit_comments,
            "limit_followers": limit_followers,
            "limit_following": limit_following,
            "headless":        int(headless),
            "notes":           notes,
            "started_at":      datetime.now(timezone.utc).isoformat(),
        }
        print(f"[SESSION] Zahájena session {self._session_id[:8]}… "
              f"({platform} / {target_username})")
        return self._session_id

    def set_counts(self, posts: int = 0, comments: int = 0,
                   followers: int = 0, following: int = 0):
        """Nastaví finální počty (volat těsně před finish_session)."""
        self._counts = {"posts": posts, "comments": comments,
                        "followers": followers, "following": following}

    def set_traffic(self, rx_bytes: int = 0, tx_bytes: int = 0):
        """Nastaví síťová data z BotTrafficCounter."""
        self._traffic = {"rx": rx_bytes, "tx": tx_bytes}

    def set_search_method(self, method: str):
        """Zaznamená jak byl profil nalezen: db_cache / x_search / google_fallback / not_found."""
        self._search_method = method

    def set_profile_found(self, found: bool):
        self._meta["profile_found"] = int(found)

    def log_error(self):
        """Inkrementuje počítadlo chyb."""
        self._error_count += 1

    def finish_session(self, interrupted: bool = False):
        """Vypočte metriky, uloží do DB."""
        if not self._session_id:
            return

        duration  = max(time.time() - self._start_time, 0.001)
        dur_min   = duration / 60.0

        posts     = self._counts["posts"]
        comments  = self._counts["comments"]
        followers = self._counts["followers"]
        following = self._counts["following"]
        rx        = self._traffic["rx"]
        tx        = self._traffic["tx"]

        posts_pm    = round(posts    / dur_min, 3) if dur_min > 0 else 0
        comments_pm = round(comments / dur_min, 3) if dur_min > 0 else 0
        followers_pm= round(followers/ dur_min, 3) if dur_min > 0 else 0
        rx_per_post = round(rx / posts, 1)         if posts   > 0 else 0
        bytes_per_c = round(rx / comments, 1)      if comments > 0 else 0

        finished_at = datetime.now(timezone.utc).isoformat()

        self._cur.execute("""
            INSERT INTO scrape_sessions (
                session_id, platform, bot_identity, target_username,
                started_at, finished_at, duration_s,
                posts_scraped, comments_scraped,
                followers_scraped, following_scraped,
                posts_per_min, comments_per_min, followers_per_min,
                rx_bytes_total, tx_bytes_total,
                rx_bytes_per_post, bytes_per_comment,
                search_method, profile_found, error_count, was_interrupted,
                headless, limit_posts, limit_comments,
                limit_followers, limit_following, notes
            ) VALUES (
                ?,?,?,?,?,?,?,
                ?,?,?,?,
                ?,?,?,
                ?,?,?,?,
                ?,?,?,?,
                ?,?,?,?,?,?
            )
        """, (
            self._session_id,
            self._meta["platform"],
            self._meta["bot_identity"],
            self._meta["target_username"],
            self._meta["started_at"],
            finished_at,
            round(duration, 2),
            posts, comments, followers, following,
            posts_pm, comments_pm, followers_pm,
            rx, tx, rx_per_post, bytes_per_c,
            self._search_method,
            self._meta.get("profile_found", 1),
            self._error_count,
            int(interrupted),
            self._meta["headless"],
            self._meta["limit_posts"],
            self._meta["limit_comments"],
            self._meta["limit_followers"],
            self._meta["limit_following"],
            self._meta["notes"],
        ))
        self._conn.commit()

        print(f"[SESSION] Dokončena {self._session_id[:8]}… | "
              f"{round(duration,1)}s | "
              f"P:{posts}({posts_pm}/min) "
              f"K:{comments}({comments_pm}/min) | "
              f"RX:{rx//1024}KB TX:{tx//1024}KB")

        self._session_id = None

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass

```

## Soubor: social_bot\src\core\watchlist_scheduler.py
```py
"""
src/core/watchlist_scheduler.py

Periodicky kontroluje watchlist a spouští scrape nových dat.
Běží ve vlastním vlákně, nekopíruje existující záznamy.
"""

import threading
import time
from datetime import datetime, timedelta
from src.core.database import DatabaseManager


class WatchlistScheduler:
    def __init__(self, scraper_factory):
        """
        scraper_factory: callable() -> instance scraperu (např. InstagramScraper)
        Volá se vždy fresh aby měl vlastní page/session.
        """
        self.scraper_factory = scraper_factory
        self.db = DatabaseManager()
        self._stop_event = threading.Event()
        self._thread = None
        self._current_target = None   # pro GUI status
        self._lock = threading.Lock()
        self.on_status_change = None  # callback(msg: str) pro GUI

    # ------------------------------------------------------------------
    # Veřejné API
    # ------------------------------------------------------------------
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self._log("[WATCHLIST] Scheduler spuštěn.")

    def stop(self):
        self._stop_event.set()
        self._log("[WATCHLIST] Scheduler zastaven.")

    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def get_current_target(self):
        with self._lock:
            return self._current_target

    # ------------------------------------------------------------------
    # Hlavní smyčka
    # ------------------------------------------------------------------
    def _loop(self):
        while not self._stop_event.is_set():
            try:
                due = self._get_due_entries()
                for entry in due:
                    if self._stop_event.is_set():
                        break
                    self._run_scrape(entry)
            except Exception as e:
                self._log(f"[WATCHLIST ERROR] {e}")

            # Kontrola každých 60 s
            self._stop_event.wait(60)

    def _get_due_entries(self):
        """Vrátí záznamy kde next_scrape_at <= now a enabled=1."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.db.cursor.execute('''
            SELECT id, platform, username, interval_min,
                   limit_posts, limit_comments, limit_followers, limit_following
            FROM watchlist
            WHERE enabled = 1
              AND (next_scrape_at IS NULL OR next_scrape_at <= ?)
            ORDER BY next_scrape_at ASC
        ''', (now,))
        return self.db.cursor.fetchall()

    def _run_scrape(self, entry):
        row_id, platform, username, interval_min, lp, lc, lf, lfol = entry

        with self._lock:
            self._current_target = username

        self._log(f"[WATCHLIST] Spouštím scrape: @{username} (interval: {interval_min} min)")

        bot = None
        try:
            bot = self.scraper_factory()          # vrací InstagramBot instanci
            bot.scraper.scrape_profile(
                target_query=username,
                limit=lp,
                comments_limit=lc,
                followers_limit=lf,
                following_limit=lfol,
            )
        except Exception as e:
            self._log(f"[WATCHLIST ERROR] Scrape @{username} selhal: {e}")
        finally:
            # Zavři bot po každém scrape
            if bot:
                try:
                    bot.close()
                except Exception:
                    pass

            now = datetime.now()
            next_scrape = (now + timedelta(minutes=interval_min)).strftime("%Y-%m-%d %H:%M:%S")
            self.db.cursor.execute('''
                UPDATE watchlist
                SET last_scraped_at = ?, next_scrape_at = ?
                WHERE id = ?
            ''', (now.strftime("%Y-%m-%d %H:%M:%S"), next_scrape, row_id))
            self.db.conn.commit()

            with self._lock:
                self._current_target = None

            self._log(f"[WATCHLIST] @{username} hotovo. Další scrape: {next_scrape}")

    def _log(self, msg):
        print(msg)
        if self.on_status_change:
            self.on_status_change(msg)
```

## Soubor: social_bot\src\gui\app.py
```py
# src/gui/app.py
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import threading
import json
import os
import time
import sys
from pathlib import Path

from src.core.watchlist_scheduler import WatchlistScheduler
from src.gui.frames.watchlist import WatchlistFrame
from src.bots.instagram.scraper import InstagramScraper

from src.gui.theme import COLORS
from src.gui.utils import PrintLogger
from src.gui.frames.dashboard import DashboardFrame
from src.gui.frames.profiles import ProfilesFrame
from src.gui.frames.database import DatabaseFrame
from src.gui.frames.analysis import AnalysisFrame
from src.gui.frames.metrics import MetricsFrame, _fmt_speed
from src.gui.frames.sessions import SessionsFrame

from src.core.session_logger import SessionLogger
from src.gui.browser_preview import CDPScreencast

from src.bots.instagram.bot import InstagramBot
from src.bots.x.bot import XBot
from src.bots.youtube.bot import YouTubeBot  # Import YouTube bota

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        def _make_watchlist_bot(self):
            """Vrátí InstagramBot pro watchlist scheduler — použije první IG identitu."""
            for key, user in self.users_map.items():
                ig = user.get("social_media", {}).get("instagram")
                if ig:
                    uid = key.split()[0]  # "0 - Jan" → "0"
                    return InstagramBot(ig["username"], ig["password"], uid)
            raise RuntimeError("Žádná Instagram identita nenalezena v users.json")

        self.scheduler = WatchlistScheduler(
            scraper_factory=lambda: self._make_watchlist_bot()
        )

        self.title("Ogma 0.0")
        self.geometry("1200x800")
        self.minsize(1000, 700)

        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        self.data_path = project_root / "data" / "users.json"
        self.db_path   = project_root / "data" / "osint.db"

        icon_path = project_root / "src" / "gui" / "ogma_ai_logo.ico"
        if icon_path.exists():
            self.iconbitmap(str(icon_path))

        self.users_map          = {}
        self.current_bot        = None
        self.current_screencast = None
        self.is_running         = False

        # Session počítadla
        self._session_posts     = 0
        self._session_comments  = 0
        self._session_followers = 0
        self._session_following = 0

        self.load_users()

        # Session logger
        self.session_logger = SessionLogger()

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        # ── Sidebar ──────────────────────────────────────────────────
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0,
                                    fg_color=COLORS["sidebar_bg"])
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.pack_propagate(False)

        # ── Main area ────────────────────────────────────────────────
        self.main_area = ctk.CTkFrame(self, corner_radius=0,
                                      fg_color=COLORS["main_bg"])
        self.main_area.grid(row=0, column=1, sticky="nsew")
        self.main_area.grid_rowconfigure(0, weight=1)
        self.main_area.grid_columnconfigure(0, weight=1)

        # ── Bottom bar (progress) ─────────────────────────────────────
        self._bottom_bar = ctk.CTkFrame(
            self, height=28, corner_radius=0,
            fg_color=COLORS["sidebar_bg"]
        )
        self._bottom_bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        self._bottom_bar.grid_propagate(False)
        self._bottom_bar.grid_columnconfigure(1, weight=1)

        self._progress_label = ctk.CTkLabel(
            self._bottom_bar, text="Připraveno",
            font=("Segoe UI", 10), text_color=COLORS["text_dim"],
            width=120, anchor="w"
        )
        self._progress_label.grid(row=0, column=0, padx=(12, 8), pady=4)

        self._global_progress = ctk.CTkProgressBar(
            self._bottom_bar, height=8, corner_radius=4,
            fg_color=COLORS["main_bg"], progress_color=COLORS["primary"]
        )
        self._global_progress.set(0)
        self._global_progress.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=9)

        self._progress_pct = ctk.CTkLabel(
            self._bottom_bar, text="",
            font=("Consolas", 10), text_color=COLORS["text_dim"],
            width=40, anchor="e"
        )
        self._progress_pct.grid(row=0, column=2, padx=(0, 12), pady=4)

        # ── Frames ──
        self.frame_dash     = DashboardFrame(self.main_area, self)
        self.frame_prof     = ProfilesFrame(self.main_area, self)
        self.frame_db       = DatabaseFrame(self.main_area, self)
        self.frame_analysis = AnalysisFrame(self.main_area, self)
        self.frame_metrics  = MetricsFrame(self.main_area, self)
        self.frame_sessions = SessionsFrame(self.main_area, self)
        self.frame_watchlist = WatchlistFrame(self.main_area, self.scheduler)

        sys.stdout = PrintLogger(self.frame_dash.log_box, self)
        sys.stderr = PrintLogger(self.frame_dash.log_box, self)

        self.setup_sidebar()
        self.show_frame("dashboard")

    def setup_sidebar(self):
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.pack(pady=(25, 20), padx=20, fill="x")
        ctk.CTkLabel(logo_frame, text="Ogma 0.0", font=("Segoe UI", 22, "bold"),
                     text_color=COLORS["text_main"], anchor="w").pack(fill="x")
        ctk.CTkLabel(logo_frame, text="OSINT Automation Tool",
                     font=("Segoe UI", 12),
                     text_color=COLORS["text_dim"], anchor="w").pack(fill="x")

        ctk.CTkFrame(self.sidebar, height=1,
                     fg_color=COLORS["border"]).pack(fill="x", pady=10)

        self.btn_nav_dash     = self.create_nav_btn("Přehled (Dashboard)", "dashboard")
        self.btn_nav_prof     = self.create_nav_btn("Scrapnuté Profily",   "profiles")
        self.btn_nav_db       = self.create_nav_btn("Databáze (Vault)",    "database")
        self.btn_nav_analysis = self.create_nav_btn("Analýza",             "analysis")
        self.btn_nav_metrics  = self.create_nav_btn("Metriky",             "metrics")
        self.btn_nav_sessions = self.create_nav_btn("Historie běhů",       "sessions")
        self.btn_nav_watchlist = self.create_nav_btn("Watchlist",          "watchlist")

        self._sidebar_traffic_frame = ctk.CTkFrame(
            self.sidebar, fg_color=COLORS["panel_bg"],
            corner_radius=6, border_width=1, border_color=COLORS["border"]
        )
        self._sidebar_traffic_frame.pack(side="bottom", fill="x",
                                         padx=14, pady=(0, 8))

        _hdr = ctk.CTkFrame(self._sidebar_traffic_frame, fg_color="transparent")
        _hdr.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(_hdr, text="SÍŤOVÝ PROVOZ",
                     font=("Segoe UI", 9, "bold"),
                     text_color=COLORS["text_dim"]).pack(side="left")
        self._traffic_status_dot = ctk.CTkLabel(
            _hdr, text="●", font=("Segoe UI", 9),
            text_color=COLORS["text_dim"])
        self._traffic_status_dot.pack(side="right")

        def _traffic_row(parent, label, color):
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=1)
            ctk.CTkLabel(row, text=label, font=("Segoe UI", 9),
                         text_color=COLORS["text_dim"],
                         width=14, anchor="w").pack(side="left")
            var = ctk.StringVar(value="—")
            ctk.CTkLabel(row, textvariable=var, font=("Consolas", 10),
                         text_color=color, anchor="e").pack(side="right")
            return var

        self._sidebar_rx_var = _traffic_row(self._sidebar_traffic_frame, "↓", "#175DDC")
        self._sidebar_tx_var = _traffic_row(self._sidebar_traffic_frame, "↑", "#2eb85c")

        self._sidebar_sparkline = tk.Canvas(
            self._sidebar_traffic_frame, height=28,
            bg=COLORS["panel_bg"], highlightthickness=0, bd=0)
        self._sidebar_sparkline.pack(fill="x", padx=8, pady=(2, 6))

        self._sidebar_traffic_poll()

        bottom_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom_frame.pack(side="bottom", fill="x", padx=14, pady=(0, 8))

        self.status_label = ctk.CTkLabel(
            bottom_frame, text="● Připraveno",
            text_color="#2eb85c", font=("Segoe UI", 12), anchor="w"
        )
        self.status_label.pack(fill="x", pady=(0, 8))

    def _sidebar_traffic_poll(self):
        try:
            t = self.frame_metrics.traffic
            with t._lock:
                rx_s    = t.rx_speed
                tx_s    = t.tx_speed
                running = t._running
                rx_hist = list(t.rx_history)
                tx_hist = list(t.tx_history)

            if running:
                self._sidebar_rx_var.set(_fmt_speed(rx_s))
                self._sidebar_tx_var.set(_fmt_speed(tx_s))
                self._traffic_status_dot.configure(text_color="#2eb85c")
            else:
                self._sidebar_rx_var.set("—")
                self._sidebar_tx_var.set("—")
                self._traffic_status_dot.configure(text_color=COLORS["text_dim"])

            self._sidebar_draw_sparkline(rx_hist, tx_hist)
        except Exception:
            pass
        self.after(1000, self._sidebar_traffic_poll)

    def _sidebar_draw_sparkline(self, rx, tx):
        c = self._sidebar_sparkline
        w = c.winfo_width()
        h = c.winfo_height()
        if w <= 1 or h <= 1: return
        c.delete("all")

        def draw(history, color):
            peak = max(history) or 1
            n    = len(history)
            pts  = []
            for i, v in enumerate(history):
                x = int(i / (n - 1) * w) if n > 1 else w // 2
                y = int(h - (v / peak) * (h - 2))
                pts.extend([x, y])
            if len(pts) >= 4:
                c.create_line(pts, fill=color, width=1, smooth=True)

        draw(rx, "#175DDC")
        draw(tx, "#2eb85c")

    def create_nav_btn(self, text, view_name):
        return (
            ctk.CTkButton(
                self.sidebar, text=text,
                command=lambda: self.show_frame(view_name),
                fg_color="transparent", text_color=COLORS["text_dim"],
                hover_color=COLORS["panel_bg"], anchor="w",
                height=45, font=("Segoe UI", 14), corner_radius=4
            ).pack(fill="x", padx=10, pady=2)
            or self.sidebar.winfo_children()[-1]
        )

    def show_frame(self, name):
        all_btns = [
            self.btn_nav_dash, self.btn_nav_prof, self.btn_nav_db,
            self.btn_nav_analysis, self.btn_nav_metrics, self.btn_nav_sessions,
            self.btn_nav_watchlist
        ]
        for btn in all_btns:
            btn.configure(fg_color="transparent", text_color=COLORS["text_dim"])

        all_frames = [
            self.frame_dash, self.frame_prof, self.frame_db,
            self.frame_analysis, self.frame_metrics, self.frame_sessions,
            self.frame_watchlist
        ]
        for f in all_frames:
            f.grid_forget()

        pad = dict(row=0, column=0, sticky="nsew", padx=30, pady=30)

        if name == "dashboard":
            self.frame_dash.grid(**pad)
            self.btn_nav_dash.configure(fg_color=COLORS["panel_bg"], text_color=COLORS["primary"])
        elif name == "profiles":
            self.frame_prof.grid(**pad)
            self.btn_nav_prof.configure(fg_color=COLORS["panel_bg"], text_color=COLORS["primary"])
            self.frame_prof.refresh_data()
        elif name == "database":
            self.frame_db.grid(**pad)
            self.btn_nav_db.configure(fg_color=COLORS["panel_bg"], text_color=COLORS["primary"])
            self.frame_db.refresh_data()
        elif name == "analysis":
            self.frame_analysis.grid(**pad)
            self.btn_nav_analysis.configure(fg_color=COLORS["panel_bg"], text_color=COLORS["primary"])
            self.frame_analysis.refresh_results()
        elif name == "metrics":
            self.frame_metrics.grid(**pad)
            self.btn_nav_metrics.configure(fg_color=COLORS["panel_bg"], text_color=COLORS["primary"])
        elif name == "sessions":
            self.frame_sessions.grid(**pad)
            self.btn_nav_sessions.configure(fg_color=COLORS["panel_bg"], text_color=COLORS["primary"])
            self.frame_sessions.refresh_data()
        elif name == "watchlist":
            self.frame_watchlist.grid(**pad)
            self.btn_nav_watchlist.configure(fg_color=COLORS["panel_bg"], text_color=COLORS["primary"])
            self.frame_watchlist._refresh_list()

    def set_progress(self, current: int, total: int, label: str = ""):
        if total <= 0:
            self._global_progress.set(0)
            self._progress_pct.configure(text="")
            self._progress_label.configure(text=label or "Připraveno")
            return
        pct = min(current / total, 1.0)
        self._global_progress.set(pct)
        self._progress_pct.configure(text=f"{int(pct * 100)} %")
        self._progress_label.configure(text=label or f"{current} / {total}")

    def reset_progress(self):
        self._global_progress.set(0)
        self._progress_pct.configure(text="")
        self._progress_label.configure(text="Připraveno")

    def update_sidebar_progress(self, key: str, current: int, total: int):
        labels = {
            "posts":     "Příspěvky",
            "comments":  "Komentáře",
            "followers": "Sledující",
            "following": "Sleduje",
            "sentiment": "Analýza sentimentu",
            "batch":     "Cíle",
        }
        lbl = f"{labels.get(key, key)}  {current}/{total}"
        self.set_progress(current, total, lbl)

    def load_users(self):
        if not os.path.exists(self.data_path):
            return
        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for user in data.get("users", []):
                self.users_map[f"{user['ID']} - {user['name']}"] = user
        except Exception:
            pass

    def start_thread(self, platform, action):
        if self.is_running:
            messagebox.showwarning("Busy", "Bot již běží.")
            return

        key = self.frame_dash.user_var.get()
        if not key:
            messagebox.showerror("Chyba", "Vyber identitu.")
            return

        user_data = self.users_map[key]
        social    = user_data.get("social_media", {}).get(platform)
        
        # YouTube nevyžaduje uložené heslo v identitě
        if not social and platform != "youtube":
            messagebox.showerror("Chyba", f"Identita nemá {platform}.")
            return

        target_input = self.frame_dash.target_var.get().strip()
        if action == "scrape" and not target_input:
            messagebox.showwarning("Chyba", "Zadej cíl.")
            return

        u = social["username"] if social else None
        p = social["password"] if social else None

        limit = 10
        if self.frame_dash.scrape_all_var.get():
            limit = -1
        else:
            try:
                limit = int(self.frame_dash.limit_var.get())
            except ValueError:
                messagebox.showerror("Chyba", "Limit příspěvků musí být číslo.")
                return

        try:
            comments_limit = int(self.frame_dash.comments_limit_var.get())
        except ValueError:
            messagebox.showerror("Chyba", "Limit komentářů musí být číslo.")
            return

        try:
            followers_limit = int(self.frame_dash.followers_limit_var.get())
        except ValueError:
            messagebox.showerror("Chyba", "Limit sledujících musí být číslo.")
            return

        try:
            following_limit = int(self.frame_dash.following_limit_var.get())
        except ValueError:
            messagebox.showerror("Chyba", "Limit 'Sleduje' musí být číslo.")
            return

        self.is_running = True
        txt_limit = "VŠE" if limit == -1 else str(limit)
        self.status_label.configure(
            text=f"● Běží: {platform} (P:{txt_limit} K:{comments_limit})",
            text_color=COLORS["primary"]
        )

        self.frame_dash.log_box.configure(state="normal")
        self.frame_dash.log_box.delete(1.0, tk.END)
        self.frame_dash.log_box.configure(state="disabled")

        headless = self.frame_dash.headless_var.get()

        threading.Thread(
            target=self.run_bot,
            args=(platform, u, p,
                  key.split()[0], action, target_input,
                  limit, comments_limit, followers_limit, following_limit,
                  headless),
            daemon=True
        ).start()

    def run_bot(self, platform, u, p, uid, action, target_input,
                limit, comments_limit, followers_limit, following_limit,
                headless=True):
        try:
            # ── Vytvoření bota ──
            if platform == "instagram":
                bot = InstagramBot(u, p, uid, headless=headless)
            elif platform == "youtube":
                bot = YouTubeBot(u, p, uid, headless=headless)
            else:
                bot = XBot(u, p, uid, headless=headless)
                
            self.current_bot = bot
            bot.login()

            # ── Progress callback ──
            self._session_posts     = 0
            self._session_comments  = 0
            self._session_followers = 0
            self._session_following = 0

            if hasattr(bot, "scraper"):
                labels = {
                    "posts":     "Příspěvky",
                    "comments":  "Komentáře",
                    "followers": "Sledující",
                    "following": "Sleduje",
                    "sentiment": "Analýza sentimentu",
                    "batch":     "Cíle",
                }
                def _progress_cb(key, current, total):
                    if key == "posts":     self._session_posts     = current
                    if key == "comments":  self._session_comments  = current
                    if key == "followers": self._session_followers  = current
                    if key == "following": self._session_following  = current
                    lbl = f"{labels.get(key, key)}  {current}/{total}"
                    self.after(0, lambda c=current, t=total, l=lbl:
                        self.set_progress(c, t, l))
                bot.scraper.progress_callback = _progress_cb

            # ── CDP Screencast ──
            try:
                self.current_screencast = CDPScreencast(
                    page=bot.page,
                    on_frame=lambda img: self.after(
                        0, lambda i=img:
                        self.frame_dash.browser_preview.push_frame(i)),
                    on_stop=lambda: self.after(
                        0, self.frame_dash.browser_preview.set_offline)
                )
                self.current_screencast.start()
            except Exception as e:
                print(f"[PREVIEW] Nelze spustit náhled: {e}")

            # ── Traffic monitoring ──
            try:
                self.frame_metrics.traffic.attach(bot.page)
                self.after(0, lambda: self.frame_metrics._bot_status_var.set(
                    "● Bot běží  —  měřím provoz"))
            except Exception as e:
                print(f"[METRICS] Nelze spustit monitoring: {e}")

            # ── Scraping ──
            if action == "scrape":
                targets = [t.strip() for t in target_input.replace("\n", ",").split(",") if t.strip()]
                total = len(targets)
                self.after(0, lambda: self.set_progress(0, total, f"Cíle  0/{total}"))

                for i, target in enumerate(targets):
                    if not self.is_running: break

                    self.after(0, lambda idx=i, tot=total, t=target: [
                        self.status_label.configure(text=f"● Težím {idx+1}/{tot}: {t}", text_color=COLORS["primary"]),
                        self.set_progress(idx, tot, f"Cíle  {idx}/{tot}: {t}"),
                    ])

                    # Reset session
                    self.frame_metrics.traffic.reset()
                    self.session_logger.start_session(
                        platform=platform, bot_identity=uid, target_username=target,
                        limit_posts=limit, limit_comments=comments_limit,
                        limit_followers=followers_limit, limit_following=following_limit
                    )

                    interrupted = False
                    try:
                        bot.scraper.scrape_profile(target, limit, comments_limit)
                    except Exception as e:
                        self.session_logger.log_error()
                        print(f"[ERROR] Chyba u cíle {target}: {e}")

                    if not self.is_running: interrupted = True

                    with self.frame_metrics.traffic._lock:
                        rx = self.frame_metrics.traffic.rx_total
                        tx = self.frame_metrics.traffic.tx_total

                    self.session_logger.set_traffic(rx_bytes=rx, tx_bytes=tx)
                    self.session_logger.set_counts(posts=self._session_posts, comments=self._session_comments)
                    self.session_logger.finish_session(interrupted=interrupted)

                    if not interrupted and i < total - 1:
                        time.sleep(3)

            elif action == "scrape_trending":
                bot.scraper.scrape_trending()

            # ── Post-processing ──
            if action == "scrape":
                print("[INFO] Spouštím automatickou sentiment analýzu...")
                try:
                    from src.analysis.sentiment import SentimentAnalyzer
                    sa = SentimentAnalyzer()
                    sa.analyze_pending()
                except: pass

        except Exception as e:
            print(f"CHYBA: {e}")
        finally:
            try:
                if self.current_screencast: self.current_screencast.stop()
                self.frame_metrics.traffic.detach()
                self.after(0, self.frame_metrics.bot_stopped)
            except: pass

            if self.current_bot: self.current_bot.close()
            self.current_bot = None
            self.is_running  = False
            self.after(0, self.reset_progress)
            self.after(0, lambda: self.status_label.configure(text="● Připraveno", text_color="#2eb85c"))

    def stop_bot(self):
        self.is_running = False
        if self.current_bot:
            try: self.current_bot.close()
            except: pass
            self.current_bot = None


if __name__ == "__main__":
    app = App()
    app.mainloop()
```

## Soubor: social_bot\src\gui\browser_preview.py
```py
# src/gui/browser_preview.py

import base64
from io import BytesIO
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk
from src.gui.theme import COLORS

class BrowserPreview(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["panel_bg"], **kwargs)
        self.pack_propagate(False)

        # Hlavička (Zůstává CTk pro zachování designu)
        self._header = ctk.CTkFrame(self, height=28, corner_radius=0, fg_color="transparent")
        self._header.pack(fill="x")
        self._header.pack_propagate(False)

        ctk.CTkLabel(self._header, text="NÁHLED PROHLÍŽEČE", font=("Segoe UI", 10, "bold"), text_color=COLORS["text_dim"]).pack(side="left", padx=8)
        self._status_dot = ctk.CTkLabel(self._header, text="● OFFLINE", font=("Segoe UI", 10), text_color=COLORS["text_dim"])
        self._status_dot.pack(side="right", padx=8)

        # Pro samotný obrázek použijeme "hloupý" tk.Label. 
        # Zabráníme tím double-scaling bugu při High-DPI ve Windows.
        self._image_label = tk.Label(
            self, 
            text="Stream není aktivní.\nSpusť scraping pro zobrazení prohlížeče.",
            bg=COLORS["sidebar_bg"], # Pozadí v barvě aplikace
            fg=COLORS["text_dim"],   # Barva textu
            font=("Segoe UI", 12)
        )
        self._image_label.pack(fill="both", expand=True)

    def _get_dpi_scale(self) -> float:
        """Vrátí DPI škálovací faktor okna (1.0 = 96 dpi, 1.25 = 120 dpi, atd.)."""
        try:
            # winfo_fpixels('1i') = kolik fyzických pixelů je 1 palec (96 = standard)
            return self._image_label.winfo_fpixels('1i') / 96.0
        except Exception:
            return 1.0

    def push_frame(self, image_b64_or_bytes):
        """Přijme snímek, vypočítá správný poměr stran a bezpečně jej zobrazí."""
        if not self.winfo_exists():
            return

        try:
            if isinstance(image_b64_or_bytes, str):
                image_bytes = base64.b64decode(image_b64_or_bytes)
            else:
                image_bytes = image_b64_or_bytes

            pil_img = Image.open(BytesIO(image_bytes))
        except Exception as e:
            print(f"[PREVIEW] Chyba dekódování: {e}")
            return

        # winfo_width/height vrací LOGICKÉ pixely — při DPI škálování > 100 %
        # (např. 125 %, 150 %) jsou menší než fyzické pixely obrazovky.
        # ImageTk.PhotoImage pracuje s fyzickými pixely, proto musíme převést.
        dpi_scale = self._get_dpi_scale()
        cw = int(self._image_label.winfo_width() * dpi_scale)
        ch = int(self._image_label.winfo_height() * dpi_scale)

        if cw < 10 or ch < 10:
            return

        iw, ih = pil_img.size
        
        # Matematika pro letterboxing (přizpůsobení s ohledem na poměr stran)
        scale = min(cw / iw, ch / ih)
        new_w = max(1, int(iw * scale))
        new_h = max(1, int(ih * scale))
        
        # Přeškálování v PIL (Bilinear je dostatečně rychlý a kvalitní pro stream)
        pil_img = pil_img.resize((new_w, new_h), Image.Resampling.BILINEAR)

        # Obalení do základního ImageTk (žádné nechtěné zvětšování na pozadí)
        img_tk = ImageTk.PhotoImage(pil_img)

        # Vykreslení
        self._image_label.configure(image=img_tk, text="")
        self._image_label.image = img_tk  # Držíme referenci, aby obrázek nezmizel
        self._status_dot.configure(text="● LIVE", text_color="#2eb85c")

    def set_offline(self):
        """Vrátí widget do OFFLINE stavu."""
        self._status_dot.configure(text="● OFFLINE", text_color=COLORS["text_dim"])
        
        # Smazání obrázku a vrácení textu
        self._image_label.configure(
            image="", 
            text="Stream není aktivní.\nSpusť scraping pro zobrazení prohlížeče."
        )
        self._image_label.image = None


class CDPScreencast:
    """Obaluje CDP komunikaci pro sběr screenshotů."""
    def __init__(self, page, on_frame, on_stop=None, quality=50, max_width=1280, max_height=720):
        self.page = page
        self.on_frame = on_frame
        self.on_stop = on_stop
        self.quality = quality
        self.max_width = max_width
        self.max_height = max_height
        
        self.client = None
        self._running = False

    def _handle_screencast_frame(self, event):
        if not self._running:
            return
        data = event.get("data")
        session_id = event.get("sessionId")
        if data:
            self.on_frame(data)
        if session_id:
            try:
                self.client.send("Page.screencastFrameAck", {"sessionId": session_id})
            except Exception:
                pass

    def start(self):
        try:
            self.client = self.page.context.new_cdp_session(self.page)
            self.client.on("Page.screencastFrame", self._handle_screencast_frame)
            self.client.send("Page.startScreencast", {
                "format": "jpeg",
                "quality": self.quality,
                "maxWidth": self.max_width,
                "maxHeight": self.max_height,
                "everyNthFrame": 1
            })
            self._running = True
            print("[PREVIEW] Screencast spuštěn.")
        except Exception as e:
            print(f"[PREVIEW] Nelze spustit screencast: {e}")

    def stop(self):
        self._running = False
        try:
            if self.client:
                self.client.send("Page.stopScreencast")
                self.client.detach()
        except Exception:
            pass
        if self.on_stop:
            self.on_stop()
```

## Soubor: social_bot\src\gui\db_viewer.py
```py
import customtkinter as ctk
from tkinter import ttk
import sqlite3
from pathlib import Path

class DatabaseViewer(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Prohlížeč Databáze - osint.db")
        self.geometry("1000x600")
        
        # Stylování standardního Tkinter Treeview do tmavého režimu
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", 
                        background="#2b2b2b", 
                        foreground="white", 
                        rowheight=25, 
                        fieldbackground="#2b2b2b",
                        bordercolor="#343638",
                        borderwidth=0)
        style.map('Treeview', background=[('selected', '#1f538d')])
        style.configure("Treeview.Heading", 
                        background="#565b5e", 
                        foreground="white", 
                        relief="flat")
        style.map("Treeview.Heading", background=[('active', '#343638')])

        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        self.db_path = project_root / 'data' / 'osint.db'

        # Přepínání tabulek
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=20)
        self.tabview.add("Uživatelé (Users)")
        self.tabview.add("Příspěvky (Posts)")

        self.users_tree = self.create_treeview(self.tabview.tab("Uživatelé (Users)"))
        self.posts_tree = self.create_treeview(self.tabview.tab("Příspěvky (Posts)"))

        self.load_data()

    def create_treeview(self, parent_frame):
        tree_scroll_y = ctk.CTkScrollbar(parent_frame, orientation="vertical")
        tree_scroll_y.pack(side="right", fill="y")
        
        tree_scroll_x = ctk.CTkScrollbar(parent_frame, orientation="horizontal")
        tree_scroll_x.pack(side="bottom", fill="x")

        tree = ttk.Treeview(parent_frame, yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)
        tree.pack(fill="both", expand=True)
        
        tree_scroll_y.configure(command=tree.yview)
        tree_scroll_x.configure(command=tree.xview)
        
        return tree

    def load_data(self):
        if not self.db_path.exists():
            return

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # Načtení uživatelů
            cursor.execute("SELECT id, platform, username, display_name, followers_count, last_scraped FROM users")
            users_rows = cursor.fetchall()
            
            self.users_tree['columns'] = ("ID", "Platform", "Username", "Display Name", "Followers", "Last Scraped")
            self.users_tree.column("#0", width=0, stretch="no")
            for col in self.users_tree['columns']:
                self.users_tree.column(col, anchor="w", width=150)
                self.users_tree.heading(col, text=col, anchor="w")

            for row in users_rows:
                self.users_tree.insert("", "end", values=row)

            # Načtení příspěvků
            cursor.execute("SELECT id, platform_post_id, text_content, likes_count, timestamp_posted, scraped_at FROM posts")
            posts_rows = cursor.fetchall()

            self.posts_tree['columns'] = ("ID", "Post ID", "Text", "Likes", "Posted At", "Scraped At")
            self.posts_tree.column("#0", width=0, stretch="no")
            for col in self.posts_tree['columns']:
                self.posts_tree.column(col, anchor="w", width=150)
                self.posts_tree.heading(col, text=col, anchor="w")

            for row in posts_rows:
                # Oříznutí textu, aby tabulka nebyla moc široká
                row_list = list(row)
                if row_list[2] and len(row_list[2]) > 50:
                    row_list[2] = row_list[2][:47] + "..."
                self.posts_tree.insert("", "end", values=row_list)

            conn.close()
        except Exception as e:
            print(f"Chyba při načítání databáze: {e}")
```

## Soubor: social_bot\src\gui\theme.py
```py
# src/gui/theme.py

# --- BITWARDEN THEME PALETTE (Dark Mode) ---
COLORS = {
    "sidebar_bg": "#171b1e",
    "main_bg": "#222529",
    "panel_bg": "#2c3035",
    "primary": "#175DDC",
    "primary_hover": "#144eb8",
    "text_main": "#ffffff",
    "text_dim": "#9eaab5",
    "border": "#3b4047",
    "danger": "#ab1818",
    "success": "#2eb85c",
    "verified": "#1DA1F2"
}
```

## Soubor: social_bot\src\gui\utils.py
```py
# src/gui/utils.py
import tkinter as tk
import customtkinter as ctk
import requests
from io import BytesIO
from PIL import Image
from datetime import datetime

class PrintLogger:
    def __init__(self, textbox, tk_app):
        self.textbox = textbox
        self.tk_app = tk_app

    def write(self, text):
        self.tk_app.after(0, self._insert_text, text)

    def _insert_text(self, text):
        if not self.textbox: return # Pojistka
        
        self.textbox.configure(state="normal")
        if text.strip():
            current_time = datetime.now().strftime("[%H:%M:%S]")
            self.textbox.insert(tk.END, f"{current_time} {text}")
        else:
            self.textbox.insert(tk.END, text)
            
        self.textbox.see(tk.END)
        self.textbox.configure(state="disabled")

    def flush(self):
        pass

class AsyncImageLoader:
    def __init__(self):
        self.image_cache = {}

    def load_image(self, url, label_widget, size=(80, 80)):
        if not url: return
        
        # Pokud je v cache, použijeme ho rovnou
        if url in self.image_cache:
            self._update_label(label_widget, self.image_cache[url])
            return

        # Jinak stáhneme (toto by se mělo volat v threadu z GUI)
        try:
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                img_data = BytesIO(response.content)
                pil_img = Image.open(img_data)
                
                # Center Crop
                width, height = pil_img.size
                if width != height:
                    new_size = min(width, height)
                    left = (width - new_size) / 2
                    top = (height - new_size) / 2
                    right = (width + new_size) / 2
                    bottom = (height + new_size) / 2
                    pil_img = pil_img.crop((left, top, right, bottom))
                
                pil_img = pil_img.resize(size, Image.Resampling.LANCZOS)
                ctk_image = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)
                
                self.image_cache[url] = ctk_image
                self._update_label(label_widget, ctk_image)
        except Exception:
            pass

    def _update_label(self, label, image):
        try:
            label.configure(image=image, text="", fg_color="transparent")
        except: pass
```

## Soubor: social_bot\src\gui\frames\analysis.py
```py
# src/gui/frames/analysis.py
"""
Záložka "Analýza" v hlavním okně aplikace.
Sekce:
  1. Sentiment analýza komentářů (VADER + kontextový slovník)
  2. OCR analýza obrázků (Tesseract)
  3. Výsledková tabulka sentimentu per uživatel
"""

import customtkinter as ctk
from tkinter import ttk
import threading
import sqlite3
from src.gui.theme import COLORS


class AnalysisFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.setup_ui()

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # --- Nadpis ---
        ctk.CTkLabel(
            self, text="Analýza dat",
            font=("Segoe UI", 24, "bold"),
            text_color=COLORS["text_main"]
        ).grid(row=0, column=0, sticky="w", pady=(0, 20))

        # --- Sekce 1: Sentiment ---
        self._build_sentiment_panel()

        # --- Sekce 2: OCR ---
        self._build_ocr_panel()

        # --- Sekce 3: Výsledková tabulka ---
        self._build_results_table()

    # ------------------------------------------------------------------
    # Panel 1 — Sentiment analýza
    # ------------------------------------------------------------------
    def _build_sentiment_panel(self):
        panel = ctk.CTkFrame(self, fg_color=COLORS["panel_bg"], corner_radius=10)
        panel.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        panel.grid_columnconfigure(1, weight=1)

        # Ikona + název
        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=3, sticky="w", padx=20, pady=(15, 4))

        ctk.CTkLabel(
            header, text="💬",
            font=("Segoe UI", 18)
        ).pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            header, text="Sentiment analýza komentářů",
            font=("Segoe UI", 15, "bold"), text_color=COLORS["text_main"]
        ).pack(side="left")

        ctk.CTkLabel(
            panel,
            text="Projde všechny nové komentáře a příspěvky v DB, přiřadí skóre "
                 "(-1.0 negativní → +1.0 pozitivní) pomocí kontextového slovníku + VADER.",
            font=("Segoe UI", 12), text_color=COLORS["text_dim"],
            wraplength=700, justify="left"
        ).grid(row=1, column=0, columnspan=3, padx=20, pady=(0, 10), sticky="w")

        self.btn_sentiment = ctk.CTkButton(
            panel, text="▶  Spustit analýzu",
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
            font=("Segoe UI", 13, "bold"), height=38, width=180,
            command=self.run_sentiment
        )
        self.btn_sentiment.grid(row=2, column=0, padx=20, pady=(0, 15), sticky="w")

        self.sentiment_progress = ctk.CTkProgressBar(
            panel, height=8, corner_radius=4, progress_color=COLORS["primary"]
        )
        self.sentiment_progress.set(0)
        self.sentiment_progress.grid(row=2, column=1, padx=(10, 10), pady=(0, 15), sticky="ew")

        self.sentiment_label = ctk.CTkLabel(
            panel, text="", font=("Segoe UI", 12),
            text_color=COLORS["text_dim"], width=120, anchor="e"
        )
        self.sentiment_label.grid(row=2, column=2, padx=(0, 20), pady=(0, 15))

    # ------------------------------------------------------------------
    # Panel 2 — OCR analýza obrázků
    # ------------------------------------------------------------------
    def _build_ocr_panel(self):
        panel = ctk.CTkFrame(self, fg_color=COLORS["panel_bg"], corner_radius=10)
        panel.grid(row=2, column=0, sticky="ew", pady=(0, 20))
        panel.grid_columnconfigure(1, weight=1)

        # Ikona + název
        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=3, sticky="w", padx=20, pady=(15, 4))

        ctk.CTkLabel(
            header, text="🖼",
            font=("Segoe UI", 18)
        ).pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            header, text="OCR analýza obrázků",
            font=("Segoe UI", 15, "bold"), text_color=COLORS["text_main"]
        ).pack(side="left")

        ctk.CTkLabel(
            panel,
            text="Stáhne obrázky z příspěvků a komentářů, extrahuje text pomocí Tesseract OCR "
                 "a provede sentiment analýzu nalezeného textu. Podporuje: EN, CS, SK, ES.",
            font=("Segoe UI", 12), text_color=COLORS["text_dim"],
            wraplength=700, justify="left"
        ).grid(row=1, column=0, columnspan=3, padx=20, pady=(0, 10), sticky="w")

        # Tlačítka — příspěvky a komentáře zvlášť
        btn_frame = ctk.CTkFrame(panel, fg_color="transparent")
        btn_frame.grid(row=2, column=0, padx=20, pady=(0, 15), sticky="w")

        self.btn_ocr_posts = ctk.CTkButton(
            btn_frame, text="▶  Příspěvky",
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
            font=("Segoe UI", 13, "bold"), height=38, width=140,
            command=lambda: self.run_ocr("posts")
        )
        self.btn_ocr_posts.pack(side="left", padx=(0, 8))

        self.btn_ocr_comments = ctk.CTkButton(
            btn_frame, text="▶  Komentáře",
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
            font=("Segoe UI", 13, "bold"), height=38, width=140,
            command=lambda: self.run_ocr("comments")
        )
        self.btn_ocr_comments.pack(side="left", padx=(0, 8))

        self.btn_ocr_both = ctk.CTkButton(
            btn_frame, text="▶  Vše",
            fg_color=COLORS["panel_bg"], hover_color=COLORS["border"],
            border_width=1, border_color=COLORS["primary"],
            text_color=COLORS["primary"],
            font=("Segoe UI", 13, "bold"), height=38, width=90,
            command=lambda: self.run_ocr("both")
        )
        self.btn_ocr_both.pack(side="left")

        self.ocr_progress = ctk.CTkProgressBar(
            panel, height=8, corner_radius=4, progress_color="#e8a020"
        )
        self.ocr_progress.set(0)
        self.ocr_progress.grid(row=2, column=1, padx=(10, 10), pady=(0, 15), sticky="ew")

        self.ocr_label = ctk.CTkLabel(
            panel, text="", font=("Segoe UI", 12),
            text_color=COLORS["text_dim"], width=120, anchor="e"
        )
        self.ocr_label.grid(row=2, column=2, padx=(0, 20), pady=(0, 15))

        # Statistiky OCR
        self.ocr_stats_label = ctk.CTkLabel(
            panel, text="",
            font=("Segoe UI", 11), text_color=COLORS["text_dim"]
        )
        self.ocr_stats_label.grid(row=3, column=0, columnspan=3, padx=20, pady=(0, 12), sticky="w")
        self._refresh_ocr_stats()

    # ------------------------------------------------------------------
    # Výsledková tabulka
    # ------------------------------------------------------------------
    def _build_results_table(self):
        ctk.CTkLabel(
            self, text="VÝSLEDKY SENTIMENTU PER UŽIVATEL",
            font=("Segoe UI", 11, "bold"), text_color=COLORS["text_dim"]
        ).grid(row=3, column=0, sticky="w", pady=(0, 5))

        results_frame = ctk.CTkFrame(self, fg_color="transparent")
        results_frame.grid(row=4, column=0, sticky="nsew")
        results_frame.grid_columnconfigure(0, weight=1)
        results_frame.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Analysis.Treeview",
            background=COLORS["main_bg"], foreground=COLORS["text_main"],
            rowheight=30, fieldbackground=COLORS["main_bg"],
            borderwidth=0, font=("Segoe UI", 11)
        )
        style.configure(
            "Analysis.Treeview.Heading",
            background=COLORS["panel_bg"], foreground=COLORS["text_main"],
            relief="flat", font=("Segoe UI", 11, "bold"), padding=(10, 5)
        )
        style.map(
            "Analysis.Treeview",
            background=[("selected", COLORS["primary"])],
            foreground=[("selected", "white")]
        )

        scroll_y = ctk.CTkScrollbar(results_frame)
        scroll_y.grid(row=0, column=1, sticky="ns")

        columns = (
            "Platform", "Uživatel", "Komentářů",
            "Avg. skóre", "😊 Pozit.", "😐 Neutr.", "😠 Negat.",
            "🖼 OCR textů"
        )
        self.tree = ttk.Treeview(
            results_frame, columns=columns,
            show="headings", style="Analysis.Treeview",
            yscrollcommand=scroll_y.set
        )
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.configure(command=self.tree.yview)

        col_widths = {
            "Platform": 80, "Uživatel": 150, "Komentářů": 100,
            "Avg. skóre": 110, "😊 Pozit.": 85, "😐 Neutr.": 85,
            "😠 Negat.": 85, "🖼 OCR textů": 100
        }
        for col in columns:
            self.tree.heading(col, text=col, anchor="w")
            self.tree.column(col, width=col_widths.get(col, 100), anchor="w")

        self.tree.tag_configure("positive", foreground="#2eb85c")
        self.tree.tag_configure("negative", foreground="#e05252")
        self.tree.tag_configure("neutral",  foreground=COLORS["text_main"])

    # ------------------------------------------------------------------
    # Akce — Sentiment
    # ------------------------------------------------------------------
    def run_sentiment(self):
        self.btn_sentiment.configure(state="disabled", text="⏳  Probíhá...")
        self.sentiment_progress.set(0)
        self.sentiment_label.configure(text="0 / ?")
        threading.Thread(target=self._sentiment_thread, daemon=True).start()

    def _sentiment_thread(self):
        try:
            from src.analysis.sentiment import SentimentAnalyzer
            analyzer = SentimentAnalyzer()

            def cb(current, total):
                pct = current / total if total > 0 else 0
                self.after(0, lambda c=current, t=total, p=pct: [
                    self.sentiment_progress.set(p),
                    self.sentiment_label.configure(text=f"{c} / {t}")
                ])

            count = analyzer.analyze_pending(callback=cb)
            self.after(0, lambda: [
                self.sentiment_progress.set(1.0),
                self.sentiment_label.configure(text=f"✓ {count} zpracováno"),
                self.refresh_results()
            ])
        except Exception as e:
            self.after(0, lambda: self.sentiment_label.configure(text=f"Chyba: {e}"))
        finally:
            self.after(0, lambda: self.btn_sentiment.configure(
                state="normal", text="▶  Spustit analýzu"
            ))

    # ------------------------------------------------------------------
    # Akce — OCR
    # ------------------------------------------------------------------
    def run_ocr(self, mode: str):
        for btn in [self.btn_ocr_posts, self.btn_ocr_comments, self.btn_ocr_both]:
            btn.configure(state="disabled")
        self.ocr_progress.set(0)
        self.ocr_label.configure(text="Probíhá...")
        threading.Thread(target=self._ocr_thread, args=(mode,), daemon=True).start()

    def _ocr_thread(self, mode: str):
        try:
            from src.analysis.image_ocr import ImageOCRAnalyzer
            analyzer = ImageOCRAnalyzer()
            total_processed = 0

            def cb(current, total):
                pct = current / total if total > 0 else 0
                self.after(0, lambda c=current, t=total, p=pct: [
                    self.ocr_progress.set(p),
                    self.ocr_label.configure(text=f"{c} / {t}")
                ])

            if mode in ("posts", "both"):
                total_processed += analyzer.analyze_pending_posts(callback=cb)
            if mode in ("comments", "both"):
                self.after(0, lambda: self.ocr_progress.set(0))
                total_processed += analyzer.analyze_pending_comments(callback=cb)

            self.after(0, lambda n=total_processed: [
                self.ocr_progress.set(1.0),
                self.ocr_label.configure(text=f"✓ {n} zpracováno"),
                self._refresh_ocr_stats(),
                self.refresh_results()
            ])
        except Exception as e:
            self.after(0, lambda err=e: self.ocr_label.configure(text=f"Chyba: {err}"))
            print(f"[OCR ERROR] {e}")
        finally:
            self.after(0, lambda: [
                btn.configure(state="normal")
                for btn in [self.btn_ocr_posts, self.btn_ocr_comments, self.btn_ocr_both]
            ])

    # ------------------------------------------------------------------
    # Statistiky OCR (kolik obrázků zbývá)
    # ------------------------------------------------------------------
    def _refresh_ocr_stats(self):
        if not self.controller.db_path.exists():
            return
        try:
            conn = sqlite3.connect(str(self.controller.db_path))
            cur = conn.cursor()

            stats = {}
            for table in ("posts", "comments"):
                try:
                    cur.execute(f"""
                        SELECT
                            COUNT(*) AS total_with_media,
                            SUM(CASE WHEN media_text IS NOT NULL AND media_text != '' THEN 1 ELSE 0 END) AS with_text,
                            SUM(CASE WHEN media_text IS NULL THEN 1 ELSE 0 END) AS pending
                        FROM {table}
                        WHERE media_url IS NOT NULL AND media_url != ''
                          AND (
                            media_url LIKE '%.jpg%' OR media_url LIKE '%.jpeg%'
                            OR media_url LIKE '%.png%' OR media_url LIKE '%.webp%'
                            OR media_url LIKE '%pbs.twimg%' OR media_url LIKE '%cdninstagram%'
                          )
                    """)
                    row = cur.fetchone()
                    stats[table] = row if row else (0, 0, 0)
                except Exception:
                    stats[table] = (0, 0, 0)

            conn.close()

            p_total, p_text, p_pend = stats["posts"]
            c_total, c_text, c_pend = stats["comments"]

            msg = (
                f"Příspěvky: {p_text or 0}/{p_total or 0} s textem  |  "
                f"Komentáře: {c_text or 0}/{c_total or 0} s textem  |  "
                f"Čeká na zpracování: {(p_pend or 0) + (c_pend or 0)}"
            )
            self.after(0, lambda: self.ocr_stats_label.configure(text=msg))

        except Exception as e:
            print(f"[OCR STATS ERROR] {e}")

    # ------------------------------------------------------------------
    # Obnovení výsledkové tabulky
    # ------------------------------------------------------------------
    def refresh_results(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        if not self.controller.db_path.exists():
            return

        try:
            conn = sqlite3.connect(str(self.controller.db_path))
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    u.platform,
                    u.username,
                    COUNT(c.id)                      AS total,
                    ROUND(AVG(c.sentiment_score), 3) AS avg_score,
                    SUM(CASE WHEN c.sentiment_label = 'positive' THEN 1 ELSE 0 END) AS pos,
                    SUM(CASE WHEN c.sentiment_label = 'neutral'  THEN 1 ELSE 0 END) AS neu,
                    SUM(CASE WHEN c.sentiment_label = 'negative' THEN 1 ELSE 0 END) AS neg,
                    SUM(CASE WHEN c.media_text IS NOT NULL AND c.media_text != '' THEN 1 ELSE 0 END) AS ocr_count
                FROM comments c
                JOIN posts p ON c.post_id = p.id
                JOIN users u ON p.user_id = u.id
                WHERE c.sentiment_score IS NOT NULL
                GROUP BY u.platform, u.username
                ORDER BY avg_score DESC
            """)
            rows = cur.fetchall()
            conn.close()

            for r in rows:
                platform, username, total, avg, pos, neu, neg, ocr = r
                avg_str = f"{avg:+.3f}" if avg is not None else "N/A"

                if avg is not None and avg >= 0.05:
                    tag = "positive"
                elif avg is not None and avg <= -0.05:
                    tag = "negative"
                else:
                    tag = "neutral"

                self.tree.insert(
                    "", "end",
                    values=(platform, username, total, avg_str, pos, neu, neg, ocr or 0),
                    tags=(tag,)
                )

        except Exception as e:
            print(f"[ANALYSIS GUI ERROR] {e}")
```

## Soubor: social_bot\src\gui\frames\dashboard.py
```py
# src/gui/frames/dashboard.py
import customtkinter as ctk
from src.gui.theme import COLORS
from src.gui.browser_preview import BrowserPreview


class DashboardFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.setup_ui()

    # ------------------------------------------------------------------
    # Hlavní layout — grid na self (NIKDY pack na self)
    # ------------------------------------------------------------------
    def setup_ui(self):
        # self používá výhradně grid
        self.grid_columnconfigure(0, weight=2, minsize=340)  # levý panel
        self.grid_columnconfigure(1, weight=3)               # pravý panel (náhled + log)
        self.grid_rowconfigure(0, weight=1)

        # ── Levý sloupec — scrollovatelný ────────────────────────────
        left_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        left_scroll.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._build_left(left_scroll)

        # ── Pravý sloupec ────────────────────────────────────────────
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(0, weight=3)   # náhled — větší část
        right.grid_rowconfigure(2, weight=1)   # log — menší část
        right.grid_columnconfigure(0, weight=1)

        # Náhled prohlížeče
        self.browser_preview = BrowserPreview(right)
        self.browser_preview.grid(row=0, column=0, sticky="nsew", pady=(0, 4))

        # Oddělovač
        ctk.CTkFrame(right, height=1, fg_color=COLORS["border"]).grid(
            row=1, column=0, sticky="ew", pady=(0, 4))

        # Log panel
        log_header = ctk.CTkFrame(right, fg_color="transparent")
        log_header.grid(row=2, column=0, sticky="nsew")
        log_header.grid_rowconfigure(1, weight=1)
        log_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(log_header, text="LOG", font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text_dim"]).grid(
            row=0, column=0, sticky="w", pady=(0, 4))

        self.log_box = ctk.CTkTextbox(
            log_header, fg_color="#121416", text_color="#00ff41",
            font=("Consolas", 12), corner_radius=4,
            border_color=COLORS["border"], border_width=1
        )
        self.log_box.grid(row=1, column=0, sticky="nsew")
        self.log_box.configure(state="disabled")

    # ------------------------------------------------------------------
    # Levý sloupec — původní obsah beze změny (pack uvnitř left_scroll)
    # ------------------------------------------------------------------
    def _build_left(self, parent):
        """Celý původní obsah setup_ui — parent je CTkScrollableFrame."""

        # Nadpis
        ctk.CTkLabel(parent, text="Ovládací panel", font=("Segoe UI", 24, "bold"),
                     text_color=COLORS["text_main"]).pack(anchor="w", pady=(0, 20))

        # 1. INPUTY
        input_container = ctk.CTkFrame(parent, fg_color="transparent")
        input_container.pack(fill="x", pady=(0, 20))

        # Identita
        ctk.CTkLabel(input_container, text="IDENTITA BOTA",
                     font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w", pady=(0, 5))
        self.user_var = ctk.StringVar()
        self.user_combo = ctk.CTkComboBox(
            input_container, variable=self.user_var, height=35,
            font=("Segoe UI", 13),
            border_color=COLORS["border"], fg_color=COLORS["panel_bg"],
            button_color=COLORS["panel_bg"],
            dropdown_hover_color=COLORS["primary"],
            text_color=COLORS["text_main"], state="readonly"
        )
        self.user_combo.pack(fill="x", pady=(0, 15))
        self.refresh_users_combo()

        # Cíle
        ctk.CTkLabel(input_container, text="CÍLOVÉ ÚČTY (odděl čárkou)",
                     font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w", pady=(0, 5))
        self.target_var = ctk.StringVar()
        self.target_entry = ctk.CTkEntry(
            input_container, textvariable=self.target_var, height=40,
            font=("Segoe UI", 14),
            border_color=COLORS["border"], fg_color=COLORS["panel_bg"],
            text_color=COLORS["text_main"],
            placeholder_text="např. elonmusk, taylorswift13"
        )
        self.target_entry.pack(fill="x", pady=(0, 15))

        # Limity
        limits_container = ctk.CTkFrame(input_container, fg_color="transparent")
        limits_container.pack(fill="x")
        limits_container.grid_columnconfigure((0, 1, 2, 3), weight=1)

        limit_frame = ctk.CTkFrame(limits_container, fg_color="transparent")
        limit_frame.grid(row=0, column=0, sticky="nw", padx=(0, 5))
        ctk.CTkLabel(limit_frame, text="PŘÍSPĚVKY", font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w", pady=(0, 5))
        limit_inner = ctk.CTkFrame(limit_frame, fg_color="transparent")
        limit_inner.pack(fill="x")
        self.scrape_all_var = ctk.BooleanVar(value=False)
        self.chk_all = ctk.CTkCheckBox(
            limit_inner, text="Vše", variable=self.scrape_all_var,
            command=self.toggle_limit_entry,
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
            border_color=COLORS["border"], font=("Segoe UI", 13), width=45
        )
        self.chk_all.pack(side="left", padx=(0, 5))
        self.limit_var = ctk.StringVar(value="10")
        self.limit_entry = ctk.CTkEntry(
            limit_inner, textvariable=self.limit_var, width=50, height=35,
            font=("Segoe UI", 13), border_color=COLORS["border"],
            fg_color=COLORS["panel_bg"], text_color=COLORS["text_main"]
        )
        self.limit_entry.pack(side="left")

        comm_limit_frame = ctk.CTkFrame(limits_container, fg_color="transparent")
        comm_limit_frame.grid(row=0, column=1, sticky="nw", padx=5)
        ctk.CTkLabel(comm_limit_frame, text="KOMENTÁŘE",
                     font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w", pady=(0, 5))
        self.comments_limit_var = ctk.StringVar(value="50")
        self.comments_limit_entry = ctk.CTkEntry(
            comm_limit_frame, textvariable=self.comments_limit_var,
            width=70, height=35, font=("Segoe UI", 13),
            border_color=COLORS["border"], fg_color=COLORS["panel_bg"],
            text_color=COLORS["text_main"]
        )
        self.comments_limit_entry.pack(side="left")

        fol_limit_frame = ctk.CTkFrame(limits_container, fg_color="transparent")
        fol_limit_frame.grid(row=0, column=2, sticky="nw", padx=5)
        ctk.CTkLabel(fol_limit_frame, text="SLEDUJÍCÍ",
                     font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w", pady=(0, 5))
        self.followers_limit_var = ctk.StringVar(value="50")
        self.followers_limit_entry = ctk.CTkEntry(
            fol_limit_frame, textvariable=self.followers_limit_var,
            width=70, height=35, font=("Segoe UI", 13),
            border_color=COLORS["border"], fg_color=COLORS["panel_bg"],
            text_color=COLORS["text_main"]
        )
        self.followers_limit_entry.pack(side="left")

        following_limit_frame = ctk.CTkFrame(limits_container, fg_color="transparent")
        following_limit_frame.grid(row=0, column=3, sticky="nw", padx=(5, 0))
        ctk.CTkLabel(following_limit_frame, text="SLEDUJE",
                     font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w", pady=(0, 5))
        self.following_limit_var = ctk.StringVar(value="50")
        self.following_limit_entry = ctk.CTkEntry(
            following_limit_frame, textvariable=self.following_limit_var,
            width=70, height=35, font=("Segoe UI", 13),
            border_color=COLORS["border"], fg_color=COLORS["panel_bg"],
            text_color=COLORS["text_main"]
        )
        self.following_limit_entry.pack(side="left")

        # 2. AKCE
        ctk.CTkLabel(parent, text="AKCE", font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w", pady=(20, 5))
        actions_frame = ctk.CTkFrame(parent, fg_color="transparent")
        actions_frame.pack(fill="x", pady=(0, 20))
        actions_frame.grid_columnconfigure((0, 1), weight=1)

        self.create_action_btn(actions_frame, "Instagram Login", 0, 0,
                               lambda: self.controller.start_thread("instagram", "login"),
                               outline=True)
        self.create_action_btn(actions_frame, "Těžit Instagram", 0, 1,
                               lambda: self.controller.start_thread("instagram", "scrape"))
        self.create_action_btn(actions_frame, "X Login", 1, 0,
                               lambda: self.controller.start_thread("X", "login"),
                               outline=True)
        self.create_action_btn(actions_frame, "Těžit X", 1, 1,
                               lambda: self.controller.start_thread("X", "scrape"))
        self.create_action_btn(actions_frame, "Těžit YouTube", 2, 0,
                               lambda: self.controller.start_thread("youtube", "scrape"))

        btn_trend = ctk.CTkButton(
            actions_frame, text="Těžit Trendy (X)",
            command=lambda: self.controller.start_thread("X", "scrape_trending"),
            height=35, fg_color=COLORS["panel_bg"], hover_color=COLORS["border"],
            text_color=COLORS["text_main"], font=("Segoe UI", 13)
        )
        btn_trend.grid(row=2, column=1, sticky="ew", padx=5, pady=5)

        # 3. PO SCRAPU
        post_frame = ctk.CTkFrame(parent, fg_color=COLORS["panel_bg"],
                                  corner_radius=8, border_width=1,
                                  border_color=COLORS["border"])
        post_frame.pack(fill="x", pady=(10, 0))

        ctk.CTkLabel(post_frame, text="PO SCRAPU", font=("Segoe UI", 10, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w", padx=12, pady=(8, 4))

        self.ocr_auto_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            post_frame,
            text="OCR obrázků  (Tesseract — zpomalí scraping)",
            variable=self.ocr_auto_var,
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
            border_color=COLORS["border"],
            font=("Segoe UI", 12),
            checkmark_color="white",
        ).pack(anchor="w", padx=12, pady=(0, 6))

        self.headless_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            post_frame,
            text="Pouze screencast  (bez viditelného okna prohlížeče)",
            variable=self.headless_var,
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
            border_color=COLORS["border"],
            font=("Segoe UI", 12),
            checkmark_color="white",
        ).pack(anchor="w", padx=12, pady=(0, 10))

        # UKONČIT
        btn_stop = ctk.CTkButton(
            parent, text="UKONČIT OPERACI",
            command=self.controller.stop_bot,
            fg_color=COLORS["danger"], hover_color="#8a1212",
            height=40, font=("Segoe UI", 13, "bold")
        )
        btn_stop.pack(fill="x", pady=(10, 0))

    # ------------------------------------------------------------------
    # Pomocné metody — beze změny
    # ------------------------------------------------------------------
    def toggle_limit_entry(self):
        if self.scrape_all_var.get():
            self.limit_entry.configure(state="disabled",
                                       fg_color=COLORS["sidebar_bg"])
        else:
            self.limit_entry.configure(state="normal",
                                       fg_color=COLORS["panel_bg"])

    def create_action_btn(self, parent, text, r, c, cmd, outline=False):
        if outline:
            fg, border, text_c, hover = (
                "transparent", 1, COLORS["primary"], COLORS["panel_bg"])
        else:
            fg, border, text_c, hover = (
                COLORS["primary"], 0, "white", COLORS["primary_hover"])
        btn = ctk.CTkButton(
            parent, text=text, command=cmd, height=35,
            fg_color=fg, text_color=text_c,
            border_width=border, border_color=COLORS["primary"],
            hover_color=hover, font=("Segoe UI", 13, "bold")
        )
        btn.grid(row=r, column=c, sticky="ew", padx=5, pady=5)

    def refresh_users_combo(self):
        if self.controller.users_map:
            users = list(self.controller.users_map.keys())
            self.user_combo.configure(values=users)
            self.user_combo.set(users[0])
```

## Soubor: social_bot\src\gui\frames\database.py
```py
import customtkinter as ctk
from tkinter import ttk
import sqlite3
from src.gui.theme import COLORS

class DatabaseFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.setup_ui()

    def setup_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(header, text="Uložená data", font=("Segoe UI", 24, "bold"), 
                     text_color=COLORS["text_main"]).pack(side="left")
        ctk.CTkButton(header, text="Obnovit", width=80, height=30, 
                      fg_color=COLORS["panel_bg"], hover_color=COLORS["border"], 
                      text_color=COLORS["text_main"], command=self.refresh_data).pack(side="right")

        # Tabs
        self.tab_db = ctk.CTkTabview(
            self, fg_color="transparent", 
            segmented_button_fg_color=COLORS["panel_bg"], 
            segmented_button_selected_color=COLORS["primary"], 
            segmented_button_selected_hover_color=COLORS["primary_hover"], 
            segmented_button_unselected_color=COLORS["panel_bg"], 
            segmented_button_unselected_hover_color=COLORS["border"]
        )
        self.tab_db.pack(fill="both", expand=True)
        
        self.tab_db.add("Uživatelé")
        self.tab_db.add("Příspěvky")
        self.tab_db.add("Trendy")
        self.tab_db.add("Síť (Connections)")

        self.tree_users = self.create_tree(self.tab_db.tab("Uživatelé"))
        self.tree_posts = self.create_tree(self.tab_db.tab("Příspěvky"))
        self.tree_trends = self.create_tree(self.tab_db.tab("Trendy"))
        self.tree_connections = self.create_tree(self.tab_db.tab("Síť (Connections)"))

    def create_tree(self, parent):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background=COLORS["main_bg"], foreground=COLORS["text_main"], 
                        rowheight=30, fieldbackground=COLORS["main_bg"], borderwidth=0, font=("Segoe UI", 11))
        style.configure("Treeview.Heading", background=COLORS["panel_bg"], foreground=COLORS["text_main"], 
                        relief="flat", font=("Segoe UI", 12, "bold"), padding=(10, 5))
        style.map('Treeview', background=[('selected', COLORS["primary"])], foreground=[('selected', 'white')])
        
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True)
        
        scroll_y = ctk.CTkScrollbar(frame, button_color=COLORS["panel_bg"], button_hover_color=COLORS["border"])
        scroll_y.pack(side="right", fill="y")
        
        tree = ttk.Treeview(frame, yscrollcommand=scroll_y.set, show="headings", selectmode="browse")
        tree.pack(fill="both", expand=True)
        scroll_y.configure(command=tree.yview)
        return tree

    def refresh_data(self):
        if not self.controller.db_path.exists(): return
        
        # Clear
        for t in [self.tree_users, self.tree_posts, self.tree_trends, self.tree_connections]:
            for i in t.get_children(): t.delete(i)
            
        try:
            conn = sqlite3.connect(str(self.controller.db_path))
            cur = conn.cursor()
            
            # Users
            cur.execute("SELECT platform, username, followers_count FROM users")
            self.tree_users['columns'] = ("Platform", "Username", "Followers")
            for c in self.tree_users['columns']: 
                self.tree_users.heading(c, text=c, anchor="w")
                self.tree_users.column(c, width=150)
            for r in cur.fetchall(): self.tree_users.insert("", "end", values=r)
            
            # Posts
            cur.execute("SELECT platform, text_content, likes_count FROM posts ORDER BY scraped_at DESC LIMIT 50")
            self.tree_posts['columns'] = ("Plat.", "Text", "Likes")
            self.tree_posts.heading("Plat.", text="Plat."); self.tree_posts.column("Plat.", width=50)
            self.tree_posts.heading("Text", text="Text"); self.tree_posts.column("Text", width=400)
            self.tree_posts.heading("Likes", text="Likes"); self.tree_posts.column("Likes", width=80)
            for r in cur.fetchall():
                tx = r[1][:60] + "..." if r[1] and len(r[1]) > 60 else r[1]
                self.tree_posts.insert("", "end", values=(r[0], tx, r[2]))
                
            # Trends
            cur.execute("SELECT rank, topic_name, post_count FROM trending ORDER BY rank ASC")
            self.tree_trends['columns'] = ("#", "Téma", "Objem")
            for c in self.tree_trends['columns']: self.tree_trends.heading(c, text=c, anchor="w")
            for r in cur.fetchall(): self.tree_trends.insert("", "end", values=r)
            
            # Connections (Followers)
            cur.execute("SELECT platform, source_username, target_username, connection_type, scraped_at FROM connections ORDER BY scraped_at DESC LIMIT 1000")
            self.tree_connections['columns'] = ("Platforma", "Zdrojový Účet", "Nalezený Sledující", "Typ", "Staženo")
            for c in self.tree_connections['columns']: 
                self.tree_connections.heading(c, text=c, anchor="w")
                self.tree_connections.column(c, width=150)
            for r in cur.fetchall():
                # Formátování data pro čistší zobrazení
                date_str = r[4].split('T')[0] if r[4] else ""
                self.tree_connections.insert("", "end", values=(r[0], r[1], r[2], r[3], date_str))

            conn.close()
        except Exception as e:
            print(f"[DB ERROR] {e}")
```

## Soubor: social_bot\src\gui\frames\metrics.py
```py
# src/gui/frames/metrics.py
"""
Metriky aplikace — síťový provoz POUZE bota (přes Playwright response listener),
rychlost scrapu a další statistiky.

Architektura:
  - BotTrafficCounter  — jednoduchý čítač, volá se z Playwright response handleru
  - MetricsFrame       — GUI, čte data z čítače každou sekundu přes after()
"""

import time
import threading
import customtkinter as ctk
from tkinter import Canvas
from src.gui.theme import COLORS


# ══════════════════════════════════════════════════════════════════════
# Čítač provozu — thread-safe, bez psutil
# ══════════════════════════════════════════════════════════════════════

class BotTrafficCounter:
    """
    Sbírá bajty z Playwright response/request eventů.
    Volat attach(page) po každém spuštění bota, detach() po zastavení.
    """

    HISTORY_SIZE = 60

    def __init__(self):
        self._lock        = threading.Lock()
        self._running     = False

        # Aktuální sekundu
        self._rx_bucket   = 0   # bajty přijaté v aktuální sekundě
        self._tx_bucket   = 0   # bajty odeslané v aktuální sekundě
        self._bucket_time = time.time()

        # Veřejné hodnoty (aktualizuje _tick())
        self.rx_speed     = 0.0
        self.tx_speed     = 0.0
        self.rx_total     = 0
        self.tx_total     = 0
        self.rx_history   = [0.0] * self.HISTORY_SIZE
        self.tx_history   = [0.0] * self.HISTORY_SIZE

        self._page        = None
        self._on_response = None
        self._on_request  = None
        self._tick_thread = None

    # ------------------------------------------------------------------
    def attach(self, page):
        """Napojí se na Playwright page. Volat ze stejného vlákna jako bot."""
        self.detach()
        self._page    = page
        self._running = True
        self.reset()

        def on_response(response):
            try:
                # content-length header — nejrychlejší, bez čtení body
                cl = response.headers.get("content-length")
                if cl:
                    with self._lock:
                        self._rx_bucket += int(cl)
            except Exception:
                pass

        def on_request(request):
            try:
                # Velikost POST dat — aproximace přes headers
                headers = request.headers
                cl = headers.get("content-length")
                if cl:
                    with self._lock:
                        self._tx_bucket += int(cl)
                else:
                    # Přidat alespoň hlavičky (~200–600 B typicky)
                    header_size = sum(len(k) + len(v) + 4
                                      for k, v in headers.items())
                    with self._lock:
                        self._tx_bucket += header_size
            except Exception:
                pass

        self._on_response = on_response
        self._on_request  = on_request
        page.on("response", on_response)
        page.on("request",  on_request)

        # Tick vlákno — každou sekundu přepočítá speed a posune historii
        self._tick_thread = threading.Thread(
            target=self._tick_loop, daemon=True, name="traffic-tick")
        self._tick_thread.start()

    def detach(self):
        """Odpojí listenery. Volat ze stejného vlákna jako bot."""
        self._running = False
        if self._page and self._on_response:
            try:
                self._page.remove_listener("response", self._on_response)
                self._page.remove_listener("request",  self._on_request)
            except Exception:
                pass
        self._page        = None
        self._on_response = None
        self._on_request  = None

    def reset(self):
        with self._lock:
            self.rx_total   = 0
            self.tx_total   = 0
            self.rx_speed   = 0.0
            self.tx_speed   = 0.0
            self._rx_bucket = 0
            self._tx_bucket = 0
            self.rx_history = [0.0] * self.HISTORY_SIZE
            self.tx_history = [0.0] * self.HISTORY_SIZE

    def _tick_loop(self):
        while self._running:
            time.sleep(1)
            with self._lock:
                rx = self._rx_bucket
                tx = self._tx_bucket
                self._rx_bucket = 0
                self._tx_bucket = 0

                self.rx_speed  = float(rx)
                self.tx_speed  = float(tx)
                self.rx_total += rx
                self.tx_total += tx

                self.rx_history.append(self.rx_speed)
                self.rx_history = self.rx_history[-self.HISTORY_SIZE:]
                self.tx_history.append(self.tx_speed)
                self.tx_history = self.tx_history[-self.HISTORY_SIZE:]


# ══════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════

def _fmt_bytes(b: float) -> str:
    if b < 1024:        return f"{b:.0f} B"
    elif b < 1024**2:   return f"{b/1024:.1f} KB"
    elif b < 1024**3:   return f"{b/1024**2:.1f} MB"
    else:               return f"{b/1024**3:.2f} GB"

def _fmt_speed(bps: float) -> str:
    return _fmt_bytes(bps) + "/s"


# ══════════════════════════════════════════════════════════════════════
# GUI Frame
# ══════════════════════════════════════════════════════════════════════

class MetricsFrame(ctk.CTkFrame):

    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.traffic    = BotTrafficCounter()
        self._start_time = time.time()
        self._poll_id   = None
        self._build_ui()
        self._poll()      # spustí periodické čtení dat

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 24))
        ctk.CTkLabel(header, text="Metriky", font=("Segoe UI", 24, "bold"),
                     text_color=COLORS["text_main"]).pack(side="left")
        ctk.CTkButton(
            header, text="Reset session", width=110, height=30,
            fg_color=COLORS["panel_bg"], hover_color=COLORS["border"],
            text_color=COLORS["text_dim"], font=("Segoe UI", 12),
            command=self._reset_session
        ).pack(side="right")

        # ── Síťový provoz ───────────────────────────────────────────
        self._section("SÍŤOVÝ PROVOZ  (pouze bot)")

        cards_row = ctk.CTkFrame(self, fg_color="transparent")
        cards_row.pack(fill="x", pady=(0, 20))
        cards_row.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self._rx_speed_var = ctk.StringVar(value="—")
        self._tx_speed_var = ctk.StringVar(value="—")
        self._rx_total_var = ctk.StringVar(value="—")
        self._tx_total_var = ctk.StringVar(value="—")

        self._stat_card(cards_row, "↓ DOWNLOAD",  self._rx_speed_var, "#175DDC", 0)
        self._stat_card(cards_row, "↑ UPLOAD",    self._tx_speed_var, "#2eb85c", 1)
        self._stat_card(cards_row, "∑ STAŽENO",   self._rx_total_var, "#5a9bd4", 2)
        self._stat_card(cards_row, "∑ ODESLÁNO",  self._tx_total_var, "#9b59b6", 3)

        # Sparkline
        graph_card = ctk.CTkFrame(self, fg_color=COLORS["panel_bg"],
                                  corner_radius=8, border_width=1,
                                  border_color=COLORS["border"])
        graph_card.pack(fill="x", pady=(0, 24))

        graph_header = ctk.CTkFrame(graph_card, fg_color="transparent")
        graph_header.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(graph_header, text="RYCHLOST — posledních 60s",
                     font=("Segoe UI", 10, "bold"),
                     text_color=COLORS["text_dim"]).pack(side="left")

        legend = ctk.CTkFrame(graph_header, fg_color="transparent")
        legend.pack(side="right")
        for lbl, color in [("↓ Download", "#175DDC"), ("↑ Upload", "#2eb85c")]:
            dot = Canvas(legend, width=8, height=8,
                         bg=COLORS["panel_bg"], highlightthickness=0)
            dot.pack(side="left", padx=(0, 3))
            dot.create_oval(0, 0, 8, 8, fill=color, outline="")
            ctk.CTkLabel(legend, text=lbl, font=("Segoe UI", 10),
                         text_color=COLORS["text_dim"]).pack(side="left", padx=(0, 12))

        self._sparkline = Canvas(graph_card, height=80,
                                 bg=COLORS["panel_bg"],
                                 highlightthickness=0, bd=0)
        self._sparkline.pack(fill="x", padx=14, pady=(0, 12))
        self._sparkline.bind("<Configure>", lambda e: self._draw_sparkline())

        # ── Výkon scrapu ────────────────────────────────────────────
        self._section("VÝKON SCRAPU")

        perf_row = ctk.CTkFrame(self, fg_color="transparent")
        perf_row.pack(fill="x", pady=(0, 20))
        perf_row.grid_columnconfigure((0, 1, 2), weight=1)

        self._profiles_var = ctk.StringVar(value="0")
        self._posts_var    = ctk.StringVar(value="0")
        self._uptime_var   = ctk.StringVar(value="00:00:00")

        self._stat_card(perf_row, "PROFILY / SESSION", self._profiles_var, "#e0a040", 0)
        self._stat_card(perf_row, "PŘÍSPĚVKY / SESSION", self._posts_var,  "#175DDC", 1)
        self._stat_card(perf_row, "UPTIME",              self._uptime_var, "#2eb85c", 2)

        # Stav bota
        status_row = ctk.CTkFrame(self, fg_color="transparent")
        status_row.pack(fill="x")
        self._bot_status_var = ctk.StringVar(value="● Bot neběží")
        ctk.CTkLabel(status_row, textvariable=self._bot_status_var,
                     font=("Segoe UI", 12), text_color=COLORS["text_dim"]).pack(side="left")

    # ------------------------------------------------------------------
    def _section(self, title):
        ctk.CTkLabel(self, text=title, font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w", pady=(0, 8))

    def _stat_card(self, parent, label, var, color, col):
        card = ctk.CTkFrame(parent, fg_color=COLORS["panel_bg"],
                            corner_radius=8, border_width=1,
                            border_color=COLORS["border"])
        card.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 6, 0))
        ctk.CTkLabel(card, text=label, font=("Segoe UI", 10, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w", padx=14, pady=(12, 2))
        ctk.CTkLabel(card, textvariable=var, font=("Segoe UI", 22, "bold"),
                     text_color=color).pack(anchor="w", padx=14, pady=(0, 12))

    # ------------------------------------------------------------------
    # Sparkline
    # ------------------------------------------------------------------
    def _draw_sparkline(self):
        c = self._sparkline
        w = c.winfo_width()
        h = c.winfo_height()
        if w <= 1 or h <= 1:
            return
        c.delete("all")

        with self.traffic._lock:
            rx = list(self.traffic.rx_history)
            tx = list(self.traffic.tx_history)

        def draw_line(history, color):
            peak = max(history) or 1
            n    = len(history)
            pts  = []
            for i, v in enumerate(history):
                x = int(i / (n - 1) * w) if n > 1 else w // 2
                y = int(h - (v / peak) * (h - 4))
                pts.extend([x, y])
            if len(pts) >= 4:
                c.create_line(pts, fill=color, width=2, smooth=True)

        draw_line(rx, "#175DDC")
        draw_line(tx, "#2eb85c")

    # ------------------------------------------------------------------
    # Polling — čte data každou sekundu, nezávisle na botu
    # ------------------------------------------------------------------
    def _poll(self):
        with self.traffic._lock:
            rx_s = self.traffic.rx_speed
            tx_s = self.traffic.tx_speed
            rx_t = self.traffic.rx_total
            tx_t = self.traffic.tx_total
            active = self.traffic._running

        if active:
            self._rx_speed_var.set(_fmt_speed(rx_s))
            self._tx_speed_var.set(_fmt_speed(tx_s))
        else:
            self._rx_speed_var.set("—")
            self._tx_speed_var.set("—")

        self._rx_total_var.set(_fmt_bytes(rx_t) if rx_t > 0 else "—")
        self._tx_total_var.set(_fmt_bytes(tx_t) if tx_t > 0 else "—")

        uptime = int(time.time() - self._start_time)
        h, rem = divmod(uptime, 3600)
        m, s   = divmod(rem, 60)
        self._uptime_var.set(f"{h:02d}:{m:02d}:{s:02d}")

        self._draw_sparkline()

        self._poll_id = self.after(1000, self._poll)

    # ------------------------------------------------------------------
    # Veřejné API — volat z app.py
    # ------------------------------------------------------------------
    def bot_started(self, page):
        """Zavolat po bot.login() — předá Playwright page pro traffic monitoring."""
        self.traffic.attach(page)
        self._bot_status_var.set("● Bot běží  —  měřím provoz")
        self._bot_status_var._label_widget = None  # reset barvy
        try:
            # Najít label a změnit barvu
            for w in self.winfo_children():
                pass  # barva přes configure níže
        except Exception:
            pass

    def bot_stopped(self):
        """Zavolat po dokončení / zastavení bota."""
        self.traffic.detach()
        self._bot_status_var.set("● Bot neběží")

    def increment_profiles(self, n: int = 1):
        val = int(self._profiles_var.get() or 0)
        self._profiles_var.set(str(val + n))

    def increment_posts(self, n: int = 1):
        val = int(self._posts_var.get() or 0)
        self._posts_var.set(str(val + n))

    def _reset_session(self):
        self.traffic.reset()
        self._start_time = time.time()
        self._profiles_var.set("0")
        self._posts_var.set("0")

    # ------------------------------------------------------------------
    def destroy(self):
        if self._poll_id:
            self.after_cancel(self._poll_id)
        self.traffic.detach()
        super().destroy()
```

## Soubor: social_bot\src\gui\frames\profiles.py
```py
# src/gui/frames/profiles.py
import customtkinter as ctk
import threading
import sqlite3
import tkinter as tk
from tkinter import Canvas
from src.gui.theme import COLORS
from src.gui.utils import AsyncImageLoader

PAGE_SIZE = 10  # Počet karet na stránku

# Možnosti řazení: (popisek, klíč v dict, reverse)
SORT_OPTIONS = [
    ("Sledující ↓",       "followers_count",  True),
    ("Sledující ↑",       "followers_count",  False),
    ("Sleduje ↓",         "following_count",  True),
    ("Sleduje ↑",         "following_count",  False),
    ("Naposledy scraped", "last_scraped",      True),
    ("Přidáno nejdřív",   "last_scraped",      False),
]


class ProfilesFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.all_profiles_data = []
        self._rendered_count   = 0
        self.image_loader      = AsyncImageLoader()
        self._sentiment_cache  = {}
        self._stats_cache      = {}
        self._active_platform  = "Vše"
        self._active_sort_idx  = 0
        self.filtered_data     = []
        self._platform_buttons = {}
        self._show_more_btn    = None
        self.setup_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # ── Řádek 0: Nadpis + počítadlo + vyhledávání ──────────────────
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        ctk.CTkLabel(
            top_bar, text="Nalezené Profily",
            font=("Segoe UI", 24, "bold"), text_color=COLORS["text_main"]
        ).pack(side="left")

        self.counter_label = ctk.CTkLabel(
            top_bar, text="", font=("Segoe UI", 13), text_color=COLORS["text_dim"]
        )
        self.counter_label.pack(side="left", padx=(15, 0))

        self.search_var = ctk.StringVar()
        self.search_var.trace("w", self._on_filter_change)

        ctk.CTkEntry(
            top_bar, textvariable=self.search_var, width=280, height=34,
            corner_radius=20, placeholder_text="🔍 Hledat jméno nebo @handle...",
            fg_color=COLORS["panel_bg"], border_color=COLORS["border"],
            text_color="white"
        ).pack(side="right")

        # ── Řádek 1: Filtr platforma + řazení ──────────────────────────
        self.filter_bar = ctk.CTkFrame(self, fg_color=COLORS["panel_bg"],
                                        corner_radius=8, height=44)
        self.filter_bar.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        self.filter_bar.grid_propagate(False)

        # Platforma — label
        ctk.CTkLabel(
            self.filter_bar, text="Platforma:",
            font=("Segoe UI", 11), text_color=COLORS["text_dim"]
        ).pack(side="left", padx=(14, 6), pady=10)

        # Tlačítko "Vše"
        btn_vse = ctk.CTkButton(
            self.filter_bar, text="Vše",
            width=46, height=26, corner_radius=6,
            font=("Segoe UI", 11, "bold"),
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
            border_width=1, border_color=COLORS["border"], text_color="white",
            command=lambda: self._set_platform("Vše")
        )
        btn_vse.pack(side="left", padx=3, pady=9)
        self._platform_buttons["Vše"] = btn_vse

        # Oddělovač
        ctk.CTkFrame(self.filter_bar, width=1, height=24,
                     fg_color=COLORS["border"]).pack(side="left", padx=12, pady=10)

        # Řazení — label
        ctk.CTkLabel(
            self.filter_bar, text="Řadit:",
            font=("Segoe UI", 11), text_color=COLORS["text_dim"]
        ).pack(side="left", padx=(0, 6))

        self.sort_var = ctk.StringVar(value=SORT_OPTIONS[0][0])
        ctk.CTkOptionMenu(
            self.filter_bar,
            variable=self.sort_var,
            values=[o[0] for o in SORT_OPTIONS],
            width=190, height=28, corner_radius=6,
            fg_color=COLORS["panel_bg"],
            button_color=COLORS["border"],
            button_hover_color=COLORS["primary"],
            dropdown_fg_color=COLORS["panel_bg"],
            dropdown_hover_color=COLORS["border"],
            text_color="white",
            font=("Segoe UI", 11),
            command=self._on_sort_change
        ).pack(side="left", padx=3, pady=8)

        # ── Řádek 2: Scrollovatelný seznam ──────────────────────────────
        self.scroll_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0
        )
        self.scroll_frame.grid(row=2, column=0, sticky="nsew")
        self.scroll_frame.grid_columnconfigure(0, weight=1)

    # ------------------------------------------------------------------
    # Načtení dat z DB
    # ------------------------------------------------------------------
    def refresh_data(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self._rendered_count  = 0
        self._sentiment_cache = {}
        self._stats_cache     = {}

        if not self.controller.db_path.exists():
            return

        try:
            conn = sqlite3.connect(str(self.controller.db_path))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            try:
                cur.execute("SELECT * FROM users ORDER BY last_scraped DESC")
            except Exception:
                cur.execute(
                    "SELECT id, platform, username, display_name, bio, "
                    "followers_count, following_count, profile_pic_url, last_scraped "
                    "FROM users ORDER BY last_scraped DESC"
                )
            self.all_profiles_data = [dict(row) for row in cur.fetchall()]

            # Dynamicky přidáme tlačítka platform které jsou v DB
            self._refresh_platform_buttons()

            # Sentiment cache
            for user in self.all_profiles_data:
                try:
                    cur.execute("""
                        SELECT COUNT(c.id), AVG(c.sentiment_score),
                               SUM(CASE WHEN c.sentiment_label='positive' THEN 1 ELSE 0 END),
                               SUM(CASE WHEN c.sentiment_label='neutral'  THEN 1 ELSE 0 END),
                               SUM(CASE WHEN c.sentiment_label='negative' THEN 1 ELSE 0 END)
                        FROM comments c JOIN posts p ON c.post_id = p.id
                        WHERE p.user_id = ? AND c.sentiment_score IS NOT NULL
                    """, (user["id"],))
                    row = cur.fetchone()
                    if row and row[0] and row[0] > 0:
                        self._sentiment_cache[user["id"]] = {
                            "total": row[0], "avg": round(row[1], 3) if row[1] else 0.0,
                            "pos": row[2] or 0, "neu": row[3] or 0, "neg": row[4] or 0,
                        }
                except Exception:
                    pass

            conn.close()
            self._on_filter_change()

        except Exception as e:
            print(f"[GUI ERROR] Chyba profilů: {e}")

    def _refresh_platform_buttons(self):
        """Zjistí platformy v DB; přidá tlačítka pro nové, odstraní prázdné."""
        seen  = {(str(u.get("platform") or "")).upper() for u in self.all_profiles_data}
        seen.discard("")
        known = set(self._platform_buttons.keys()) - {"Vše"}

        for plat in sorted(seen - known):
            btn = ctk.CTkButton(
                self.filter_bar, text=plat,
                width=46, height=26, corner_radius=6,
                font=("Segoe UI", 11, "bold"),
                fg_color="transparent", hover_color=COLORS["primary_hover"],
                border_width=1, border_color=COLORS["border"], text_color="white",
                command=lambda p=plat: self._set_platform(p)
            )
            # Vložit PŘED oddělovač (oddělovač je 3. widget od konce)
            btn.pack(side="left", padx=3, pady=9)
            self._platform_buttons[plat] = btn

        # Reset výběru pokud aktuální platforma zmizela z DB
        if self._active_platform not in ({"Vše"} | seen):
            self._active_platform = "Vše"

    # ------------------------------------------------------------------
    # Filtrování a řazení
    # ------------------------------------------------------------------
    def _set_platform(self, plat: str):
        self._active_platform = plat
        for p, btn in self._platform_buttons.items():
            btn.configure(
                fg_color=COLORS["primary"] if p == plat else "transparent"
            )
        self._on_filter_change()

    def _on_sort_change(self, _=None):
        label = self.sort_var.get()
        self._active_sort_idx = next(
            (i for i, o in enumerate(SORT_OPTIONS) if o[0] == label), 0
        )
        self._on_filter_change()

    def _on_filter_change(self, *args):
        query = self.search_var.get().lower()
        plat  = self._active_platform

        data = self.all_profiles_data

        # Filtr platformy
        if plat != "Vše":
            data = [u for u in data
                    if (str(u.get("platform") or "")).upper() == plat]

        # Fulltextové vyhledávání
        if query:
            data = [u for u in data
                    if query in (u.get("username") or "").lower()
                    or query in (u.get("display_name") or "").lower()]

        # Řazení
        _, field, reverse = SORT_OPTIONS[self._active_sort_idx]
        data = sorted(
            data,
            key=lambda u: (u.get(field) or 0) if field != "last_scraped"
                          else (u.get(field) or ""),
            reverse=reverse
        )

        self.filtered_data    = data
        self._rendered_count  = 0
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self._render_next_page()

    # ------------------------------------------------------------------
    # Paginace
    # ------------------------------------------------------------------
    def _render_next_page(self):
        total = len(self.filtered_data)
        start = self._rendered_count
        end   = min(start + PAGE_SIZE, total)

        for user in self.filtered_data[start:end]:
            self.create_card(user)

        self._rendered_count = end
        self.counter_label.configure(text=f"Zobrazeno {self._rendered_count} z {total}")

        if self._show_more_btn:
            try: self._show_more_btn.destroy()
            except Exception: pass
            self._show_more_btn = None

        if self._rendered_count < total:
            remaining = total - self._rendered_count
            self._show_more_btn = ctk.CTkButton(
                self.scroll_frame,
                text=f"Načíst dalších {min(PAGE_SIZE, remaining)}  ↓",
                fg_color=COLORS["panel_bg"], hover_color=COLORS["border"],
                border_width=1, border_color=COLORS["border"],
                text_color=COLORS["text_dim"], font=("Segoe UI", 13),
                height=40, corner_radius=8, command=self._render_next_page
            )
            self._show_more_btn.pack(fill="x", pady=(8, 4), padx=4)
        else:
            if total > PAGE_SIZE:
                ctk.CTkLabel(
                    self.scroll_frame,
                    text=f"— Všechny profily načteny ({total}) —",
                    font=("Segoe UI", 11), text_color="#444"
                ).pack(pady=(8, 4))

    # ------------------------------------------------------------------
    # Karta profilu
    # ------------------------------------------------------------------
    def create_card(self, user):
        card = ctk.CTkFrame(
            self.scroll_frame, fg_color=COLORS["panel_bg"],
            corner_radius=12, border_color=COLORS["border"], border_width=1
        )
        card.pack(fill="x", pady=6, padx=4)
        card.grid_columnconfigure(1, weight=1)

        # Avatar
        img_widget = ctk.CTkLabel(card, text="", width=80, height=80,
                                   corner_radius=10, fg_color="#333")
        if user.get("profile_pic_url"):
            threading.Thread(
                target=self.image_loader.load_image,
                args=(user.get("profile_pic_url"), img_widget),
                daemon=True
            ).start()
        img_widget.grid(row=0, column=0, rowspan=2, padx=15, pady=(15, 5), sticky="n")

        # Jméno + verifikace + handle
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.grid(row=0, column=1, sticky="nw", pady=(15, 0), padx=5)

        name_text = user.get("display_name") or user["username"]
        ctk.CTkLabel(info_frame, text=name_text,
                     font=("Segoe UI", 16, "bold"), text_color="white").pack(side="left")

        if user.get("is_verified") == 1:
            ctk.CTkLabel(info_frame, text="☑",
                         font=("Segoe UI", 16), text_color=COLORS["verified"]).pack(side="left", padx=(5, 0))

        handle_txt = f"@{user['username']} • {str(user.get('platform') or '').upper()}"
        ctk.CTkLabel(info_frame, text=handle_txt,
                     font=("Segoe UI", 13), text_color=COLORS["text_dim"]).pack(side="left", padx=(10, 0))

        # Followers / Following
        stats_frame = ctk.CTkFrame(card, fg_color="transparent")
        stats_frame.grid(row=1, column=1, sticky="nw", pady=(2, 0), padx=5)

        def fmt(n): return f"{n:,}".replace(",", " ") if n is not None else "0"

        ctk.CTkLabel(stats_frame, text=fmt(user.get("followers_count", 0)),
                     font=("Segoe UI", 13, "bold"), text_color=COLORS["text_main"]).pack(side="left")
        ctk.CTkLabel(stats_frame, text="Followers",
                     font=("Segoe UI", 13), text_color=COLORS["text_dim"]).pack(side="left", padx=(3, 15))
        ctk.CTkLabel(stats_frame, text=fmt(user.get("following_count", 0)),
                     font=("Segoe UI", 13, "bold"), text_color=COLORS["text_main"]).pack(side="left")
        ctk.CTkLabel(stats_frame, text="Following",
                     font=("Segoe UI", 13), text_color=COLORS["text_dim"]).pack(side="left", padx=(3, 0))

        # Bio + metadata + last_scraped (dynamický blok bez prázdných řádků)
        bottom_parts = []
        bio = user.get("bio")
        if bio:
            bottom_parts.append(("bio", " ".join(bio.split())))
        meta = []
        if user.get("location"):    meta.append(f"📍 {user['location']}")
        if user.get("website"):     meta.append(f"🔗 {user['website']}")
        if user.get("joined_date"): meta.append(f"📅 {user['joined_date']}")
        if meta:
            bottom_parts.append(("meta", "   ".join(meta)))

        last_s = str(user.get("last_scraped", "")).split("T")[0] or "?"

        bottom_frame = ctk.CTkFrame(card, fg_color="transparent")
        bottom_frame.grid(row=2, column=0, columnspan=3, sticky="ew",
                          padx=(110, 15), pady=(2, 10))
        bottom_frame.grid_columnconfigure(0, weight=1)

        r = 0
        for kind, text in bottom_parts:
            if kind == "bio":
                short = (text[:120] + "...") if len(text) > 120 else text
                ctk.CTkLabel(bottom_frame, text=short,
                             font=("Segoe UI", 12, "italic"), text_color="#b0b0b0",
                             anchor="w", justify="left", wraplength=800).grid(
                    row=r, column=0, columnspan=2, sticky="w", pady=(0, 2))
            else:
                ctk.CTkLabel(bottom_frame, text=text,
                             font=("Segoe UI", 11), text_color=COLORS["text_dim"],
                             anchor="w").grid(row=r, column=0, sticky="w")
            r += 1

        ctk.CTkLabel(bottom_frame, text=f"Upd: {last_s}",
                     font=("Segoe UI", 10), text_color="#555",
                     anchor="e").grid(row=max(r - 1, 0), column=1, sticky="e")

        # Sentiment widget
        sentiment_data = self._sentiment_cache.get(user["id"])
        if sentiment_data:
            self._add_sentiment_widget(card, sentiment_data)

        # Textová analytika (bez word cloud)
        self._add_expandable_stats(card, user)

    # ------------------------------------------------------------------
    # Rozbalitelná sekce — Textová analytika
    # ------------------------------------------------------------------
    def _add_expandable_stats(self, card, user):
        user_id = user["id"]

        ctk.CTkFrame(card, height=1, fg_color=COLORS["border"]).grid(
            row=6, column=0, columnspan=3, sticky="ew", padx=15, pady=(0, 0)
        )

        toggle_var    = tk.BooleanVar(value=False)
        content_frame = ctk.CTkFrame(card, fg_color=COLORS["main_bg"], corner_radius=8)

        toggle_btn = ctk.CTkButton(
            card,
            text="▶  Textová analytika  (hashtagy · zmínky · top slova)",
            fg_color="transparent", hover_color=COLORS["border"],
            text_color=COLORS["text_dim"], anchor="w",
            font=("Segoe UI", 12), height=34,
            command=lambda: self._toggle_stats(card, user_id, toggle_var, toggle_btn, content_frame)
        )
        toggle_btn.grid(row=7, column=0, columnspan=3, sticky="ew", padx=10, pady=2)

    def _toggle_stats(self, card, user_id, toggle_var, toggle_btn, content_frame):
        if not toggle_var.get():
            toggle_var.set(True)
            toggle_btn.configure(text="▼  Textová analytika  (hashtagy · zmínky · top slova)")
            content_frame.grid(row=8, column=0, columnspan=3, sticky="ew", padx=15, pady=(4, 12))
            content_frame.grid_columnconfigure((0, 1, 2), weight=1)
            if user_id not in self._stats_cache:
                self._load_stats_async(user_id, content_frame)
            else:
                self._render_stats(content_frame, user_id)
        else:
            toggle_var.set(False)
            toggle_btn.configure(text="▶  Textová analytika  (hashtagy · zmínky · top slova)")
            content_frame.grid_forget()

    def _load_stats_async(self, user_id, content_frame):
        loading = ctk.CTkLabel(content_frame, text="⏳  Načítám data...",
                               font=("Segoe UI", 12), text_color=COLORS["text_dim"])
        loading.grid(row=0, column=0, columnspan=3, pady=15)

        def worker():
            try:
                from src.analysis.text_stats import TextStatsAnalyzer
                analyzer = TextStatsAnalyzer()
                stats    = analyzer.get_profile_stats(user_id, posts_limit=100, top_n=10)
                self._stats_cache[user_id] = stats
                self.after(0, lambda: self._render_stats(content_frame, user_id, "commenters"))
            except Exception as e:
                self.after(0, lambda err=e: loading.configure(text=f"Chyba: {err}"))

        threading.Thread(target=worker, daemon=True).start()

    def _render_stats(self, content_frame, user_id, active_tab="commenters"):
        for w in content_frame.winfo_children():
            w.destroy()

        stats = self._stats_cache.get(user_id, {})
        if not stats:
            ctk.CTkLabel(content_frame, text="Žádná data k zobrazení.",
                         font=("Segoe UI", 12), text_color=COLORS["text_dim"]).grid(
                row=0, column=0, columnspan=3, pady=10)
            return

        section = stats.get(active_tab, {})

        # Záložky
        tab_bar = ctk.CTkFrame(content_frame, fg_color="transparent")
        tab_bar.grid(row=0, column=0, columnspan=3, sticky="w", padx=15, pady=(10, 4))

        owner_count   = stats.get("owner", {}).get("total_posts", 0)
        comment_count = stats.get("commenters", {}).get("total_comments", 0)

        for tab_key, tab_label in [
            ("owner",      f"Vlastník  ({owner_count} příspěvků)"),
            ("commenters", f"Komentující  ({comment_count} komentářů)"),
        ]:
            is_active = tab_key == active_tab
            ctk.CTkButton(
                tab_bar, text=tab_label, height=28,
                font=("Segoe UI", 11, "bold" if is_active else "normal"),
                fg_color=COLORS["border"] if is_active else "transparent",
                hover_color=COLORS["border"],
                text_color=COLORS["text_main"] if is_active else COLORS["text_dim"],
                corner_radius=6,
                command=lambda k=tab_key: self._render_stats(content_frame, user_id, k)
            ).pack(side="left", padx=(0, 6))

        # Tři sloupce
        data_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        data_frame.grid(row=1, column=0, columnspan=3, sticky="ew")
        data_frame.grid_columnconfigure((0, 1, 2), weight=1)

        for col_idx, (title, key, color) in enumerate([
            ("# HASHTAGY", "top_hashtags", "#175DDC"),
            ("@ ZMÍNKY",   "top_mentions", "#2eb85c"),
            ("TOP SLOVA",  "top_words",    "#9b59b6"),
        ]):
            frame = ctk.CTkFrame(data_frame, fg_color="transparent")
            frame.grid(row=0, column=col_idx, sticky="nw", padx=15, pady=(4, 12))
            ctk.CTkLabel(frame, text=title, font=("Segoe UI", 10, "bold"),
                         text_color=COLORS["text_dim"]).pack(anchor="w")
            items = section.get(key, [])
            if items:
                max_c = items[0][1]
                for label, count in items:
                    self._bar_row(frame, label, count, max_c, color)
            else:
                ctk.CTkLabel(frame, text="—", font=("Segoe UI", 11),
                             text_color=COLORS["text_dim"]).pack(anchor="w")

    def _bar_row(self, parent, label, count, max_count, color):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=1)
        short = label if len(label) <= 18 else label[:17] + "…"
        ctk.CTkLabel(row, text=short, font=("Segoe UI", 11),
                     text_color=COLORS["text_main"], width=130, anchor="w").pack(side="left")
        bar_width  = 60
        fill_width = max(2, int((count / max_count) * bar_width))
        bar_bg = Canvas(row, width=bar_width, height=10,
                        bg=COLORS["main_bg"], highlightthickness=0)
        bar_bg.pack(side="left", padx=(4, 4))
        bar_bg.create_rectangle(0, 2, fill_width, 8, fill=color, outline="")
        ctk.CTkLabel(row, text=str(count), font=("Segoe UI", 10),
                     text_color=COLORS["text_dim"]).pack(side="left")

    # ------------------------------------------------------------------
    # Sentiment widget
    # ------------------------------------------------------------------
    def _add_sentiment_widget(self, card, s):
        POS_COLOR = "#2eb85c"; NEU_COLOR = "#5a6370"; NEG_COLOR = "#e05252"
        total = s["total"]; pos = s["pos"]; neu = s["neu"]
        neg   = s["neg"];   avg = s["avg"]

        ctk.CTkFrame(card, height=1, fg_color=COLORS["border"]).grid(
            row=4, column=0, columnspan=3, sticky="ew", padx=15, pady=(0, 10))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.grid(row=5, column=0, columnspan=3, sticky="ew", padx=15, pady=(0, 8))
        row.grid_columnconfigure(1, weight=1)

        score_panel = ctk.CTkFrame(row, fg_color="transparent", width=90)
        score_panel.grid(row=0, column=0, sticky="nw", padx=(0, 15))
        score_panel.grid_propagate(False)

        ctk.CTkLabel(score_panel, text="SENTIMENT", font=("Segoe UI", 9, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w")

        if avg >= 0.05:    sc, sl = POS_COLOR, "pozitivní"
        elif avg <= -0.05: sc, sl = NEG_COLOR, "negativní"
        else:              sc, sl = NEU_COLOR, "neutrální"

        ctk.CTkLabel(score_panel, text=f"{avg:+.3f}", font=("Segoe UI", 20, "bold"),
                     text_color=sc).pack(anchor="w", pady=(2, 0))
        ctk.CTkLabel(score_panel, text=sl, font=("Segoe UI", 11),
                     text_color=sc).pack(anchor="w")
        ctk.CTkLabel(score_panel, text=f"{total} komentářů", font=("Segoe UI", 10),
                     text_color=COLORS["text_dim"]).pack(anchor="w", pady=(4, 0))

        bar_panel = ctk.CTkFrame(row, fg_color="transparent")
        bar_panel.grid(row=0, column=1, sticky="nsew")
        bar_panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(bar_panel, text="ROZLOŽENÍ KOMENTÁŘŮ", font=("Segoe UI", 9, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w")

        canvas = Canvas(bar_panel, height=22, bg=COLORS["panel_bg"],
                        highlightthickness=0, bd=0)
        canvas.pack(fill="x", pady=(4, 6))

        def draw_bar(event=None):
            canvas.delete("all")
            w = canvas.winfo_width()
            if w <= 1: canvas.after(50, draw_bar); return
            r = 6
            segments = [(pos, POS_COLOR), (neu, NEU_COLOR), (neg, NEG_COLOR)]
            x = 0; drawn = []
            for cnt, color in segments:
                if total > 0 and cnt > 0:
                    sw = max(int((cnt / total) * w), 1)
                    drawn.append((x, sw, color)); x += sw
            for i, (sx, sw, color) in enumerate(drawn):
                x0, y0, x1, y1 = sx, 0, sx + sw, 22
                fl = i == 0; la = i == len(drawn) - 1
                if fl and la:  _rounded_rect(canvas, x0, y0, x1, y1, r, color)
                elif fl:       _rounded_rect_left(canvas, x0, y0, x1, y1, r, color)
                elif la:       _rounded_rect_right(canvas, x0, y0, x1, y1, r, color)
                else:          canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline="")

        canvas.bind("<Configure>", draw_bar)
        canvas.after(100, draw_bar)

        legend = ctk.CTkFrame(bar_panel, fg_color="transparent")
        legend.pack(fill="x")
        for lbl, cnt, color in [("Pozitivní", pos, POS_COLOR),
                                 ("Neutrální", neu, NEU_COLOR),
                                 ("Negativní", neg, NEG_COLOR)]:
            pct = round((cnt / total) * 100) if total > 0 else 0
            item = ctk.CTkFrame(legend, fg_color="transparent")
            item.pack(side="left", padx=(0, 18))
            dot = Canvas(item, width=8, height=8, bg=COLORS["panel_bg"], highlightthickness=0)
            dot.pack(side="left", padx=(0, 4))
            dot.create_oval(0, 0, 8, 8, fill=color, outline="")
            ctk.CTkLabel(item, text=f"{lbl} {pct}% ({cnt})", font=("Segoe UI", 10),
                         text_color=COLORS["text_dim"]).pack(side="left")


# ------------------------------------------------------------------
# Canvas helpers
# ------------------------------------------------------------------
def _rounded_rect(canvas, x0, y0, x1, y1, r, color):
    canvas.create_arc(x0, y0, x0+2*r, y0+2*r, start=90,  extent=90,  fill=color, outline="")
    canvas.create_arc(x1-2*r, y0, x1, y0+2*r, start=0,   extent=90,  fill=color, outline="")
    canvas.create_arc(x0, y1-2*r, x0+2*r, y1, start=180, extent=90,  fill=color, outline="")
    canvas.create_arc(x1-2*r, y1-2*r, x1, y1, start=270, extent=90,  fill=color, outline="")
    canvas.create_rectangle(x0+r, y0, x1-r, y1, fill=color, outline="")
    canvas.create_rectangle(x0, y0+r, x1, y1-r, fill=color, outline="")

def _rounded_rect_left(canvas, x0, y0, x1, y1, r, color):
    canvas.create_arc(x0, y0, x0+2*r, y0+2*r, start=90,  extent=90,  fill=color, outline="")
    canvas.create_arc(x0, y1-2*r, x0+2*r, y1, start=180, extent=90,  fill=color, outline="")
    canvas.create_rectangle(x0+r, y0, x1, y1,     fill=color, outline="")
    canvas.create_rectangle(x0, y0+r, x0+r, y1-r, fill=color, outline="")

def _rounded_rect_right(canvas, x0, y0, x1, y1, r, color):
    canvas.create_arc(x1-2*r, y0, x1, y0+2*r, start=0,   extent=90,  fill=color, outline="")
    canvas.create_arc(x1-2*r, y1-2*r, x1, y1, start=270, extent=90,  fill=color, outline="")
    canvas.create_rectangle(x0, y0, x1-r, y1,     fill=color, outline="")
    canvas.create_rectangle(x1-r, y0+r, x1, y1-r, fill=color, outline="")
```

## Soubor: social_bot\src\gui\frames\sessions.py
```py
# src/gui/frames/sessions.py
"""
SessionsFrame — přehled a porovnání jednotlivých běhů scrapingu.

Záložky:
  Historie    — tabulka všech sessionů, řaditelná, s barevným kódováním
  Porovnání   — sloupcový graf pro vybrané metriky (výběr ze seznamu)
  Export      — export do CSV pro použití v diplomové práci
"""

import csv
import sqlite3
import tkinter as tk
from tkinter import ttk, filedialog
from datetime import datetime
from pathlib import Path

import customtkinter as ctk

from src.gui.theme import COLORS


# ── Helpers ────────────────────────────────────────────────────────────

def _fmt_bytes(b):
    if b is None: return "—"
    b = float(b)
    if b < 1024:       return f"{b:.0f} B"
    elif b < 1024**2:  return f"{b/1024:.1f} KB"
    else:              return f"{b/1024**2:.1f} MB"

def _fmt_dur(s):
    if s is None: return "—"
    s = int(s)
    m, sec = divmod(s, 60)
    return f"{m}m {sec:02d}s"

def _db_path():
    return Path(__file__).resolve().parent.parent.parent.parent / "data" / "osint.db"


# ── Hlavní frame ───────────────────────────────────────────────────────

class SessionsFrame(ctk.CTkFrame):

    COLUMNS = [
        # (db_col,            header,           width, fmt)
        ("started_at",        "Datum",           115,  lambda v: v[:16].replace("T"," ") if v else "—"),
        ("platform",          "Platforma",        75,  None),
        ("target_username",   "Cíl",             120,  None),
        ("duration_s",        "Délka",            70,  _fmt_dur),
        ("posts_scraped",     "Příspěvky",        80,  None),
        ("comments_scraped",  "Komentáře",        80,  None),
        ("followers_scraped", "Sledující",        80,  None),
        ("posts_per_min",     "P/min",            60,  lambda v: f"{v:.1f}" if v else "0"),
        ("comments_per_min",  "K/min",            60,  lambda v: f"{v:.1f}" if v else "0"),
        ("rx_bytes_total",    "Staženo",          80,  _fmt_bytes),
        ("tx_bytes_total",    "Odesláno",         80,  _fmt_bytes),
        ("rx_bytes_per_post", "B/příspěvek",      90,  _fmt_bytes),
        ("search_method",     "Metoda hledání",  110,  None),
        ("error_count",       "Chyby",            55,  None),
        ("was_interrupted",   "Přerušeno",        75,  lambda v: "Ano" if v else "Ne"),
    ]

    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self._all_rows  = []   # surová data z DB
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        # Nadpis + tlačítka
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(header, text="Historie běhů", font=("Segoe UI", 24, "bold"),
                     text_color=COLORS["text_main"]).pack(side="left")

        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.pack(side="right")
        ctk.CTkButton(btn_frame, text="Obnovit", width=80, height=30,
                      fg_color=COLORS["panel_bg"], hover_color=COLORS["border"],
                      text_color=COLORS["text_dim"], font=("Segoe UI", 12),
                      command=self.refresh_data).pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_frame, text="Export CSV", width=95, height=30,
                      fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
                      text_color="white", font=("Segoe UI", 12),
                      command=self._export_csv).pack(side="left")

        # Záložky
        self._tabs = ctk.CTkTabview(
            self, fg_color="transparent",
            segmented_button_fg_color=COLORS["panel_bg"],
            segmented_button_selected_color=COLORS["primary"],
            segmented_button_selected_hover_color=COLORS["primary_hover"],
            segmented_button_unselected_color=COLORS["panel_bg"],
            segmented_button_unselected_hover_color=COLORS["border"],
        )
        self._tabs.pack(fill="both", expand=True)
        self._tabs.add("Historie")
        self._tabs.add("Porovnání")
        self._tabs.add("Souhrn")

        self._build_history_tab(self._tabs.tab("Historie"))
        self._build_compare_tab(self._tabs.tab("Porovnání"))
        self._build_summary_tab(self._tabs.tab("Souhrn"))

    # ------------------------------------------------------------------
    # Záložka: Historie
    # ------------------------------------------------------------------
    def _build_history_tab(self, tab):
        # Ttk styl pro tmavé pozadí
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Sessions.Treeview",
                        background=COLORS["panel_bg"],
                        foreground=COLORS["text_main"],
                        fieldbackground=COLORS["panel_bg"],
                        rowheight=26,
                        font=("Segoe UI", 11))
        style.configure("Sessions.Treeview.Heading",
                        background=COLORS["main_bg"],
                        foreground=COLORS["text_dim"],
                        font=("Segoe UI", 10, "bold"),
                        relief="flat")
        style.map("Sessions.Treeview",
                  background=[("selected", COLORS["primary"])],
                  foreground=[("selected", "white")])

        cols = [c[0] for c in self.COLUMNS]
        self._tree = ttk.Treeview(tab, columns=cols, show="headings",
                                  style="Sessions.Treeview")

        for db_col, header, width, _ in self.COLUMNS:
            self._tree.heading(db_col, text=header,
                               command=lambda c=db_col: self._sort(c))
            self._tree.column(db_col, width=width, minwidth=40, anchor="center")

        # Scrollbary
        vsb = ttk.Scrollbar(tab, orient="vertical",   command=self._tree.yview)
        hsb = ttk.Scrollbar(tab, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tab.grid_rowconfigure(0, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        # Barevné tagy
        self._tree.tag_configure("ok",          background="#1a2a1a")
        self._tree.tag_configure("interrupted",  background="#2a1a1a")
        self._tree.tag_configure("errors",       background="#2a2a1a")

        # Detail při kliknutí
        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        # Detail panel pod tabulkou
        self._detail_var = ctk.StringVar(value="Klikni na řádek pro detail.")
        ctk.CTkLabel(tab, textvariable=self._detail_var,
                     font=("Consolas", 11), text_color=COLORS["text_dim"],
                     wraplength=900, justify="left").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

    # ------------------------------------------------------------------
    # Záložka: Porovnání (sloupcový graf přes tk.Canvas)
    # ------------------------------------------------------------------
    def _build_compare_tab(self, tab):
        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        ctrl = ctk.CTkFrame(tab, fg_color="transparent")
        ctrl.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        ctk.CTkLabel(ctrl, text="Metrika:", font=("Segoe UI", 12),
                     text_color=COLORS["text_dim"]).pack(side="left", padx=(0, 8))

        self._metric_var = ctk.StringVar(value="posts_per_min")
        metrics = [
            ("Příspěvky/min",   "posts_per_min"),
            ("Komentáře/min",   "comments_per_min"),
            ("Sledující/min",   "followers_per_min"),
            ("Staženo (KB)",    "rx_bytes_total"),
            ("Délka (s)",       "duration_s"),
            ("Chyby",           "error_count"),
            ("B/příspěvek",     "rx_bytes_per_post"),
        ]
        metric_labels = [m[0] for m in metrics]
        self._metric_map = {m[0]: m[1] for m in metrics}

        combo = ctk.CTkComboBox(ctrl, values=metric_labels,
                                variable=ctk.StringVar(value="Příspěvky/min"),
                                width=180, height=30,
                                fg_color=COLORS["panel_bg"],
                                border_color=COLORS["border"],
                                text_color=COLORS["text_main"],
                                command=lambda v: self._draw_chart())
        combo.pack(side="left")
        self._metric_combo = combo

        ctk.CTkButton(ctrl, text="Překreslit", width=90, height=30,
                      fg_color=COLORS["panel_bg"], hover_color=COLORS["border"],
                      text_color=COLORS["text_dim"], font=("Segoe UI", 12),
                      command=self._draw_chart).pack(side="left", padx=8)

        self._chart = tk.Canvas(tab, bg=COLORS["main_bg"],
                                highlightthickness=0, bd=0)
        self._chart.grid(row=1, column=0, sticky="nsew")
        self._chart.bind("<Configure>", lambda e: self._draw_chart())

    # ------------------------------------------------------------------
    # Záložka: Souhrn
    # ------------------------------------------------------------------
    def _build_summary_tab(self, tab):
        self._summary_frame = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self._summary_frame.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    def refresh_data(self):
        try:
            conn = sqlite3.connect(str(_db_path()), timeout=5)
            cur  = conn.cursor()
            cur.execute("""
                SELECT session_id, platform, bot_identity, target_username,
                       started_at, finished_at, duration_s,
                       posts_scraped, comments_scraped,
                       followers_scraped, following_scraped,
                       posts_per_min, comments_per_min, followers_per_min,
                       rx_bytes_total, tx_bytes_total,
                       rx_bytes_per_post, bytes_per_comment,
                       search_method, profile_found, error_count,
                       was_interrupted, headless,
                       limit_posts, limit_comments,
                       limit_followers, limit_following, notes
                FROM scrape_sessions
                ORDER BY started_at DESC
            """)
            self._all_rows = cur.fetchall()
            conn.close()
        except Exception as e:
            self._all_rows = []
            print(f"[SESSIONS] Chyba načítání: {e}")

        self._populate_tree()
        self._draw_chart()
        self._populate_summary()

    def _populate_tree(self):
        self._tree.delete(*self._tree.get_children())

        col_indices = {
            "session_id": 0, "platform": 1, "bot_identity": 2,
            "target_username": 3, "started_at": 4, "finished_at": 5,
            "duration_s": 6, "posts_scraped": 7, "comments_scraped": 8,
            "followers_scraped": 9, "following_scraped": 10,
            "posts_per_min": 11, "comments_per_min": 12, "followers_per_min": 13,
            "rx_bytes_total": 14, "tx_bytes_total": 15,
            "rx_bytes_per_post": 16, "bytes_per_comment": 17,
            "search_method": 18, "profile_found": 19, "error_count": 20,
            "was_interrupted": 21, "headless": 22,
            "limit_posts": 23, "limit_comments": 24,
            "limit_followers": 25, "limit_following": 26, "notes": 27,
        }

        for row in self._all_rows:
            values = []
            for db_col, _, _, fmt in self.COLUMNS:
                raw = row[col_indices[db_col]]
                values.append(fmt(raw) if fmt else (raw if raw is not None else "—"))

            interrupted = row[col_indices["was_interrupted"]]
            errors      = row[col_indices["error_count"]]
            tag = "interrupted" if interrupted else ("errors" if errors > 0 else "ok")
            self._tree.insert("", "end", values=values, tags=(tag,),
                              iid=row[0])  # session_id jako iid

    def _on_select(self, event):
        sel = self._tree.selection()
        if not sel:
            return
        sid = sel[0]
        row = next((r for r in self._all_rows if r[0] == sid), None)
        if not row:
            return

        dur  = _fmt_dur(row[6])
        rx   = _fmt_bytes(row[14])
        tx   = _fmt_bytes(row[15])
        note = row[27] or "—"

        self._detail_var.set(
            f"Session: {sid[:8]}…  |  Bot: {row[2]}  |  Cíl: {row[3]}  |  "
            f"Platforma: {row[1]}  |  Délka: {dur}  |  "
            f"P:{row[7]} K:{row[8]} Sl:{row[9]}  |  "
            f"P/min: {row[11]:.1f}  K/min: {row[12]:.1f}  |  "
            f"RX: {rx}  TX: {tx}  |  "
            f"Metoda: {row[18]}  |  Chyby: {row[20]}  |  Poznámka: {note}"
        )

    # ------------------------------------------------------------------
    # Graf
    # ------------------------------------------------------------------
    def _draw_chart(self):
        c = self._chart
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w <= 1 or h <= 1 or not self._all_rows:
            return

        label_str = self._metric_combo.get()
        db_col    = self._metric_map.get(label_str, "posts_per_min")

        col_idx = {
            "posts_per_min": 11, "comments_per_min": 12, "followers_per_min": 13,
            "rx_bytes_total": 14, "duration_s": 6, "error_count": 20,
            "rx_bytes_per_post": 16,
        }
        idx = col_idx.get(db_col, 11)

        # Posledních 20 sessionů (chronologicky)
        rows = list(reversed(self._all_rows[:20]))
        values = [float(r[idx] or 0) for r in rows]
        peak   = max(values) or 1

        pad_l, pad_r, pad_t, pad_b = 40, 20, 20, 50
        chart_w = w - pad_l - pad_r
        chart_h = h - pad_t - pad_b
        bar_w   = max(4, chart_w // max(len(rows), 1) - 4)

        COLORS_BAR = ["#175DDC", "#2eb85c", "#e0a040", "#9b59b6",
                      "#5a9bd4", "#e05252", "#175DDC"]

        for i, (row, val) in enumerate(zip(rows, values)):
            x0 = pad_l + i * (chart_w // len(rows))
            bar_h = int((val / peak) * chart_h)
            y0 = pad_t + chart_h - bar_h
            y1 = pad_t + chart_h

            color = "#e05252" if row[21] else COLORS_BAR[i % len(COLORS_BAR)]
            c.create_rectangle(x0, y0, x0 + bar_w, y1,
                               fill=color, outline="", width=0)

            # Hodnota nad sloupcem
            display = f"{val/1024:.0f}KB" if "bytes" in db_col and val > 1024 else f"{val:.1f}"
            c.create_text(x0 + bar_w // 2, y0 - 4,
                          text=display, fill=COLORS["text_dim"],
                          font=("Segoe UI", 8), anchor="s")

            # Popisek pod (datum + cíl)
            label = f"{row[4][5:10]}\n{row[3][:10]}"
            c.create_text(x0 + bar_w // 2, y1 + 6,
                          text=label, fill=COLORS["text_dim"],
                          font=("Segoe UI", 8), anchor="n")

        # Y osa
        c.create_line(pad_l, pad_t, pad_l, pad_t + chart_h,
                      fill=COLORS["border"], width=1)
        for pct in [0, 0.25, 0.5, 0.75, 1.0]:
            y = pad_t + chart_h - int(pct * chart_h)
            val_label = f"{peak * pct:.1f}"
            c.create_text(pad_l - 4, y, text=val_label,
                          fill=COLORS["text_dim"], font=("Segoe UI", 8), anchor="e")
            c.create_line(pad_l, y, pad_l + chart_w, y,
                          fill=COLORS["border"], width=1, dash=(2, 4))

    # ------------------------------------------------------------------
    # Souhrn
    # ------------------------------------------------------------------
    def _populate_summary(self):
        for w in self._summary_frame.winfo_children():
            w.destroy()

        if not self._all_rows:
            ctk.CTkLabel(self._summary_frame, text="Žádné session.",
                         text_color=COLORS["text_dim"]).pack()
            return

        total   = len(self._all_rows)
        ok      = sum(1 for r in self._all_rows if not r[21])
        inter   = total - ok
        avg_dur = sum(r[6] or 0 for r in self._all_rows) / total
        avg_ppm = sum(r[11] or 0 for r in self._all_rows) / total
        avg_kpm = sum(r[12] or 0 for r in self._all_rows) / total
        tot_rx  = sum(r[14] or 0 for r in self._all_rows)
        tot_err = sum(r[20] or 0 for r in self._all_rows)

        # Nejrychlejší session
        best_p  = max(self._all_rows, key=lambda r: r[11] or 0)
        best_k  = max(self._all_rows, key=lambda r: r[12] or 0)

        stats = [
            ("Celkem běhů",              str(total)),
            ("Dokončeno / přerušeno",    f"{ok} / {inter}"),
            ("Průměrná délka",           _fmt_dur(avg_dur)),
            ("Průměrně příspěvků/min",   f"{avg_ppm:.2f}"),
            ("Průměrně komentářů/min",   f"{avg_kpm:.2f}"),
            ("Celkem staženo",           _fmt_bytes(tot_rx)),
            ("Celkem chyb",              str(tot_err)),
            ("Nejrychlejší P/min",       f"{best_p[11]:.2f}  ({best_p[3]} @ {best_p[4][:10]})"),
            ("Nejrychlejší K/min",       f"{best_k[12]:.2f}  ({best_k[3]} @ {best_k[4][:10]})"),
        ]

        # Skupiny podle platformy
        platforms = sorted(set(r[1] for r in self._all_rows))
        for plat in platforms:
            plat_rows = [r for r in self._all_rows if r[1] == plat]
            avg_p = sum(r[11] or 0 for r in plat_rows) / len(plat_rows)
            avg_k = sum(r[12] or 0 for r in plat_rows) / len(plat_rows)
            stats.append((f"{plat} — průměr P/min", f"{avg_p:.2f}"))
            stats.append((f"{plat} — průměr K/min", f"{avg_k:.2f}"))
            stats.append((f"{plat} — počet běhů",   str(len(plat_rows))))

        for label, value in stats:
            row = ctk.CTkFrame(self._summary_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=label, font=("Segoe UI", 12),
                         text_color=COLORS["text_dim"], width=260,
                         anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=value, font=("Segoe UI", 12, "bold"),
                         text_color=COLORS["text_main"], anchor="w").pack(side="left")

    # ------------------------------------------------------------------
    # Export CSV
    # ------------------------------------------------------------------
    def _export_csv(self):
        if not self._all_rows:
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"ogma_sessions_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        )
        if not path:
            return

        all_cols = [
            "session_id", "platform", "bot_identity", "target_username",
            "started_at", "finished_at", "duration_s",
            "posts_scraped", "comments_scraped",
            "followers_scraped", "following_scraped",
            "posts_per_min", "comments_per_min", "followers_per_min",
            "rx_bytes_total", "tx_bytes_total",
            "rx_bytes_per_post", "bytes_per_comment",
            "search_method", "profile_found", "error_count",
            "was_interrupted", "headless",
            "limit_posts", "limit_comments",
            "limit_followers", "limit_following", "notes",
        ]

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(all_cols)
                writer.writerows(self._all_rows)
            print(f"[SESSIONS] Export dokončen: {path}")
        except Exception as e:
            print(f"[SESSIONS] Export selhal: {e}")

    # ------------------------------------------------------------------
    def _sort(self, col):
        """Řazení po kliknutí na hlavičku sloupce."""
        col_idx = {c[0]: i for i, c in enumerate(self.COLUMNS)}
        idx = col_idx.get(col, 0)
        self._all_rows.sort(
            key=lambda r: (r[idx] is None, r[idx]),
            reverse=getattr(self, f"_sort_rev_{col}", False)
        )
        setattr(self, f"_sort_rev_{col}",
                not getattr(self, f"_sort_rev_{col}", False))
        self._populate_tree()

```

## Soubor: social_bot\src\gui\frames\watchlist.py
```py
"""
src/gui/frames/watchlist.py
"""

import customtkinter as ctk
from datetime import datetime
from src.core.database import DatabaseManager


COLORS = {
    "bg":        "#1a1a2e",
    "surface":   "#16213e",
    "border":    "#2a2a4a",
    "accent":    "#175DDC",
    "text_main": "#e0e0e0",
    "text_dim":  "#888",
    "danger":    "#e05252",
    "success":   "#2eb85c",
}


class WatchlistFrame(ctk.CTkFrame):
    def __init__(self, parent, scheduler, **kwargs):
        super().__init__(parent, fg_color=COLORS["bg"], **kwargs)
        self.scheduler = scheduler
        self.db = DatabaseManager()
        self._build_ui()
        self._refresh_list()

        # Pravidelný refresh statusu
        self._tick()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        # ---- Horní panel: přidání účtu ----
        add_frame = ctk.CTkFrame(self, fg_color=COLORS["surface"],
                                 corner_radius=10)
        add_frame.pack(fill="x", padx=16, pady=(16, 8))

        ctk.CTkLabel(add_frame, text="Přidat účet do watchlistu",
                     font=("Segoe UI", 14, "bold"),
                     text_color=COLORS["text_main"]).pack(anchor="w", padx=14, pady=(10, 6))

        fields = ctk.CTkFrame(add_frame, fg_color="transparent")
        fields.pack(fill="x", padx=14, pady=(0, 10))

        # Username
        ctk.CTkLabel(fields, text="Uživatelské jméno:",
                     text_color=COLORS["text_dim"],
                     font=("Segoe UI", 12)).grid(row=0, column=0, sticky="w", padx=(0,8))
        self._entry_username = ctk.CTkEntry(fields, width=180,
                                            placeholder_text="např. nasa")
        self._entry_username.grid(row=0, column=1, padx=(0, 16))

        # Interval
        ctk.CTkLabel(fields, text="Interval (min):",
                     text_color=COLORS["text_dim"],
                     font=("Segoe UI", 12)).grid(row=0, column=2, sticky="w", padx=(0,8))
        self._entry_interval = ctk.CTkEntry(fields, width=70)
        self._entry_interval.insert(0, "20")
        self._entry_interval.grid(row=0, column=3, padx=(0, 16))

        # Limity
        for col, (label, default, attr) in enumerate([
            ("Příspěvky", "10",  "_entry_lp"),
            ("Komentáře", "50",  "_entry_lc"),
            ("Sledující",  "0",  "_entry_lf"),
            ("Sledovaní",  "0",  "_entry_lfol"),
        ], start=4):
            ctk.CTkLabel(fields, text=f"{label}:",
                         text_color=COLORS["text_dim"],
                         font=("Segoe UI", 12)).grid(row=0, column=col*2, sticky="w", padx=(0,4))
            e = ctk.CTkEntry(fields, width=55)
            e.insert(0, default)
            e.grid(row=0, column=col*2+1, padx=(0, 12))
            setattr(self, attr, e)

        ctk.CTkButton(fields, text="+ Přidat", width=90,
                      fg_color=COLORS["accent"],
                      command=self._add_entry).grid(row=0, column=13, padx=(8, 0))

        # ---- Scheduler controls ----
        ctrl_frame = ctk.CTkFrame(self, fg_color=COLORS["surface"],
                                  corner_radius=10)
        ctrl_frame.pack(fill="x", padx=16, pady=(0, 8))

        inner = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=10)

        self._btn_start = ctk.CTkButton(
            inner, text="▶  Spustit scheduler", width=160,
            fg_color=COLORS["success"], command=self._toggle_scheduler)
        self._btn_start.pack(side="left", padx=(0, 12))

        self._lbl_status = ctk.CTkLabel(
            inner, text="Scheduler: zastaven",
            text_color=COLORS["text_dim"], font=("Segoe UI", 12))
        self._lbl_status.pack(side="left")

        # ---- Tabulka watchlistu ----
        list_frame = ctk.CTkFrame(self, fg_color=COLORS["surface"],
                                  corner_radius=10)
        list_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        ctk.CTkLabel(list_frame, text="Sledované účty",
                     font=("Segoe UI", 14, "bold"),
                     text_color=COLORS["text_main"]).pack(anchor="w", padx=14, pady=(10, 4))

        # Scrollable list
        self._scroll = ctk.CTkScrollableFrame(
            list_frame, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._rows = []  # seznam widgetů

    # ------------------------------------------------------------------
    # Logika
    # ------------------------------------------------------------------
    def _add_entry(self):
        username = self._entry_username.get().strip().lstrip("@")
        if not username:
            return

        try:
            interval = int(self._entry_interval.get())
            lp   = int(self._entry_lp.get())
            lc   = int(self._entry_lc.get())
            lf   = int(self._entry_lf.get())
            lfol = int(self._entry_lfol.get())
        except ValueError:
            return

        try:
            self.db.cursor.execute('''
                INSERT OR IGNORE INTO watchlist
                    (platform, username, interval_min,
                     limit_posts, limit_comments, limit_followers, limit_following)
                VALUES ('IG', ?, ?, ?, ?, ?, ?)
            ''', (username, interval, lp, lc, lf, lfol))
            self.db.conn.commit()
            self._entry_username.delete(0, "end")
            self._refresh_list()
        except Exception as e:
            print(f"[WATCHLIST] Chyba přidávání: {e}")

    def _toggle_scheduler(self):
        if self.scheduler.is_running():
            self.scheduler.stop()
        else:
            self.scheduler.start()
        self._update_status()

    def _toggle_entry(self, row_id, enabled):
        self.db.cursor.execute(
            "UPDATE watchlist SET enabled=? WHERE id=?",
            (0 if enabled else 1, row_id))
        self.db.conn.commit()
        self._refresh_list()

    def _delete_entry(self, row_id):
        self.db.cursor.execute("DELETE FROM watchlist WHERE id=?", (row_id,))
        self.db.conn.commit()
        self._refresh_list()

    def _update_interval(self, row_id, value):
        try:
            self.db.cursor.execute(
                "UPDATE watchlist SET interval_min=?, next_scrape_at=NULL WHERE id=?",
                (int(value), row_id))
            self.db.conn.commit()
        except:
            pass

    # ------------------------------------------------------------------
    # Refresh GUI
    # ------------------------------------------------------------------
    def _refresh_list(self):
        for w in self._scroll.winfo_children():
            w.destroy()

        self.db.cursor.execute('''
            SELECT id, username, interval_min, enabled,
                   last_scraped_at, next_scrape_at,
                   limit_posts, limit_comments, limit_followers, limit_following
            FROM watchlist ORDER BY added_at DESC
        ''')
        rows = self.db.cursor.fetchall()

        if not rows:
            ctk.CTkLabel(self._scroll, text="Žádné sledované účty.",
                         text_color=COLORS["text_dim"]).pack(pady=20)
            return

        # Hlavička
        hdr = ctk.CTkFrame(self._scroll, fg_color=COLORS["border"], corner_radius=6)
        hdr.pack(fill="x", pady=(0, 4))
        for col, (text, w) in enumerate([
            ("Uživatel", 160), ("Interval", 90), ("P/K/S/Sl", 120),
            ("Poslední scrape", 140), ("Další scrape", 140),
            ("Stav", 60), ("", 120)
        ]):
            ctk.CTkLabel(hdr, text=text, width=w,
                         font=("Segoe UI", 11, "bold"),
                         text_color=COLORS["text_dim"]).grid(
                row=0, column=col, padx=6, pady=4, sticky="w")

        for row in rows:
            row_id, username, interval, enabled, last_at, next_at, lp, lc, lf, lfol = row
            self._build_row(row_id, username, interval, enabled,
                            last_at, next_at, lp, lc, lf, lfol)

    def _build_row(self, row_id, username, interval, enabled,
                   last_at, next_at, lp, lc, lf, lfol):
        frame = ctk.CTkFrame(self._scroll, fg_color=COLORS["surface"],
                             corner_radius=6)
        frame.pack(fill="x", pady=2)

        # Username
        ctk.CTkLabel(frame, text=f"@{username}", width=160,
                     font=("Segoe UI", 12, "bold"),
                     text_color=COLORS["text_main"],
                     anchor="w").grid(row=0, column=0, padx=8, pady=6, sticky="w")

        # Interval (editovatelný)
        interval_var = ctk.StringVar(value=str(interval))
        interval_entry = ctk.CTkEntry(frame, textvariable=interval_var,
                                      width=60, justify="center")
        interval_entry.grid(row=0, column=1, padx=4)
        ctk.CTkLabel(frame, text="min", text_color=COLORS["text_dim"],
                     font=("Segoe UI", 11)).grid(row=0, column=1, padx=(68, 0))
        interval_entry.bind("<FocusOut>",
            lambda e, rid=row_id, v=interval_var: self._update_interval(rid, v.get()))

        # Limity
        ctk.CTkLabel(frame, text=f"{lp} / {lc} / {lf} / {lfol}",
                     width=120, text_color=COLORS["text_dim"],
                     font=("Segoe UI", 11)).grid(row=0, column=2, padx=4)

        # Časy
        last_str = last_at[11:16] if last_at else "nikdy"
        next_str = next_at[11:16] if next_at else "ihned"
        ctk.CTkLabel(frame, text=last_str, width=140,
                     text_color=COLORS["text_dim"],
                     font=("Segoe UI", 11)).grid(row=0, column=3, padx=4)
        ctk.CTkLabel(frame, text=next_str, width=140,
                     text_color=COLORS["accent"] if next_at else COLORS["success"],
                     font=("Segoe UI", 11)).grid(row=0, column=4, padx=4)

        # Enable/disable
        state_color = COLORS["success"] if enabled else COLORS["text_dim"]
        state_text  = "ON" if enabled else "OFF"
        ctk.CTkLabel(frame, text=state_text, width=60,
                     text_color=state_color,
                     font=("Segoe UI", 11, "bold")).grid(row=0, column=5, padx=4)

        # Akce
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.grid(row=0, column=6, padx=8)

        ctk.CTkButton(btn_frame,
                      text="Pause" if enabled else "Resume",
                      width=60, height=26,
                      fg_color=COLORS["border"],
                      command=lambda rid=row_id, en=enabled:
                          self._toggle_entry(rid, en)).pack(side="left", padx=2)

        ctk.CTkButton(btn_frame, text="✕", width=30, height=26,
                      fg_color=COLORS["danger"],
                      command=lambda rid=row_id:
                          self._delete_entry(rid)).pack(side="left", padx=2)

    def _update_status(self):
        if self.scheduler.is_running():
            target = self.scheduler.get_current_target()
            status = f"Scheduler: běží  |  Právě: @{target}" if target else "Scheduler: běží  |  Čeká na další cíl"
            self._btn_start.configure(text="⏹  Zastavit", fg_color=COLORS["danger"])
            self._lbl_status.configure(text=status, text_color=COLORS["success"])
        else:
            self._btn_start.configure(text="▶  Spustit scheduler", fg_color=COLORS["success"])
            self._lbl_status.configure(text="Scheduler: zastaven", text_color=COLORS["text_dim"])

    def _tick(self):
        self._update_status()
        self.after(5000, self._tick)  # refresh statusu každých 5s
```

## Soubor: social_bot\src\utils\human_input.py
```py
import time
import random

def delay(min_seconds=1.0, max_seconds=3.0):
    """Náhodná prodleva mezi akcemi."""
    time.sleep(random.uniform(min_seconds, max_seconds))

def human_typing(locator, text):
    """
    Simuluje psaní člověka pro Playwright Locator s variabilním zpožděním.
    Slouží jako alternativa k nativnímu locator.press_sequentially(text, delay=150),
    pokud je vyžadována vyšší úroveň simulace (zcela náhodné pauzy mezi znaky).
    """
    try:
        locator.fill("") # Vyčištění pole před zápisem
        for char in text:
            # press_sequentially jednoho znaku s náhodnou mezní pauzou
            locator.press_sequentially(char, delay=int(random.uniform(10, 50)))
            time.sleep(random.uniform(0.05, 0.25))
    except Exception as e:
        print(f"[DEBUG] Chyba při human_typing: {e}")

def random_mouse_movement(page=None):
    """
    Generuje náhodné pohyby myší napříč viewportem.
    Využívá Playwright page.mouse API pro zvýšení důvěryhodnosti (stealth).
    """
    if not page:
        return
        
    try:
        viewport = page.viewport_size
        if not viewport:
            # Fallback hodnoty, pokud viewport není detekován
            width, height = 1280, 720
        else:
            width = viewport['width']
            height = viewport['height']
            
        # Provede 2 až 5 náhodných křivek/pohybů
        for _ in range(random.randint(2, 5)):
            target_x = random.randint(0, width)
            target_y = random.randint(0, height)
            
            # steps určuje plynulost (počet mezikroků při pohybu kurzoru)
            page.mouse.move(target_x, target_y, steps=random.randint(5, 15))
            time.sleep(random.uniform(0.1, 0.4))
            
    except Exception:
        pass
```

