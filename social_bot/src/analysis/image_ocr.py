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