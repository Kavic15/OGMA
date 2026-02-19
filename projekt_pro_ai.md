## Soubor: requirements.txt
```txt
DrissionPage
customtkinter
keyboard
pillow
requests
```

## Soubor: social_bot\main.py
```py
from src.gui.app import App

if __name__ == "__main__":
    try:
        app = App()
        app.update()
        app.mainloop()
    except KeyboardInterrupt:
        print("\n[INFO] Aplikace byla ukončena uživatelem (CTRL+C).")
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Aplikace spadla: {e}")
        
```

## Soubor: social_bot\src\bots\instagram\auth.py
```py
from src.utils.human_input import delay

class InstagramAuthenticator:
    def __init__(self, bot):
        self.bot = bot

    def login(self):
        self.bot.open_url(self.bot.base_url)
        
        print("[IG] Kontroluji stav přihlášení...")
        # 1. RYCHLÁ KONTROLA SESSION (přesunuto na začátek pro okamžité přeskočení)
        if self.bot.page.ele('css:svg[aria-label="Domů"]', timeout=3) or self.bot.page.ele('css:svg[aria-label="Home"]', timeout=3):
            print("[IG] Již přihlášeno (ze session). Přeskakuji login a cookies.")
            return

        # 2. LIKVIDACE COOKIES (Spustí se jen u prvního přihlášení)
        print("[IG] Kontroluji Cookies okna...")
        cookie_keywords = ['Povolit', 'Odmítnout', 'Allow', 'Decline']
        for word in cookie_keywords:
            # Rychlé hledání prvního tlačítka (timeout 0.5s místo dlouhého čekání)
            btn = self.bot.page.ele(f'text:{word}', timeout=0.5)
            if btn and btn.states.is_displayed:
                try:
                    btn.click(by_js=True)
                    print(f"[IG] Odkliknuto cookie tlačítko: '{word}'")
                    delay(1.5)
                    break
                except:
                    pass

        # 3. HLEDÁNÍ PŘIHLÁŠOVACÍHO FORMULÁŘE
        all_login_inputs = self.bot.page.eles('@name=email') + self.bot.page.eles('@name=username')
        all_pass_inputs = self.bot.page.eles('@name=pass') + self.bot.page.eles('@name=password')
        
        login_input = None
        for inp in all_login_inputs:
            if inp.states.is_displayed:
                login_input = inp
                break
                
        pass_input = None
        for inp in all_pass_inputs:
            if inp.states.is_displayed:
                pass_input = inp
                break

        if not login_input:
            print("[IG] Nevidím viditelný login formulář, ale ani znaky přihlášení.")
            return

        # 4. SAMOTNÝ LOGIN
        print("[IG] Zadávám přihlašovací údaje...")
        login_input.input(self.bot.username)
        delay(0.5, 1)
        
        if pass_input:
            pass_input.input(self.bot.password)
        delay(1, 2)
        
        submit_btn = self.bot.page.ele('@type=submit', timeout=2)
        if submit_btn and submit_btn.states.is_displayed:
            submit_btn.click(by_js=True)
        else:
            login_btns = self.bot.page.eles('text:Přihlásit') + self.bot.page.eles('text:Log in')
            for btn in login_btns:
                if btn.states.is_displayed:
                    btn.click(by_js=True)
                    break
            
        delay(5, 8)
        
        # 5. ÚKLID PO PŘIHLÁŠENÍ
        print("[IG] Provádím úklid po přihlášení...")
        self.bot.handle_popups(['Nyní ne', 'Not Now', 'Uložit', 'Save'])
        print("[IG] Přihlašovací proces dokončen.")
```

## Soubor: social_bot\src\bots\instagram\bot.py
```py
from src.core.base_bot import BaseBot
from .auth import InstagramAuthenticator
from .scraper import InstagramScraper

class InstagramBot(BaseBot):
    def __init__(self, username, password, user_id="default"):
        super().__init__(user_id=user_id, platform="ig") 
        self.username = username
        self.password = password
        
        # DOPLNĚNA CHYBĚJÍCÍ BASE URL
        self.base_url = "https://www.instagram.com/"
        
        self.auth = InstagramAuthenticator(self)
        self.scraper = InstagramScraper(self)

    def login(self):
        self.auth.login()
```

## Soubor: social_bot\src\bots\instagram\scraper.py
```py
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
```

## Soubor: social_bot\src\bots\x\auth.py
```py
from src.utils.human_input import delay

class XAuthenticator:
    def __init__(self, bot):
        self.bot = bot
        self.base_url = "https://x.com/"

    def login(self):
        print("[X] Kontroluji session na hlavní stránce...")
        
        self.bot.page.get(self.base_url)
        delay(4, 6) 

        is_logged_in = False
        if self.bot.page.ele('@aria-label:Timeline: Your Home Timeline', timeout=5):
            is_logged_in = True
        elif self.bot.page.ele('@aria-label:Profile', timeout=2):
             is_logged_in = True
        elif "/home" in self.bot.page.url:
             is_logged_in = True

        if is_logged_in:
            print("[X] Úspěšně ověřeno: Již přihlášeno (ze session).")
            return
        
        print("[X] Session nenalezena, jdu se přihlásit...")
        self.bot.page.get(self.base_url + "i/flow/login")
        delay(3)
        
        if self.bot.page.ele('@autocomplete=username', timeout=10):
            print("[X] Zadávám uživatelské jméno...")
            self.bot.page.ele('@autocomplete=username').input(self.bot.username)
            delay(1, 2)
            
            next_xpath = "xpath://span[text()='Next' or text()='Další']"
            self.bot.click_smart(next_xpath, "Tlačítko Další")
            delay(2, 3)

        if self.bot.page.ele('@name=password', timeout=10):
            print("[X] Zadávám heslo...")
            self.bot.page.ele('@name=password').input(self.bot.password)
            delay(1, 2)
            
            login_xpath = "xpath://span[text()='Log in' or text()='Přihlásit se']"
            self.bot.click_smart(login_xpath, "Tlačítko Login")
            delay(5, 8)
            
            self.bot.handle_popups(['Refuse', 'Odmítnout', 'Accept all', 'Povolit'])
            
            print("[X] Přihlášení dokončeno, ukládám session...")
            delay(3)
```

## Soubor: social_bot\src\bots\x\bot.py
```py
from src.core.base_bot import BaseBot
from .auth import XAuthenticator
from .scraper import XScraper

class XBot(BaseBot):
    def __init__(self, username, password, user_id="default"):
        super().__init__(user_id=user_id, platform="x")
        self.username = username
        self.password = password
        
        # CHYBĚJÍCÍ PROMĚNNÁ DOPLNĚNA
        self.base_url = "https://x.com/" 
        
        self.auth = XAuthenticator(self)
        self.scraper = XScraper(self)

    def login(self):
        self.auth.login()
```

## Soubor: social_bot\src\bots\x\scraper.py
```py
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
```

## Soubor: social_bot\src\bots\x\modules\comments.py
```py
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
```

## Soubor: social_bot\src\bots\x\modules\posts.py
```py
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
```

## Soubor: social_bot\src\bots\x\modules\profile.py
```py
from src.utils.human_input import delay
from .utils import XUtils

class XProfileModule:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    def scrape_metadata(self, actual_username):
        """Vytěží bio, followers, location, web, datum registrace atd."""
        print(f"[X-PROFILE] Těžím metadata pro @{actual_username}...")
        
        try:
            # Display Name + Verifikace
            display_name_ele = self.bot.page.ele('@data-testid=UserName', timeout=3)
            if display_name_ele:
                display_name = display_name_ele.text.split('\n')[0]
                is_verified = 1 if display_name_ele.ele('tag:svg@aria-label=Verified account', timeout=0.1) else 0
            else:
                display_name = actual_username
                is_verified = 0

            # Bio
            bio_ele = self.bot.page.ele('@data-testid=UserDescription', timeout=2)
            bio = bio_ele.text if bio_ele else ""
            
            # Location
            loc_ele = self.bot.page.ele('@data-testid=UserLocation', timeout=1)
            location = loc_ele.text if loc_ele else None

            # Website
            web_ele = self.bot.page.ele('@data-testid=UserUrl', timeout=1)
            website = web_ele.text if web_ele else None

            # Joined Date
            join_ele = self.bot.page.ele('@data-testid=UserJoinDate', timeout=1)
            joined_date = join_ele.text if join_ele else None

            # Followers
            followers_ele = self.bot.page.ele('xpath://a[contains(@href, "/followers")]/span[1]|//a[contains(@href, "/verified_followers")]/span[1]', timeout=2)
            followers_count = XUtils.parse_number(followers_ele.text if followers_ele else "0")

            # Following
            following_ele = self.bot.page.ele('xpath://a[contains(@href, "/following")]/span[1]', timeout=2)
            following_count = XUtils.parse_number(following_ele.text if following_ele else "0")

            # Banner
            banner_url = None
            try:
                banner_link = self.bot.page.ele('xpath://a[contains(@href, "/header_photo")]//img', timeout=1)
                if banner_link: banner_url = banner_link.attr('src')
            except: pass

            # Profile Pic (s HD logikou)
            profile_pic_url = self._get_hd_profile_pic()

        except Exception as e:
            print(f"[ERROR] Chyba čtení metadat: {e}")
            # Fallback hodnoty
            display_name = actual_username; bio = ""; followers_count = 0; following_count = 0
            location = None; website = None; joined_date = None; is_verified = 0; banner_url = None; profile_pic_url = None

        # Uložení do DB
        user_id = self.db.upsert_user(
            platform="X", 
            username=actual_username, 
            display_name=display_name, 
            bio=bio, 
            followers_count=followers_count, 
            following_count=following_count,
            joined_date=joined_date,
            location=location,
            website=website,
            is_verified=is_verified,
            profile_pic_url=profile_pic_url,
            banner_url=banner_url
        )
        print(f"[X-PROFILE] Uloženo. Verifikace: {is_verified} | Lokace: {location}")
        return user_id

    def _get_hd_profile_pic(self):
        profile_pic_url = None
        try:
            avatar_img = self.bot.page.ele('css:img[alt="Opens profile photo"]', timeout=1)
            if not avatar_img: avatar_img = self.bot.page.ele('css:img[alt="Square profile picture and Opens profile photo"]', timeout=1)
            if not avatar_img: avatar_img = self.bot.page.ele('xpath://div[contains(@data-testid, "UserAvatar-Container")]//img', timeout=1)
            
            if avatar_img:
                profile_pic_url = avatar_img.attr('src')
                # Pokus o HD verzi
                if profile_pic_url and any(x in profile_pic_url for x in ['_bigger', '_mini', '_normal']):
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
        return profile_pic_url
```

## Soubor: social_bot\src\bots\x\modules\search.py
```py
from src.utils.human_input import delay, human_typing

class XSearchModule:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    def find_profile(self, target_query):
        """Řídí celý proces hledání profilu."""
        
        # 1. KROK: KONTROLA DATABÁZE (CACHE)
        print("[X-SEARCH] 1. Krok: Kontrola lokální databáze...")
        known_handle = self.db.get_known_handle(target_query)
        if known_handle:
            print(f"[DATABASE] Nalezen uložený handle: @{known_handle}. Jdu na jistotu.")
            self.bot.open_url(f"{self.bot.base_url}{known_handle}")
            delay(2, 4)
            if self.bot.page.ele('@data-testid=UserName', timeout=5):
                return True
        
        # 2. KROK: X SEARCH (EXPLORE)
        print("[X-SEARCH] 2. Krok: Interní vyhledávání na X...")
        if self._internal_search(target_query):
            return True
            
        # 3. KROK: GOOGLE FALLBACK
        print("[X-SEARCH] 3. Krok: Interní hledání selhalo. Volám Google Search...")
        if self._google_search_fallback(target_query):
            if self.bot.page.wait.ele_displayed('@data-testid=UserName', timeout=8):
                return True
        
        return False

    def _internal_search(self, target_query):
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
                print("[X-SEARCH] Profil nalezen v interním hledání. Klikám.")
                first_user.click()
                if self.bot.page.wait.ele_displayed('@data-testid=UserName', timeout=6):
                    return True
        return False

    def _google_search_fallback(self, target_query):
        print(f"[GOOGLE] Spouštím záchranné vyhledávání pro: '{target_query}'")
        try:
            self.bot.open_url("https://www.google.com")
            self.bot.handle_popups(['Přijmout vše', 'Accept all', 'Souhlasím', 'I agree'])
            
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
                        delay(3, 5)
                        return True
            return False
        except Exception as e:
            print(f"[GOOGLE ERROR] {e}")
            return False
```

## Soubor: social_bot\src\bots\x\modules\utils.py
```py
import re

class XUtils:
    @staticmethod
    def parse_number(text):
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

    @staticmethod
    def extract_media(article, current_text):
        """Vrátí tuple (updated_text, media_url, is_video)"""
        media_url = None
        is_video = False
        
        try:
            # Foto
            photo_ele = article.ele('@data-testid=tweetPhoto', timeout=0.05)
            # Video
            video_ele = article.ele('@data-testid=videoPlayer', timeout=0.05)
            
            if photo_ele:
                img_ele = photo_ele.ele('tag:img', timeout=0.05)
                if img_ele:
                    media_url = img_ele.attr('src')
                if not current_text.strip():
                    current_text = "[OBSAHUJE FOTKU]"
                    
            elif video_ele:
                is_video = True
                # Zkusíme získat alespoň poster (thumbnail)
                poster_video = video_ele.ele('tag:video', timeout=0.05)
                if poster_video:
                    media_url = poster_video.attr('poster')
                
                if not current_text.strip():
                    current_text = "[OBSAHUJE VIDEO]"
                    
        except:
            pass
                
        return current_text, media_url, is_video
```

## Soubor: social_bot\src\core\base_bot.py
```py
from DrissionPage import ChromiumPage, ChromiumOptions
from src.utils.human_input import delay
import os
from pathlib import Path

class BaseBot:
    def __init__(self, headless=False, user_id="default", platform="general"):
        self.user_id = str(user_id)
        self.platform = platform
        self.page = self._setup_driver(headless)

    def _setup_driver(self, headless):
        co = ChromiumOptions()
        
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        
        profile_folder = f"{self.user_id}_{self.platform}"
        profile_path = project_root / 'profiles' / profile_folder
        os.makedirs(profile_path, exist_ok=True)
        
        print(f"[BOT] Nastavuji izolovaný profil: {profile_path}")
        
        browser_path = project_root / 'browser' / 'chrome.exe'
        if browser_path.exists():
            co.set_paths(browser_path=str(browser_path))
        
        co.set_user_data_path(str(profile_path))
        co.set_local_port(9333) 

        if headless:
            co.headless(True)
        
        # ZMĚNA: Pouze zajistíme start na primárním monitoru.
        co.set_argument('--window-position=0,0') 
        # (Argument --start-maximized byl odstraněn, vyvolával konflikt v Chromiu)

        co.set_argument('--no-first-run')
        co.set_argument('--no-default-browser-check') 
        co.set_argument('--restore-last-session')

        try:
            page = ChromiumPage(co)
            # ZMĚNA: Nativní spolehlivá maximalizace okna pomocí DrissionPage
            page.set.window.max() 
            
            # Poznámka: Pokud jsi myslel "absolutní fullscreen" bez hlavního panelu Windows (jako po stisku F11), 
            # nahraď řádek výše tímto: page.set.window.full()
            
            return page
            
        except Exception as e:
            print(f"[CRITICAL ERROR] Nelze spustit prohlížeč: {e}")
            raise e

    def open_url(self, url):
        print(f"[BOT] Otevírám {url}")
        try:
            self.page.get(url)
            delay(3, 5)
        except Exception as e:
            print(f"[ERROR] Chyba při otevírání URL: {e}")

    def find_element_smart(self, selector, description="prvek", timeout=10):
        try:
            return self.page.ele(selector, timeout=timeout)
        except:
            return None

    def click_smart(self, selector, description="tlačítko", timeout=5):
        ele = self.find_element_smart(selector, description, timeout)
        if ele:
            try:
                ele.click()
                return True
            except:
                try:
                    ele.click(by_js=True)
                    return True
                except:
                    pass
        return False
        
    def handle_popups(self, triggers):
        for text in triggers:
            ele = self.page.ele(f'text:{text}', timeout=0.5)
            if ele:
                try:
                    ele.click()
                    print(f"[BOT] Odkliknuto vyskakovací okno: '{text}'")
                    delay(1)
                    return True
                except:
                    try:
                        ele.click(by_js=True)
                        return True
                    except:
                        pass
        return False

    def close(self):
        # POJISTKA: Pokud už je stránka zavřená, nedělej nic
        if getattr(self, 'page', None) is None:
            return
            
        print(f"[BOT] Ukládám profil {self.user_id}_{self.platform} a zavírám...")
        try:
            self.page.quit() 
            self.page = None # Vynulujeme objekt, abychom nezavírali dvakrát
            print("[BOT] Uloženo.")
        except Exception:
            pass # Ignorujeme chyby, pokud už uživatel prohlížeč zavřel křížkem
```

## Soubor: social_bot\src\core\database.py
```py
import sqlite3
import os
import uuid
from pathlib import Path
from datetime import datetime, timezone

import sqlite3
import os
import uuid
from pathlib import Path
from datetime import datetime, timezone

class DatabaseManager:
    def __init__(self, db_name="osint.db"):
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        self.data_dir = project_root / 'data'
        
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.db_path = self.data_dir / db_name
        self.conn = None
        self.cursor = None
        
        self._connect()
        self._create_tables()
        self._migrate_db() # Důležité: Přidá nové sloupce do existující DB

    def _connect(self):
        self.conn = sqlite3.connect(str(self.db_path), timeout=10) 
        self.cursor = self.conn.cursor()

    def _create_tables(self):
        # TABULKA USERS - Rozšířená o metadata
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                platform_user_id TEXT,
                username TEXT NOT NULL,
                display_name TEXT,
                bio TEXT,
                followers_count INTEGER,
                following_count INTEGER,       -- NOVÉ
                joined_date TEXT,              -- NOVÉ
                location TEXT,                 -- NOVÉ
                website TEXT,                  -- NOVÉ
                is_verified INTEGER DEFAULT 0, -- NOVÉ (Bonus)
                profile_pic_url TEXT, 
                banner_url TEXT,               -- NOVÉ (Bonus)
                last_scraped TIMESTAMP,
                UNIQUE(platform, username)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                platform_post_id TEXT NOT NULL,
                text_content TEXT,
                media_url TEXT,
                timestamp_posted TIMESTAMP,
                likes_count INTEGER DEFAULT 0,
                shares_count INTEGER DEFAULT 0,
                comments_count INTEGER DEFAULT 0,
                url TEXT,
                scraped_at TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id),
                UNIQUE(platform_post_id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS comments (
                id TEXT PRIMARY KEY,
                post_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                platform_comment_id TEXT NOT NULL,
                author_username TEXT,
                author_display_name TEXT,
                text_content TEXT,
                media_url TEXT,
                timestamp_posted TIMESTAMP,
                likes_count INTEGER DEFAULT 0,
                shares_count INTEGER DEFAULT 0,
                replies_count INTEGER DEFAULT 0,
                scraped_at TIMESTAMP,
                FOREIGN KEY(post_id) REFERENCES posts(id),
                UNIQUE(platform_comment_id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS trending (
                id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                rank INTEGER,
                category TEXT,
                topic_name TEXT NOT NULL,
                post_count TEXT,
                scraped_at TIMESTAMP,
                UNIQUE(platform, topic_name)
            )
        ''')
        
        self.conn.commit()

    def _migrate_db(self):
        """Zkontroluje a přidá chybějící sloupce."""
        required_columns = {
            "following_count": "INTEGER",
            "joined_date": "TEXT",
            "location": "TEXT",
            "website": "TEXT",
            "is_verified": "INTEGER DEFAULT 0",
            "banner_url": "TEXT",
            "profile_pic_url": "TEXT"
        }

        try:
            self.cursor.execute("PRAGMA table_info(users)")
            existing = [row[1] for row in self.cursor.fetchall()]

            for col, type_ in required_columns.items():
                if col not in existing:
                    print(f"[DB] Migrace: Přidávám sloupec '{col}'...")
                    try: self.cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {type_}")
                    except: pass
            self.conn.commit()
        except Exception as e:
            print(f"[DB ERROR] Migrace selhala: {e}")

    def upsert_user(self, platform, username, platform_user_id=None, display_name=None, 
                    bio=None, followers_count=None, following_count=None, 
                    joined_date=None, location=None, website=None, is_verified=0,
                    profile_pic_url=None, banner_url=None):
        
        now = datetime.now(timezone.utc).isoformat()
        
        self.cursor.execute('SELECT id FROM users WHERE platform = ? AND username = ?', (platform, username))
        row = self.cursor.fetchone()
        
        if row:
            user_id = row[0]
            self.cursor.execute('''
                UPDATE users SET
                    platform_user_id = COALESCE(?, platform_user_id),
                    display_name = COALESCE(?, display_name),
                    bio = COALESCE(?, bio),
                    followers_count = COALESCE(?, followers_count),
                    following_count = COALESCE(?, following_count),
                    joined_date = COALESCE(?, joined_date),
                    location = COALESCE(?, location),
                    website = COALESCE(?, website),
                    is_verified = ?,
                    profile_pic_url = COALESCE(?, profile_pic_url),
                    banner_url = COALESCE(?, banner_url),
                    last_scraped = ?
                WHERE id = ?
            ''', (platform_user_id, display_name, bio, followers_count, following_count, 
                  joined_date, location, website, is_verified, profile_pic_url, banner_url, now, user_id))
        else:
            user_id = str(uuid.uuid4())
            self.cursor.execute('''
                INSERT INTO users (
                    id, platform, platform_user_id, username, display_name, bio, 
                    followers_count, following_count, joined_date, location, website, is_verified,
                    profile_pic_url, banner_url, last_scraped
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, platform, platform_user_id, username, display_name, bio, 
                  followers_count, following_count, joined_date, location, website, is_verified,
                  profile_pic_url, banner_url, now))
        
        self.conn.commit()
        return user_id

    def upsert_post(self, user_id, platform, platform_post_id, text_content, timestamp_posted, likes_count=0, shares_count=0, comments_count=0, url=None, media_url=None):
        now = datetime.now(timezone.utc).isoformat()
        self.cursor.execute('SELECT id FROM posts WHERE platform_post_id = ?', (platform_post_id,))
        row = self.cursor.fetchone()
        if row:
            post_id = row[0]
            self.cursor.execute('''UPDATE posts SET media_url=?, likes_count=?, shares_count=?, comments_count=?, scraped_at=? WHERE id=?''', (media_url, likes_count, shares_count, comments_count, now, post_id))
        else:
            post_id = str(uuid.uuid4())
            self.cursor.execute('''INSERT INTO posts (id, user_id, platform, platform_post_id, text_content, media_url, timestamp_posted, likes_count, shares_count, comments_count, url, scraped_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (post_id, user_id, platform, platform_post_id, text_content, media_url, timestamp_posted, likes_count, shares_count, comments_count, url, now))
        self.conn.commit()
        return post_id

    def upsert_comment(self, post_id, platform, platform_comment_id, author_username, author_display_name, text_content, timestamp_posted, likes_count=0, shares_count=0, replies_count=0, media_url=None):
        now = datetime.now(timezone.utc).isoformat()
        self.cursor.execute('SELECT id FROM comments WHERE platform_comment_id = ?', (platform_comment_id,))
        row = self.cursor.fetchone()
        if row:
            comment_id = row[0]
            self.cursor.execute('''UPDATE comments SET media_url=?, likes_count=?, shares_count=?, replies_count=?, scraped_at=? WHERE id=?''', (media_url, likes_count, shares_count, replies_count, now, comment_id))
        else:
            comment_id = str(uuid.uuid4())
            self.cursor.execute('''INSERT INTO comments (id, post_id, platform, platform_comment_id, author_username, author_display_name, text_content, media_url, timestamp_posted, likes_count, shares_count, replies_count, scraped_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (comment_id, post_id, platform, platform_comment_id, author_username, author_display_name, text_content, media_url, timestamp_posted, likes_count, shares_count, replies_count, now))
        self.conn.commit()
        return comment_id

    def upsert_trend(self, platform, rank, category, topic_name, post_count):
        now = datetime.now(timezone.utc).isoformat()
        self.cursor.execute('SELECT id FROM trending WHERE platform = ? AND topic_name = ?', (platform, topic_name))
        row = self.cursor.fetchone()
        if row:
            trend_id = row[0]
            self.cursor.execute('''UPDATE trending SET rank=?, category=?, post_count=?, scraped_at=? WHERE id=?''', (rank, category, post_count, now, trend_id))
        else:
            trend_id = str(uuid.uuid4())
            self.cursor.execute('''INSERT INTO trending (id, platform, rank, category, topic_name, post_count, scraped_at) VALUES (?, ?, ?, ?, ?, ?, ?)''', (trend_id, platform, rank, category, topic_name, post_count, now))
        self.conn.commit()
        return trend_id
    
    def get_known_handle(self, query):
        """
        Pokusí se najít username v DB na základě query (shoda s username nebo display_name).
        Vrací username (str) nebo None.
        """
        clean_q = query.replace('@', '').strip()
        
        try:
            self.cursor.execute('''
                SELECT username FROM users 
                WHERE platform = 'X' AND (LOWER(username) = LOWER(?) OR LOWER(display_name) = LOWER(?))
                LIMIT 1
            ''', (clean_q, clean_q))
            row = self.cursor.fetchone()
            
            if row:
                return row[0]
            return None
            
        except Exception as e:
            print(f"[DB ERROR] Chyba při hledání handle: {e}")
            return None

    def close(self):
        if self.conn:
            self.conn.close()
```

## Soubor: social_bot\src\gui\app.py
```py
# src/gui/app.py
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import threading
import json
import os
import time
import sys
from pathlib import Path

# Modulární importy
from src.gui.theme import COLORS
from src.gui.utils import PrintLogger
from src.gui.frames.dashboard import DashboardFrame
from src.gui.frames.profiles import ProfilesFrame
from src.gui.frames.database import DatabaseFrame

from src.bots.instagram.bot import InstagramBot
from src.bots.x.bot import XBot

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # --- KONFIGURACE ---
        self.title("Ogma 0.0") 
        self.geometry("1200x800")
        self.minsize(1000, 700)
        
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        self.data_path = project_root / 'data' / 'users.json'
        self.db_path = project_root / 'data' / 'osint.db'
        
        icon_path = project_root / 'src' / 'gui' / 'ogma_ai_logo.ico'
        if icon_path.exists(): self.iconbitmap(str(icon_path))

        self.users_map = {}
        self.load_users()
        self.current_bot = None 
        self.is_running = False

        # --- LAYOUT ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. Sidebar
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color=COLORS["sidebar_bg"])
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.setup_sidebar()

        # 2. Main Content
        self.main_area = ctk.CTkFrame(self, corner_radius=0, fg_color=COLORS["main_bg"])
        self.main_area.grid(row=0, column=1, sticky="nsew")
        self.main_area.grid_rowconfigure(0, weight=1)
        self.main_area.grid_columnconfigure(0, weight=1)

        # 3. Frames (Moduly)
        self.frame_dash = DashboardFrame(self.main_area, self)
        self.frame_prof = ProfilesFrame(self.main_area, self)
        self.frame_db = DatabaseFrame(self.main_area, self)

        # 4. Logger Hook
        # Přesměrujeme stdout do log boxu uvnitř DashboardFrame
        sys.stdout = PrintLogger(self.frame_dash.log_box, self)
        sys.stderr = PrintLogger(self.frame_dash.log_box, self)

        self.show_frame("dashboard")

    def setup_sidebar(self):
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.pack(pady=(25, 20), padx=20, fill="x")
        
        ctk.CTkLabel(logo_frame, text="Ogma 0.0", font=("Segoe UI", 22, "bold"), text_color=COLORS["text_main"], anchor="w").pack(fill="x")
        ctk.CTkLabel(logo_frame, text="OSINT Automation Tool", font=("Segoe UI", 12), text_color=COLORS["text_dim"], anchor="w").pack(fill="x")

        ctk.CTkFrame(self.sidebar, height=1, fg_color=COLORS["border"]).pack(fill="x", padx=0, pady=10)

        self.btn_nav_dash = self.create_nav_btn("Přehled (Dashboard)", "dashboard")
        self.btn_nav_prof = self.create_nav_btn("Scrapnuté Profily", "profiles") 
        self.btn_nav_db = self.create_nav_btn("Databáze (Vault)", "database")
        
        ctk.CTkLabel(self.sidebar, text="", height=50).pack(side="bottom") # Spacer

        self.status_label = ctk.CTkLabel(self.sidebar, text="● Připraveno", text_color="#2eb85c", font=("Segoe UI", 12))
        self.status_label.pack(side="bottom", pady=(5, 20), padx=20, anchor="w")

        self.progress_bar = ctk.CTkProgressBar(self.sidebar, width=200, height=8, corner_radius=4, progress_color=COLORS["primary"])
        self.progress_bar.set(0)

    def create_nav_btn(self, text, view_name):
        return ctk.CTkButton(
            self.sidebar, text=text, command=lambda: self.show_frame(view_name),
            fg_color="transparent", text_color=COLORS["text_dim"], hover_color=COLORS["panel_bg"],
            anchor="w", height=45, font=("Segoe UI", 14), corner_radius=4
        ).pack(fill="x", padx=10, pady=2) or self.sidebar.winfo_children()[-1]

    def show_frame(self, name):
        # Reset buttons (simple style reset)
        for btn in [self.btn_nav_dash, self.btn_nav_prof, self.btn_nav_db]:
            btn.configure(fg_color="transparent", text_color=COLORS["text_dim"])
        
        # Hide all
        self.frame_dash.grid_forget()
        self.frame_prof.grid_forget()
        self.frame_db.grid_forget()

        if name == "dashboard":
            self.frame_dash.grid(row=0, column=0, sticky="nsew", padx=30, pady=30)
            self.btn_nav_dash.configure(fg_color=COLORS["panel_bg"], text_color=COLORS["primary"])
        elif name == "profiles":
            self.frame_prof.grid(row=0, column=0, sticky="nsew", padx=30, pady=30)
            self.btn_nav_prof.configure(fg_color=COLORS["panel_bg"], text_color=COLORS["primary"])
            self.frame_prof.refresh_data()
        elif name == "database":
            self.frame_db.grid(row=0, column=0, sticky="nsew", padx=30, pady=30)
            self.btn_nav_db.configure(fg_color=COLORS["panel_bg"], text_color=COLORS["primary"])
            self.frame_db.refresh_data()

    def load_users(self):
        if not os.path.exists(self.data_path): return
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for user in data.get("users", []):
                self.users_map[f"{user['ID']} - {user['name']}"] = user
        except: pass

    # --- BOT LOGIC (Zůstává zde kvůli Threadingu a přístupu ke stavu) ---
    def start_thread(self, platform, action):
        if self.is_running: messagebox.showwarning("Busy", "Bot již běží."); return
        
        # Data taháme z DashboardFrame
        key = self.frame_dash.user_var.get()
        if not key: messagebox.showerror("Chyba", "Vyber identitu."); return
        
        user_data = self.users_map[key]
        social = user_data.get('social_media', {}).get(platform)
        if not social: messagebox.showerror("Chyba", f"Identita nemá {platform}."); return
        
        target_input = self.frame_dash.target_var.get().strip()
        if action == "scrape" and not target_input: messagebox.showwarning("Chyba", "Zadej cíl."); return
        
        limit = 10
        if self.frame_dash.scrape_all_var.get(): limit = -1
        else:
            try: limit = int(self.frame_dash.limit_var.get())
            except ValueError: messagebox.showerror("Chyba", "Limit musí být číslo."); return
        
        self.is_running = True
        txt_limit = "VŠE" if limit == -1 else str(limit)
        self.status_label.configure(text=f"● Běží: {platform} {action} (Limit: {txt_limit})", text_color=COLORS["primary"])
        
        # Vyčistit log
        self.frame_dash.log_box.configure(state="normal")
        self.frame_dash.log_box.delete(1.0, tk.END)
        self.frame_dash.log_box.configure(state="disabled")
        
        threading.Thread(target=self.run_bot, args=(platform, social['username'], social['password'], key.split()[0], action, target_input, limit), daemon=True).start()

    def run_bot(self, platform, u, p, uid, action, target_input, limit):
        try:
            if platform == "instagram": bot = InstagramBot(u, p, uid)
            else: bot = XBot(u, p, uid)
            self.current_bot = bot
            bot.login()
            
            if action == "scrape": 
                targets = [t.strip() for t in target_input.replace('\n', ',').split(',') if t.strip()]
                total = len(targets)
                
                self.after(0, lambda: self.progress_bar.pack(side="bottom", padx=20, pady=(0, 10), before=self.status_label))
                print(f"[BATCH] Nalezeno {total} cílů ke zpracování: {targets}")

                for i, target in enumerate(targets):
                    if not self.is_running:
                        print("[STOP] Přerušeno uživatelem.")
                        break

                    progress_percent = i / total
                    self.after(0, lambda p=progress_percent, t=target, idx=i, tot=total: [
                        self.progress_bar.set(p),
                        self.status_label.configure(text=f"● Těžím {idx+1}/{tot}: {t}", text_color=COLORS["primary"])
                    ])
                    
                    print(f"\n=== CÍL {i+1}/{total}: {target} ===")
                    try:
                        bot.scraper.scrape_profile(target, limit)
                    except Exception as e:
                        print(f"[ERROR] Chyba u cíle {target}: {e}")
                    
                    self.after(0, lambda p=((i + 1) / total): self.progress_bar.set(p))
                    if i < total - 1:
                        print(f"[INFO] Pauza 3s...")
                        time.sleep(3)

            elif action == "scrape_trending": 
                bot.scraper.scrape_trending()
            
            print("--- HOTOVO ---")
            self.status_label.configure(text=f"● Hotovo (Čekám na STOP)", text_color="#2eb85c")
            while self.is_running: time.sleep(1)

        except Exception as e: print(f"CHYBA: {e}")
        finally:
            self.after(0, lambda: self.progress_bar.pack_forget())
            self.after(0, lambda: self.progress_bar.set(0))
            if self.current_bot: self.current_bot.close()
            self.current_bot = None
            self.is_running = False
            self.status_label.configure(text="● Připraveno", text_color="#2eb85c")

    def stop_bot(self):
        if self.is_running:
            self.is_running = False
            if self.current_bot: self.current_bot.close()
            print("--- ZASTAVENO UŽIVATELEM ---")

if __name__ == "__main__":
    app = App()
    app.mainloop()
```

## Soubor: social_bot\src\gui\db_viewer.py
```py
import customtkinter as ctk
from tkinter import ttk
import sqlite3
from pathlib import Path

class DatabaseViewer(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Prohlížeč Databáze - osint.db")
        self.geometry("1000x600")
        
        # Stylování standardního Tkinter Treeview do tmavého režimu
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", 
                        background="#2b2b2b", 
                        foreground="white", 
                        rowheight=25, 
                        fieldbackground="#2b2b2b",
                        bordercolor="#343638",
                        borderwidth=0)
        style.map('Treeview', background=[('selected', '#1f538d')])
        style.configure("Treeview.Heading", 
                        background="#565b5e", 
                        foreground="white", 
                        relief="flat")
        style.map("Treeview.Heading", background=[('active', '#343638')])

        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        self.db_path = project_root / 'data' / 'osint.db'

        # Přepínání tabulek
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=20)
        self.tabview.add("Uživatelé (Users)")
        self.tabview.add("Příspěvky (Posts)")

        self.users_tree = self.create_treeview(self.tabview.tab("Uživatelé (Users)"))
        self.posts_tree = self.create_treeview(self.tabview.tab("Příspěvky (Posts)"))

        self.load_data()

    def create_treeview(self, parent_frame):
        tree_scroll_y = ctk.CTkScrollbar(parent_frame, orientation="vertical")
        tree_scroll_y.pack(side="right", fill="y")
        
        tree_scroll_x = ctk.CTkScrollbar(parent_frame, orientation="horizontal")
        tree_scroll_x.pack(side="bottom", fill="x")

        tree = ttk.Treeview(parent_frame, yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)
        tree.pack(fill="both", expand=True)
        
        tree_scroll_y.configure(command=tree.yview)
        tree_scroll_x.configure(command=tree.xview)
        
        return tree

    def load_data(self):
        if not self.db_path.exists():
            return

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # Načtení uživatelů
            cursor.execute("SELECT id, platform, username, display_name, followers_count, last_scraped FROM users")
            users_rows = cursor.fetchall()
            
            self.users_tree['columns'] = ("ID", "Platform", "Username", "Display Name", "Followers", "Last Scraped")
            self.users_tree.column("#0", width=0, stretch="no")
            for col in self.users_tree['columns']:
                self.users_tree.column(col, anchor="w", width=150)
                self.users_tree.heading(col, text=col, anchor="w")

            for row in users_rows:
                self.users_tree.insert("", "end", values=row)

            # Načtení příspěvků
            cursor.execute("SELECT id, platform_post_id, text_content, likes_count, timestamp_posted, scraped_at FROM posts")
            posts_rows = cursor.fetchall()

            self.posts_tree['columns'] = ("ID", "Post ID", "Text", "Likes", "Posted At", "Scraped At")
            self.posts_tree.column("#0", width=0, stretch="no")
            for col in self.posts_tree['columns']:
                self.posts_tree.column(col, anchor="w", width=150)
                self.posts_tree.heading(col, text=col, anchor="w")

            for row in posts_rows:
                # Oříznutí textu, aby tabulka nebyla moc široká
                row_list = list(row)
                if row_list[2] and len(row_list[2]) > 50:
                    row_list[2] = row_list[2][:47] + "..."
                self.posts_tree.insert("", "end", values=row_list)

            conn.close()
        except Exception as e:
            print(f"Chyba při načítání databáze: {e}")
```

## Soubor: social_bot\src\gui\theme.py
```py
# src/gui/theme.py

# --- BITWARDEN THEME PALETTE (Dark Mode) ---
COLORS = {
    "sidebar_bg": "#171b1e",
    "main_bg": "#222529",
    "panel_bg": "#2c3035",
    "primary": "#175DDC",
    "primary_hover": "#144eb8",
    "text_main": "#ffffff",
    "text_dim": "#9eaab5",
    "border": "#3b4047",
    "danger": "#ab1818",
    "success": "#2eb85c",
    "verified": "#1DA1F2"
}
```

## Soubor: social_bot\src\gui\utils.py
```py
# src/gui/utils.py
import tkinter as tk
import customtkinter as ctk
import requests
from io import BytesIO
from PIL import Image
from datetime import datetime

class PrintLogger:
    def __init__(self, textbox, tk_app):
        self.textbox = textbox
        self.tk_app = tk_app

    def write(self, text):
        self.tk_app.after(0, self._insert_text, text)

    def _insert_text(self, text):
        if not self.textbox: return # Pojistka
        
        self.textbox.configure(state="normal")
        if text.strip():
            current_time = datetime.now().strftime("[%H:%M:%S]")
            self.textbox.insert(tk.END, f"{current_time} {text}")
        else:
            self.textbox.insert(tk.END, text)
            
        self.textbox.see(tk.END)
        self.textbox.configure(state="disabled")

    def flush(self):
        pass

class AsyncImageLoader:
    def __init__(self):
        self.image_cache = {}

    def load_image(self, url, label_widget, size=(80, 80)):
        if not url: return
        
        # Pokud je v cache, použijeme ho rovnou
        if url in self.image_cache:
            self._update_label(label_widget, self.image_cache[url])
            return

        # Jinak stáhneme (toto by se mělo volat v threadu z GUI)
        try:
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                img_data = BytesIO(response.content)
                pil_img = Image.open(img_data)
                
                # Center Crop
                width, height = pil_img.size
                if width != height:
                    new_size = min(width, height)
                    left = (width - new_size) / 2
                    top = (height - new_size) / 2
                    right = (width + new_size) / 2
                    bottom = (height + new_size) / 2
                    pil_img = pil_img.crop((left, top, right, bottom))
                
                pil_img = pil_img.resize(size, Image.Resampling.LANCZOS)
                ctk_image = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)
                
                self.image_cache[url] = ctk_image
                self._update_label(label_widget, ctk_image)
        except Exception:
            pass

    def _update_label(self, label, image):
        try:
            label.configure(image=image, text="", fg_color="transparent")
        except: pass
```

## Soubor: social_bot\src\gui\frames\dashboard.py
```py
# src/gui/frames/dashboard.py
import customtkinter as ctk
from src.gui.theme import COLORS

class DashboardFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller # Reference na hlavní App
        self.setup_ui()

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        
        # Nadpis
        ctk.CTkLabel(self, text="Ovládací panel", font=("Segoe UI", 24, "bold"), 
                     text_color=COLORS["text_main"]).pack(anchor="w", pady=(0, 20))

        # 1. INPUTY
        input_container = ctk.CTkFrame(self, fg_color="transparent")
        input_container.pack(fill="x", pady=(0, 20))
        
        # Identita
        ctk.CTkLabel(input_container, text="IDENTITA BOTA", font=("Segoe UI", 11, "bold"), text_color=COLORS["text_dim"]).pack(anchor="w", pady=(0, 5))
        self.user_var = ctk.StringVar()
        self.user_combo = ctk.CTkComboBox(
            input_container, variable=self.user_var, height=35, font=("Segoe UI", 13),
            border_color=COLORS["border"], fg_color=COLORS["panel_bg"], 
            button_color=COLORS["panel_bg"], dropdown_hover_color=COLORS["primary"],
            text_color=COLORS["text_main"], state="readonly"
        )
        self.user_combo.pack(fill="x", pady=(0, 15))
        self.refresh_users_combo()

        # Cíle
        ctk.CTkLabel(input_container, text="CÍLOVÉ ÚČTY (odděl čárkou)", font=("Segoe UI", 11, "bold"), text_color=COLORS["text_dim"]).pack(anchor="w", pady=(0, 5))
        self.target_var = ctk.StringVar()
        self.target_entry = ctk.CTkEntry(
            input_container, textvariable=self.target_var, height=40, font=("Segoe UI", 14), 
            border_color=COLORS["border"], fg_color=COLORS["panel_bg"], 
            text_color=COLORS["text_main"], placeholder_text="např. elonmusk, taylorswift13"
        )
        self.target_entry.pack(fill="x", pady=(0, 15))

        # Limity
        limit_frame = ctk.CTkFrame(input_container, fg_color="transparent")
        limit_frame.pack(fill="x")
        ctk.CTkLabel(limit_frame, text="LIMIT PŘÍSPĚVKŮ", font=("Segoe UI", 11, "bold"), text_color=COLORS["text_dim"]).pack(anchor="w", pady=(0, 5))
        
        limit_inner = ctk.CTkFrame(limit_frame, fg_color="transparent")
        limit_inner.pack(fill="x")
        
        self.scrape_all_var = ctk.BooleanVar(value=False)
        self.chk_all = ctk.CTkCheckBox(
            limit_inner, text="Stáhnout vše", variable=self.scrape_all_var, 
            command=self.toggle_limit_entry, fg_color=COLORS["primary"], 
            hover_color=COLORS["primary_hover"], border_color=COLORS["border"], font=("Segoe UI", 13)
        )
        self.chk_all.pack(side="left", padx=(0, 20))
        
        self.limit_var = ctk.StringVar(value="10")
        self.limit_entry = ctk.CTkEntry(
            limit_inner, textvariable=self.limit_var, width=100, height=35, 
            font=("Segoe UI", 13), border_color=COLORS["border"], 
            fg_color=COLORS["panel_bg"], text_color=COLORS["text_main"]
        )
        self.limit_entry.pack(side="left")

        # 2. AKCE
        ctk.CTkLabel(self, text="AKCE", font=("Segoe UI", 11, "bold"), text_color=COLORS["text_dim"]).pack(anchor="w", pady=(10, 5))
        actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        actions_frame.pack(fill="x", pady=(0, 20))
        actions_frame.grid_columnconfigure((0, 1), weight=1)
        
        self.create_action_btn(actions_frame, "Instagram Login", 0, 0, lambda: self.controller.start_thread("instagram", "login"), outline=True)
        self.create_action_btn(actions_frame, "Těžit Instagram", 0, 1, lambda: self.controller.start_thread("instagram", "scrape"))
        self.create_action_btn(actions_frame, "X Login", 1, 0, lambda: self.controller.start_thread("X", "login"), outline=True)
        self.create_action_btn(actions_frame, "Těžit X", 1, 1, lambda: self.controller.start_thread("X", "scrape"))
        
        btn_trend = ctk.CTkButton(
            actions_frame, text="Těžit Trendy (X)", command=lambda: self.controller.start_thread("X", "scrape_trending"), 
            height=35, fg_color=COLORS["panel_bg"], hover_color=COLORS["border"], 
            text_color=COLORS["text_main"], font=("Segoe UI", 13)
        )
        btn_trend.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        
        btn_stop = ctk.CTkButton(
            self, text="UKONČIT OPERACI", command=self.controller.stop_bot, 
            fg_color=COLORS["danger"], hover_color="#8a1212", height=40, font=("Segoe UI", 13, "bold")
        )
        btn_stop.pack(fill="x", pady=(10, 20))

        # 3. LOG
        ctk.CTkLabel(self, text="LOG", font=("Segoe UI", 11, "bold"), text_color=COLORS["text_dim"]).pack(anchor="w", pady=(0, 5))
        self.log_box = ctk.CTkTextbox(
            self, fg_color="#121416", text_color="#00ff41", font=("Consolas", 12), 
            corner_radius=4, border_color=COLORS["border"], border_width=1
        )
        self.log_box.pack(fill="both", expand=True)
        self.log_box.configure(state="disabled")

    def toggle_limit_entry(self):
        if self.scrape_all_var.get(): 
            self.limit_entry.configure(state="disabled", fg_color=COLORS["sidebar_bg"])
        else: 
            self.limit_entry.configure(state="normal", fg_color=COLORS["panel_bg"])

    def create_action_btn(self, parent, text, r, c, cmd, outline=False):
        if outline: fg, border, text_c, hover = "transparent", 1, COLORS["primary"], COLORS["panel_bg"]
        else: fg, border, text_c, hover = COLORS["primary"], 0, "white", COLORS["primary_hover"]
        
        btn = ctk.CTkButton(
            parent, text=text, command=cmd, height=35, fg_color=fg, 
            text_color=text_c, border_width=border, border_color=COLORS["primary"], 
            hover_color=hover, font=("Segoe UI", 13, "bold")
        )
        btn.grid(row=r, column=c, sticky="ew", padx=5, pady=5)

    def refresh_users_combo(self):
        if self.controller.users_map:
            users = list(self.controller.users_map.keys())
            self.user_combo.configure(values=users)
            self.user_combo.set(users[0])
```

## Soubor: social_bot\src\gui\frames\database.py
```py
# src/gui/frames/database.py
import customtkinter as ctk
from tkinter import ttk
import sqlite3
from src.gui.theme import COLORS

class DatabaseFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.setup_ui()

    def setup_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(header, text="Uložená data", font=("Segoe UI", 24, "bold"), 
                     text_color=COLORS["text_main"]).pack(side="left")
        ctk.CTkButton(header, text="Obnovit", width=80, height=30, 
                      fg_color=COLORS["panel_bg"], hover_color=COLORS["border"], 
                      text_color=COLORS["text_main"], command=self.refresh_data).pack(side="right")

        # Tabs
        self.tab_db = ctk.CTkTabview(
            self, fg_color="transparent", 
            segmented_button_fg_color=COLORS["panel_bg"], 
            segmented_button_selected_color=COLORS["primary"], 
            segmented_button_selected_hover_color=COLORS["primary_hover"], 
            segmented_button_unselected_color=COLORS["panel_bg"], 
            segmented_button_unselected_hover_color=COLORS["border"]
        )
        self.tab_db.pack(fill="both", expand=True)
        
        self.tab_db.add("Uživatelé")
        self.tab_db.add("Příspěvky")
        self.tab_db.add("Trendy")

        self.tree_users = self.create_tree(self.tab_db.tab("Uživatelé"))
        self.tree_posts = self.create_tree(self.tab_db.tab("Příspěvky"))
        self.tree_trends = self.create_tree(self.tab_db.tab("Trendy"))

    def create_tree(self, parent):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background=COLORS["main_bg"], foreground=COLORS["text_main"], 
                        rowheight=30, fieldbackground=COLORS["main_bg"], borderwidth=0, font=("Segoe UI", 11))
        style.configure("Treeview.Heading", background=COLORS["panel_bg"], foreground=COLORS["text_main"], 
                        relief="flat", font=("Segoe UI", 12, "bold"), padding=(10, 5))
        style.map('Treeview', background=[('selected', COLORS["primary"])], foreground=[('selected', 'white')])
        
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True)
        
        scroll_y = ctk.CTkScrollbar(frame, button_color=COLORS["panel_bg"], button_hover_color=COLORS["border"])
        scroll_y.pack(side="right", fill="y")
        
        tree = ttk.Treeview(frame, yscrollcommand=scroll_y.set, show="headings", selectmode="browse")
        tree.pack(fill="both", expand=True)
        scroll_y.configure(command=tree.yview)
        return tree

    def refresh_data(self):
        if not self.controller.db_path.exists(): return
        
        # Clear
        for t in [self.tree_users, self.tree_posts, self.tree_trends]:
            for i in t.get_children(): t.delete(i)
            
        try:
            conn = sqlite3.connect(str(self.controller.db_path))
            cur = conn.cursor()
            
            # Users
            cur.execute("SELECT platform, username, followers_count FROM users")
            self.tree_users['columns'] = ("Platform", "Username", "Followers")
            for c in self.tree_users['columns']: 
                self.tree_users.heading(c, text=c, anchor="w")
                self.tree_users.column(c, width=150)
            for r in cur.fetchall(): self.tree_users.insert("", "end", values=r)
            
            # Posts
            cur.execute("SELECT platform, text_content, likes_count FROM posts ORDER BY scraped_at DESC LIMIT 50")
            self.tree_posts['columns'] = ("Plat.", "Text", "Likes")
            self.tree_posts.heading("Plat.", text="Plat."); self.tree_posts.column("Plat.", width=50)
            self.tree_posts.heading("Text", text="Text"); self.tree_posts.column("Text", width=400)
            self.tree_posts.heading("Likes", text="Likes"); self.tree_posts.column("Likes", width=80)
            for r in cur.fetchall():
                tx = r[1][:60] + "..." if r[1] and len(r[1]) > 60 else r[1]
                self.tree_posts.insert("", "end", values=(r[0], tx, r[2]))
                
            # Trends
            cur.execute("SELECT rank, topic_name, post_count FROM trending ORDER BY rank ASC")
            self.tree_trends['columns'] = ("#", "Téma", "Objem")
            for c in self.tree_trends['columns']: self.tree_trends.heading(c, text=c, anchor="w")
            for r in cur.fetchall(): self.tree_trends.insert("", "end", values=r)
            
            conn.close()
        except Exception as e:
            print(f"[DB ERROR] {e}")
```

## Soubor: social_bot\src\gui\frames\profiles.py
```py
# src/gui/frames/profiles.py
import customtkinter as ctk
import threading
import sqlite3
from src.gui.theme import COLORS
from src.gui.utils import AsyncImageLoader

class ProfilesFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.all_profiles_data = []
        self.image_loader = AsyncImageLoader()
        
        self.setup_ui()

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Top Bar
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 20))

        ctk.CTkLabel(top_bar, text="Nalezené Profily", font=("Segoe UI", 24, "bold"), 
                     text_color=COLORS["text_main"]).pack(side="left")

        self.search_var = ctk.StringVar()
        self.search_var.trace("w", self.filter_profiles)
        
        search_entry = ctk.CTkEntry(
            top_bar, textvariable=self.search_var, width=300, height=35, 
            corner_radius=20, placeholder_text="🔍 Hledat jméno...",
            fg_color=COLORS["panel_bg"], border_color=COLORS["border"], text_color="white"
        )
        search_entry.pack(side="right")

        # Scrollable Area
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self.scroll_frame.grid(row=1, column=0, sticky="nsew")
        self.scroll_frame.grid_columnconfigure(0, weight=1)

    def refresh_data(self):
        # Vyčistit
        for widget in self.scroll_frame.winfo_children(): widget.destroy()
        
        if not self.controller.db_path.exists(): return
        
        try:
            conn = sqlite3.connect(str(self.controller.db_path))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            
            try:
                cur.execute("SELECT * FROM users ORDER BY last_scraped DESC")
            except:
                # Fallback pro starou DB
                cur.execute("SELECT id, platform, username, display_name, bio, followers_count, profile_pic_url, last_scraped FROM users ORDER BY last_scraped DESC")
            
            self.all_profiles_data = [dict(row) for row in cur.fetchall()]
            conn.close()
            self.filter_profiles()
        except Exception as e:
            print(f"[GUI ERROR] Chyba profilů: {e}")

    def filter_profiles(self, *args):
        query = self.search_var.get().lower()
        for widget in self.scroll_frame.winfo_children(): widget.destroy()
        
        for user in self.all_profiles_data:
            u_name = (user['username'] or "").lower()
            d_name = (user.get('display_name') or "").lower()
            
            if query in u_name or query in d_name:
                self.create_card(user)

    def create_card(self, user):
        card = ctk.CTkFrame(self.scroll_frame, fg_color=COLORS["panel_bg"], corner_radius=10, 
                            border_color=COLORS["border"], border_width=1)
        card.pack(fill="x", pady=5, padx=5)
        card.grid_columnconfigure(1, weight=1) 
        
        # 1. Avatar
        img_widget = ctk.CTkLabel(card, text="", width=80, height=80, corner_radius=10, fg_color="#444")
        if user.get('profile_pic_url'):
            # Spustit načítání v threadu
            threading.Thread(
                target=self.image_loader.load_image, 
                args=(user.get('profile_pic_url'), img_widget), 
                daemon=True
            ).start()
            
        img_widget.grid(row=0, column=0, rowspan=4, padx=15, pady=15, sticky="n")

        # 2. Info Frame
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.grid(row=0, column=1, sticky="nw", pady=(15, 0), padx=5)
        
        # Jméno
        name_text = user.get('display_name') or user['username']
        ctk.CTkLabel(info_frame, text=name_text, font=("Segoe UI", 16, "bold"), 
                     text_color="white").pack(side="left")

        # Verifikace
        if user.get('is_verified') == 1:
            ctk.CTkLabel(info_frame, text="☑", font=("Segoe UI", 16), 
                         text_color=COLORS["verified"]).pack(side="left", padx=(5, 0))

        # Handle
        handle_txt = f"@{user['username']} • {str(user.get('platform')).upper()}"
        ctk.CTkLabel(info_frame, text=handle_txt, font=("Segoe UI", 13), 
                     text_color=COLORS["text_dim"]).pack(side="left", padx=(10, 0))

        # 3. Stats
        stats_frame = ctk.CTkFrame(card, fg_color="transparent")
        stats_frame.grid(row=1, column=1, sticky="nw", pady=(5, 5), padx=5)
        
        def fmt(n): return f"{n:,}".replace(",", " ") if n is not None else "0"
        
        # Followers
        ctk.CTkLabel(stats_frame, text=fmt(user.get('followers_count', 0)), font=("Segoe UI", 13, "bold"), text_color=COLORS["text_main"]).pack(side="left")
        ctk.CTkLabel(stats_frame, text="Followers", font=("Segoe UI", 13), text_color=COLORS["text_dim"]).pack(side="left", padx=(3, 15))
        
        # Following
        ctk.CTkLabel(stats_frame, text=fmt(user.get('following_count', 0)), font=("Segoe UI", 13, "bold"), text_color=COLORS["text_main"]).pack(side="left")
        ctk.CTkLabel(stats_frame, text="Following", font=("Segoe UI", 13), text_color=COLORS["text_dim"]).pack(side="left", padx=(3, 0))

        # 4. Bio
        bio = user.get('bio')
        if bio:
            short_bio = (bio.replace('\n', ' ')[:90] + "...") if len(bio)>90 else bio
            ctk.CTkLabel(card, text=short_bio, font=("Segoe UI", 12, "italic"), 
                         text_color="#b0b0b0", anchor="w").grid(row=2, column=1, sticky="w", padx=5, pady=(0, 5))

        # 5. Metadata
        meta_frame = ctk.CTkFrame(card, fg_color="transparent")
        meta_frame.grid(row=3, column=1, sticky="nw", pady=(0, 15), padx=5)
        
        meta = []
        if user.get('location'): meta.append(f"📍 {user['location']}")
        if user.get('website'): meta.append(f"🔗 {user['website']}")
        if user.get('joined_date'): meta.append(f"📅 {user['joined_date']}")
        
        if meta:
            ctk.CTkLabel(meta_frame, text="   ".join(meta), font=("Segoe UI", 11), 
                         text_color=COLORS["text_dim"]).pack(side="left")

        # Date
        last_s = str(user.get('last_scraped')).split('T')[0] if user.get('last_scraped') else "?"
        ctk.CTkLabel(card, text=f"Upd: {last_s}", font=("Segoe UI", 10), 
                     text_color="#555").grid(row=3, column=1, sticky="e", padx=15, pady=(0, 15))
```

## Soubor: social_bot\src\utils\human_input.py
```py
import time
import random

def delay(min_seconds=1.0, max_seconds=3.0):
    """Náhodná prodleva mezi akcemi."""
    time.sleep(random.uniform(min_seconds, max_seconds))

def human_typing(element, text):
    """
    Simuluje psaní člověka.
    Určeno pro DrissionPage element.
    """
    # DrissionPage má metodu .input(), která píše rovnou.
    # Pokud chceme simulovat prodlevy, musíme psát po znacích.
    
    # Vyčistit pole (pokud to DrissionPage neudělá sám v kontextu)
    # element.clear() 
    
    for char in text:
        # append=True zajistí, že nepřepisujeme, ale přidáváme znaky
        element.input(char, clear=False) 
        
        # Rychlost psaní (náhodná)
        time.sleep(random.uniform(0.05, 0.2))
        
        # Občasná "chyba" (zjednodušeno pro stabilitu - zatím vynecháme Backspace logiku, 
        # protože u DP je input čistší bez mazání)

def random_mouse_movement(page_object=None):
    """
    Placeholder pro kompatibilitu.
    DrissionPage ovládá prohlížeč přes protokol (CDP), nepotřebuje hýbat fyzickou myší 
    jako Selenium, aby nebyl detekován.
    """
    pass
```