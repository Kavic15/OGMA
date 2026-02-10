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