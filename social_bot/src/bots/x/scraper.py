from src.core.database import DatabaseManager
from .modules.search import XSearchModule
from .modules.profile import XProfileModule
from .modules.posts import XPostsModule
from .modules.comments import XCommentsModule

class XScraper:
    def __init__(self, bot):
        self.bot = bot
        self.db = DatabaseManager()
        
        # Inicializace modulů
        self.search_module = XSearchModule(bot, self.db)
        self.profile_module = XProfileModule(bot, self.db)
        self.posts_module = XPostsModule(bot, self.db)
        self.comments_module = XCommentsModule(bot, self.db)

    def scrape_profile(self, target_query, limit=10):
        limit_text = "NEOMEZENO" if limit == -1 else str(limit)
        print(f"[X-SCRAPER] Cíl: '{target_query}' (Limit: {limit_text})")
        
        # 1. Najít profil (Navigace)
        if not self.search_module.find_profile(target_query):
            print(f"[ERROR] Profil '{target_query}' nebyl nalezen ani přes Google.")
            return

        # Zjistit aktuální username z URL
        try:
            current_url = self.bot.page.url
            if "x.com/" in current_url:
                actual_username = current_url.split('x.com/')[-1].split('?')[0].split('/')[0]
            else:
                actual_username = target_query.replace('@', '').replace(' ', '')
        except:
            actual_username = target_query.replace('@', '').replace(' ', '')

        # 2. Vytěžit metadata profilu
        user_id = self.profile_module.scrape_metadata(actual_username)

        # 3. Vytěžit příspěvky (Timeline)
        # Získáváme dvě fronty: jednu pro videa, druhou pro komentáře (všechny posty)
        videos_queue, comments_queue = self.posts_module.scrape_timeline(user_id, limit)

        # 4. Fáze 2: Video Sniffing (Volitelné/Experimentální)
        # Pokud nefunguje ideálně, nevadí, pouze se pokusí vylepšit data
        if videos_queue:
            self.posts_module.process_videos(videos_queue)

        # 5. Fáze 3: Komentáře
        # Spustíme těžbu komentářů pro všechny stažené příspěvky
        if comments_queue:
            self.comments_module.scrape_for_queue(comments_queue, limit=20)
        else:
            print("[X-SCRAPER] Žádné příspěvky ke zpracování komentářů.")

        print("\n[X-SCRAPER] Hotovo.")

    def scrape_trending(self):
        print("[X-SCRAPER] Těžba trendů...")
        self.bot.page.get("https://x.com/explore/tabs/trending")
        if not self.bot.page.ele('@data-testid=trend', timeout=6):
            print("[X-SCRAPER] Trendy se nenačetly.")
            return
        trends = self.bot.page.eles('@data-testid=trend', timeout=4)
        print(f"[X-SCRAPER] Nalezeno {len(trends)} trendů.")
        for index, trend in enumerate(trends):
            try:
                text = trend.text.split('\n')
                topic = text[1] if len(text) > 1 else text[0]
                count = text[-1] if "posts" in text[-1] else "N/A"
                self.db.upsert_trend("X", index+1, "General", topic, count)
                print(f"  -> #{index+1} {topic}")
            except: pass