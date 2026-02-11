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
from tkinter import messagebox
import customtkinter as ctk
import threading
import json
import os
import time
import sys
from src.bots.instagram import InstagramBot
from src.bots.x import XBot

# Nastavení moderního vzhledu
ctk.set_appearance_mode("Dark")  # Možnosti: "System", "Dark", "Light"
ctk.set_default_color_theme("blue")  # Možnosti: "blue", "green", "dark-blue"

# --- Odchytávání printů do GUI ---
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
        self.title("Social Bot - Command Center")
        self.geometry("1440x900")
        
        # --- NASTAVENÍ IKONY OKNA ---
        base_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_dir, 'src', 'gui', 'ogma_ai_logo.ico')
        
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)
        else:
            print(f"[WARNING] Ikona nenalezena na cestě: {icon_path}")
        # ----------------------------
        
        self.current_bot = None 
        self.is_running = False

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.data_path = os.path.join(base_dir, 'data', 'users.json')
        
        self.users_map = {}
        self.load_users()

        # --- OVLÁDÁNÍ A LOGY (CTkFrames) ---
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.pack(side="top", fill="x", pady=20, padx=40)
        
        log_frame = ctk.CTkFrame(self)
        log_frame.pack(side="bottom", fill="both", expand=True, padx=40, pady=(0, 40))

        # --- PRVKY ---
        ctk.CTkLabel(top_frame, text="Vyber bota (Identita):", font=("Arial", 16, "bold")).pack(pady=5)
        
        self.user_var = ctk.StringVar()
        self.user_combo = ctk.CTkComboBox(
            top_frame, 
            variable=self.user_var, 
            state="readonly", 
            font=("Arial", 14), 
            dropdown_font=("Arial", 14),
            width=350,
            height=40
        )
        self.user_combo.configure(values=list(self.users_map.keys()))
        if self.users_map:
            self.user_combo.set(list(self.users_map.keys())[0])
        self.user_combo.pack(pady=5)

        btn_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        btn_frame.pack(pady=20)

        self.btn_ig = ctk.CTkButton(
            btn_frame, 
            text="Přihlásit IG", 
            command=lambda: self.start_thread("instagram"), 
            width=200, 
            height=45,
            font=("Arial", 14, "bold")
        )
        self.btn_ig.grid(row=0, column=0, padx=15)

        self.btn_x = ctk.CTkButton(
            btn_frame, 
            text="Přihlásit X", 
            command=lambda: self.start_thread("X"), 
            width=200, 
            height=45,
            font=("Arial", 14, "bold")
        )
        self.btn_x.grid(row=0, column=1, padx=15)

        # Výrazné červené tlačítko STOP
        self.btn_stop = ctk.CTkButton(
            top_frame, 
            text="STOP A ULOŽIT SESSION", 
            fg_color="#CC0000", 
            hover_color="#990000", 
            font=("Arial", 14, "bold"), 
            command=self.stop_bot,
            width=300,
            height=45
        )
        self.btn_stop.pack(pady=15)

        self.status_label = ctk.CTkLabel(top_frame, text="Připraveno", text_color="gray", font=("Arial", 14))
        self.status_label.pack(pady=5)

        # --- LOGY ---
        ctk.CTkLabel(log_frame, text="Real-time Bot Logs:", font=("Consolas", 14, "bold")).pack(anchor="w", padx=15, pady=(15, 5))
        
        # CTkTextbox má nativně zabudovaný scrollbar, takže kód je mnohem čistší
        self.log_text = ctk.CTkTextbox(
            log_frame, 
            fg_color="#121212", 
            text_color="#00ff00", 
            font=("Consolas", 13), 
            wrap="word"
        )
        self.log_text.pack(side="bottom", fill="both", expand=True, padx=15, pady=(0, 15))

        # Přesměrování výstupů
        sys.stdout = PrintLogger(self.log_text, self)
        sys.stderr = PrintLogger(self.log_text, self)

        print("=== COMMAND CENTER INICIALIZOVÁNO ===")
        print("Grafické rozhraní přepnuto do režimu CustomTkinter.")
        print("Přesunut okno na sekundární monitor a můžeš začít...")

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

        user_id = self.user_var.get().split(" - ")[0]

        self.update_status(f"Spouštím {platform} pro ID {user_id}...")
        self.is_running = True
        
        self.log_text.delete(1.0, tk.END)
        print(f"=== STARTING {platform.upper()} BOT ===")
        
        threading.Thread(target=self.run_bot, args=(platform, username, password, user_id), daemon=True).start()

    def run_bot(self, platform, username, password, user_id):
        try:
            if platform == "instagram":
                self.current_bot = InstagramBot(username, password, user_id=user_id)
                self.current_bot.login()
            elif platform == "X":
                self.current_bot = XBot(username, password, user_id=user_id)
                self.current_bot.login()
            
            self.update_status("Login hotový. Čekám. Klikni na STOP pro uložení.")
            print("\n[INFO] Bot dokončil úlohu. Čeká na tvůj příkaz STOP...")
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
        """Zastaví bota. Pokud silent=True, nevypisuje messagebox při nečinnosti."""
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

## Soubor: social_bot\src\bots\instagram.py
```py
from src.core.base_bot import BaseBot
from src.utils.human_input import delay

class InstagramBot(BaseBot):
    def __init__(self, username, password, user_id="default"):
        super().__init__(user_id=user_id, platform="ig") 
        self.username = username
        self.password = password
        self.base_url = "https://www.instagram.com/"

    def login(self):
        self.open_url(self.base_url)
        
        # 1. Agresivní likvidace Cookies (Hunter Mode)
        print("[IG] Kontroluji Cookies okna...")
        cookie_keywords = ['Povolit', 'Odmítnout', 'Allow', 'Decline']
        for word in cookie_keywords:
            elements = self.page.eles(f'text:{word}')
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
        all_login_inputs = self.page.eles('@name=email') + self.page.eles('@name=username')
        all_pass_inputs = self.page.eles('@name=pass') + self.page.eles('@name=password')
        
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
            if self.page.ele('css:svg[aria-label="Domů"]', timeout=3) or self.page.ele('css:svg[aria-label="Home"]', timeout=1):
                print("[IG] Již přihlášeno (ze session). Přeskakuji login.")
                return
            else:
                print("[IG] Nevidím viditelný login formulář, ale ani znaky přihlášení.")
                return

        # 3. Samotný Login
        print("[IG] Zadávám přihlašovací údaje...")
        login_input.input(self.username)
        delay(0.5, 1)
        
        if pass_input:
            pass_input.input(self.password)
        delay(1, 2)
        
        submit_btn = self.page.ele('@type=submit', timeout=2)
        if submit_btn and submit_btn.states.is_displayed:
            submit_btn.click(by_js=True)
        else:
            login_btns = self.page.eles('text:Přihlásit') + self.page.eles('text:Log in')
            for btn in login_btns:
                if btn.states.is_displayed:
                    btn.click(by_js=True)
                    break
            
        delay(5, 8)
        
        # 4. Úklid po přihlášení
        print("[IG] Provádím úklid po přihlášení...")
        self.handle_popups(['Nyní ne', 'Not Now', 'Uložit', 'Save'])
        print("[IG] Přihlašovací proces dokončen.")
```

## Soubor: social_bot\src\bots\x.py
```py
from src.core.base_bot import BaseBot
from src.utils.human_input import delay

class XBot(BaseBot):
    def __init__(self, username, password, user_id="default"):
        # Předáme platform="x" do BaseBot
        super().__init__(user_id=user_id, platform="x")
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
        
        # --- ZMĚNA: Prohlížeč se zapne na hlavním monitoru a maximalizuje se ---
        co.set_argument('--start-maximized')
        co.set_argument('--window-position=0,0') # Pojistka, aby začal na hlavním displeji

        co.set_argument('--no-first-run')
        co.set_argument('--no-default-browser-check') 
        co.set_argument('--restore-last-session')

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

