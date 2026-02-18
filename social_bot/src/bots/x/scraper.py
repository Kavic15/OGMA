from src.utils.human_input import delay, human_typing
from src.core.database import DatabaseManager
import re
import time

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
        # ULTRA-FAST CHECK: Timeout 0.05
        try:
            photo_ele = article.ele('@data-testid=tweetPhoto', timeout=0.05)
            video_ele = article.ele('@data-testid=videoPlayer', timeout=0.05)
            
            if photo_ele:
                img_ele = photo_ele.ele('tag:img', timeout=0.05)
                if img_ele:
                    media_url = img_ele.attr('src')
                if not current_text.strip():
                    current_text = "[OBSAHUJE FOTKU]"
            elif video_ele:
                if not current_text.strip():
                    current_text = "[OBSAHUJE VIDEO]"
        except:
            pass
                
        return current_text, media_url

    def scrape_comments_for_post(self, db_post_id, platform_post_id, post_url, max_comments=20):
        print(f"  -> [X-SCRAPER] Těžím komentáře: {post_url}")
        
        try:
            self.bot.page.get(post_url)
            # Čekáme na načtení tweetu - pokud se nenačte do 4s, jdeme dál
            if not self.bot.page.ele('@data-testid=tweetText', timeout=4):
                print("  -> [WARNING] Tweet se nenačetl nebo byl smazán.")
                return
        except Exception as e:
            print(f"  -> [ERROR] Chyba navigace: {e}")
            return

        delay(0.5, 1.0)

        comments_collected = 0
        processed_comment_ids = set()
        
        for scroll_attempt in range(6): 
            if comments_collected >= max_comments: break

            articles = self.bot.page.eles('tag:article', timeout=0.5)
            
            for article in articles:
                if comments_collected >= max_comments: break

                try:
                    time_ele = article.ele('tag:time', timeout=0.05)
                    if not time_ele: continue
                    
                    link_ele = time_ele.parent('tag:a')
                    if not link_ele: continue
                    
                    raw_href = link_ele.attr('href')
                    if not raw_href: continue

                    platform_comment_id = raw_href.split('/')[-1]

                    if not platform_comment_id or platform_comment_id == platform_post_id or platform_comment_id in processed_comment_ids:
                        continue

                    processed_comment_ids.add(platform_comment_id)
                    timestamp = time_ele.attr('datetime')

                    user_name_ele = article.ele('@data-testid=User-Name', timeout=0.05)
                    author_display = ""
                    author_username = ""
                    if user_name_ele:
                        parts = user_name_ele.text.split('\n')
                        if len(parts) >= 2:
                            author_display = parts[0]
                            author_username = parts[1].replace('@', '')

                    text_ele = article.ele('@data-testid=tweetText', timeout=0.05)
                    text_content = text_ele.text if text_ele else ""
                    text_content, media_url = self.extract_media(article, text_content)

                    likes_count = 0
                    try:
                        like_ele = article.ele('@data-testid=like', timeout=0.01)
                        if like_ele: likes_count = self.parse_number(like_ele.text)
                    except: pass

                    self.db.upsert_comment(
                        post_id=db_post_id,
                        platform="X",
                        platform_comment_id=platform_comment_id,
                        author_username=author_username,
                        author_display_name=author_display,
                        text_content=text_content,
                        timestamp_posted=timestamp,
                        likes_count=likes_count,
                        shares_count=0,
                        replies_count=0,
                        media_url=media_url
                    )
                    comments_collected += 1
                except:
                    continue

            self.bot.page.scroll.down(700)
            delay(0.5, 0.8)

    # --- NOVÁ METODA: GOOGLE FALLBACK ---
    def _google_search_fallback(self, target_query):
        print(f"[GOOGLE] Spouštím záchranné vyhledávání pro: '{target_query}'")
        try:
            self.bot.open_url("https://www.google.com")
            
            cookie_btns = ['Přijmout vše', 'Accept all', 'Souhlasím', 'I agree']
            self.bot.handle_popups(cookie_btns)
            
            search_input = self.bot.page.ele('tag:textarea@name=q', timeout=2) or self.bot.page.ele('tag:input@name=q', timeout=2)
            
            if search_input:
                query = f"{target_query} twitter"
                search_input.input(query)
                delay(0.5)
                self.bot.page.actions.type_key('ENTER')
                
                print("[GOOGLE] Čekám na výsledky...")
                delay(2, 3)
                
                results = self.bot.page.eles('tag:a', timeout=3)
                for res in results:
                    href = res.attr('href')
                    if href and ("twitter.com/" in href or "x.com/" in href) and "status" not in href and "search" not in href:
                        print(f"[GOOGLE] Nalezen profil: {href}")
                        res.click()
                        delay(3, 5) # Čekání na načtení X
                        return True
            
            print("[GOOGLE] Nepodařilo se najít relevantní X profil.")
            return False
            
        except Exception as e:
            print(f"[GOOGLE ERROR] {e}")
            return False

    def scrape_profile(self, target_query, limit=10):
        limit_text = "NEOMEZENO" if limit == -1 else str(limit)
        print(f"[X-SCRAPER] Cíl: '{target_query}' (Limit: {limit_text})")
        
        # 1. KROK: KONTROLA DATABÁZE (CACHE)
        print("[X-SCRAPER] 1. Krok: Kontrola lokální databáze...")
        known_handle = self.db.get_known_handle(target_query)
        profile_found = False
        
        if known_handle:
            print(f"[DATABASE] Nalezen uložený handle: @{known_handle}. Jdu na jistotu.")
            self.bot.open_url(f"{self.bot.base_url}{known_handle}")
            delay(2, 4)
            if self.bot.page.ele('@data-testid=UserName', timeout=5):
                profile_found = True
            else:
                print("[WARNING] Uložený handle nefunguje, zkusím vyhledávání.")
        
        # 2. KROK: X SEARCH (EXPLORE)
        if not profile_found:
            print("[X-SCRAPER] 2. Krok: Interní vyhledávání na X...")
            if "search" not in self.bot.page.url and "explore" not in self.bot.page.url:
                self.bot.open_url(self.bot.base_url + "explore")
                delay(1.5, 2.5)

            search_box = self.bot.page.ele('@data-testid=SearchBox_Search_Input', timeout=5)
            if search_box:
                search_box.click()
                search_box.clear()
                human_typing(search_box, target_query)
                delay(0.5)
                search_box.input('\n')
                
                people_tab = self.bot.page.ele("xpath://span[text()='People' or text()='Lidé']", timeout=4)
                if people_tab:
                    people_tab.click()
                    delay(1.5, 3)
                
                first_user = self.bot.page.ele('@data-testid=UserCell', timeout=4)
                if first_user:
                    print("[X-SCRAPER] Profil nalezen v interním hledání. Klikám.")
                    first_user.click()
                    if self.bot.page.wait.ele_displayed('@data-testid=UserName', timeout=6):
                        profile_found = True
            
        # 3. KROK: GOOGLE FALLBACK
        if not profile_found:
            print("[X-SCRAPER] 3. Krok: Interní hledání selhalo. Volám Google Search...")
            if self._google_search_fallback(target_query):
                if self.bot.page.wait.ele_displayed('@data-testid=UserName', timeout=8):
                    profile_found = True
                else:
                    print("[ERROR] Google odkaz otevřen, ale profil se nenačetl.")
            else:
                print(f"[ERROR] Ani Google nenašel profil pro '{target_query}'. Přeskakuji.")
                return

        # 4. TĚŽBA DAT PROFILU
        delay(1, 2)
        current_url = self.bot.page.url
        try:
            if "x.com/" in current_url:
                actual_username = current_url.split('x.com/')[-1].split('?')[0].split('/')[0]
            else:
                actual_username = target_query.replace('@', '').replace(' ', '')
        except:
            actual_username = target_query.replace('@', '').replace(' ', '')

        print(f"[X-SCRAPER] Jsem na profilu: @{actual_username}")
        
        # --- TĚŽBA METADAT (NOVÉ) ---
        try:
            # Display Name + Verifikace
            display_name_ele = self.bot.page.ele('@data-testid=UserName', timeout=3)
            if display_name_ele:
                display_name = display_name_ele.text.split('\n')[0]
                # Kontrola modré fajfky
                is_verified = 1 if display_name_ele.ele('tag:svg@aria-label=Verified account', timeout=0.1) else 0
            else:
                display_name = actual_username
                is_verified = 0

            # Bio
            bio_ele = self.bot.page.ele('@data-testid=UserDescription', timeout=2)
            bio = bio_ele.text if bio_ele else ""
            
            # Location (Lokace)
            loc_ele = self.bot.page.ele('@data-testid=UserLocation', timeout=1)
            location = loc_ele.text if loc_ele else None

            # Website (Link in Bio)
            web_ele = self.bot.page.ele('@data-testid=UserUrl', timeout=1)
            website = web_ele.text if web_ele else None

            # Joined Date (Datum registrace)
            join_ele = self.bot.page.ele('@data-testid=UserJoinDate', timeout=1)
            joined_date = join_ele.text if join_ele else None

            # Followers (Sledující)
            followers_ele = self.bot.page.ele('xpath://a[contains(@href, "/followers")]/span[1]|//a[contains(@href, "/verified_followers")]/span[1]', timeout=2)
            followers_text = followers_ele.text if followers_ele else "0"
            followers_count = self.parse_number(followers_text)

            # Following (Sledovaní) - NOVÉ
            following_ele = self.bot.page.ele('xpath://a[contains(@href, "/following")]/span[1]', timeout=2)
            following_text = following_ele.text if following_ele else "0"
            following_count = self.parse_number(following_text)

            # Banner (Hlavička) - NOVÉ
            banner_url = None
            try:
                banner_link = self.bot.page.ele('xpath://a[contains(@href, "/header_photo")]//img', timeout=1)
                if banner_link: banner_url = banner_link.attr('src')
            except: pass

            # Profile Pic (Zachováno)
            profile_pic_url = None
            try:
                avatar_img = self.bot.page.ele('css:img[alt="Opens profile photo"]', timeout=1)
                if not avatar_img: avatar_img = self.bot.page.ele('css:img[alt="Square profile picture and Opens profile photo"]', timeout=1)
                if not avatar_img: avatar_img = self.bot.page.ele('xpath://div[contains(@data-testid, "UserAvatar-Container")]//img', timeout=1)
                
                if avatar_img:
                    initial_url = avatar_img.attr('src')
                    profile_pic_url = initial_url 
                    # HD logika (zkrácená)
                    if initial_url and any(x in initial_url for x in ['_bigger', '_mini', '_normal']):
                        photo_link = self.bot.page.ele('xpath://div[contains(@data-testid, "UserAvatar-Container")]//a[contains(@href, "/photo")]', timeout=2)
                        if photo_link:
                            photo_link.click()
                            large_img = self.bot.page.ele('xpath://div[@data-testid="swipe-to-dismiss"]//img', timeout=3)
                            if large_img: profile_pic_url = large_img.attr('src')
                            close_btn = self.bot.page.ele('css:div[aria-label="Close"]', timeout=1) or self.bot.page.ele('css:div[aria-label="Zavřít"]', timeout=1)
                            if close_btn: close_btn.click()
                            else: self.bot.page.back()
                            delay(0.5)
            except: pass

        except Exception as e:
            print(f"[ERROR] Chyba čtení metadat: {e}")
            display_name = actual_username; bio = ""; followers_count = 0; following_count = 0
            location = None; website = None; joined_date = None; is_verified = 0; banner_url = None; profile_pic_url = None

        # Uložení do DB s novými poli
        user_id = self.db.upsert_user(
            platform="X", 
            username=actual_username, 
            display_name=display_name, 
            bio=bio, 
            followers_count=followers_count, 
            following_count=following_count, # NOVÉ
            joined_date=joined_date,         # NOVÉ
            location=location,               # NOVÉ
            website=website,                 # NOVÉ
            is_verified=is_verified,         # NOVÉ
            profile_pic_url=profile_pic_url,
            banner_url=banner_url            # NOVÉ
        )
        print(f"[X-SCRAPER] Uživatel @{actual_username} uložen. (Verifikace: {is_verified})")

        # 5. TĚŽBA PŘÍSPĚVKŮ
        print("[X-SCRAPER] Sbírám příspěvky...")
        posts_collected = 0
        processed_post_ids = set()
        posts_to_scrape_comments = [] 
        
        while True:
            if limit != -1 and posts_collected >= limit: break
            articles = self.bot.page.eles('tag:article', timeout=1.5)
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
                    text_ele = article.ele('@data-testid=tweetText', timeout=0.05)
                    post_text = text_ele.text if text_ele else ""
                    post_text, media_url = self.extract_media(article, post_text)
                    timestamp = time_ele.attr('datetime')
                    likes, shares, comments = 0, 0, 0
                    try:
                        re_el = article.ele('@data-testid=reply', timeout=0.01)
                        if re_el: comments = self.parse_number(re_el.text)
                        rt_el = article.ele('@data-testid=retweet', timeout=0.01)
                        if rt_el: shares = self.parse_number(rt_el.text)
                        li_el = article.ele('@data-testid=like', timeout=0.01)
                        if li_el: likes = self.parse_number(li_el.text)
                    except: pass

                    db_post_id = self.db.upsert_post(user_id, "X", platform_post_id, post_text, timestamp, likes, shares, comments, full_url, media_url)
                    posts_collected += 1
                    print(f"[X-SCRAPER] ({posts_collected}) Tweet ID: {platform_post_id}")
                    posts_to_scrape_comments.append({'db_id': db_post_id, 'platform_id': platform_post_id, 'url': full_url})
                except: pass

            if not new_in_batch:
                self.bot.page.scroll.down(300)
                delay(1)
            self.bot.page.scroll.down(600)
            delay(0.8, 1.2)

        # 6. KOMENTÁŘE
        if posts_to_scrape_comments:
            count = len(posts_to_scrape_comments)
            print(f"\n[X-SCRAPER] --- FÁZE 2: KOMENTÁŘE ({count} příspěvků) ---")
            for i, post_data in enumerate(posts_to_scrape_comments):
                print(f"[X-SCRAPER] Komentáře {i+1}/{count}...")
                try:
                    self.scrape_comments_for_post(post_data['db_id'], post_data['platform_id'], post_data['url'], 20)
                except Exception as e:
                    print(f"[ERROR] Chyba u komentářů: {e}")

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