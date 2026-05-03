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
