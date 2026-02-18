from src.utils.human_input import delay
from .utils import XUtils

class XCommentsModule:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    def scrape_for_queue(self, queue, limit=20):
        if not queue: return
        
        count = len(queue)
        print(f"\n[X-COMMENTS] --- Těžba komentářů ({count} příspěvků) ---")
        
        for i, post_data in enumerate(queue):
            print(f"[X-COMMENTS] Komentáře pro {post_data['platform_id']} ({i+1}/{count})...")
            try:
                self._scrape_single_post(post_data['db_id'], post_data['platform_id'], post_data['url'], limit)
            except Exception as e:
                print(f"[ERROR] Chyba u komentářů: {e}")

    def _scrape_single_post(self, db_post_id, platform_post_id, post_url, max_comments):
        try:
            self.bot.page.get(post_url)
            if not self.bot.page.ele('@data-testid=tweetText', timeout=4): return
        except: return

        delay(0.5, 1.0)
        comments_collected = 0
        processed_ids = set()
        
        for _ in range(6): 
            if comments_collected >= max_comments: break
            articles = self.bot.page.eles('tag:article', timeout=0.5)
            
            for article in articles:
                if comments_collected >= max_comments: break
                try:
                    time_ele = article.ele('tag:time', timeout=0.05)
                    if not time_ele: continue
                    
                    raw_href = time_ele.parent('tag:a').attr('href')
                    if not raw_href: continue
                    
                    cid = raw_href.split('/')[-1]
                    if not cid or cid == platform_post_id or cid in processed_ids: continue
                    processed_ids.add(cid)

                    # Autor
                    user_name_ele = article.ele('@data-testid=User-Name', timeout=0.05)
                    author_user = user_name_ele.text.split('\n')[1].replace('@', '') if user_name_ele else ""
                    
                    # Text
                    text_ele = article.ele('@data-testid=tweetText', timeout=0.05)
                    text_content = text_ele.text if text_ele else ""
                    text_content, media_url, _ = XUtils.extract_media(article, text_content)

                    self.db.upsert_comment(
                        post_id=db_post_id,
                        platform="X",
                        platform_comment_id=cid,
                        author_username=author_user,
                        author_display_name="",
                        text_content=text_content,
                        timestamp_posted=time_ele.attr('datetime'),
                        likes_count=0, shares_count=0, replies_count=0,
                        media_url=media_url
                    )
                    comments_collected += 1
                except: continue

            self.bot.page.scroll.down(700)
            delay(0.5, 0.8)