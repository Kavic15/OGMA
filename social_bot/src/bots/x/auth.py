from src.utils.human_input import delay

class XAuthenticator:
    def __init__(self, bot):
        self.bot = bot
        self.base_url = "https://x.com/"

    def login(self):
        print("[X] Kontroluji session na hlavní stránce...")
        
        self.bot.page.get(self.base_url)
        delay(4, 6) 

        is_logged_in = False
        if self.bot.page.ele('@aria-label:Timeline: Your Home Timeline', timeout=5):
            is_logged_in = True
        elif self.bot.page.ele('@aria-label:Profile', timeout=2):
             is_logged_in = True
        elif "/home" in self.bot.page.url:
             is_logged_in = True

        if is_logged_in:
            print("[X] Úspěšně ověřeno: Již přihlášeno (ze session).")
            return
        
        print("[X] Session nenalezena, jdu se přihlásit...")
        self.bot.page.get(self.base_url + "i/flow/login")
        delay(3)
        
        if self.bot.page.ele('@autocomplete=username', timeout=10):
            print("[X] Zadávám uživatelské jméno...")
            self.bot.page.ele('@autocomplete=username').input(self.bot.username)
            delay(1, 2)
            
            next_xpath = "xpath://span[text()='Next' or text()='Další']"
            self.bot.click_smart(next_xpath, "Tlačítko Další")
            delay(2, 3)

        if self.bot.page.ele('@name=password', timeout=10):
            print("[X] Zadávám heslo...")
            self.bot.page.ele('@name=password').input(self.bot.password)
            delay(1, 2)
            
            login_xpath = "xpath://span[text()='Log in' or text()='Přihlásit se']"
            self.bot.click_smart(login_xpath, "Tlačítko Login")
            delay(5, 8)
            
            self.bot.handle_popups(['Refuse', 'Odmítnout', 'Accept all', 'Povolit'])
            
            print("[X] Přihlášení dokončeno, ukládám session...")
            delay(3)