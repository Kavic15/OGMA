# DONE: Ogma — Implementované funkcionality

---

## Sběr dat (Scraping)

### Instagram
- [x] **Přihlášení a správa session** — `src/bots/instagram/auth.py`
  - Detekce existující session, cookies handling, submit formuláře
- [x] **Scraping profilu** — `src/bots/instagram/scraper.py`
  - Username, display name, bio, followers, following, web, verifikace, profilová fotka
- [x] **Scraping příspěvků** — vč. podpory kolotočů (více fotek), videí, reels
  - Lajky, komentáře, timestamp, media URL, text obsahu
- [x] **Scraping komentářů** — s limitem, scrollování, de-duplikace
- [x] **Scraping followers / following sítě**
  - Ukládání do tabulky `connections`
- [x] **Vyhledávání profilu** — přes interní našeptávač + direct URL fallback

### X / Twitter
- [x] **Přihlášení a správa session** — `src/bots/x/auth.py`
  - Detekce session, dvoukrokový login (username → heslo)
- [x] **Scraping profilu** — `src/bots/x/modules/profile.py`
  - Username, display name, bio, followers, following, lokace, web, datum založení, verifikace, HD profilová fotka, banner
- [x] **Scraping příspěvků (timeline)** — `src/bots/x/modules/posts.py`
  - Text, timestamp, lajky, retweety, komentáře, media URL
  - Detekce a extrakce MP4 stream URL pro videa (network sniffer)
- [x] **Scraping komentářů** — `src/bots/x/modules/comments.py`
  - Včetně Fáze 4: extrakce MP4 z video-komentářů
- [x] **Scraping followers / following sítě** — `src/bots/x/modules/network.py`
- [x] **Scraping trendů** — `src/bots/x/scraper.py → scrape_trending()`
- [x] **Vyhledávání profilu** — `src/bots/x/modules/search.py`
  - 3 kroky: lokální DB cache → interní X hledání → Google fallback

---

## Databáze

- [x] **SQLite databáze** — `src/core/database.py`
- [x] **Tabulky:** `users`, `posts`, `comments`, `trending`, `connections`
- [x] **Upsert logika** — žádné duplikáty, aktualizace stávajících záznamů
- [x] **Automatická migrace** — přidání nových sloupců do existující DB bez ztráty dat
- [x] **Rozšířená metadata uživatelů:**
  - `following_count`, `joined_date`, `location`, `website`, `is_verified`, `profile_pic_url`, `banner_url`

---

## Analytika

### Sentiment analýza
- [x] **Dvouvrstvá sentiment analýza** — `src/analysis/sentiment.py`
  - Vrstva 1: Kontextový slovník (`context_lexicon.json`) — doménové výrazy informační války
  - Vrstva 2: VADER — lexikální analýza
  - Vážený průměr (55 % slovník / 45 % VADER)
- [x] **Preprocessing textu před analýzou**
  - Emoji → textový popis (knihovna `emoji`)
  - Hashtagy → slova (`#FreeIran` → `free iran`, `#NoDeal` → `no deal`)
  - Odstranění URL a @mentions
- [x] **Detekce jazyka** (`langdetect`) + překlad do EN (`deep-translator`)
- [x] **Kontextový slovník** — `src/analysis/context_lexicon.json`
  - ~150 výrazů v kategoriích: politické osobnosti, dezinformační narativy, bot/spam, válečná terminologie, solidarita, emoji jako text, CZ/SK/ES specifika
  - Sekce `custom` pro rozšiřování za běhu
- [x] **Hromadná analýza** `analyze_pending()` + **jednorázová** `analyze_single()`
- [x] **Statistiky per uživatel** `get_stats_for_user()`
- [x] **Rozšíření slovníku za běhu** `add_to_lexicon()`
- [x] **Nové sloupce v DB:** `sentiment_score`, `sentiment_label`, `sentiment_lang`

### OCR analýza obrázků
- [x] **Tesseract OCR** — `src/analysis/image_ocr.py`
  - Preprocessing obrázků (zvětšení, kontrast, zostření)
  - Podpora více URL (Instagram kolotoče, `;` separátor)
  - Filtrování video thumbnail URL
  - Čištění OCR výstupu (artefakty, šum)
- [x] **Sentiment extrahovaného textu z obrázků**
- [x] **Hromadné zpracování** — příspěvky i komentáře zvlášť
- [x] **Nové sloupce v DB:** `media_text`, `media_sentiment_score`, `media_sentiment_label`

---

## GUI

- [x] **Hlavní okno** — `src/gui/app.py` (CustomTkinter, dark mode)
- [x] **Sidebar navigace** — Dashboard, Profily, Databáze, Analýza
- [x] **Dashboard** — `src/gui/frames/dashboard.py`
  - Výběr identity bota, cílové účty (batch, čárkou oddělené)
  - Limity: příspěvky, komentáře, followers, following
  - Tlačítka: IG login, IG scrape, X login, X scrape, trendy, STOP
  - Live log (stdout redirect), progress bar
- [x] **Záložka Profily** — `src/gui/frames/profiles.py`
  - Karty profilů s avatarem, jménem, handle, verifikací, followers/following, bio, metadaty
  - Vyhledávání/filtrování
  - **Sentiment vizualizace na kartě:**
    - Průměrné skóre s barevným kódováním
    - Stacked bar (pozitivní / neutrální / negativní)
    - Legenda s procenty a absolutními počty
- [x] **Záložka Databáze** — `src/gui/frames/database.py`
  - Tabulky: Uživatelé, Příspěvky, Trendy, Síť (Connections)
- [x] **Záložka Analýza** — `src/gui/frames/analysis.py`
  - Sentiment analýza s progress barem
  - OCR analýza — příspěvky / komentáře / vše, live statistiky
  - Výsledková tabulka per uživatel (vč. počtu OCR textů)
- [x] **Dark theme** — `src/gui/theme.py` (Bitwarden-inspired paleta)
- [x] **AsyncImageLoader** — načítání profilových fotek v threadu
- [x] **PrintLogger** — přesměrování stdout/stderr do GUI log boxu

---

## Architektura a infrastruktura

- [x] **Modulární architektura** — `core`, `bots`, `analysis`, `gui`, `utils`
- [x] **BaseBot** — `src/core/base_bot.py`
  - Playwright persistent context (izolované profily per identita)
  - Anti-detekční skripty (webdriver, plugins, languages)
  - `open_url`, `find_element_smart`, `click_smart`, `handle_popups`
- [x] **Správa identit** — `data/users.json`, výběr v GUI
- [x] **Batch scraping** — více cílů naráz s progress barem a pauzami
- [x] **Thread safety** — veškeré bot operace v daemon threadech
- [x] **Human input simulace** — `src/utils/human_input.py`
  - `delay()`, `human_typing()`, `random_mouse_movement()`
- [x] **Stealth mode** — základní anti-detekce v `BaseBot._apply_stealth_scripts()`
  - `navigator.webdriver = undefined`, falešné pluginy, jazyky