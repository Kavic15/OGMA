from src.utils.human_input import delay

class InstagramAuthenticator:
    def __init__(self, bot):
        self.bot = bot

    def login(self):
        self.bot.open_url(self.bot.base_url)
        
        print("[IG] Kontroluji stav přihlášení...")
        # 1. RYCHLÁ KONTROLA SESSION (přesunuto na začátek pro okamžité přeskočení)
        if self.bot.page.ele('css:svg[aria-label="Domů"]', timeout=3) or self.bot.page.ele('css:svg[aria-label="Home"]', timeout=3):
            print("[IG] Již přihlášeno (ze session). Přeskakuji login a cookies.")
            return

        # 2. LIKVIDACE COOKIES (Spustí se jen u prvního přihlášení)
        print("[IG] Kontroluji Cookies okna...")
        cookie_keywords = ['Povolit', 'Odmítnout', 'Allow', 'Decline']
        for word in cookie_keywords:
            # Rychlé hledání prvního tlačítka (timeout 0.5s místo dlouhého čekání)
            btn = self.bot.page.ele(f'text:{word}', timeout=0.5)
            if btn and btn.states.is_displayed:
                try:
                    btn.click(by_js=True)
                    print(f"[IG] Odkliknuto cookie tlačítko: '{word}'")
                    delay(1.5)
                    break
                except:
                    pass

        # 3. HLEDÁNÍ PŘIHLÁŠOVACÍHO FORMULÁŘE
        all_login_inputs = self.bot.page.eles('@name=email') + self.bot.page.eles('@name=username')
        all_pass_inputs = self.bot.page.eles('@name=pass') + self.bot.page.eles('@name=password')
        
        login_input = None
        for inp in all_login_inputs:
            if inp.states.is_displayed:
                login_input = inp
                break
                
        pass_input = None
        for inp in all_pass_inputs:
            if inp.states.is_displayed:
                pass_input = inp
                break

        if not login_input:
            print("[IG] Nevidím viditelný login formulář, ale ani znaky přihlášení.")
            return

        # 4. SAMOTNÝ LOGIN
        print("[IG] Zadávám přihlašovací údaje...")
        login_input.input(self.bot.username)
        delay(0.5, 1)
        
        if pass_input:
            pass_input.input(self.bot.password)
        delay(1, 2)
        
        submit_btn = self.bot.page.ele('@type=submit', timeout=2)
        if submit_btn and submit_btn.states.is_displayed:
            submit_btn.click(by_js=True)
        else:
            login_btns = self.bot.page.eles('text:Přihlásit') + self.bot.page.eles('text:Log in')
            for btn in login_btns:
                if btn.states.is_displayed:
                    btn.click(by_js=True)
                    break
            
        delay(5, 8)
        
        # 5. ÚKLID PO PŘIHLÁŠENÍ
        print("[IG] Provádím úklid po přihlášení...")
        self.bot.handle_popups(['Nyní ne', 'Not Now', 'Uložit', 'Save'])
        print("[IG] Přihlašovací proces dokončen.")