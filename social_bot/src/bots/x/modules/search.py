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