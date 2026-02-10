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
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import json
import os
import time  # Přidán import time
from src.bots.instagram import InstagramBot
from src.bots.x import XBot

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Social Bot 2.0 (IG & X)")
        self.geometry("450x400")
        
        self.current_bot = None 
        self.is_running = False

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_path = os.path.join(base_dir, 'data', 'users.json')
        
        self.users_map = {}
        self.load_users()

        # --- UI Prvky ---
        ttk.Label(self, text="Vyber bota (Identita):").pack(pady=5)
        
        self.user_var = tk.StringVar()
        self.user_combo = ttk.Combobox(self, textvariable=self.user_var, state="readonly")
        self.user_combo['values'] = list(self.users_map.keys())
        if self.users_map:
            self.user_combo.current(0)
        self.user_combo.pack(pady=5, fill='x', padx=20)

        ttk.Label(self, text="Cíl (Target Username):").pack(pady=5)
        self.entry_target = ttk.Entry(self)
        self.entry_target.insert(0, "realDonaldTrump")
        self.entry_target.pack(pady=5, fill='x', padx=20)

        # Frame pro tlačítka
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=20)

        self.btn_ig = ttk.Button(btn_frame, text="Spustit Instagram", command=lambda: self.start_thread("instagram"))
        self.btn_ig.grid(row=0, column=0, padx=10)

        self.btn_x = ttk.Button(btn_frame, text="Spustit X (Twitter)", command=lambda: self.start_thread("X"))
        self.btn_x.grid(row=0, column=1, padx=10)

        # Tlačítko STOP
        self.btn_stop = tk.Button(self, text="STOP / UKONČIT BOTA", bg="#ffcccc", fg="red", command=self.stop_bot)
        self.btn_stop.pack(pady=10, fill='x', padx=50)

        self.status_label = ttk.Label(self, text="Připraveno", foreground="gray")
        self.status_label.pack(side="bottom", pady=5)

    def load_users(self):
        if not os.path.exists(self.data_path):
            messagebox.showerror("Chyba", f"Nenalezen soubor: {self.data_path}")
            return

        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for user in data.get("users", []):
                display_name = f"{user['ID']} - {user['name']} {user['surname']}"
                self.users_map[display_name] = user
        except Exception as e:
            messagebox.showerror("Chyba JSON", f"Chyba při čtení users.json:\n{e}")

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

    def start_thread(self, platform):
        if self.is_running:
            messagebox.showwarning("Běží", "Bot už běží. Použij STOP tlačítko.")
            return

        username, password = self.get_credentials(platform)
        if not username: return

        target = self.entry_target.get()
        user_id = self.user_var.get().split(" - ")[0]

        self.status_label.config(text=f"Spouštím {platform} pro ID {user_id}...")
        self.is_running = True
        
        threading.Thread(target=self.run_bot, args=(platform, username, password, target, user_id)).start()

    def run_bot(self, platform, username, password, target, user_id):
        try:
            if platform == "instagram":
                self.current_bot = InstagramBot(username, password, user_id=user_id)
                self.current_bot.login()
                if target:
                    self.current_bot.scrape_profile(target)
            elif platform == "X":
                self.current_bot = XBot(username, password, user_id=user_id)
                self.current_bot.login()
            
            # --- DŮLEŽITÁ ZMĚNA: NEKONČIT, DOKUD NENÍ STISKNUTO STOP ---
            self.update_status("Bot běží a čeká. Klikni na STOP pro uložení.")
            while self.is_running:
                time.sleep(1) # Čekáme ve smyčce, aby se bot nevypnul
            # -----------------------------------------------------------

        except Exception as e:
            if "Connection closed" not in str(e) and "Target closed" not in str(e):
                print(f"ERROR: {e}")
                self.update_status(f"Chyba: {e}")
            else:
                self.update_status("Bot byl ukončen.")
        finally:
            # Tento blok se provede až když self.is_running nastaveno na False (tlačítkem STOP)
            if self.current_bot:
                self.current_bot.close() # Tady se uloží data!
                self.current_bot = None
            self.is_running = False

    def stop_bot(self):
        """Bezpečné ukončení bota."""
        if self.is_running:
            self.status_label.config(text="Zastavuji bota a ukládám data...")
            print("--- STOP BUTTON PRESSED ---")
            # Nastavením na False se přeruší smyčka while v run_bot
            self.is_running = False 
        else:
            messagebox.showinfo("Info", "Žádný bot neběží.")

    def update_status(self, text):
        self.after(0, lambda: self.status_label.config(text=text))

    def on_closing(self):
        self.stop_bot()
        # Malá pauza, aby se stihlo zavolat close() ve vlákně
        self.after(1000, self.destroy)

if __name__ == "__main__":
    try:
        app = App()
        # update() pomáhá stabilizovat okno před spuštěním smyčky
        app.update() 
        app.mainloop()
    except KeyboardInterrupt:
        print("\n[INFO] Aplikace byla ukončena uživatelem (CTRL+C).")
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Aplikace spadla: {e}")
```

## Soubor: social_bot\src\bots\instagram.py
```py
from src.core.base_bot import BaseBot
from src.utils.human_input import delay

class InstagramBot(BaseBot):
    def __init__(self, username, password, user_id="default"):
        super().__init__(user_id=user_id)
        self.username = username
        self.password = password
        self.base_url = "https://www.instagram.com/"

    def login(self):
        self.open_url(self.base_url)
        
        # 1. Kontrola, zda už nejsme přihlášeni (Session Persistence)
        # Hledáme ikonu domů nebo profilu
        if self.page.ele('@aria-label=Domů') or self.page.ele('text:Profile'):
            print("[IG] Již přihlášeno (ze session). Přeskakuji login.")
            return

        # 2. Univerzální likvidace Cookies
        self.handle_popups(['Decline', 'Odmítnout', 'Allow all', 'Povolit', 'Only allow essential'])

        # 3. Samotný Login (jen pokud vidíme inputy)
        if self.page.ele('@name=username', timeout=5):
            print("[IG] Zadávám přihlašovací údaje...")
            self.page.ele('@name=username').input(self.username)
            delay(0.5, 1)
            self.page.ele('@name=password').input(self.password)
            delay(1, 2)
            self.click_smart('@type=submit', "Login Button")
            delay(5, 8)
        
        # 4. Úklid po přihlášení (Not Now, Save Info)
        triggers = ['Not Now', 'Nyní ne', 'Not now', 'Uložit informace']
        for _ in range(2): # Zkusíme dvakrát, často jsou tam dvě okna za sebou
            self.handle_popups(triggers)

    def scrape_profile(self, target_username):
        url = f"{self.base_url}{target_username}/"
        self.open_url(url)
        
        # Klik na první post
        first_post = self.page.ele('css:article a', timeout=5) 
        if first_post:
            print(f"[IG] Otevírám první post u {target_username}...")
            first_post.click()
            delay(2)
```

## Soubor: social_bot\src\bots\x.py
```py
from src.core.base_bot import BaseBot
from src.utils.human_input import delay

class XBot(BaseBot):
    def __init__(self, username, password, user_id="default"):
        super().__init__(user_id=user_id)
        self.username = username
        self.password = password
        self.base_url = "https://x.com/"

    def login(self):
        print("[X] Kontroluji session na hlavní stránce...")
        
        # 1. Jdeme na root a čekáme déle
        self.page.get(self.base_url)
        delay(4, 6) # Dáme Brave čas načíst cookies z disku

        # 2. Inteligentní kontrola (Timeline NEBO Profilové tlačítko)
        # Hledáme indikátory přihlášení
        is_logged_in = False
        
        # Zkusíme najít Timeline
        if self.page.ele('@aria-label:Timeline: Your Home Timeline', timeout=5):
            is_logged_in = True
        # Nebo tlačítko "Profile" v menu
        elif self.page.ele('@aria-label:Profile', timeout=2):
             is_logged_in = True
        # Nebo jestli URL obsahuje /home
        elif "/home" in self.page.url:
             is_logged_in = True

        if is_logged_in:
            print("[X] Úspěšně ověřeno: Již přihlášeno (ze session).")
            return
        
        # 3. Pokud nic z toho neplatí, teprve teď jdeme na login
        print("[X] Session nenalezena, jdu se přihlásit...")
        self.page.get(self.base_url + "i/flow/login")
        delay(3)
        
        # --- LOGIN FLOW (Zůstává stejné) ---
        if self.page.ele('@autocomplete=username', timeout=10):
            print("[X] Zadávám uživatelské jméno...")
            self.page.ele('@autocomplete=username').input(self.username)
            delay(1, 2)
            
            next_xpath = "xpath://span[text()='Next' or text()='Další']"
            self.click_smart(next_xpath, "Tlačítko Další")
            delay(2, 3)

        if self.page.ele('@name=password', timeout=10):
            print("[X] Zadávám heslo...")
            self.page.ele('@name=password').input(self.password)
            delay(1, 2)
            
            login_xpath = "xpath://span[text()='Log in' or text()='Přihlásit se']"
            self.click_smart(login_xpath, "Tlačítko Login")
            delay(5, 8)
            
            self.handle_popups(['Refuse', 'Odmítnout', 'Accept all', 'Povolit'])
            
            # Po přihlášení chvíli počkáme, aby se stihly zapsat cookies na disk!
            print("[X] Přihlášení dokončeno, ukládám session...")
            delay(3)

    def tweet(self, text):
        pass
```

## Soubor: social_bot\src\core\base_bot.py
```py
from DrissionPage import ChromiumPage, ChromiumOptions
from src.utils.human_input import delay
import os
from pathlib import Path

class BaseBot:
    def __init__(self, headless=False, user_id="default"):
        self.user_id = str(user_id)
        self.page = self._setup_driver(headless)

    def _setup_driver(self, headless):
        co = ChromiumOptions()
        
        # --- 1. CESTY (Relativní k projektu) ---
        # Získáme kořenovou složku projektu (social_bot)
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        
        # A) Cesta k PROFILŮM (social_bot/profiles/ID)
        profile_path = project_root / 'profiles' / self.user_id
        os.makedirs(profile_path, exist_ok=True)
        print(f"[BOT] Profil: {profile_path}")
        co.set_user_data_path(str(profile_path))
        
        # B) Cesta k PROHLÍŽEČI (social_bot/browser/chrome.exe)
        # Hledáme soubor chrome.exe ve složce browser
        browser_path = project_root / 'browser' / 'chrome.exe'
        
        if browser_path.exists():
            print(f"[BOT] Používám Portable Browser: {browser_path}")
            co.set_paths(browser_path=str(browser_path))
        else:
            # Kdyby se něco pokazilo a soubor tam nebyl
            print(f"[WARNING] Portable browser nenalezen v {browser_path}!")
            print("[BOT] Zkouším najít systémový prohlížeč jako zálohu...")

        # --- 2. CONFIG ---
        co.auto_port() 
        if headless:
            co.headless(True)
        
        # Argumenty pro Ungoogled Chromium / Portable verzi
        co.set_argument('--start-maximized')
        co.set_argument('--no-first-run')
        co.set_argument('--password-store=basic') 
        co.set_argument('--restore-last-session')
        co.set_argument('--no-default-browser-check') 

        try:
            return ChromiumPage(co)
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
        conditions = [f"contains(text(), '{text}')" for text in triggers]
        xpath = f"xpath://*[{' or '.join(conditions)}]"
        if self.click_smart(xpath, "Popup Dialog", timeout=2):
            delay(1)
            return True
        return False

    def close(self):
        print(f"[BOT] Ukládám profil {self.user_id} a zavírám...")
        try:
            self.page.quit() 
            print("[BOT] Uloženo.")
        except Exception as e:
            print(f"[ERROR] Chyba při zavírání: {e}")
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

