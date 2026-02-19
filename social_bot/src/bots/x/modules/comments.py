from src.utils.human_input import delay
from .utils import XUtils
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
import time
import re

class XCommentsModule:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    def scrape_for_queue(self, queue, limit=20):
        if not queue: return
        
        count = len(queue)
        print(f"\n[X-COMMENTS] --- Těžba komentářů ({count} příspěvků) ---")
        
        # Nová fronta čistě pro videa v komentářích
        comment_videos_queue = []
        
        for i, post_data in enumerate(queue):
            print(f"[X-COMMENTS] Komentáře pro {post_data['platform_id']} ({i+1}/{count})...")
            try:
                self._scrape_single_post(
                    post_data['db_id'], 
                    post_data['platform_id'], 
                    post_data['url'], 
                    limit,
                    comment_videos_queue
                )
            except Exception as e:
                print(f"[ERROR] Chyba u komentářů: {e}")

        # Pokud jsme narazili na video v komentářích, vyvoláme Fázi 4
        if comment_videos_queue:
            self._process_comment_videos(comment_videos_queue)

    def _scrape_single_post(self, db_post_id, platform_post_id, post_url, max_comments, video_queue):
        try:
            self.bot.page.goto(post_url, wait_until="domcontentloaded", timeout=20000)
            
            main_article = self.bot.page.locator('article').first
            main_article.wait_for(state="visible", timeout=10000)
            
            self.bot.page.wait_for_timeout(2000)
        except PlaywrightTimeoutError:
            print(f"  -> [WARNING] Timeout při načítání příspěvku {platform_post_id}.")
            return
        except Exception as e:
            print(f"  -> [ERROR] Nelze načíst příspěvek {platform_post_id}: {e}")
            return

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
                    author_user = user_name_ele.inner_text().split('\n')[1].replace('@', '') if user_name_ele.count() > 0 else ""
                    
                    text_ele = article.locator('[data-testid="tweetText"]').first
                    text_content = text_ele.inner_text() if text_ele.count() > 0 else ""
                    
                    # Nyní už nevyhazujeme boolean pro is_video, ale zachytáváme ho
                    text_content, media_url, is_video = XUtils.extract_media(article, text_content)

                    # Uložíme komentář s aktuálním náhledem a získáme jeho vnitřní UUID z naší DB
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

                    # Pokud je to video, pošleme ho s UUID a URL na "operaci Fáze 4"
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

    def _process_comment_videos(self, video_queue):
        """Dodatečná Fáze 4 - stahuje MP4 pro komentáře."""
        count = len(video_queue)
        print(f"\n[X-COMMENTS-VIDEO] --- FÁZE 4: Těžba MP4 z komentářů ({count} položek) ---")
        
        for i, item in enumerate(video_queue):
            print(f"[X-COMMENTS-VIDEO] Zpracovávám komentář {i+1}/{count} (ID: {item['platform_id']})...")
            try:
                stream_url = self._get_video_stream(item['url'])
                
                if stream_url:
                    # Rozdíl oproti příspěvkům: updatujeme tabulku 'comments'
                    self.db.cursor.execute("UPDATE comments SET media_url = ? WHERE id = ?", (stream_url, item['db_id']))
                    self.db.conn.commit()
                    print(f"  -> [DB] Video aktualizováno pro komentář.")
                else:
                    print(f"  -> [WARNING] Stream nenalezen.")
                    
                delay(2, 4)
            except Exception as e:
                print(f"  -> [ERROR] {e}")

    def _get_video_stream(self, post_url):
        """Identický sniffer jako v posts.py."""
        video_url = None
        
        def handle_response(response):
            nonlocal video_url
            try:
                if "graphql" in response.url:
                    text_body = response.text().replace('\\/', '/')
                    links = re.findall(r'(https://video\.twimg\.com/[^"\'\s]+\.(?:mp4|m3u8))', text_body)
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