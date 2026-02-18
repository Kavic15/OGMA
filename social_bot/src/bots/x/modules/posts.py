import time
from src.utils.human_input import delay
from .utils import XUtils

class XPostsModule:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    def scrape_timeline(self, user_id, limit):
        """
        Scrapuje příspěvky z timeline. 
        Vrací: (videos_queue, all_posts_queue)
        """
        print("[X-POSTS] Sbírám příspěvky...")
        posts_collected = 0
        processed_post_ids = set()
        
        posts_to_process_video = []   # Fronta pro videa (Fáze 2)
        posts_for_comments = []       # Fronta pro komentáře (Fáze 3 - Všechny)
        
        while True:
            if limit != -1 and posts_collected >= limit: break
            
            articles = self.bot.page.eles('tag:article', timeout=2)
            new_in_batch = False

            for article in articles:
                if limit != -1 and posts_collected >= limit: break
                try:
                    time_ele = article.ele('tag:time', timeout=0.05)
                    if not time_ele: continue 
                    
                    raw_href = time_ele.parent('tag:a').attr('href')
                    if not raw_href: continue
                    full_url = raw_href if raw_href.startswith("http") else f"https://x.com{raw_href}"
                    platform_post_id = raw_href.split('/')[-1]
                    
                    if not platform_post_id or platform_post_id in processed_post_ids: continue
                    processed_post_ids.add(platform_post_id)
                    new_in_batch = True
                    
                    # Text & Media
                    text_ele = article.ele('@data-testid=tweetText', timeout=0.05)
                    post_text = text_ele.text if text_ele else ""
                    post_text, media_url, is_video = XUtils.extract_media(article, post_text)
                    
                    timestamp = time_ele.attr('datetime')
                    
                    # Stats
                    likes, shares, comments = 0, 0, 0
                    try:
                        re_el = article.ele('@data-testid=reply', timeout=0.01); comments = XUtils.parse_number(re_el.text) if re_el else 0
                        rt_el = article.ele('@data-testid=retweet', timeout=0.01); shares = XUtils.parse_number(rt_el.text) if rt_el else 0
                        li_el = article.ele('@data-testid=like', timeout=0.01); likes = XUtils.parse_number(li_el.text) if li_el else 0
                    except: pass

                    # Uložit do DB
                    db_post_id = self.db.upsert_post(user_id, "X", platform_post_id, post_text, timestamp, likes, shares, comments, full_url, media_url)
                    posts_collected += 1
                    
                    print(f"[X-POSTS] ({posts_collected}) Tweet: {platform_post_id} | Video: {is_video}")
                    
                    # Přidat do seznamu pro komentáře (všechny úspěšně stažené)
                    posts_for_comments.append({
                        'db_id': db_post_id,
                        'platform_id': platform_post_id,
                        'url': full_url
                    })

                    # Pokud je to video, uložíme si pro sniffing (i když nefunguje 100%, logika tu zůstane)
                    if is_video:
                        posts_to_process_video.append({
                            'db_id': db_post_id,
                            'url': full_url,
                            'platform_id': platform_post_id
                        })
                    
                except Exception: 
                    pass

            if not new_in_batch:
                self.bot.page.scroll.down(400)
                delay(1)
            self.bot.page.scroll.down(700)
            delay(0.8, 1.5)
            
        return posts_to_process_video, posts_for_comments

    def process_videos(self, video_queue):
        """2. Fáze: Projde seznam videí a získá m3u8 stream."""
        if not video_queue: return

        count = len(video_queue)
        print(f"\n[X-VIDEO] --- FÁZE 2: Těžba odkazů videí ({count} položek) ---")
        
        for i, item in enumerate(video_queue):
            print(f"[X-VIDEO] Zpracovávám video {i+1}/{count}...")
            try:
                stream_url = self._get_video_stream(item['url'])
                
                if stream_url:
                    self.db.cursor.execute("UPDATE posts SET media_url = ? WHERE id = ?", (stream_url, item['db_id']))
                    self.db.conn.commit()
                    print(f"  -> [DB] Video aktualizováno.")
                else:
                    print(f"  -> [WARNING] Stream nenalezen.")
                    
                delay(2, 4)
            except Exception as e:
                print(f"  -> [ERROR] {e}")

    def _get_video_stream(self, post_url):
        print(f"  -> [SNIFFER] Jdu pro video: {post_url}")
        
        self.bot.page.listen.start(targets="video.twimg.com")
        self.bot.page.get(post_url)
        
        try:
            # Kliknout na video pro vynucení načtení
            video_ele = self.bot.page.ele('@data-testid=videoPlayer', timeout=5)
            if video_ele: video_ele.click(by_js=True)
        except: pass

        video_url = None
        start_time = time.time()
        
        while time.time() - start_time < 6:
            for packet in self.bot.page.listen.steps(timeout=0.5):
                if ".m3u8" in packet.url and "video.twimg.com" in packet.url:
                    video_url = packet.url
                    print(f"  -> [SNIFFER] ÚSPĚCH! URL zachycena.")
                    break
            if video_url: break
        
        self.bot.page.listen.stop()
        return video_url