## Soubor: requirements.txt
```txt
DrissionPage
customtkinter
keyboard
pillow
requests
playwright-stealth
playwright
```

## Soubor: __init__.py
```py

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

## Soubor: social_bot\test_profile.py
```py
from src.core.base_bot import BaseBot
import time
import os

# Jednoduchý test, zda se vytvoří profil
print("--- TEST ZAČÍNÁ ---")

# Inicializace bota (použije ID "test_user")
try:
    bot = BaseBot(headless=False, user_id="test_user")
    
    print("Otevírám Google...")
    bot.page.get("https://www.google.com")
    
    print("Čekám 5 sekund (nyní zkontroluj složku profiles/test_user)...")
    time.sleep(5)
    
    print("Zavírám bota...")
    bot.close()
    print("--- TEST DOKONČEN ---")
    
    # Kontrola
    profile_dir = os.path.join(os.getcwd(), 'profiles', 'test_user')
    if os.path.exists(profile_dir) and len(os.listdir(profile_dir)) > 0:
        print(f"✅ ÚSPĚCH! Složka profilu není prázdná: {profile_dir}")
        print(f"Počet souborů/složek: {len(os.listdir(profile_dir))}")
    else:
        print(f"❌ CHYBA! Složka profilu je stále prázdná: {profile_dir}")

except Exception as e:
    print(f"CRITICAL ERROR: {e}")
```

## Soubor: social_bot\profiles\0_ig\Default\Service Worker\CacheStorage\2348e52d6de9218df880d9a88ad6a5d8c2c9555c\index.txt
```txt
Chyba při čtení souboru: 'utf-8' codec can't decode byte 0x80 in position 55: invalid start byte
```

## Soubor: social_bot\profiles\0_ig\Default\Service Worker\CacheStorage\d324cea85344c240641e02ac75d9ff5b961ca213\index.txt
```txt
Chyba při čtení souboru: 'utf-8' codec can't decode byte 0x80 in position 62: invalid start byte
```

## Soubor: social_bot\profiles\0_x\Default\Service Worker\CacheStorage\bd1c4d03a881bd4b56183475e9bd7806830c983b\index.txt
```txt
Chyba při čtení souboru: 'utf-8' codec can't decode byte 0x89 in position 1: invalid start byte
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
        try:
            home_icon = self.bot.page.locator('svg[aria-label="Domů"], svg[aria-label="Home"]').first
            if home_icon.is_visible(timeout=3000):
                print("[IG] Již přihlášeno (ze session). Přeskakuji login a cookies.")
                return
        except:
            pass

        print("[IG] Kontroluji Cookies okna...")
        cookie_keywords = ['Povolit', 'Odmítnout', 'Allow', 'Decline']
        for word in cookie_keywords:
            try:
                btn = self.bot.page.get_by_text(word, exact=False).first
                if btn.is_visible(timeout=500):
                    btn.click(force=True)
                    print(f"[IG] Odkliknuto cookie tlačítko: '{word}'")
                    delay(1.5)
                    break
            except:
                pass

        all_login_inputs = self.bot.page.locator('input[name="email"], input[name="username"]').all()
        all_pass_inputs = self.bot.page.locator('input[name="pass"], input[name="password"]').all()
        
        login_input = None
        for inp in all_login_inputs:
            if inp.is_visible():
                login_input = inp
                break
                
        pass_input = None
        for inp in all_pass_inputs:
            if inp.is_visible():
                pass_input = inp
                break

        if not login_input:
            print("[IG] Nevidím viditelný login formulář, ale ani znaky přihlášení.")
            return

        print("[IG] Zadávám přihlašovací údaje...")
        login_input.fill("")
        login_input.press_sequentially(self.bot.username, delay=150)
        delay(0.5, 1)
        
        if pass_input:
            pass_input.fill("")
            pass_input.press_sequentially(self.bot.password, delay=150)
        delay(1, 2)
        
        submit_btn = self.bot.page.locator('button[type="submit"]').first
        if submit_btn.is_visible(timeout=2000):
            submit_btn.click(force=True)
        else:
            try:
                login_btn = self.bot.page.get_by_text('Přihlásit', exact=False).first
                if not login_btn.is_visible():
                    login_btn = self.bot.page.get_by_text('Log in', exact=False).first
                if login_btn.is_visible():
                    login_btn.click(force=True)
            except:
                pass
            
        delay(5, 8)
        
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
        
        self.base_url = "https://www.instagram.com/"
        
        self.auth = InstagramAuthenticator(self)
        self.scraper = InstagramScraper(self)

    def login(self):
        self.auth.login()
```

## Soubor: social_bot\src\bots\instagram\scraper.py
```py
from src.utils.human_input import delay
from src.core.database import DatabaseManager
import re
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

class InstagramScraper:
    def __init__(self, bot):
        self.bot = bot
        self.db = DatabaseManager()

    def parse_number(self, text):
        if not text: 
            return 0
        
        # Odstranění nedělitelných mezer (\xa0) a všech dalších whitespace znaků
        text = str(text).upper().replace('\xa0', '').replace('&NBSP;', '')
        text = re.sub(r'\s+', '', text)
        
        if 'TIS' in text:
            text = text.replace('TIS.', 'K').replace('TIS', 'K')
            
        text = text.replace('TOSEMILÍBÍ', '').replace('LIKES', '')
        text = text.replace(',', '.')
        
        match = re.search(r'([\d\.]+)([KMB]?)', text)
        if not match: 
            return 0
            
        num_str, suffix = match.groups()
        try:
            num = float(num_str)
        except:
            return 0
        
        if suffix == 'K': num *= 1000
        elif suffix == 'M': num *= 1000000
        elif suffix == 'B': num *= 1000000000
        
        return int(num)

    def scrape_post_and_comments(self, db_user_id, post_url, comments_limit=50):
        print(f"\n  -> [IG-SCRAPER] Otevírám příspěvek: {post_url}")
        self.bot.open_url(post_url)
        delay(3, 5)

        platform_post_id = post_url.rstrip('/').split('/')[-1]
        
        current_url = self.bot.page.url
        try:
            actual_username = current_url.split('instagram.com/')[-1].split('/')[0].split('?')[0]
        except:
            actual_username = ""

        post_container = self.bot.page.locator('main, article, [role="dialog"]').first
        
        # 1. Extrakce textu příspěvku
        post_text = ""
        h1_els = post_container.locator('h1[dir="auto"]').all()
        for h1 in h1_els:
            txt = h1.inner_text()
            if txt and txt != actual_username:
                post_text += txt + "\n"
                
        if not post_text.strip():
            span_els = post_container.locator('span[dir="auto"]').all()
            for sp in span_els[:5]:
                txt = sp.inner_text()
                if txt and txt != actual_username and len(txt) > 5 and not re.match(r'^\d+\s+[hdwmsčty]$', txt, re.IGNORECASE):
                    post_text = txt
                    break
        post_text = post_text.strip()

        # 2. Extrakce média (Podpora kolotočů s využitím JS evaluace pro ignorování mřížky)
        media_urls = []
        is_video = False
        
        for _ in range(15):
            # Videa
            for v in post_container.locator('video').all():
                try:
                    if v.evaluate("el => el.closest('a') !== null"):
                        continue
                        
                    src = v.get_attribute('src') or v.get_attribute('poster')
                    if src and not src.startswith('blob:'):
                        src = src.replace('&amp;', '&')
                        if src not in media_urls:
                            media_urls.append(src)
                            is_video = True
                except:
                    pass
            
            # Fotky
            for img in post_container.locator('div._aagv img, ul li img').all():
                try:
                    if img.evaluate("el => el.closest('a') !== null"):
                        continue
                        
                    alt = (img.get_attribute('alt') or "").lower()
                    src = img.get_attribute('src') or ""
                    
                    if "profile" not in alt and "profilov" not in alt and "data:image" not in src:
                        src = src.replace('&amp;', '&')
                        if src and src not in media_urls:
                            media_urls.append(src)
                except:
                    pass
            
            # Pokus o posun kolotoče na další fotku
            try:
                next_btn = post_container.locator('button[aria-label="Další"], button[aria-label="Next"]').first
                if next_btn.is_visible(timeout=500):
                    next_btn.click(force=True)
                    self.bot.page.wait_for_timeout(800)
                else:
                    break
            except:
                break

        if not post_text:
            if is_video:
                post_text = "[OBSAHUJE VIDEO]"
            elif media_urls:
                post_text = "[OBSAHUJE FOTKU]"

        final_media_url = ";".join(media_urls) if media_urls else None

        # 3. Extrakce statistik
        stats_js = """
        (container) => {
            let likes = "0";
            let comments = "0";
            if(!container) container = document;
            
            let svgs = container.querySelectorAll('svg');
            for(let svg of svgs) {
                let label = svg.getAttribute('aria-label');
                if (label === 'To se mi líbí' || label === 'Like') {
                    let btn = svg.closest('div[role="button"], a');
                    if (btn && btn.innerText.match(/\\d/)) {
                        likes = btn.innerText;
                    }
                } else if (label === 'Komentář' || label === 'Comment') {
                    let btn = svg.closest('div[role="button"], a');
                    if (btn && btn.innerText.match(/\\d/)) {
                        comments = btn.innerText;
                    }
                }
            }
            return {likes, comments};
        }
        """
        try:
            post_element_handle = post_container.element_handle()
            stats_data = self.bot.page.evaluate(stats_js, post_element_handle)
            likes_count = self.parse_number(stats_data.get('likes', '0'))
            comments_count = self.parse_number(stats_data.get('comments', '0'))
        except:
            likes_count, comments_count = 0, 0

        time_loc = post_container.locator('time').first
        timestamp = time_loc.get_attribute('datetime') if time_loc.count() > 0 else ""

        db_post_id = self.db.upsert_post(
            user_id=db_user_id,
            platform="IG",
            platform_post_id=platform_post_id,
            text_content=post_text,
            timestamp_posted=timestamp,
            likes_count=likes_count,
            shares_count=0, 
            comments_count=comments_count, 
            url=post_url,
            media_url=final_media_url
        )
        print(f"  -> [IG-SCRAPER] Uložen příspěvek ID: {platform_post_id} | Lajky: {likes_count} | Komentáře: {comments_count} | Média: {len(media_urls)}")

        # --- Těžba komentářů ---
        print(f"  -> [IG-SCRAPER] Těžím komentáře k tomuto příspěvku (Limit: {comments_limit})...")
        comments_collected = 0
        processed_comment_ids = set()
        
        max_comments = comments_limit

        # OPRAVENÝ SKRIPT PRO KOMENTÁŘE
        js_extract_comments = """
        () => {
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
                var dirEls = block.querySelectorAll('span[dir="auto"], div[dir="auto"], span');
                for (var k = 0; k < dirEls.length; k++) {
                    var txt = dirEls[k].innerText.trim();
                    var ignoreWords = ['Odpovědět', 'Reply', 'Zobrazit překlad', 'See translation', 'Skrýt odpovědi', 'Hide replies'];
                    
                    var isTimeStr = /^\\d+\\s*[hdwmsčty]$/i.test(txt) || /^před\\s+\\d+/i.test(txt);
                    // Nový filtr pro skrytí textů "Zobrazit odpovědi"
                    var isReplyStr = /zobrazit\\s+všech/i.test(txt) || /view\\s+all/i.test(txt) || /odpovědí/i.test(txt) || /replies/i.test(txt);
                    
                    if (txt && txt !== author && !ignoreWords.includes(txt) && !txt.includes('To se mi líbí') && !txt.includes(' like') && !isTimeStr && !isReplyStr) {
                        // Zabráníme čtení textu z obrovských rodičovských divů
                        if (author && txt.includes(author) && txt.length > author.length + 5) continue;
                        
                        if (!textContent.includes(txt) && txt.length > 1) {
                            textContent += txt + " ";
                        }
                    }
                }
                
                var likesStr = "0";
                var allTextEls = block.querySelectorAll('span, div');
                for (var k = 0; k < allTextEls.length; k++) {
                    var txt = allTextEls[k].innerText.trim();
                    if ((txt.includes('To se mi líbí') || txt.includes(' like') || txt.includes('Likes') || txt.includes('likes')) && /\\d/.test(txt)) {
                        // KLÍČOVÁ OCHRANA: List lajků má pár znaků, rodičovský div s celým komentářem jich má spoustu.
                        // Omezíme to na 40 znaků, takže se uloží jen konkrétní element "33 To se mi líbí".
                        if (txt.length < 40) {
                            likesStr = txt;
                            break;
                        }
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
        """

        js_scroll_comments = """
        () => {
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
        }
        """

        for scroll_attempt in range(12):
            try:
                load_more = self.bot.page.locator('svg[aria-label="Načíst další komentáře"], svg[aria-label="Load more comments"]').first
                if load_more.is_visible(timeout=500):
                    load_more.locator('xpath=./ancestor::button | ./ancestor::div[@role="button"]').first.click(force=True)
                    delay(1.5, 2.5)
            except: pass

            extracted_data = self.bot.page.evaluate(js_extract_comments)
            
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
                self.bot.page.evaluate(js_scroll_comments)
            except: pass
            delay(1.5, 2.5)

    def scrape_profile(self, target_query, limit=10, comments_limit=50, followers_limit=50, following_limit=50):
        limit_text = "NEOMEZENO" if limit == -1 else str(limit)
        print(f"[IG-SCRAPER] Zahajuji simulaci lidského vyhledávání: '{target_query}' (Limit: {limit_text} P / {comments_limit} K / {followers_limit} S / {following_limit} S)")

        if "instagram.com" not in self.bot.page.url:
            self.bot.open_url(self.bot.base_url)
            delay(2, 4)

        search_icon = self.bot.page.locator('svg[aria-label="Hledat"]').first
        if search_icon.count() == 0:
            search_icon = self.bot.page.locator('svg[aria-label="Search"]').first

        if search_icon.count() > 0:
            print("[IG-SCRAPER] Klikám na záložku Hledání (Lupa)...")
            try:
                search_icon.locator('xpath=./ancestor::a').first.click(force=True)
            except:
                search_icon.click(force=True)
            delay(2, 4)

            search_box = self.bot.page.locator('input').first
            
            if search_box.count() > 0:
                print("[IG-SCRAPER] Vyhledávací pole nalezeno, simuluji psaní...")
                search_box.click()
                delay(0.5, 1.5)
                
                search_box.fill("")
                search_box.press_sequentially(target_query, delay=150)
                print("[IG-SCRAPER] Dopsáno, čekám na dynamické výsledky...")
                delay(4, 6)
                
                found_profile = False
                ignore_list = ['explore', 'reels', 'direct', 'stories', 'tags', 'locations', 'p', 'your_activity', 'saved', 'settings', 'accounts', 'language']
                
                current_links = self.bot.page.locator('a').all()
                for link in current_links:
                    if link.is_visible():
                        href = link.get_attribute('href')
                        if href and (href.startswith('https://www.instagram.com/') or href.startswith('/')):
                            path = href.replace('https://www.instagram.com', '').split('?')[0].strip('/')
                            
                            if path and '/' not in path:
                                if path not in ignore_list and path != self.bot.username:
                                    if link.inner_text().strip():
                                        print(f"[IG-SCRAPER] Nalezen profil (/{path}/), přecházím na něj.")
                                        link.click(force=True)
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

        current_url = self.bot.page.url
        try:
            actual_username = current_url.split('instagram.com/')[-1].split('/')[0].split('?')[0]
        except:
            actual_username = target_query.replace('@', '').replace(' ', '')

        print("[IG-SCRAPER] Stahuji data o uživateli...")
        
        # Komplexní extrakce profilu přes Javascript s lepším filtrováním
        profile_js = """
        () => {
            let header = document.querySelector('header');
            if (!header) return {};
            
            let data = {
                followers: "0",
                following: "0",
                bio: "",
                display_name: "",
                website: "",
                profile_pic_url: "",
                is_verified: 0,
                texts: []
            };
            
            // Followers
            let flw_link = header.querySelector('a[href*="/followers/"]');
            if (flw_link) {
                let span = flw_link.querySelector('span[title]');
                if (span) data.followers = span.getAttribute('title');
                else data.followers = flw_link.innerText;
            }
            
            // Following
            let flg_link = header.querySelector('a[href*="/following/"]');
            if (flg_link) {
                let span = flg_link.querySelector('span:not([dir])');
                if (span) data.following = span.innerText;
                else data.following = flg_link.innerText;
            }
            
            // Verifikace
            if (header.querySelector('svg[aria-label="Ověřeno"], svg[aria-label="Verified"]')) {
                data.is_verified = 1;
            }
            
            // Web
            let web_link = header.querySelector('a[target="_blank"]');
            if (web_link) {
                data.website = web_link.innerText.trim();
            }
            
            // Profilovka
            let img = header.querySelector('img');
            if (img) data.profile_pic_url = img.getAttribute('src');
            
            // Extrakce všech textových elementů pro jméno a bio
            let dirEls = Array.from(header.querySelectorAll('span[dir="auto"], h1[dir="auto"], h2[dir="auto"], div[dir="auto"]'));
            
            for(let el of dirEls) {
                let t = el.innerText.trim();
                if(!t) continue;
                
                let tLow = t.toLowerCase();
                
                // Opravené a přísnější filtrování tlačítek a statistik (zachytí i "Sleduji (47)")
                let isStat = tLow.includes('příspěvky') || tLow.includes('sledující') || tLow.includes('sleduji') ||
                             tLow.includes('posts') || tLow.includes('followers') || tLow.includes('following');
                
                let isBtn = ['sledovat', 'zpráva', 'follow', 'message', 'přidat do příběhu', 'add to story'].includes(tLow);
                
                if (isStat || isBtn) continue;
                
                if (!data.texts.includes(t)) {
                    data.texts.push(t);
                }
            }
            
            return data;
        }
        """
        
        try:
            profile_data = self.bot.page.evaluate(profile_js)
            
            followers_count = self.parse_number(profile_data.get('followers', '0'))
            following_count = self.parse_number(profile_data.get('following', '0'))
            
            display_name = actual_username
            bio = ""
            website = profile_data.get('website', None)
            
            # Očištění posbíraných textů a jejich přiřazení
            texts = profile_data.get('texts', [])
            clean_texts = []
            for t in texts:
                if t.lower() == actual_username.lower(): continue # Vynecháme username
                if website and t == website: continue             # Vynecháme web
                if re.match(r'^[\d\s,]+(?:mil\.|tis\.|m|k)?$', t.lower().replace('\xa0', ' ')): continue # Zbloudilá čísla
                clean_texts.append(t)
                
            # Pokud zbyly texty: první je obvykle jméno (display name), druhý a další je bio
            if len(clean_texts) > 0:
                display_name = clean_texts[0]
                if len(clean_texts) > 1:
                    bio = "\n".join(clean_texts[1:])
            
            is_verified = profile_data.get('is_verified', 0)
            profile_pic_url = profile_data.get('profile_pic_url', None)

        except Exception as e:
            print(f"[ERROR] Selhala extrakce metadat profilu: {e}")
            followers_count, following_count, is_verified = 0, 0, 0
            display_name = actual_username
            bio, website, profile_pic_url = "", None, None

        # Uložení rozšířených dat do DB
        user_id = self.db.upsert_user(
            platform="IG",
            username=actual_username,
            display_name=display_name,
            bio=bio,
            followers_count=followers_count,
            following_count=following_count,
            website=website,
            is_verified=is_verified,
            profile_pic_url=profile_pic_url
        )
        print(f"[IG-SCRAPER] Profil uložen do DB (Sledujících: {followers_count}). Interní ID: {user_id}")

        print("[IG-SCRAPER] Skenuji zeď a sbírám URL příspěvků...")
        
        urls_to_scrape = []
        scroll_attempts_without_new = 0
        max_scroll_loops = 500 if limit == -1 else 100 
        
        loop_counter = 0
        while True:
            all_links = self.bot.page.locator('a').all()
            new_found = False
            
            for link in all_links:
                href = link.get_attribute('href')
                if href and ('/p/' in href or '/reel/' in href):
                    clean_href = href.split('?')[0]
                    full_url = f"https://www.instagram.com{clean_href}" if clean_href.startswith('/') else clean_href
                    
                    if full_url not in urls_to_scrape:
                        urls_to_scrape.append(full_url)
                        new_found = True
                        
                        if limit != -1 and len(urls_to_scrape) >= limit:
                            break
            
            print(f"  -> Nalezeno {len(urls_to_scrape)} unikátních příspěvků...")

            if limit != -1 and len(urls_to_scrape) >= limit:
                print(f"[IG-SCRAPER] Dosažen požadovaný limit {limit}.")
                break
            
            if not new_found:
                scroll_attempts_without_new += 1
                if scroll_attempts_without_new >= 4:
                    print("[IG-SCRAPER] Zdá se, že jsme na konci profilu (žádné nové příspěvky).")
                    break
            else:
                scroll_attempts_without_new = 0

            loop_counter += 1
            if limit == -1 and loop_counter > max_scroll_loops:
                print("[WARNING] Dosažen interní bezpečnostní limit scrollu.")
                break

            self.bot.page.evaluate("window.scrollBy(0, 800)")
            delay(1.5, 3.0)

        final_urls = urls_to_scrape[:limit] if limit != -1 else urls_to_scrape
        
        if not final_urls:
            print("[IG-SCRAPER] Nebyly nalezeny žádné příspěvky (profil je soukromý nebo prázdný).")
            return
            
        if followers_limit > 0:
            self._scrape_network(actual_username, followers_limit, "followers")
        if following_limit > 0:
            self._scrape_network(actual_username, following_limit, "following")

        print(f"\n[IG-SCRAPER] Zahajuji hloubkovou těžbu {len(final_urls)} příspěvků...")
        for i, url in enumerate(final_urls):
            print(f"--- Zpracovávám {i+1} z {len(final_urls)} ---")
            try:
                self.scrape_post_and_comments(user_id, url, comments_limit)
            except Exception as e:
                print(f"[IG-SCRAPER] Chyba při těžbě příspěvku {url}: {e}")

        print("\n[IG-SCRAPER] Kompletní těžba cílového IG profilu a komentářů byla úspěšně dokončena.")

    def _scrape_network(self, username, limit, mode):
        if limit <= 0: return
        
        conn_type = "follower" if mode == "followers" else "following"
        type_cs = "Sledujících" if mode == "followers" else "Sledovaných"
        print(f"\n[IG-NETWORK] --- Těžba {type_cs} pro @{username} (Limit: {limit}) ---")
        
        try:
            if f"/{username}/" not in self.bot.page.url:
                self.bot.open_url(f"{self.bot.base_url}{username}/")
                delay(2, 4)

            link = self.bot.page.locator(f'header a[href*="/{mode}/"]').first
            if link.is_visible(timeout=5000):
                link.click()
            else:
                print(f"[IG-NETWORK] Tlačítko {type_cs} nebylo nalezeno.")
                return

            dialog = self.bot.page.locator('div[role="dialog"]').first
            dialog.wait_for(state="visible", timeout=8000)
            delay(2, 4)

        except Exception as e:
            print(f"[IG-NETWORK] Nelze otevřít seznam {type_cs}: {e}")
            return

        collected = 0
        processed = set()
        scroll_attempts = 0

        # JS injekce zaměřená čistě na izolované posouvání uvnitř Modalu
        js_extract = """
        () => {
            let dialog = document.querySelector('div[role="dialog"]');
            if (!dialog) return {users: [], scrolled: false};

            let users = [];
            let links = dialog.querySelectorAll('a[href]');
            for (let a of links) {
                let href = a.getAttribute('href');
                if (href && href.startsWith('/') && href.split('/').length === 3) {
                    let un = href.replace(/\\//g, '');
                    if (un && !['explore', 'reels', 'direct', 'stories'].includes(un)) {
                        users.push(un);
                    }
                }
            }

            let scrolled = false;
            let divs = dialog.querySelectorAll('div');
            for (let d of divs) {
                let style = window.getComputedStyle(d);
                if (style.overflowY === 'auto' || style.overflowY === 'scroll') {
                    if (d.scrollHeight > d.clientHeight + 10) {
                        d.scrollTop += 600; 
                        scrolled = true;
                        break;
                    }
                }
            }
            return {users: [...new Set(users)], scrolled: scrolled};
        }
        """

        while collected < limit and scroll_attempts < 10:
            try:
                data = self.bot.page.evaluate(js_extract)
                new_found = False

                for target_user in data.get('users', []):
                    if target_user == username: continue
                    if collected >= limit: break

                    if target_user not in processed:
                        processed.add(target_user)
                        new_found = True
                        self.db.upsert_connection("IG", username, target_user, conn_type)
                        collected += 1
                        print(f"  -> Uložen záznam ({conn_type}): @{target_user} ({collected}/{limit})")

                if not new_found: scroll_attempts += 1
                else: scroll_attempts = 0

                delay(1.5, 3.0)
            except Exception as e:
                print(f"[IG-NETWORK] Chyba při těžbě modal okna: {e}")
                break

        print(f"[IG-NETWORK] Těžba {type_cs} dokončena.")
        
        try:
            close_btn = self.bot.page.locator('div[role="dialog"] button, css:svg[aria-label="Zavřít"], css:svg[aria-label="Close"]').first
            if close_btn.is_visible(timeout=1000): close_btn.click(force=True)
            delay(1)
        except: pass
```

## Soubor: social_bot\src\bots\instagram\__init__.py
```py
from .bot import InstagramBot
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
        
        # Playwright využívá metodu goto s nastavením chování při načítání
        try:
            self.bot.page.goto(self.base_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"[X] Varování při načítání úvodní stránky: {e}")
            
        delay(4, 6) 

        is_logged_in = False
        
        try:
            # Selektory přepsány do standardního formátu pro Playwright
            if self.bot.page.locator('[aria-label="Timeline: Your Home Timeline"]').is_visible(timeout=5000):
                is_logged_in = True
            elif self.bot.page.locator('[aria-label="Profile"]').is_visible(timeout=2000):
                 is_logged_in = True
            elif "/home" in self.bot.page.url:
                 is_logged_in = True
        except:
            pass

        if is_logged_in:
            print("[X] Úspěšně ověřeno: Již přihlášeno (ze session).")
            return
        
        print("[X] Session nenalezena, jdu se přihlásit...")
        try:
            self.bot.page.goto(self.base_url + "i/flow/login", wait_until="domcontentloaded", timeout=30000)
        except:
            pass
        delay(3)
        
        username_input = self.bot.page.locator('[autocomplete="username"]').first
        try:
            # Playwright vyžaduje explicitní čekání na stav elementu, pokud nevyužíváme auto-waiting akce
            username_input.wait_for(state="visible", timeout=10000)
            print("[X] Zadávám uživatelské jméno...")
            
            # press_sequentially nahrazuje původní iterativní human_typing
            username_input.press_sequentially(self.bot.username, delay=150)
            delay(1, 2)
            
            next_xpath = "//span[text()='Next' or text()='Další']"
            self.bot.click_smart(next_xpath, "Tlačítko Další")
            delay(2, 3)
        except Exception as e:
            print(f"[X] Pole pro username nebylo včas nalezeno: {e}")

        password_input = self.bot.page.locator('[name="password"]').first
        try:
            password_input.wait_for(state="visible", timeout=10000)
            print("[X] Zadávám heslo...")
            
            password_input.press_sequentially(self.bot.password, delay=150)
            delay(1, 2)
            
            login_xpath = "//span[text()='Log in' or text()='Přihlásit se']"
            self.bot.click_smart(login_xpath, "Tlačítko Login")
            delay(5, 8)
            
            self.bot.handle_popups(['Refuse', 'Odmítnout', 'Accept all', 'Povolit'])
            
            print("[X] Přihlášení dokončeno, ukládám session...")
            delay(3)
        except Exception as e:
            print(f"[X] Pole pro heslo nebylo včas nalezeno: {e}")
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
from .modules.network import XNetworkModule
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

class XScraper:
    def __init__(self, bot):
        self.bot = bot
        self.db = DatabaseManager()
        
        self.search_module = XSearchModule(bot, self.db)
        self.profile_module = XProfileModule(bot, self.db)
        self.posts_module = XPostsModule(bot, self.db)
        self.comments_module = XCommentsModule(bot, self.db)
        self.network_module = XNetworkModule(bot, self.db)

    def scrape_profile(self, target_query, limit=10, comments_limit=50, followers_limit=50, following_limit=50):
        limit_text = "NEOMEZENO" if limit == -1 else str(limit)
        
        # Drobná úprava printu, aby ukazoval i limit sledujících
        print(f"[X-SCRAPER] Cíl: '{target_query}' (Limit: {limit_text} P / {comments_limit} K / {followers_limit} S)")
        
        if not self.search_module.find_profile(target_query):
            print(f"[ERROR] Profil '{target_query}' nebyl nalezen ani přes Google.")
            return

        try:
            current_url = self.bot.page.url
            if "x.com/" in current_url:
                actual_username = current_url.split('x.com/')[-1].split('?')[0].split('/')[0]
            else:
                actual_username = target_query.replace('@', '').replace(' ', '')
        except:
            actual_username = target_query.replace('@', '').replace(' ', '')

        user_id = self.profile_module.scrape_metadata(actual_username)

        videos_queue, comments_queue = self.posts_module.scrape_timeline(user_id, limit)

        if videos_queue:
            self.posts_module.process_videos(videos_queue)

        if comments_queue:
            self.comments_module.scrape_for_queue(comments_queue, limit=comments_limit)
        else:
            print("[X-SCRAPER] Žádné příspěvky ke zpracování komentářů.")
            
        if followers_limit > 0:
            self.network_module.scrape_followers(actual_username, limit=followers_limit)
            
        if following_limit > 0:
            self.network_module.scrape_following(actual_username, limit=following_limit)

        print("\n[X-SCRAPER] Hotovo.")

    def scrape_trending(self):
        print("[X-SCRAPER] Těžba trendů...")
        try:
            self.bot.page.goto("https://x.com/explore/tabs/trending", wait_until="domcontentloaded", timeout=30000)
        except PlaywrightTimeoutError:
            print("[X-SCRAPER] Varování: Timeout při načítání stránky trendů.")

        trends_locator = self.bot.page.locator('[data-testid="trend"]')
        
        try:
            trends_locator.first.wait_for(state="visible", timeout=6000)
        except PlaywrightTimeoutError:
            print("[X-SCRAPER] Trendy se nenačetly.")
            return
            
        trends = trends_locator.all()
        print(f"[X-SCRAPER] Nalezeno {len(trends)} trendů.")
        
        for index, trend in enumerate(trends):
            try:
                # Playwright používá inner_text() pro zachování formátování s novými řádky
                text_content = trend.inner_text()
                if not text_content:
                    continue
                    
                text = text_content.split('\n')
                topic = text[1] if len(text) > 1 else text[0]
                count = text[-1] if "posts" in text[-1] else "N/A"
                
                self.db.upsert_trend("X", index+1, "General", topic, count)
                print(f"  -> #{index+1} {topic}")
            except Exception:
                pass
```

## Soubor: social_bot\src\bots\x\__init__.py
```py
from .bot import XBot
```

## Soubor: social_bot\src\bots\x\modules\comments.py
```py
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
```

## Soubor: social_bot\src\bots\x\modules\network.py
```py
from src.utils.human_input import delay
import re

class XNetworkModule:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    def scrape_followers(self, username, limit=50):
        self._scrape_users_list(username, "followers", "follower", limit)

    def scrape_following(self, username, limit=50):
        self._scrape_users_list(username, "following", "following", limit)

    def _scrape_users_list(self, username, endpoint, conn_type, limit):
        if limit <= 0: return
        
        type_cs = "Sledujících" if conn_type == "follower" else "Sledovaných"
        print(f"\n[X-NETWORK] --- Těžba {type_cs} pro @{username} (Limit: {limit}) ---")
        
        try:
            self.bot.page.goto(f"https://x.com/{username}/{endpoint}", wait_until="domcontentloaded", timeout=15000)
            self.bot.page.locator('[data-testid="primaryColumn"]').first.wait_for(state="visible", timeout=10000)
            delay(2, 4)
        except Exception as e:
            print(f"[X-NETWORK] Nelze načíst seznam {type_cs}: {e}")
            return

        collected = 0
        processed = set()
        scroll_attempts = 0

        while collected < limit and scroll_attempts < 15:
            cells = self.bot.page.locator('[data-testid="UserCell"]').all()
            new_found = False

            for cell in cells:
                if collected >= limit: break
                try:
                    # Načteme veškerý text z buňky daného uživatele
                    text_content = cell.inner_text()
                    
                    # Robustní hledání handle pomocí regulárního výrazu (hledá slovo začínající na @)
                    match = re.search(r'@([a-zA-Z0-9_]+)', text_content)
                    
                    if match:
                        target_user = match.group(1).strip()
                        
                        # Zabráníme uložení sebe sama a duplikátů
                        if target_user and target_user.lower() != username.lower() and target_user not in processed:
                            processed.add(target_user)
                            new_found = True
                            
                            # Uložení do databáze do naší sítě (Connections)
                            self.db.upsert_connection("X", username, target_user, conn_type)
                            
                            collected += 1
                            print(f"  -> Uložen záznam ({conn_type}): @{target_user} ({collected}/{limit})")
                except Exception: 
                    continue

            if not new_found: 
                scroll_attempts += 1
            else: 
                scroll_attempts = 0

            if collected < limit:
                self.bot.page.evaluate("window.scrollBy(0, 1000)")
                delay(1.5, 3.0)

        print(f"[X-NETWORK] Těžba {type_cs} dokončena.")
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
        print("[X-POSTS] Sbírám příspěvky...")
        posts_collected = 0
        processed_post_ids = set()
        
        posts_to_process_video = []
        posts_for_comments = []
        
        scroll_attempts_without_new = 0
        
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
                    
                    # Nalezení nadřazeného odkazu k tagu time
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

                    db_post_id = self.db.upsert_post(user_id, "X", platform_post_id, post_text, timestamp, likes, shares, comments, full_url, media_url)
                    posts_collected += 1
                    
                    print(f"[X-POSTS] ({posts_collected}) Tweet: {platform_post_id} | Video: {is_video}")
                    
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

            # NOVÉ: Logika proti zacyklení
            if not new_in_batch:
                scroll_attempts_without_new += 1
                if scroll_attempts_without_new >= 4:
                    print("[X-POSTS] Dosažen konec profilu nebo účet nemá (další) příspěvky.")
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
        video_url = None
        
        def handle_response(response):
            nonlocal video_url
            try:
                # 1. Analýza GraphQL
                if "graphql" in response.url:
                    # Klíčová oprava: odstranění escapování lomítek z JSONu
                    text_body = response.text().replace('\\/', '/')
                    
                    # Zachytáváme .mp4 i .m3u8
                    links = re.findall(r'(https://video\.twimg\.com/[^"\'\s]+\.(?:mp4|m3u8))', text_body)
                    
                    if links:
                        # Prioritizace .mp4 před .m3u8, pokud jsou k dispozici oba formáty
                        mp4s = [l for l in links if l.endswith('.mp4')]
                        video_url = mp4s[0] if mp4s else links[0]
                
                # 2. Záchranná síť pro přímé requesty přehrávače
                elif not video_url and "video.twimg.com" in response.url:
                    if ".mp4" in response.url or ".m3u8" in response.url:
                        video_url = response.url
            except:
                pass

        self.bot.page.on("response", handle_response)
        
        try:
            self.bot.page.goto(post_url, wait_until="domcontentloaded", timeout=15000)
            
            # Vynucené kliknutí na video pro spuštění přehrávání a odeslání requestu
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
        print(f"[X-PROFILE] Těžím metadata pro @{actual_username}...")
        
        try:
            display_name_loc = self.bot.page.locator('[data-testid="UserName"]').first
            if display_name_loc.count() > 0:
                display_name = display_name_loc.inner_text().split('\n')[0]
                is_verified = 1 if display_name_loc.locator('svg[aria-label="Verified account"]').count() > 0 else 0
            else:
                display_name = actual_username
                is_verified = 0

            bio_loc = self.bot.page.locator('[data-testid="UserDescription"]').first
            bio = bio_loc.inner_text() if bio_loc.count() > 0 else ""
            
            loc_ele = self.bot.page.locator('[data-testid="UserLocation"]').first
            location = loc_ele.inner_text() if loc_ele.count() > 0 else None

            web_ele = self.bot.page.locator('[data-testid="UserUrl"]').first
            website = web_ele.inner_text() if web_ele.count() > 0 else None

            join_ele = self.bot.page.locator('[data-testid="UserJoinDate"]').first
            joined_date = join_ele.inner_text() if join_ele.count() > 0 else None

            followers_ele = self.bot.page.locator('xpath=//a[contains(@href, "/followers")]/span[1] | //a[contains(@href, "/verified_followers")]/span[1]').first
            followers_count = XUtils.parse_number(followers_ele.inner_text() if followers_ele.count() > 0 else "0")

            following_ele = self.bot.page.locator('xpath=//a[contains(@href, "/following")]/span[1]').first
            following_count = XUtils.parse_number(following_ele.inner_text() if following_ele.count() > 0 else "0")

            banner_url = None
            try:
                banner_link = self.bot.page.locator('xpath=//a[contains(@href, "/header_photo")]//img').first
                if banner_link.count() > 0:
                    banner_url = banner_link.get_attribute('src')
            except: pass

            profile_pic_url = self._get_hd_profile_pic()

        except Exception as e:
            print(f"[ERROR] Chyba čtení metadat: {e}")
            display_name = actual_username; bio = ""; followers_count = 0; following_count = 0
            location = None; website = None; joined_date = None; is_verified = 0; banner_url = None; profile_pic_url = None

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
            avatar_img = self.bot.page.locator('img[alt="Opens profile photo"]').first
            if avatar_img.count() == 0: 
                avatar_img = self.bot.page.locator('img[alt="Square profile picture and Opens profile photo"]').first
            if avatar_img.count() == 0: 
                avatar_img = self.bot.page.locator('xpath=//div[contains(@data-testid, "UserAvatar-Container")]//img').first
            
            if avatar_img.count() > 0:
                profile_pic_url = avatar_img.get_attribute('src')
                if profile_pic_url and any(x in profile_pic_url for x in ['_bigger', '_mini', '_normal']):
                    photo_link = self.bot.page.locator('xpath=//div[contains(@data-testid, "UserAvatar-Container")]//a[contains(@href, "/photo")]').first
                    if photo_link.count() > 0:
                        photo_link.click()
                        large_img = self.bot.page.locator('xpath=//div[@data-testid="swipe-to-dismiss"]//img').first
                        large_img.wait_for(state="visible", timeout=3000)
                        if large_img.count() > 0:
                            profile_pic_url = large_img.get_attribute('src')
                        
                        close_btn = self.bot.page.locator('div[aria-label="Close"], div[aria-label="Zavřít"]').first
                        if close_btn.count() > 0: 
                            close_btn.click()
                        else: 
                            self.bot.page.go_back()
                        delay(0.5)
        except: pass
        return profile_pic_url
```

## Soubor: social_bot\src\bots\x\modules\search.py
```py
from src.utils.human_input import delay
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

class XSearchModule:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    def find_profile(self, target_query):
        print("[X-SEARCH] 1. Krok: Kontrola lokální databáze...")
        known_handle = self.db.get_known_handle(target_query)
        if known_handle:
            print(f"[DATABASE] Nalezen uložený handle: @{known_handle}. Jdu na jistotu.")
            self.bot.open_url(f"{self.bot.base_url}{known_handle}")
            delay(2, 4)
            try:
                if self.bot.page.locator('[data-testid="UserName"]').first.is_visible(timeout=5000):
                    return True
            except:
                pass
        
        print("[X-SEARCH] 2. Krok: Interní vyhledávání na X...")
        if self._internal_search(target_query):
            return True
            
        print("[X-SEARCH] 3. Krok: Interní hledání selhalo. Volám Google Search...")
        if self._google_search_fallback(target_query):
            try:
                self.bot.page.locator('[data-testid="UserName"]').first.wait_for(state="visible", timeout=8000)
                return True
            except:
                pass
        
        return False

    def _internal_search(self, target_query):
        if "search" not in self.bot.page.url and "explore" not in self.bot.page.url:
            self.bot.open_url(self.bot.base_url + "explore")
            delay(1.5, 2.5)

        try:
            search_box = self.bot.page.locator('[data-testid="SearchBox_Search_Input"]').first
            search_box.wait_for(state="visible", timeout=5000)
            
            search_box.click()
            search_box.fill("")
            search_box.press_sequentially(target_query, delay=100)
            delay(0.5)
            search_box.press("Enter")
            
            people_tab = self.bot.page.locator("xpath=//span[text()='People' or text()='Lidé']").first
            try:
                people_tab.wait_for(state="visible", timeout=4000)
                people_tab.click()
                delay(1.5, 3)
            except PlaywrightTimeoutError:
                pass
            
            first_user = self.bot.page.locator('[data-testid="UserCell"]').first
            first_user.wait_for(state="visible", timeout=4000)
            
            print("[X-SEARCH] Profil nalezen v interním hledání. Klikám.")
            first_user.click()
            
            self.bot.page.locator('[data-testid="UserName"]').first.wait_for(state="visible", timeout=6000)
            return True
        except Exception:
            return False

    def _google_search_fallback(self, target_query):
        print(f"[GOOGLE] Spouštím záchranné vyhledávání pro: '{target_query}'")
        try:
            self.bot.open_url("https://www.google.com")
            self.bot.handle_popups(['Přijmout vše', 'Accept all', 'Souhlasím', 'I agree'])
            
            search_input = self.bot.page.locator('textarea[name="q"], input[name="q"]').first
            search_input.fill(f"{target_query} twitter")
            delay(0.5)
            search_input.press("Enter")
            
            print("[GOOGLE] Čekám na výsledky...")
            delay(2, 3)
            
            results = self.bot.page.locator('a').all()
            for res in results:
                href = res.get_attribute('href')
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
    def extract_media(article_locator, current_text):
        """Vrátí tuple (updated_text, media_url, is_video)"""
        media_url = None
        is_video = False
        
        try:
            # 1. Hledáme primárně explicitní video přehrávač nebo tag video
            video_loc = article_locator.locator('[data-testid="videoPlayer"], video').first
            photo_loc = article_locator.locator('[data-testid="tweetPhoto"]').first
            
            if video_loc.count() > 0:
                is_video = True
                
                # Zjištění, zda je nalezený element přímo video tag
                is_video_tag = video_loc.evaluate("el => el.tagName.toLowerCase() === 'video'")
                if is_video_tag:
                    media_url = video_loc.get_attribute('poster')
                else:
                    poster_video = video_loc.locator('video').first
                    if poster_video.count() > 0:
                        media_url = poster_video.get_attribute('poster')
                
                if not current_text.strip():
                    current_text = "[OBSAHUJE VIDEO]"
                    
            # 2. Pokud se tváří jako fotka, zkontrolujeme ji
            elif photo_loc.count() > 0:
                img_loc = photo_loc.locator('img').first
                if img_loc.count() > 0:
                    media_url = img_loc.get_attribute('src')
                    
                    # Záchranná detekce: X často lazy-loaduje videa jako statické obrázky
                    # Pokud URL obsahuje text indikující náhled videa, přehodnotíme to
                    if media_url and ('video_thumb' in media_url or 'ext_tw_video' in media_url):
                        is_video = True
                        if not current_text.strip():
                            current_text = "[OBSAHUJE VIDEO]"
                            
                # Pokud to video opravdu není, potvrdíme fotku
                if not is_video and not current_text.strip():
                    current_text = "[OBSAHUJE FOTKU]"
                    
        except Exception:
            pass
                
        return current_text, media_url, is_video
```

## Soubor: social_bot\src\bots\x\modules\__init__.py
```py

```

## Soubor: social_bot\src\core\base_bot.py
```py
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from src.utils.human_input import delay

class BaseBot:
    def __init__(self, headless=False, user_id="default", platform="general"):
        self.user_id = str(user_id)
        self.platform = platform
        
        self.playwright = sync_playwright().start()
        self.context = None
        self.page = self._setup_driver(headless)

    def _setup_driver(self, headless):
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        
        profile_folder = f"{self.user_id}_{self.platform}"
        profile_path = project_root / 'profiles' / profile_folder
        os.makedirs(profile_path, exist_ok=True)
        
        print(f"[BOT] Nastavuji izolovaný profil (Playwright): {profile_path}")
        
        args = [
            '--disable-blink-features=AutomationControlled',
            '--window-position=0,0',
            '--disable-infobars',
            '--disable-extensions'
        ]

        try:
            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_path),
                headless=headless,
                args=args,
                no_viewport=True,
                channel="chrome",
                accept_downloads=True
            )
            
            page = self.context.pages[0] if self.context.pages else self.context.new_page()
            
            # Aplikace vlastních anti-detekčních skriptů (nahrazuje playwright-stealth)
            self._apply_stealth_scripts(page)
            
            return page
            
        except Exception as e:
            print(f"[CRITICAL ERROR] Nelze spustit Playwright prohlížeč: {e}")
            if self.playwright:
                self.playwright.stop()
            raise e

    def _apply_stealth_scripts(self, page):
        """Aplikuje základní anti-detekční skripty přímo přes Playwright."""
        # Skrytí příznaku botnetu
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        # Falešné pluginy (často kontrolováno Instagramem a X)
        page.add_init_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]})")
        # Falešné jazyky
        page.add_init_script("Object.defineProperty(navigator, 'languages', {get: () => ['cs-CZ', 'cs', 'en-US', 'en']})")

    def open_url(self, url):
        print(f"[BOT] Otevírám {url}")
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            delay(3, 5)
        except Exception as e:
            print(f"[ERROR] Chyba při otevírání URL: {e}")

    def find_element_smart(self, selector, description="prvek", timeout=10):
        try:
            locator = self.page.locator(selector).first
            locator.wait_for(state="attached", timeout=timeout * 1000)
            return locator
        except PlaywrightTimeoutError:
            return None
        except Exception as e:
            print(f"[DEBUG] Chyba hledání prvku '{description}': {e}")
            return None

    def click_smart(self, selector, description="tlačítko", timeout=5):
        locator = self.find_element_smart(selector, description, timeout)
        if locator:
            try:
                locator.click(timeout=timeout * 1000)
                return True
            except:
                try:
                    locator.click(force=True, timeout=timeout * 1000)
                    return True
                except:
                    pass
        return False
        
    def handle_popups(self, triggers):
        for text in triggers:
            try:
                locator = self.page.get_by_text(text, exact=False).first
                if locator.is_visible(timeout=500):
                    locator.click(force=True)
                    print(f"[BOT] Odkliknuto vyskakovací okno: '{text}'")
                    delay(1)
                    return True
            except:
                pass
        return False

    def close(self):
        if getattr(self, 'context', None) is None:
            return
            
        print(f"[BOT] Ukládám profil {self.user_id}_{self.platform} a zavírám (Playwright)...")
        try:
            self.context.close()
            if self.playwright:
                self.playwright.stop()
            self.context = None
            self.page = None
            print("[BOT] Uloženo.")
        except Exception:
            pass
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
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS connections (
                id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                source_username TEXT NOT NULL,
                target_username TEXT NOT NULL,
                connection_type TEXT NOT NULL,
                scraped_at TIMESTAMP,
                UNIQUE(platform, source_username, target_username, connection_type)
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
        
    def upsert_connection(self, platform, source_username, target_username, connection_type="follower"):
        now = datetime.now(timezone.utc).isoformat()
        self.cursor.execute('''
            SELECT id FROM connections 
            WHERE platform = ? AND source_username = ? AND target_username = ? AND connection_type = ?
        ''', (platform, source_username, target_username, connection_type))
        row = self.cursor.fetchone()
        
        if row:
            conn_id = row[0]
            self.cursor.execute('UPDATE connections SET scraped_at = ? WHERE id = ?', (now, conn_id))
        else:
            conn_id = str(uuid.uuid4())
            self.cursor.execute('''
                INSERT INTO connections (id, platform, source_username, target_username, connection_type, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (conn_id, platform, source_username, target_username, connection_type, now))
        self.conn.commit()
        return conn_id

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

    # --- BOT LOGIC ---
    def start_thread(self, platform, action):
        if self.is_running: messagebox.showwarning("Busy", "Bot již běží."); return
        
        key = self.frame_dash.user_var.get()
        if not key: messagebox.showerror("Chyba", "Vyber identitu."); return
        
        user_data = self.users_map[key]
        social = user_data.get('social_media', {}).get(platform)
        if not social: messagebox.showerror("Chyba", f"Identita nemá {platform}."); return
        
        target_input = self.frame_dash.target_var.get().strip()
        if action == "scrape" and not target_input: messagebox.showwarning("Chyba", "Zadej cíl."); return
        
        # Načtení limitů
        limit = 10
        if self.frame_dash.scrape_all_var.get(): 
            limit = -1
        else:
            try: limit = int(self.frame_dash.limit_var.get())
            except ValueError: messagebox.showerror("Chyba", "Limit příspěvků musí být číslo."); return
            
        try: comments_limit = int(self.frame_dash.comments_limit_var.get())
        except ValueError: messagebox.showerror("Chyba", "Limit komentářů musí být číslo."); return
        
        self.is_running = True
        txt_limit = "VŠE" if limit == -1 else str(limit)
        self.status_label.configure(text=f"● Běží: {platform} {action} (P: {txt_limit}, K: {comments_limit})", text_color=COLORS["primary"])

        try: followers_limit = int(self.frame_dash.followers_limit_var.get())
        except ValueError: messagebox.showerror("Chyba", "Limit sledujících musí být číslo."); return
        
        try: following_limit = int(self.frame_dash.following_limit_var.get())
        except ValueError: messagebox.showerror("Chyba", "Limit 'Sleduje' musí být číslo."); return
        
        self.is_running = True
        txt_limit = "VŠE" if limit == -1 else str(limit)
        self.status_label.configure(text=f"● Běží: {platform} {action} (P: {txt_limit}, K: {comments_limit}, SE: {followers_limit}, SD: {following_limit})", text_color=COLORS["primary"])
        
        # Vyčištění logu a start vlákna s novým argumentem
        self.frame_dash.log_box.configure(state="normal")
        self.frame_dash.log_box.delete(1.0, tk.END)
        self.frame_dash.log_box.configure(state="disabled")
        # Odeslání do threadu (přidán argument following_limit)
        threading.Thread(target=self.run_bot, args=(platform, social['username'], social['password'], key.split()[0], action, target_input, limit, comments_limit, followers_limit, following_limit), daemon=True).start()

    def run_bot(self, platform, u, p, uid, action, target_input, limit, comments_limit, followers_limit, following_limit):
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
                        bot.scraper.scrape_profile(target, limit, comments_limit, followers_limit, following_limit)
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
            # Změna: Záměrně zde nevoláme self.current_bot.close().
            # Vlákno (run_bot) si po změně is_running na False 
            # samo vyskočí ze smyček a zavře prohlížeč bezpečně ve svém bloku finally.
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
        self.controller = controller
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

        # Limity (Kontejner pro všechny čtyři limity vedle sebe)
        limits_container = ctk.CTkFrame(input_container, fg_color="transparent")
        limits_container.pack(fill="x")
        limits_container.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # -- Sloupec 1: Příspěvky --
        limit_frame = ctk.CTkFrame(limits_container, fg_color="transparent")
        limit_frame.grid(row=0, column=0, sticky="nw", padx=(0, 5))
        ctk.CTkLabel(limit_frame, text="PŘÍSPĚVKY", font=("Segoe UI", 11, "bold"), text_color=COLORS["text_dim"]).pack(anchor="w", pady=(0, 5))
        
        limit_inner = ctk.CTkFrame(limit_frame, fg_color="transparent")
        limit_inner.pack(fill="x")
        
        self.scrape_all_var = ctk.BooleanVar(value=False)
        self.chk_all = ctk.CTkCheckBox(limit_inner, text="Vše", variable=self.scrape_all_var, command=self.toggle_limit_entry, fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"], border_color=COLORS["border"], font=("Segoe UI", 13), width=45)
        self.chk_all.pack(side="left", padx=(0, 5))
        
        self.limit_var = ctk.StringVar(value="10")
        self.limit_entry = ctk.CTkEntry(limit_inner, textvariable=self.limit_var, width=50, height=35, font=("Segoe UI", 13), border_color=COLORS["border"], fg_color=COLORS["panel_bg"], text_color=COLORS["text_main"])
        self.limit_entry.pack(side="left")

        # -- Sloupec 2: Komentáře --
        comm_limit_frame = ctk.CTkFrame(limits_container, fg_color="transparent")
        comm_limit_frame.grid(row=0, column=1, sticky="nw", padx=5)
        ctk.CTkLabel(comm_limit_frame, text="KOMENTÁŘE", font=("Segoe UI", 11, "bold"), text_color=COLORS["text_dim"]).pack(anchor="w", pady=(0, 5))
        
        self.comments_limit_var = ctk.StringVar(value="50")
        self.comments_limit_entry = ctk.CTkEntry(comm_limit_frame, textvariable=self.comments_limit_var, width=70, height=35, font=("Segoe UI", 13), border_color=COLORS["border"], fg_color=COLORS["panel_bg"], text_color=COLORS["text_main"])
        self.comments_limit_entry.pack(side="left")

        # -- Sloupec 3: Sledující (Followers) --
        fol_limit_frame = ctk.CTkFrame(limits_container, fg_color="transparent")
        fol_limit_frame.grid(row=0, column=2, sticky="nw", padx=5)
        ctk.CTkLabel(fol_limit_frame, text="SLEDUJÍCÍ", font=("Segoe UI", 11, "bold"), text_color=COLORS["text_dim"]).pack(anchor="w", pady=(0, 5))
        
        self.followers_limit_var = ctk.StringVar(value="50")
        self.followers_limit_entry = ctk.CTkEntry(fol_limit_frame, textvariable=self.followers_limit_var, width=70, height=35, font=("Segoe UI", 13), border_color=COLORS["border"], fg_color=COLORS["panel_bg"], text_color=COLORS["text_main"])
        self.followers_limit_entry.pack(side="left")

        # -- Sloupec 4: Sleduje (Following) --
        following_limit_frame = ctk.CTkFrame(limits_container, fg_color="transparent")
        following_limit_frame.grid(row=0, column=3, sticky="nw", padx=(5, 0))
        ctk.CTkLabel(following_limit_frame, text="SLEDUJE", font=("Segoe UI", 11, "bold"), text_color=COLORS["text_dim"]).pack(anchor="w", pady=(0, 5))
        
        self.following_limit_var = ctk.StringVar(value="50")
        self.following_limit_entry = ctk.CTkEntry(following_limit_frame, textvariable=self.following_limit_var, width=70, height=35, font=("Segoe UI", 13), border_color=COLORS["border"], fg_color=COLORS["panel_bg"], text_color=COLORS["text_main"])
        self.following_limit_entry.pack(side="left")

        # 2. AKCE
        ctk.CTkLabel(self, text="AKCE", font=("Segoe UI", 11, "bold"), text_color=COLORS["text_dim"]).pack(anchor="w", pady=(20, 5))
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
        self.tab_db.add("Síť (Connections)")

        self.tree_users = self.create_tree(self.tab_db.tab("Uživatelé"))
        self.tree_posts = self.create_tree(self.tab_db.tab("Příspěvky"))
        self.tree_trends = self.create_tree(self.tab_db.tab("Trendy"))
        self.tree_connections = self.create_tree(self.tab_db.tab("Síť (Connections)"))

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
        for t in [self.tree_users, self.tree_posts, self.tree_trends, self.tree_connections]:
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
            
            # Connections (Followers)
            cur.execute("SELECT platform, source_username, target_username, connection_type, scraped_at FROM connections ORDER BY scraped_at DESC LIMIT 1000")
            self.tree_connections['columns'] = ("Platforma", "Zdrojový Účet", "Nalezený Sledující", "Typ", "Staženo")
            for c in self.tree_connections['columns']: 
                self.tree_connections.heading(c, text=c, anchor="w")
                self.tree_connections.column(c, width=150)
            for r in cur.fetchall():
                # Formátování data pro čistší zobrazení
                date_str = r[4].split('T')[0] if r[4] else ""
                self.tree_connections.insert("", "end", values=(r[0], r[1], r[2], r[3], date_str))

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
            # Bezpečné odstranění všech nových řádků a přebytečných mezer pro kompaktní UI kartu
            clean_bio = " ".join(bio.split())
            short_bio = (clean_bio[:90] + "...") if len(clean_bio) > 90 else clean_bio
            
            # Přidán parametr justify="left" pro správné zarovnání textu
            ctk.CTkLabel(card, text=short_bio, font=("Segoe UI", 12, "italic"), 
                         text_color="#b0b0b0", anchor="w", justify="left").grid(row=2, column=1, sticky="w", padx=5, pady=(0, 5))

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

## Soubor: social_bot\src\gui\frames\__init__.py
```py

```

## Soubor: social_bot\src\utils\human_input.py
```py
import time
import random

def delay(min_seconds=1.0, max_seconds=3.0):
    """Náhodná prodleva mezi akcemi."""
    time.sleep(random.uniform(min_seconds, max_seconds))

def human_typing(locator, text):
    """
    Simuluje psaní člověka pro Playwright Locator s variabilním zpožděním.
    Slouží jako alternativa k nativnímu locator.press_sequentially(text, delay=150),
    pokud je vyžadována vyšší úroveň simulace (zcela náhodné pauzy mezi znaky).
    """
    try:
        locator.fill("") # Vyčištění pole před zápisem
        for char in text:
            # press_sequentially jednoho znaku s náhodnou mezní pauzou
            locator.press_sequentially(char, delay=int(random.uniform(10, 50)))
            time.sleep(random.uniform(0.05, 0.25))
    except Exception as e:
        print(f"[DEBUG] Chyba při human_typing: {e}")

def random_mouse_movement(page=None):
    """
    Generuje náhodné pohyby myší napříč viewportem.
    Využívá Playwright page.mouse API pro zvýšení důvěryhodnosti (stealth).
    """
    if not page:
        return
        
    try:
        viewport = page.viewport_size
        if not viewport:
            # Fallback hodnoty, pokud viewport není detekován
            width, height = 1280, 720
        else:
            width = viewport['width']
            height = viewport['height']
            
        # Provede 2 až 5 náhodných křivek/pohybů
        for _ in range(random.randint(2, 5)):
            target_x = random.randint(0, width)
            target_y = random.randint(0, height)
            
            # steps určuje plynulost (počet mezikroků při pohybu kurzoru)
            page.mouse.move(target_x, target_y, steps=random.randint(5, 15))
            time.sleep(random.uniform(0.1, 0.4))
            
    except Exception:
        pass
```