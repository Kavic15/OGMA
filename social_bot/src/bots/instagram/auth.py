from src.utils.human_input import delay

class InstagramAuthenticator:
    def __init__(self, bot):
        self.bot = bot

    def login(self):
        self.bot.open_url(self.bot.base_url)
        
        print("[IG] Kontroluji stav přihlášení...")
        try:
            home_icon = self.bot.page.locator('svg[aria-label="Domů"], svg[aria-label="Home"]').first
            if home_icon.is_visible(timeout=3000):
                print("[IG] Již přihlášeno (ze session). Přeskakuji login a cookies.")
                return
        except:
            pass

        print("[IG] Kontroluji Cookies okna...")
        cookie_keywords = ['Povolit', 'Odmítnout', 'Allow', 'Decline']
        for word in cookie_keywords:
            try:
                btn = self.bot.page.get_by_text(word, exact=False).first
                if btn.is_visible(timeout=500):
                    btn.click(force=True)
                    print(f"[IG] Odkliknuto cookie tlačítko: '{word}'")
                    delay(1.5)
                    break
            except:
                pass

        all_login_inputs = self.bot.page.locator('input[name="email"], input[name="username"]').all()
        all_pass_inputs = self.bot.page.locator('input[name="pass"], input[name="password"]').all()
        
        login_input = None
        for inp in all_login_inputs:
            if inp.is_visible():
                login_input = inp
                break
                
        pass_input = None
        for inp in all_pass_inputs:
            if inp.is_visible():
                pass_input = inp
                break

        if not login_input:
            print("[IG] Nevidím viditelný login formulář, ale ani znaky přihlášení.")
            return

        print("[IG] Zadávám přihlašovací údaje...")
        login_input.fill("")
        login_input.press_sequentially(self.bot.username, delay=150)
        delay(0.5, 1)
        
        if pass_input:
            pass_input.fill("")
            pass_input.press_sequentially(self.bot.password, delay=150)
        delay(1, 2)
        
        submit_btn = self.bot.page.locator('button[type="submit"]').first
        if submit_btn.is_visible(timeout=2000):
            submit_btn.click(force=True)
        else:
            try:
                login_btn = self.bot.page.get_by_text('Přihlásit', exact=False).first
                if not login_btn.is_visible():
                    login_btn = self.bot.page.get_by_text('Log in', exact=False).first
                if login_btn.is_visible():
                    login_btn.click(force=True)
            except:
                pass
            
        delay(5, 8)
        
        print("[IG] Provádím úklid po přihlášení...")
        self.bot.handle_popups(['Nyní ne', 'Not Now', 'Uložit', 'Save'])
        print("[IG] Přihlašovací proces dokončen.")