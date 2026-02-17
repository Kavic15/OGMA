from src.utils.human_input import delay, human_typing
from src.core.database import DatabaseManager
import re
import time

class InstagramScraper:
    def __init__(self, bot):
        self.bot = bot
        self.db = DatabaseManager()

    def parse_number(self, text):
        if not text: 
            return 0
        text = text.upper().replace(',', '').replace(' ', '').replace('.', '')
        match = re.search(r'([\d\.]+)([KMB]?)', text)
        if not match: 
            return 0
            
        num_str, suffix = match.groups()
        num = float(num_str)
        
        if suffix == 'K': num *= 1000
        elif suffix == 'M': num *= 1000000
        elif suffix == 'B': num *= 1000000000
        
        return int(num)

    def scrape_post_and_comments(self, db_user_id, post_url):
        print(f"\n  -> [IG-SCRAPER] Otevírám příspěvek: {post_url}")
        self.bot.open_url(post_url)
        delay(3, 5)

        platform_post_id = post_url.rstrip('/').split('/')[-1]

        post_text_ele = self.bot.page.ele('xpath://h1[@dir="auto"]', timeout=2)
        post_text = post_text_ele.text if post_text_ele else ""

        media_url = None
        img_ele = self.bot.page.ele('xpath://article//img', timeout=1)
        if img_ele:
            media_url = img_ele.attr('src')
            if not post_text: post_text = "[OBSAHUJE FOTKU]"
        else:
            video_ele = self.bot.page.ele('tag:video', timeout=1)
            if video_ele:
                media_url = video_ele.attr('src')
                if not post_text: post_text = "[OBSAHUJE VIDEO]"

        likes_ele = self.bot.page.ele('xpath://a[contains(@href, "/liked_by/")]//span', timeout=1)
        if not likes_ele:
            likes_ele = self.bot.page.ele('xpath://section//span[contains(text(), "To se mi líbí") or contains(text(), "likes")]', timeout=1)
        likes_count = self.parse_number(likes_ele.text if likes_ele else "0")

        time_ele = self.bot.page.ele('tag:time', timeout=1)
        timestamp = time_ele.attr('datetime') if time_ele else ""

        db_post_id = self.db.upsert_post(
            user_id=db_user_id,
            platform="IG",
            platform_post_id=platform_post_id,
            text_content=post_text,
            timestamp_posted=timestamp,
            likes_count=likes_count,
            shares_count=0, 
            comments_count=0, 
            url=post_url,
            media_url=media_url
        )
        print(f"  -> [IG-SCRAPER] Uložen příspěvek ID: {platform_post_id} | Lajky: {likes_count}")

        print(f"  -> [IG-SCRAPER] Těžím komentáře k tomuto příspěvku...")
        comments_collected = 0
        processed_comment_ids = set()
        max_comments = 50

        # --- JS INJEKCE PRO KOMENTÁŘE (ZACHOVÁNO) ---
        js_extract_comments = """
        function extract() {
            var results = [];
            var times = document.querySelectorAll('time');
            for (var i = 0; i < times.length; i++) {
                var timeEl = times[i];
                var timestamp = timeEl.getAttribute('datetime');
                if (!timestamp) continue;
                
                var block = timeEl;
                for(var j=0; j<8; j++) {
                    if(block.parentElement) block = block.parentElement;
                }
                
                var author = "";
                var links = block.querySelectorAll('a');
                for (var k = 0; k < links.length; k++) {
                    var href = links[k].getAttribute('href');
                    var txt = links[k].innerText.trim();
                    if (href && href.startsWith('/') && txt) {
                        author = txt;
                        break;
                    }
                }
                
                var textContent = "";
                var dirEls = block.querySelectorAll('span[dir="auto"], div[dir="auto"]');
                for (var k = 0; k < dirEls.length; k++) {
                    var txt = dirEls[k].innerText.trim();
                    var ignoreWords = ['Odpovědět', 'Reply', 'Zobrazit překlad', 'See translation', 'Skrýt odpovědi', 'Hide replies'];
                    if (txt && txt !== author && !ignoreWords.includes(txt) && !txt.includes('To se mi líbí') && !txt.includes(' like')) {
                        if (!textContent.includes(txt)) {
                            textContent += txt + " ";
                        }
                    }
                }
                
                var likesStr = "0";
                var allTextEls = block.querySelectorAll('span, div');
                for (var k = 0; k < allTextEls.length; k++) {
                    var txt = allTextEls[k].innerText.trim();
                    if ((txt.includes('To se mi líbí') || txt.includes(' like')) && /\\d/.test(txt)) {
                        likesStr = txt;
                        break;
                    }
                }
                
                results.push({
                    timestamp: timestamp,
                    author: author,
                    text: textContent.trim(),
                    likesStr: likesStr
                });
            }
            return results;
        }
        return extract();
        """

        js_scroll_comments = """
        var times = document.querySelectorAll('time');
        if (times.length > 1) {
            var el = times[times.length - 1]; 
            for (var i = 0; i < 15; i++) {
                if (!el.parentElement || el.tagName === 'BODY' || el.tagName === 'HTML') break;
                el = el.parentElement;
                var style = window.getComputedStyle(el);
                if (style.overflowY === 'auto' || style.overflowY === 'scroll' || style.overflowY === 'hidden') {
                    if (el.scrollHeight > el.clientHeight + 10) {
                        el.scrollTop = el.scrollHeight;
                        return true;
                    }
                }
            }
        }
        var divs = document.querySelectorAll('div, ul');
        for (var i=0; i<divs.length; i++) {
            var style = window.getComputedStyle(divs[i]);
            if ((style.overflowY === 'auto' || style.overflowY === 'scroll') && divs[i].scrollHeight > divs[i].clientHeight) {
                divs[i].scrollTop = divs[i].scrollHeight;
            }
        }
        return false;
        """

        for scroll_attempt in range(12):
            try:
                load_more = self.bot.page.ele('css:svg[aria-label="Načíst další komentáře"], css:svg[aria-label="Load more comments"]', timeout=0.5)
                if load_more:
                    load_more.parent().click(by_js=True)
                    delay(1.5, 2.5)
            except: pass

            extracted_data = self.bot.page.run_js(js_extract_comments)
            
            if extracted_data:
                for data in extracted_data:
                    if comments_collected >= max_comments: break
                    
                    c_timestamp = data.get('timestamp')
                    author_username = data.get('author')
                    c_text = data.get('text')
                    likes_str = data.get('likesStr', "0")
                    
                    if not c_timestamp or c_timestamp == timestamp: continue
                    if not author_username: continue
                        
                    platform_comment_id = f"{platform_post_id}_{author_username}_{c_timestamp}"
                    
                    if platform_comment_id in processed_comment_ids: continue
                    processed_comment_ids.add(platform_comment_id)
                    
                    if not c_text: c_text = "[OBSAHUJE MÉDIA/GIF]"
                    c_likes = self.parse_number(likes_str)
                    
                    self.db.upsert_comment(
                        post_id=db_post_id,
                        platform="IG",
                        platform_comment_id=platform_comment_id,
                        author_username=author_username,
                        author_display_name="",
                        text_content=c_text,
                        timestamp_posted=c_timestamp,
                        likes_count=c_likes,
                        shares_count=0,
                        replies_count=0,
                        media_url=None
                    )
                    comments_collected += 1

            if comments_collected >= max_comments: break
            try:
                self.bot.page.run_js(js_scroll_comments)
            except: pass
            delay(1.5, 2.5)

    def scrape_profile(self, target_query, limit=10):
        """
        Hlavní metoda pro těžbu profilu.
        limit: int -> Počet příspěvků ke stažení. Pokud -1, stahuje vše.
        """
        limit_text = "NEOMEZENO" if limit == -1 else str(limit)
        print(f"[IG-SCRAPER] Zahajuji simulaci lidského vyhledávání: '{target_query}' (Limit: {limit_text})")

        if "instagram.com" not in self.bot.page.url:
            self.bot.open_url(self.bot.base_url)
            delay(2, 4)

        # 1. VYHLEDÁVÁNÍ (Simulace)
        search_icon = self.bot.page.ele('css:svg[aria-label="Hledat"]', timeout=2)
        if not search_icon:
            search_icon = self.bot.page.ele('css:svg[aria-label="Search"]', timeout=2)

        if search_icon:
            print("[IG-SCRAPER] Klikám na záložku Hledání (Lupa)...")
            parent_link = search_icon.parent('tag:a')
            if parent_link:
                parent_link.click(by_js=True)
            else:
                search_icon.click(by_js=True)
            delay(2, 4)

            search_box = self.bot.page.ele('tag:input', timeout=3)
            
            if search_box:
                print("[IG-SCRAPER] Vyhledávací pole nalezeno, simuluji psaní...")
                search_box.click()
                delay(0.5, 1.5)
                
                human_typing(search_box, target_query)
                print("[IG-SCRAPER] Dopsáno, čekám na dynamické výsledky...")
                delay(4, 6)
                
                found_profile = False
                ignore_list = ['explore', 'reels', 'direct', 'stories', 'tags', 'locations', 'p', 'your_activity', 'saved', 'settings', 'accounts', 'language']
                
                current_links = self.bot.page.eles('tag:a', timeout=3)
                for link in current_links:
                    if link.states.is_displayed:
                        href = link.attr('href')
                        if href and (href.startswith('https://www.instagram.com/') or href.startswith('/')):
                            path = href.replace('https://www.instagram.com', '').split('?')[0].strip('/')
                            
                            if path and '/' not in path:
                                if path not in ignore_list and path != self.bot.username:
                                    if link.text.strip():
                                        print(f"[IG-SCRAPER] Nalezen profil (/{path}/), přecházím na něj.")
                                        link.click(by_js=True)
                                        found_profile = True
                                        delay(4, 6)
                                        break 
                
                if not found_profile:
                    print("[WARNING] Profil nenalezen v našeptávači, zkouším Direct URL.")
                    clean_target = target_query.replace('@', '').replace(' ', '')
                    self.bot.open_url(f"{self.bot.base_url}{clean_target}/")
                    delay(4, 6)
            else:
                self.bot.open_url(f"{self.bot.base_url}{target_query.replace('@', '').replace(' ', '')}/")
        else:
            self.bot.open_url(f"{self.bot.base_url}{target_query.replace('@', '').replace(' ', '')}/")
            delay(4, 6)

        # 2. ULOŽENÍ UŽIVATELE
        current_url = self.bot.page.url
        try:
            actual_username = current_url.split('instagram.com/')[-1].split('/')[0].split('?')[0]
        except:
            actual_username = target_query.replace('@', '').replace(' ', '')

        print("[IG-SCRAPER] Stahuji data o uživateli...")
        
        followers_ele = self.bot.page.ele('xpath://a[contains(@href, "/followers")]//span', timeout=3)
        followers_text = followers_ele.attr('title') if (followers_ele and followers_ele.attr('title')) else (followers_ele.text if followers_ele else "0")
        followers_count = self.parse_number(followers_text)

        bio_ele = self.bot.page.ele('xpath://h1[@dir="auto"]', timeout=2)
        bio = bio_ele.text if bio_ele else ""
        
        display_name_ele = self.bot.page.ele('xpath://span[@dir="auto" and contains(@class, "x1")]', timeout=2)
        display_name = display_name_ele.text if display_name_ele else actual_username

        user_id = self.db.upsert_user(
            platform="IG",
            username=actual_username,
            display_name=display_name,
            bio=bio,
            followers_count=followers_count
        )
        print(f"[IG-SCRAPER] Profil uložen do DB (Sledujících: {followers_count}). Interní ID: {user_id}")

        # 3. SBĚR URL PŘÍSPĚVKŮ (RESPEKTUJE LIMIT)
        print("[IG-SCRAPER] Skenuji zeď a sbírám URL příspěvků...")
        
        urls_to_scrape = []
        scroll_attempts_without_new = 0
        
        # Pojistka proti nekonečné smyčce, pokud limit je -1
        max_scroll_loops = 500 if limit == -1 else 100 
        
        loop_counter = 0
        while True:
            # a) Sbírání
            all_links = self.bot.page.eles('tag:a', timeout=2)
            new_found = False
            
            for link in all_links:
                href = link.attr('href')
                if href and ('/p/' in href or '/reel/' in href):
                    clean_href = href.split('?')[0]
                    full_url = f"https://www.instagram.com{clean_href}" if clean_href.startswith('/') else clean_href
                    
                    if full_url not in urls_to_scrape:
                        urls_to_scrape.append(full_url)
                        new_found = True
                        
                        # Kontrola limitu okamžitě po přidání
                        if limit != -1 and len(urls_to_scrape) >= limit:
                            break
            
            print(f"  -> Nalezeno {len(urls_to_scrape)} unikátních příspěvků...")

            # b) Podmínka ukončení (Limit)
            if limit != -1 and len(urls_to_scrape) >= limit:
                print(f"[IG-SCRAPER] Dosažen požadovaný limit {limit}.")
                break
            
            # c) Podmínka ukončení (Konec stránky)
            if not new_found:
                scroll_attempts_without_new += 1
                if scroll_attempts_without_new >= 4:
                    print("[IG-SCRAPER] Zdá se, že jsme na konci profilu (žádné nové příspěvky).")
                    break
            else:
                scroll_attempts_without_new = 0

            # d) Bezpečnostní pojistka
            loop_counter += 1
            if limit == -1 and loop_counter > max_scroll_loops:
                print("[WARNING] Dosažen interní bezpečnostní limit scrollu.")
                break

            # e) Scroll
            self.bot.page.scroll.down(800)
            delay(1.5, 3.0)

        # 4. ITERACE A TĚŽBA DETAILŮ
        final_urls = urls_to_scrape[:limit] if limit != -1 else urls_to_scrape
        
        if not final_urls:
            print("[IG-SCRAPER] Nebyly nalezeny žádné příspěvky (profil je soukromý nebo prázdný).")
            return

        print(f"\n[IG-SCRAPER] Zahajuji hloubkovou těžbu {len(final_urls)} příspěvků...")
        for i, url in enumerate(final_urls):
            print(f"--- Zpracovávám {i+1} z {len(final_urls)} ---")
            try:
                self.scrape_post_and_comments(user_id, url)
            except Exception as e:
                print(f"[IG-SCRAPER] Chyba při těžbě příspěvku {url}: {e}")

        print("\n[IG-SCRAPER] Kompletní těžba cílového IG profilu a komentářů byla úspěšně dokončena.")