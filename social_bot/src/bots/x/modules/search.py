from src.utils.human_input import delay, human_typing

class XSearchModule:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    def find_profile(self, target_query):
        """Řídí celý proces hledání profilu."""
        
        # 1. KROK: KONTROLA DATABÁZE (CACHE)
        print("[X-SEARCH] 1. Krok: Kontrola lokální databáze...")
        known_handle = self.db.get_known_handle(target_query)
        if known_handle:
            print(f"[DATABASE] Nalezen uložený handle: @{known_handle}. Jdu na jistotu.")
            self.bot.open_url(f"{self.bot.base_url}{known_handle}")
            delay(2, 4)
            if self.bot.page.ele('@data-testid=UserName', timeout=5):
                return True
        
        # 2. KROK: X SEARCH (EXPLORE)
        print("[X-SEARCH] 2. Krok: Interní vyhledávání na X...")
        if self._internal_search(target_query):
            return True
            
        # 3. KROK: GOOGLE FALLBACK
        print("[X-SEARCH] 3. Krok: Interní hledání selhalo. Volám Google Search...")
        if self._google_search_fallback(target_query):
            if self.bot.page.wait.ele_displayed('@data-testid=UserName', timeout=8):
                return True
        
        return False

    def _internal_search(self, target_query):
        if "search" not in self.bot.page.url and "explore" not in self.bot.page.url:
            self.bot.open_url(self.bot.base_url + "explore")
            delay(1.5, 2.5)

        search_box = self.bot.page.ele('@data-testid=SearchBox_Search_Input', timeout=5)
        if search_box:
            search_box.click()
            search_box.clear()
            human_typing(search_box, target_query)
            delay(0.5)
            search_box.input('\n')
            
            people_tab = self.bot.page.ele("xpath://span[text()='People' or text()='Lidé']", timeout=4)
            if people_tab:
                people_tab.click()
                delay(1.5, 3)
            
            first_user = self.bot.page.ele('@data-testid=UserCell', timeout=4)
            if first_user:
                print("[X-SEARCH] Profil nalezen v interním hledání. Klikám.")
                first_user.click()
                if self.bot.page.wait.ele_displayed('@data-testid=UserName', timeout=6):
                    return True
        return False

    def _google_search_fallback(self, target_query):
        print(f"[GOOGLE] Spouštím záchranné vyhledávání pro: '{target_query}'")
        try:
            self.bot.open_url("https://www.google.com")
            self.bot.handle_popups(['Přijmout vše', 'Accept all', 'Souhlasím', 'I agree'])
            
            search_input = self.bot.page.ele('tag:textarea@name=q', timeout=2) or self.bot.page.ele('tag:input@name=q', timeout=2)
            
            if search_input:
                query = f"{target_query} twitter"
                search_input.input(query)
                delay(0.5)
                self.bot.page.actions.type_key('ENTER')
                
                print("[GOOGLE] Čekám na výsledky...")
                delay(2, 3)
                
                results = self.bot.page.eles('tag:a', timeout=3)
                for res in results:
                    href = res.attr('href')
                    if href and ("twitter.com/" in href or "x.com/" in href) and "status" not in href and "search" not in href:
                        print(f"[GOOGLE] Nalezen profil: {href}")
                        res.click()
                        delay(3, 5)
                        return True
            return False
        except Exception as e:
            print(f"[GOOGLE ERROR] {e}")
            return False