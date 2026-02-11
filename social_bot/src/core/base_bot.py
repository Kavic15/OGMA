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