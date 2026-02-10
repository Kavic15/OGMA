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
        
        # 1. CESTY
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        
        # Cesta k profilu
        profile_path = project_root / 'profiles' / self.user_id
        os.makedirs(profile_path, exist_ok=True)
        
        print(f"[BOT] Profil: {profile_path}")
        
        # 2. PROHLÍŽEČ (Portable)
        browser_path = project_root / 'browser' / 'chrome.exe'
        if browser_path.exists():
            co.set_paths(browser_path=str(browser_path))
        else:
            print("[WARNING] Portable browser nenalezen, používám systémový.")
        
        # 3. NASTAVENÍ PROFILU A PORTU
        co.set_user_data_path(str(profile_path))
        co.set_local_port(9333) # Pevný port je nutný pro správné načtení profilu

        # 4. CONFIG
        if headless:
            co.headless(True)
        
        co.set_argument('--start-maximized')
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