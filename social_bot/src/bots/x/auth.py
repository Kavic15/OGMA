from src.utils.human_input import delay

class XAuthenticator:
    def __init__(self, bot):
        self.bot = bot
        self.base_url = "https://x.com/"

    def login(self):
        print("[X] Kontroluji session na hlavní stránce...")
        
        # Playwright využívá metodu goto s nastavením chování při načítání
        try:
            self.bot.page.goto(self.base_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"[X] Varování při načítání úvodní stránky: {e}")
            
        delay(4, 6) 

        is_logged_in = False
        
        try:
            # Selektory přepsány do standardního formátu pro Playwright
            if self.bot.page.locator('[aria-label="Timeline: Your Home Timeline"]').is_visible(timeout=5000):
                is_logged_in = True
            elif self.bot.page.locator('[aria-label="Profile"]').is_visible(timeout=2000):
                 is_logged_in = True
            elif "/home" in self.bot.page.url:
                 is_logged_in = True
        except:
            pass

        if is_logged_in:
            print("[X] Úspěšně ověřeno: Již přihlášeno (ze session).")
            return
        
        print("[X] Session nenalezena, jdu se přihlásit...")
        try:
            self.bot.page.goto(self.base_url + "i/flow/login", wait_until="domcontentloaded", timeout=30000)
        except:
            pass
        delay(3)
        
        username_input = self.bot.page.locator('[autocomplete="username"]').first
        try:
            # Playwright vyžaduje explicitní čekání na stav elementu, pokud nevyužíváme auto-waiting akce
            username_input.wait_for(state="visible", timeout=10000)
            print("[X] Zadávám uživatelské jméno...")
            
            # press_sequentially nahrazuje původní iterativní human_typing
            username_input.press_sequentially(self.bot.username, delay=150)
            delay(1, 2)
            
            next_xpath = "//span[text()='Next' or text()='Další']"
            self.bot.click_smart(next_xpath, "Tlačítko Další")
            delay(2, 3)
        except Exception as e:
            print(f"[X] Pole pro username nebylo včas nalezeno: {e}")

        password_input = self.bot.page.locator('[name="password"]').first
        try:
            password_input.wait_for(state="visible", timeout=10000)
            print("[X] Zadávám heslo...")
            
            password_input.press_sequentially(self.bot.password, delay=150)
            delay(1, 2)
            
            login_xpath = "//span[text()='Log in' or text()='Přihlásit se']"
            self.bot.click_smart(login_xpath, "Tlačítko Login")
            delay(5, 8)
            
            self.bot.handle_popups(['Refuse', 'Odmítnout', 'Accept all', 'Povolit'])
            
            print("[X] Přihlášení dokončeno, ukládám session...")
            delay(3)
        except Exception as e:
            print(f"[X] Pole pro heslo nebylo včas nalezeno: {e}")