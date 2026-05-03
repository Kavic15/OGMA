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