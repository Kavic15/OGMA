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