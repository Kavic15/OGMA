# src/bots/x/modules/search.py
from src.utils.human_input import delay
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
import re


class XSearchModule:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    def find_profile(self, target_query):
        # --- Krok 1: DB cache ---
        print("[X-SEARCH] 1. Krok: Kontrola lokální databáze...")
        known_handle = self.db.get_known_handle(target_query)
        if known_handle:
            print(f"[DATABASE] Nalezen uložený handle: @{known_handle}. Jdu na jistotu.")
            self.bot.open_url(f"{self.bot.base_url}{known_handle}")
            delay(2, 4)
            try:
                if self.bot.page.locator('[data-testid="UserName"]').first.is_visible(timeout=5000):
                    return True
            except Exception:
                pass

        # --- Krok 2: Interní vyhledávání — People záložka ---
        print("[X-SEARCH] 2. Krok: Interní vyhledávání — záložka People...")
        people_result = self._search_in_tab(target_query, tab="people")
        if people_result:
            if self._verify_profile_match(target_query):
                print("[X-SEARCH] Profil ověřen — shoda s dotazem.")
                return True
            else:
                print("[X-SEARCH] Výsledek People záložky neodpovídá dotazu. Zkouším záložku All...")

        # --- Krok 3: Záložka All (vše) ---
        print("[X-SEARCH] 3. Krok: Interní vyhledávání — záložka All...")
        all_result = self._search_in_tab(target_query, tab="all")
        if all_result:
            if self._verify_profile_match(target_query):
                print("[X-SEARCH] Profil ověřen přes záložku All.")
                return True
            else:
                print("[X-SEARCH] Ani záložka All nevrátila shodu. Zkouším Direct URL...")

        # --- Krok 4: Direct URL ---
        print("[X-SEARCH] 4. Krok: Pokus o přímou URL...")
        if self._direct_url(target_query):
            return True

        # --- Krok 5: Google fallback ---
        print("[X-SEARCH] 5. Krok: Google Search fallback...")
        if self._google_search_fallback(target_query):
            try:
                self.bot.page.locator('[data-testid="UserName"]').first.wait_for(
                    state="visible", timeout=8000
                )
                return True
            except Exception:
                pass

        return False

    # ------------------------------------------------------------------
    # Vyhledávání v konkrétní záložce (people / all)
    # ------------------------------------------------------------------
    def _search_in_tab(self, target_query: str, tab: str) -> bool:
        try:
            if "search" not in self.bot.page.url and "explore" not in self.bot.page.url:
                self.bot.open_url(self.bot.base_url + "explore")
                delay(1.5, 2.5)

            search_box = self.bot.page.locator('[data-testid="SearchBox_Search_Input"]').first
            search_box.wait_for(state="visible", timeout=5000)

            search_box.click()
            search_box.fill("")
            search_box.press_sequentially(target_query, delay=100)
            delay(0.5)
            search_box.press("Enter")
            delay(1.5, 2.5)

            if tab == "people":
                tab_xpath = "//span[text()='People' or text()='Lidé']"
            else:
                tab_xpath = "//span[text()='Top' or text()='Vše' or text()='All']"

            try:
                tab_locator = self.bot.page.locator(f"xpath={tab_xpath}").first
                tab_locator.wait_for(state="visible", timeout=4000)
                tab_locator.click()
                delay(1.5, 2.5)
            except PlaywrightTimeoutError:
                print(f"[X-SEARCH] Záložka '{tab}' nenalezena, pokračuji bez přepnutí.")

            first_user = self.bot.page.locator('[data-testid="UserCell"]').first
            first_user.wait_for(state="visible", timeout=4000)
            first_user.click()

            self.bot.page.locator('[data-testid="UserName"]').first.wait_for(
                state="visible", timeout=6000
            )
            return True

        except Exception:
            return False

    # ------------------------------------------------------------------
    # Ověření shody výsledku s původním dotazem
    # ------------------------------------------------------------------
    def _verify_profile_match(self, target_query: str) -> bool:
        try:
            current_url = self.bot.page.url
            url_username = ""
            if "x.com/" in current_url:
                url_username = current_url.split("x.com/")[-1].split("?")[0].split("/")[0].lower()

            username_loc = self.bot.page.locator('[data-testid="UserName"]').first
            full_text = username_loc.inner_text().lower() if username_loc.count() > 0 else ""

            query_clean = re.sub(r'[^a-z0-9]', '', target_query.lower())

            url_clean = re.sub(r'[^a-z0-9]', '', url_username)
            if query_clean and url_clean and (
                query_clean in url_clean or url_clean in query_clean
            ):
                return True

            full_clean = re.sub(r'[^a-z0-9]', '', full_text)
            if query_clean and full_clean and query_clean in full_clean:
                return True

            return False

        except Exception:
            return True

    # ------------------------------------------------------------------
    # Direct URL pokus
    # ------------------------------------------------------------------
    def _direct_url(self, target_query: str) -> bool:
        handle = re.sub(r'[^a-zA-Z0-9_]', '', target_query.replace('@', ''))
        if not handle:
            return False

        try:
            print(f"[X-SEARCH] Zkouším přímou URL: x.com/{handle}")
            self.bot.open_url(f"{self.bot.base_url}{handle}")
            delay(2, 4)

            user_name = self.bot.page.locator('[data-testid="UserName"]').first
            if user_name.is_visible(timeout=5000):
                print(f"[X-SEARCH] Direct URL úspěch: x.com/{handle}")
                return True

            return False

        except Exception:
            return False

    # ------------------------------------------------------------------
    # Google fallback
    # ------------------------------------------------------------------
    def _google_search_fallback(self, target_query: str) -> bool:
        print(f"[GOOGLE] Spouštím záchranné vyhledávání pro: '{target_query}'")
        try:
            self.bot.open_url("https://www.google.com")

            # Odkliknutí cookie dialogu — čekáme až zmizí před dalším krokem
            self.bot.handle_popups(['Přijmout vše', 'Accept all', 'Souhlasím', 'I agree'])

            # Explicitně počkáme na search input — dialog musí být pryč
            # než začneme psát (jinak fill() trefí schovaný input pod overlayem)
            search_input = self.bot.page.locator('textarea[name="q"], input[name="q"]').first
            try:
                search_input.wait_for(state="visible", timeout=6000)
            except PlaywrightTimeoutError:
                print("[GOOGLE] Search input není viditelný — dialog se možná nezavřel.")
                return False

            search_input.click()
            search_input.fill(f"{target_query} twitter")
            delay(0.5)
            search_input.press("Enter")

            print("[GOOGLE] Čekám na výsledky...")
            delay(2, 3)

            results = self.bot.page.locator('a').all()
            for res in results:
                href = res.get_attribute('href')
                if href and (
                    "twitter.com/" in href or "x.com/" in href
                ) and "status" not in href and "search" not in href:
                    print(f"[GOOGLE] Nalezen profil: {href}")
                    res.click()
                    delay(3, 5)
                    return True

            return False

        except Exception as e:
            print(f"[GOOGLE ERROR] {e}")
            return False