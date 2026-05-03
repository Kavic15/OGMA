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