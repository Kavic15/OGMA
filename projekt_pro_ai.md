## Soubor: requirements.txt
```txt
DrissionPage
customtkinter
keyboard
pillow
requests
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
        self.base_url = "https://www.instagram.com/"

    def login(self):
        self.bot.open_url(self.base_url)
        
        # 1. Agresivní likvidace Cookies (Hunter Mode)
        print("[IG] Kontroluji Cookies okna...")
        cookie_keywords = ['Povolit', 'Odmítnout', 'Allow', 'Decline']
        for word in cookie_keywords:
            elements = self.bot.page.eles(f'text:{word}')
            for ele in elements:
                if ele.states.is_displayed:
                    try:
                        ele.click(by_js=True)
                        print(f"[IG] Odkliknuto cookie tlačítko: '{word}'")
                        delay(2)
                        break
                    except:
                        pass

        # 2. HLEDÁME VIDITELNÝ FORMULÁŘ
        print("[IG] Kontroluji stav přihlášení...")
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
            if self.bot.page.ele('css:svg[aria-label="Domů"]', timeout=3) or self.bot.page.ele('css:svg[aria-label="Home"]', timeout=1):
                print("[IG] Již přihlášeno (ze session). Přeskakuji login.")
                return
            else:
                print("[IG] Nevidím viditelný login formulář, ale ani znaky přihlášení.")
                return

        # 3. Samotný Login
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
        
        # 4. Úklid po přihlášení
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
        
        # Inicializace modulů a předání instance bota
        self.auth = InstagramAuthenticator(self)
        self.scraper = InstagramScraper(self)

    def login(self):
        self.auth.login()
```

## Soubor: social_bot\src\bots\instagram\scraper.py
```py
from src.utils.human_input import delay

class InstagramScraper:
    def __init__(self, bot):
        self.bot = bot
        # Zde později přijmeme připojení k databázi (DatabaseManager)

    def scrape_profile(self, target_username):
        print(f"[IG-SCRAPER] Připravuji se na těžbu profilu: @{target_username}")
        # Sem budeme psát logiku pro stahování dat
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
```

## Soubor: social_bot\src\bots\x\__init__.py
```py
from .bot import XBot
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

    def _connect(self):
        self.conn = sqlite3.connect(str(self.db_path))
        self.cursor = self.conn.cursor()

    def _create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                platform_user_id TEXT,
                username TEXT NOT NULL,
                display_name TEXT,
                bio TEXT,
                followers_count INTEGER,
                last_scraped TIMESTAMP,
                UNIQUE(platform, username)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
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
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
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

        # NOVÁ TABULKA: Trending témata
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS trending (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                rank INTEGER,
                category TEXT,
                topic_name TEXT NOT NULL,
                post_count TEXT,
                scraped_at TIMESTAMP,
                UNIQUE(platform, topic_name)
            )
        ''')
        
        try:
            self.cursor.execute("ALTER TABLE posts ADD COLUMN media_url TEXT")
        except sqlite3.OperationalError:
            pass 

        try:
            self.cursor.execute("ALTER TABLE comments ADD COLUMN media_url TEXT")
        except sqlite3.OperationalError:
            pass 

        self.conn.commit()

    def upsert_user(self, platform, username, platform_user_id=None, display_name=None, bio=None, followers_count=None):
        now = datetime.now(timezone.utc).isoformat()
        
        self.cursor.execute('''
            INSERT INTO users (platform, platform_user_id, username, display_name, bio, followers_count, last_scraped)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(platform, username) DO UPDATE SET
                platform_user_id = COALESCE(excluded.platform_user_id, users.platform_user_id),
                display_name = COALESCE(excluded.display_name, users.display_name),
                bio = COALESCE(excluded.bio, users.bio),
                followers_count = COALESCE(excluded.followers_count, users.followers_count),
                last_scraped = excluded.last_scraped
        ''', (platform, platform_user_id, username, display_name, bio, followers_count, now))
        
        self.conn.commit()
        
        self.cursor.execute('SELECT id FROM users WHERE platform = ? AND username = ?', (platform, username))
        return self.cursor.fetchone()[0]

    def upsert_post(self, user_id, platform_post_id, text_content, timestamp_posted, likes_count=0, shares_count=0, comments_count=0, url=None, media_url=None):
        now = datetime.now(timezone.utc).isoformat()
        
        self.cursor.execute('''
            INSERT INTO posts (user_id, platform_post_id, text_content, media_url, timestamp_posted, likes_count, shares_count, comments_count, url, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(platform_post_id) DO UPDATE SET
                media_url = COALESCE(excluded.media_url, posts.media_url),
                likes_count = excluded.likes_count,
                shares_count = excluded.shares_count,
                comments_count = excluded.comments_count,
                scraped_at = excluded.scraped_at
        ''', (user_id, platform_post_id, text_content, media_url, timestamp_posted, likes_count, shares_count, comments_count, url, now))
        
        self.conn.commit()
        
        self.cursor.execute('SELECT id FROM posts WHERE platform_post_id = ?', (platform_post_id,))
        return self.cursor.fetchone()[0]

    def upsert_comment(self, post_id, platform_comment_id, author_username, author_display_name, text_content, timestamp_posted, likes_count=0, shares_count=0, replies_count=0, media_url=None):
        now = datetime.now(timezone.utc).isoformat()
        
        self.cursor.execute('''
            INSERT INTO comments (post_id, platform_comment_id, author_username, author_display_name, text_content, media_url, timestamp_posted, likes_count, shares_count, replies_count, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(platform_comment_id) DO UPDATE SET
                media_url = COALESCE(excluded.media_url, comments.media_url),
                likes_count = excluded.likes_count,
                shares_count = excluded.shares_count,
                replies_count = excluded.replies_count,
                scraped_at = excluded.scraped_at
        ''', (post_id, platform_comment_id, author_username, author_display_name, text_content, media_url, timestamp_posted, likes_count, shares_count, replies_count, now))
        
        self.conn.commit()

    def upsert_trend(self, platform, rank, category, topic_name, post_count):
        """Vloží nebo aktualizuje trend v databázi."""
        now = datetime.now(timezone.utc).isoformat()
        
        self.cursor.execute('''
            INSERT INTO trending (platform, rank, category, topic_name, post_count, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(platform, topic_name) DO UPDATE SET
                rank = excluded.rank,
                category = excluded.category,
                post_count = excluded.post_count,
                scraped_at = excluded.scraped_at
        ''', (platform, rank, category, topic_name, post_count, now))
        
        self.conn.commit()

    def close(self):
        if self.conn:
            self.conn.close()
```

## Soubor: social_bot\src\gui\app.py
```py
import tkinter as tk
from tkinter import messagebox, ttk
import customtkinter as ctk
import threading
import json
import os
import time
import sys
import sqlite3
from pathlib import Path
from src.bots.instagram.bot import InstagramBot
from src.bots.x.bot import XBot

ctk.set_appearance_mode("Dark") 
ctk.set_default_color_theme("blue") 

class PrintLogger:
    def __init__(self, textbox, tk_app):
        self.textbox = textbox
        self.tk_app = tk_app

    def write(self, text):
        self.tk_app.after(0, self._insert_text, text)

    def _insert_text(self, text):
        self.textbox.insert(tk.END, text)
        self.textbox.see(tk.END) 

    def flush(self):
        pass

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Ogma 0.0")
        
        self.geometry("1440x900+2560+0")
        self.after(1500, self._maximize_window)
        
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        
        icon_path = project_root / 'src' / 'gui' / 'ogma_ai_logo.ico'
        if icon_path.exists():
            self.iconbitmap(str(icon_path))
            
        self.data_path = project_root / 'data' / 'users.json'
        self.db_path = project_root / 'data' / 'osint.db'
        
        self.current_bot = None 
        self.is_running = False

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.users_map = {}
        self.load_users()

        self.main_tabview = ctk.CTkTabview(self, command=self.on_tab_change)
        self.main_tabview.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.tab_control = self.main_tabview.add("Ovládání bota")
        self.tab_database = self.main_tabview.add("Databáze")

        self.setup_control_tab()
        self.setup_database_tab()

    def _maximize_window(self):
        try:
            self.state('zoomed')
        except Exception as e:
            print(f"[WARNING] Nelze maximalizovat okno: {e}")

    def setup_control_tab(self):
        top_frame = ctk.CTkFrame(self.tab_control, fg_color="transparent")
        top_frame.pack(side="top", fill="x", pady=5, padx=20)
        
        log_frame = ctk.CTkFrame(self.tab_control)
        log_frame.pack(side="bottom", fill="both", expand=True, padx=20, pady=(0, 20))

        # SEKCE 1
        identity_frame = ctk.CTkFrame(top_frame)
        identity_frame.pack(fill="x", pady=5, ipadx=10, ipady=10)

        ctk.CTkLabel(identity_frame, text="1. Identita a Přihlášení", font=("Arial", 16, "bold")).pack(pady=5)
        
        self.user_var = ctk.StringVar()
        self.user_combo = ctk.CTkComboBox(
            identity_frame, variable=self.user_var, state="readonly", 
            font=("Arial", 14), dropdown_font=("Arial", 14), width=350, height=40
        )
        self.user_combo.configure(values=list(self.users_map.keys()))
        if self.users_map:
            self.user_combo.set(list(self.users_map.keys())[0])
        self.user_combo.pack(pady=5)

        btn_login_frame = ctk.CTkFrame(identity_frame, fg_color="transparent")
        btn_login_frame.pack(pady=10)

        self.btn_ig_login = ctk.CTkButton(
            btn_login_frame, text="Pouze Přihlásit IG", 
            command=lambda: self.start_thread("instagram", action="login"), 
            width=180, height=40, font=("Arial", 13, "bold"), fg_color="#405DE6"
        )
        self.btn_ig_login.grid(row=0, column=0, padx=10)

        self.btn_x_login = ctk.CTkButton(
            btn_login_frame, text="Pouze Přihlásit X", 
            command=lambda: self.start_thread("X", action="login"), 
            width=180, height=40, font=("Arial", 13, "bold"), fg_color="#000000", hover_color="#333333"
        )
        self.btn_x_login.grid(row=0, column=1, padx=10)

        # SEKCE 2
        scrape_frame = ctk.CTkFrame(top_frame)
        scrape_frame.pack(fill="x", pady=10, ipadx=10, ipady=10)

        ctk.CTkLabel(scrape_frame, text="2. Těžba dat (Scraping)", font=("Arial", 16, "bold")).pack(pady=5)
        
        self.target_var = ctk.StringVar()
        self.target_entry = ctk.CTkEntry(
            scrape_frame, textvariable=self.target_var, width=350, height=40, 
            font=("Arial", 14), placeholder_text="Cílový účet (např. elon musk)"
        )
        self.target_entry.pack(pady=5)

        btn_scrape_frame = ctk.CTkFrame(scrape_frame, fg_color="transparent")
        btn_scrape_frame.pack(pady=10)

        self.btn_ig_scrape = ctk.CTkButton(
            btn_scrape_frame, text="Těžit profil IG", 
            command=lambda: self.start_thread("instagram", action="scrape"), 
            width=180, height=40, font=("Arial", 13, "bold"), fg_color="#E1306C"
        )
        self.btn_ig_scrape.grid(row=0, column=0, padx=10)

        self.btn_x_scrape = ctk.CTkButton(
            btn_scrape_frame, text="Těžit profil X", 
            command=lambda: self.start_thread("X", action="scrape"), 
            width=180, height=40, font=("Arial", 13, "bold"), fg_color="#1DA1F2", text_color="white"
        )
        self.btn_x_scrape.grid(row=0, column=1, padx=10)

        # NOVÉ TLAČÍTKO PRO TRENDY
        self.btn_x_trending = ctk.CTkButton(
            scrape_frame, text="Těžit Trendy (X)", 
            command=lambda: self.start_thread("X", action="scrape_trending"), 
            width=380, height=40, font=("Arial", 13, "bold"), fg_color="#107C10", hover_color="#0B5A0B", text_color="white"
        )
        self.btn_x_trending.pack(pady=(0, 10))

        # SEKCE 3
        self.btn_stop = ctk.CTkButton(
            top_frame, text="STOP A ULOŽIT SESSION", 
            fg_color="#CC0000", hover_color="#990000", font=("Arial", 14, "bold"), 
            command=self.stop_bot, width=300, height=45
        )
        self.btn_stop.pack(pady=15)

        self.status_label = ctk.CTkLabel(top_frame, text="Připraveno", text_color="gray", font=("Arial", 14))
        self.status_label.pack(pady=0)

        # LOGY
        ctk.CTkLabel(log_frame, text="Real-time Bot Logs:", font=("Consolas", 14, "bold")).pack(anchor="w", padx=15, pady=(10, 5))
        self.log_text = ctk.CTkTextbox(log_frame, fg_color="#121212", text_color="#00ff00", font=("Consolas", 13), wrap="word")
        self.log_text.pack(side="bottom", fill="both", expand=True, padx=15, pady=(0, 15))

        sys.stdout = PrintLogger(self.log_text, self)
        sys.stderr = PrintLogger(self.log_text, self)

        print("=== OGMA 0.0 INICIALIZOVÁNO ===")
        print("Aplikace připravena.")

    def setup_database_tab(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#2b2b2b", foreground="white", rowheight=25, fieldbackground="#2b2b2b", bordercolor="#343638", borderwidth=0)
        style.map('Treeview', background=[('selected', '#1f538d')])
        style.configure("Treeview.Heading", background="#565b5e", foreground="white", relief="flat")
        style.map("Treeview.Heading", background=[('active', '#343638')])

        btn_refresh = ctk.CTkButton(self.tab_database, text="Obnovit data", command=self.load_db_data, width=150)
        btn_refresh.pack(pady=10)

        self.db_subtabs = ctk.CTkTabview(self.tab_database)
        self.db_subtabs.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        self.db_subtabs.add("Uživatelé")
        self.db_subtabs.add("Příspěvky")
        self.db_subtabs.add("Trendy") # NOVÁ TABULKA

        self.users_tree = self.create_treeview(self.db_subtabs.tab("Uživatelé"))
        self.posts_tree = self.create_treeview(self.db_subtabs.tab("Příspěvky"))
        self.trends_tree = self.create_treeview(self.db_subtabs.tab("Trendy"))

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

    def on_tab_change(self):
        if self.main_tabview.get() == "Databáze":
            self.load_db_data()

    def load_db_data(self):
        if not self.db_path.exists():
            return

        for item in self.users_tree.get_children(): self.users_tree.delete(item)
        for item in self.posts_tree.get_children(): self.posts_tree.delete(item)
        for item in self.trends_tree.get_children(): self.trends_tree.delete(item)

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute("SELECT id, platform, username, display_name, followers_count, last_scraped FROM users")
            self.users_tree['columns'] = ("ID", "Platform", "Username", "Display Name", "Followers", "Last Scraped")
            self.users_tree.column("#0", width=0, stretch="no")
            for col in self.users_tree['columns']:
                self.users_tree.column(col, anchor="w", width=150)
                self.users_tree.heading(col, text=col, anchor="w")
            for row in cursor.fetchall(): self.users_tree.insert("", "end", values=row)

            cursor.execute("SELECT id, platform_post_id, text_content, likes_count, timestamp_posted, scraped_at FROM posts")
            self.posts_tree['columns'] = ("ID", "Post ID", "Text", "Likes", "Posted At", "Scraped At")
            self.posts_tree.column("#0", width=0, stretch="no")
            for col in self.posts_tree['columns']:
                self.posts_tree.column(col, anchor="w", width=150)
                self.posts_tree.heading(col, text=col, anchor="w")
            for row in cursor.fetchall():
                row_list = list(row)
                if row_list[2] and len(row_list[2]) > 60: row_list[2] = row_list[2][:57] + "..."
                self.posts_tree.insert("", "end", values=row_list)

            # Nahrání trendů do GUI
            try:
                cursor.execute("SELECT rank, platform, category, topic_name, post_count, scraped_at FROM trending ORDER BY rank ASC")
                self.trends_tree['columns'] = ("Rank", "Platform", "Category", "Topic", "Posts Count", "Scraped At")
                self.trends_tree.column("#0", width=0, stretch="no")
                for col in self.trends_tree['columns']:
                    self.trends_tree.column(col, anchor="w", width=150)
                    self.trends_tree.heading(col, text=col, anchor="w")
                for row in cursor.fetchall():
                    self.trends_tree.insert("", "end", values=row)
            except Exception as e:
                pass # Tabulka možná ještě nevznikla

            conn.close()
        except Exception as e:
            print(f"[ERROR] Chyba při načítání databáze: {e}")

    def load_users(self):
        if not os.path.exists(self.data_path):
            return
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for user in data.get("users", []):
                self.users_map[f"{user['ID']} - {user['name']} {user['surname']}"] = user
        except Exception as e:
            print(f"[ERROR] Chyba při čtení users.json: {e}")

    def get_credentials(self, platform_key):
        selected_key = self.user_var.get()
        if not selected_key:
            messagebox.showwarning("Pozor", "Nevybral jsi žádného uživatele!")
            return None, None
        user_data = self.users_map.get(selected_key)
        social_data = user_data.get('social_media', {}).get(platform_key)
        if not social_data:
            messagebox.showerror("Chyba", f"Uživatel nemá údaje pro {platform_key}!")
            return None, None
        return social_data.get('username'), social_data.get('password')

    def start_thread(self, platform, action="login"):
        if self.is_running:
            messagebox.showwarning("Běží", "Bot už běží. Použij STOP tlačítko.")
            return

        username, password = self.get_credentials(platform)
        if not username: return

        target = self.target_var.get().strip()
        # ZMĚNA: Pro těžbu trendů nevyžadujeme vyplněný Target
        if action == "scrape" and not target:
            messagebox.showwarning("Pozor", "Pro spuštění těžby profilu musíš zadat Cílový účet!")
            return

        user_id = self.user_var.get().split(" - ")[0]

        self.update_status(f"Spouštím {platform} ({action}) pro ID {user_id}...")
        self.is_running = True
        
        self.log_text.delete(1.0, tk.END)
        print(f"=== STARTING {platform.upper()} BOT ({action.upper()}) ===")
        
        threading.Thread(target=self.run_bot, args=(platform, username, password, user_id, action, target), daemon=True).start()

    def run_bot(self, platform, username, password, user_id, action, target):
        try:
            if platform == "instagram":
                self.current_bot = InstagramBot(username, password, user_id=user_id)
            elif platform == "X":
                self.current_bot = XBot(username, password, user_id=user_id)
            
            self.current_bot.login()
            
            # ZMĚNA: Rozdělení akcí
            if action == "scrape":
                self.current_bot.scraper.scrape_profile(target)
                self.update_status(f"Těžba @{target} na {platform} byla dokončena.")
            elif action == "scrape_trending":
                self.current_bot.scraper.scrape_trending()
                self.update_status(f"Těžba trendů na {platform} byla dokončena.")
            else:
                self.update_status("Login hotový. Čekám. Klikni na STOP pro uložení.")
                
            print("\n[INFO] Bot dokončil zadanou úlohu. Čeká na tvůj příkaz STOP...")
            while self.is_running:
                time.sleep(1)

        except Exception as e:
            err_msg = str(e)
            ignored_errors = ["Connection closed", "Target closed", "页面的连接已断开", "disconnected"]
            if any(err in err_msg for err in ignored_errors):
                self.update_status("Bot byl bezpečně ukončen.")
            else:
                print(f"\n[CRITICAL ERROR]: {e}")
                self.update_status("Chyba: V logu")
        finally:
            if self.current_bot:
                self.current_bot.close()
                self.current_bot = None
            self.is_running = False

    def stop_bot(self, silent=False):
        if self.is_running:
            self.update_status("Zastavuji bota a ukládám data...")
            print("\n--- PŘIJAT PŘÍKAZ K UKONČENÍ A ULOŽENÍ ---")
            self.is_running = False 
            if self.current_bot:
                self.current_bot.close()
        else:
            if not silent:
                messagebox.showinfo("Info", "Žádný bot neběží.")

    def update_status(self, text):
        try:
            if self.winfo_exists():
                self.after(0, lambda: self.status_label.configure(text=text))
        except Exception:
            pass

    def on_closing(self):
        self.stop_bot(silent=True)
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        self.after(500, self.destroy)
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

