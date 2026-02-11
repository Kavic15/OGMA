from src.utils.human_input import delay, human_typing
from src.core.database import DatabaseManager
import re

class XScraper:
    def __init__(self, bot):
        self.bot = bot
        self.db = DatabaseManager()

    def parse_number(self, text):
        if not text: 
            return 0
        text = text.upper().replace(',', '').replace(' ', '')
        match = re.search(r'([\d\.]+)([KMB]?)', text)
        if not match: 
            return 0
            
        num_str, suffix = match.groups()
        num = float(num_str)
        
        if suffix == 'K': num *= 1000
        elif suffix == 'M': num *= 1000000
        elif suffix == 'B': num *= 1000000000
        
        return int(num)

    def extract_media(self, article, current_text):
        media_url = None
        photo_ele = article.ele('@data-testid=tweetPhoto', timeout=0.1)
        video_ele = article.ele('@data-testid=videoPlayer', timeout=0.1)
        
        if photo_ele:
            img_ele = photo_ele.ele('tag:img', timeout=0.1)
            if img_ele:
                media_url = img_ele.attr('src')
            if not current_text.strip():
                current_text = "[OBSAHUJE FOTKU]"
        elif video_ele:
            if not current_text.strip():
                current_text = "[OBSAHUJE VIDEO]"
                
        return current_text, media_url

    def scrape_comments_for_post(self, db_post_id, platform_post_id, post_url, max_comments=50):
        print(f"  -> [X-SCRAPER] Otevírám detail příspěvku a těžím komentáře...")
        self.bot.open_url(post_url)
        delay(3, 5)

        comments_collected = 0
        processed_comment_ids = set()

        for scroll_attempt in range(15):
            articles = self.bot.page.eles('tag:article', timeout=2)
            
            for article in articles:
                if comments_collected >= max_comments:
                    break

                time_ele = article.ele('tag:time', timeout=0.1)
                if not time_ele:
                    continue
                
                link_ele = time_ele.parent('tag:a')
                if not link_ele:
                    continue
                
                comment_url = link_ele.attr('href')
                platform_comment_id = comment_url.split('/')[-1] if comment_url else None

                if not platform_comment_id or platform_comment_id == platform_post_id or platform_comment_id in processed_comment_ids:
                    continue

                processed_comment_ids.add(platform_comment_id)
                timestamp = time_ele.attr('datetime')

                user_name_ele = article.ele('@data-testid=User-Name', timeout=0.1)
                author_display = ""
                author_username = ""
                if user_name_ele:
                    parts = user_name_ele.text.split('\n')
                    if len(parts) >= 2:
                        author_display = parts[0]
                        author_username = parts[1].replace('@', '')

                text_ele = article.ele('@data-testid=tweetText', timeout=0.1)
                text_content = text_ele.text if text_ele else ""
                
                text_content, media_url = self.extract_media(article, text_content)

                reply_ele = article.ele('@data-testid=reply', timeout=0.1)
                repost_ele = article.ele('@data-testid=retweet', timeout=0.1)
                like_ele = article.ele('@data-testid=like', timeout=0.1)

                replies_count = self.parse_number(reply_ele.text if reply_ele else "0")
                shares_count = self.parse_number(repost_ele.text if repost_ele else "0")
                likes_count = self.parse_number(like_ele.text if like_ele else "0")

                self.db.upsert_comment(
                    post_id=db_post_id,
                    platform="X",
                    platform_comment_id=platform_comment_id,
                    author_username=author_username,
                    author_display_name=author_display,
                    text_content=text_content,
                    timestamp_posted=timestamp,
                    likes_count=likes_count,
                    shares_count=shares_count,
                    replies_count=replies_count,
                    media_url=media_url
                )
                
                comments_collected += 1
                if comments_collected % 10 == 0 or comments_collected == max_comments:
                    print(f"  -> [X-SCRAPER] Staženo {comments_collected}/{max_comments} komentářů...")

            if comments_collected >= max_comments:
                break
                
            self.bot.page.scroll.down(600)
            delay(1.5, 2.5)

        print(f"  -> [X-SCRAPER] Hotovo. Celkem staženo {comments_collected} komentářů k tomuto příspěvku.")

    def scrape_profile(self, target_query):
        print(f"[X-SCRAPER] Zahajuji simulaci lidského vyhledávání: '{target_query}'")
        
        explore_btn = self.bot.page.ele('@data-testid=AppTabBar_Explore_Link', timeout=3)
        if explore_btn:
            print("[X-SCRAPER] Klikám na záložku Explore (Lupa)...")
            explore_btn.click()
            delay(2, 4)
        else:
            if "search" not in self.bot.page.url and "explore" not in self.bot.page.url:
                self.bot.open_url(self.bot.base_url + "explore")
                delay(2, 4)

        search_box = self.bot.page.ele('@data-testid=SearchBox_Search_Input', timeout=5)
        
        if search_box:
            print("[X-SCRAPER] Vyhledávací pole nalezeno, simuluji psaní...")
            search_box.click()
            delay(0.5, 1.5)
            
            human_typing(search_box, target_query)
            delay(1, 2)
            
            search_box.input('\n') 
            print("[X-SCRAPER] Potvrzeno, čekám na výsledky...")
            delay(4, 6)
            
            people_tab = self.bot.page.ele("xpath://span[text()='People' or text()='Lidé']", timeout=3)
            if people_tab:
                people_tab.click()
                delay(2, 3)
                
            first_user_cell = self.bot.page.ele('@data-testid=UserCell', timeout=5)
            if first_user_cell:
                print(f"[X-SCRAPER] První profil ve výsledcích nalezen, přecházím na něj.")
                first_user_cell.click()
                delay(3, 5)
            else:
                if " " not in target_query:
                    print("[WARNING] Profil nebyl ve výsledcích nalezen, používám záchrannou Direct URL.")
                    clean_target = target_query.replace('@', '')
                    self.bot.open_url(f"{self.bot.base_url}{clean_target}")
                    delay(3, 5)
                else:
                    print("[ERROR] Vyhledávání nenalezlo výsledky a dotaz obsahuje mezery (nelze použít URL).")
                    return
        else:
            if " " not in target_query:
                print("[WARNING] Vyhledávací pole nenalezeno, používám záchrannou Direct URL.")
                clean_target = target_query.replace('@', '')
                self.bot.open_url(f"{self.bot.base_url}{clean_target}")
                delay(3, 5)
            else:
                print("[ERROR] Vyhledávací pole nenalezeno a dotaz obsahuje mezery (nelze použít URL).")
                return

        current_url = self.bot.page.url
        try:
            actual_username = current_url.split('x.com/')[-1].split('?')[0].split('/')[0]
            print(f"[X-SCRAPER] Skutečný handle účtu identifikován jako: @{actual_username}")
        except:
            actual_username = target_query.replace('@', '').replace(' ', '')
            
        print("[X-SCRAPER] Stahuji data o uživateli...")
        
        display_name_ele = self.bot.page.ele('@data-testid=UserName', timeout=3)
        bio_ele = self.bot.page.ele('@data-testid=UserDescription', timeout=2)
        followers_ele = self.bot.page.ele('xpath://a[contains(@href, "/followers")]/span[1]|//a[contains(@href, "/verified_followers")]/span[1]', timeout=2)
        
        display_name = display_name_ele.text.split('\n')[0] if display_name_ele else actual_username
        bio = bio_ele.text if bio_ele else ""
        followers_text = followers_ele.text if followers_ele else "0"
        followers_count = self.parse_number(followers_text)

        user_id = self.db.upsert_user(
            platform="X",
            username=actual_username,
            display_name=display_name,
            bio=bio,
            followers_count=followers_count
        )
        print(f"[X-SCRAPER] Profil uložen do DB (Sledujících: {followers_count}). Interní ID: {user_id}")

        print("[X-SCRAPER] Prohledávám příspěvky na zdi...")
        
        articles = self.bot.page.eles('tag:article', timeout=5)
        
        if not articles:
            print("[X-SCRAPER] Na profilu nebyly nalezeny žádné příspěvky.")
            return

        posts_to_scrape_comments = []

        for index, article in enumerate(articles[:3]):
            try:
                text_ele = article.ele('@data-testid=tweetText', timeout=1)
                post_text = text_ele.text if text_ele else ""
                
                post_text, media_url = self.extract_media(article, post_text)

                time_ele = article.ele('tag:time', timeout=1)
                if not time_ele:
                    continue 
                
                timestamp = time_ele.attr('datetime') 
                
                link_ele = time_ele.parent('tag:a')
                post_url = link_ele.attr('href') if link_ele else ""
                
                platform_post_id = post_url.split('/')[-1] if post_url else None
                if not platform_post_id:
                    continue

                full_url = f"https://x.com{post_url}" if post_url.startswith('/') else post_url

                reply_ele = article.ele('@data-testid=reply', timeout=0.5)
                repost_ele = article.ele('@data-testid=retweet', timeout=0.5)
                like_ele = article.ele('@data-testid=like', timeout=0.5)

                comments_count = self.parse_number(reply_ele.text if reply_ele else "0")
                shares_count = self.parse_number(repost_ele.text if repost_ele else "0")
                likes_count = self.parse_number(like_ele.text if like_ele else "0")

                db_post_id = self.db.upsert_post(
                    user_id=user_id,
                    platform="X",
                    platform_post_id=platform_post_id,
                    text_content=post_text,
                    timestamp_posted=timestamp,
                    likes_count=likes_count,
                    shares_count=shares_count,
                    comments_count=comments_count,
                    url=full_url,
                    media_url=media_url
                )
                
                print(f"[X-SCRAPER] Uložen příspěvek ID: {platform_post_id} | Lajky: {likes_count}")
                
                posts_to_scrape_comments.append({
                    'db_id': db_post_id,
                    'platform_id': platform_post_id,
                    'url': full_url
                })
                
            except Exception as e:
                print(f"[X-SCRAPER] Skok na další příspěvek kvůli drobné chybě čtení: {e}")

        print("\n[X-SCRAPER] --- FÁZE 2: TĚŽBA KOMENTÁŘŮ ---")
        for post_data in posts_to_scrape_comments:
            self.scrape_comments_for_post(
                db_post_id=post_data['db_id'],
                platform_post_id=post_data['platform_id'],
                post_url=post_data['url'],
                max_comments=50
            )

        print("\n[X-SCRAPER] Kompletní těžba cílového profilu a komentářů byla úspěšně dokončena.")

    def scrape_trending(self):
        print("[X-SCRAPER] Zahajuji plošnou těžbu Trending témat...")
        self.bot.open_url(self.bot.base_url + "explore/tabs/trending")
        delay(3, 5)
        
        trends = self.bot.page.eles('@data-testid=trend', timeout=5)
        
        if not trends:
            print("[X-SCRAPER] Nenalezeny žádné trendy. Pravděpodobně pomalé načtení sítě.")
            return
            
        print(f"[X-SCRAPER] Nalezeno {len(trends)} aktivních trendů. Začínám extrakci...")
        
        for index, trend in enumerate(trends):
            try:
                lines = [line.strip() for line in trend.text.split('\n') if line.strip() and line.strip() not in ['.', '·']]
                
                if not lines:
                    continue
                    
                rank = index + 1
                category = ""
                topic_name = ""
                post_count = ""
                
                if lines and lines[0].isdigit():
                    rank = int(lines.pop(0))
                    
                if lines and ("post" in lines[-1].lower() or "příspěv" in lines[-1].lower()):
                    post_count = lines.pop(-1)
                    
                if len(lines) >= 2:
                    raw_category = lines.pop(0)
                    
                    # --- OČIŠTĚNÍ KATEGORIE ---
                    clean_cat = raw_category
                    
                    # Odstraní formát jako "Politics · Trending"
                    if '·' in clean_cat:
                        clean_cat = clean_cat.split('·')[0].strip()
                        
                    # Odstraní formát jako "Trending in Czechia"
                    if clean_cat.lower().startswith('trending in'):
                        clean_cat = clean_cat[11:].strip()
                        
                    # Pokud zbylo jen samotné slovo "Trending"
                    if clean_cat.lower() == 'trending':
                        clean_cat = 'General'
                        
                    category = clean_cat
                    
                if lines:
                    topic_name = lines[0]
                else:
                    continue 
                        
                self.db.upsert_trend(
                    platform="X",
                    rank=rank,
                    category=category,
                    topic_name=topic_name,
                    post_count=post_count
                )
                print(f"  -> Uloženo: #{rank} [{category}] {topic_name} ({post_count})")
            except Exception as e:
                pass
                
        print("[X-SCRAPER] Těžba globálních trendů byla úspěšně dokončena a uložena do DB.")