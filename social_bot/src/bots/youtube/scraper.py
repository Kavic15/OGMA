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