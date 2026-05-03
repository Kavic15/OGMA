import os
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from src.utils.human_input import delay

class BaseBot:
    def __init__(self, headless=True, user_id="default", platform="general"):
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
            self._apply_stealth_scripts(page)
            return page
            
        except Exception as e:
            print(f"[CRITICAL ERROR] Nelze spustit Playwright prohlížeč: {e}")
            if self.playwright:
                self.playwright.stop()
            raise e

    def _apply_stealth_scripts(self, page):
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page.add_init_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]})")
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
        """
        Klikne na první viditelné tlačítko/odkaz jehož text přesně odpovídá
        některému z řetězců v `triggers`.

        Rozdíl oproti původní verzi:
          - Hledáme konkrétně <button> nebo <a> elementy (ne libovolný text na stránce),
            čímž se vyhneme trefení textu v dropdownech nebo popisných odstavcích.
          - Po úspěšném kliknutí čekáme až dialog zmizí z DOM (max 5 s),
            teprve pak vrátíme True — volající kód tak dostane stránku bez překrytí.
        """
        # CSS selektor omezený na interaktivní prvky
        BUTTON_SELECTOR = "button, a[role='button'], a"

        for text in triggers:
            try:
                # Filtrujeme: interaktivní prvek, jehož viditelný text obsahuje hledaný řetězec
                locator = self.page.locator(BUTTON_SELECTOR).filter(has_text=text).first
                if not locator.is_visible(timeout=1500):
                    continue

                # Ověříme že jde skutečně o tlačítko (ne náhodný odkaz s podobným textem)
                tag = locator.evaluate("el => el.tagName.toLowerCase()")
                role = locator.get_attribute("role") or ""
                el_text = (locator.inner_text() or "").strip()

                # Přijmeme pouze pokud text odpovídá celému tlačítku (ne jen části dlouhého textu)
                if len(el_text) > len(text) * 3:
                    continue  # příliš dlouhý text → pravděpodobně špatný element

                locator.click(force=True)
                print(f"[BOT] Odkliknuto vyskakovací okno: '{text}'")

                # Počkáme až element zmizí (dialog se zavřel)
                try:
                    locator.wait_for(state="hidden", timeout=5000)
                except Exception:
                    pass  # nevadí — pokud už zmizel, timeout je OK

                delay(1.5, 2.5)  # extra pauza pro překreslení stránky
                return True

            except Exception:
                continue

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