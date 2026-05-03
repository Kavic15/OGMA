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