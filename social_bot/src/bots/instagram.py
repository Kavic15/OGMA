from src.core.base_bot import BaseBot
from src.utils.human_input import delay

class InstagramBot(BaseBot):
    def __init__(self, username, password, user_id="default"):
        super().__init__(user_id=user_id, platform="ig") 
        self.username = username
        self.password = password
        self.base_url = "https://www.instagram.com/"

    def login(self):
        self.open_url(self.base_url)
        
        # 1. Agresivní likvidace Cookies (Hunter Mode)
        print("[IG] Kontroluji Cookies okna...")
        cookie_keywords = ['Povolit', 'Odmítnout', 'Allow', 'Decline']
        for word in cookie_keywords:
            elements = self.page.eles(f'text:{word}')
            for ele in elements:
                if ele.states.is_displayed:
                    try:
                        ele.click(by_js=True)
                        print(f"[IG] Odkliknuto cookie tlačítko: '{word}'")
                        delay(2)
                        break
                    except:
                        pass

        # 2. HLEDÁME VIDITELNÝ FORMULÁŘ
        print("[IG] Kontroluji stav přihlášení...")
        all_login_inputs = self.page.eles('@name=email') + self.page.eles('@name=username')
        all_pass_inputs = self.page.eles('@name=pass') + self.page.eles('@name=password')
        
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
            if self.page.ele('css:svg[aria-label="Domů"]', timeout=3) or self.page.ele('css:svg[aria-label="Home"]', timeout=1):
                print("[IG] Již přihlášeno (ze session). Přeskakuji login.")
                return
            else:
                print("[IG] Nevidím viditelný login formulář, ale ani znaky přihlášení.")
                return

        # 3. Samotný Login
        print("[IG] Zadávám přihlašovací údaje...")
        login_input.input(self.username)
        delay(0.5, 1)
        
        if pass_input:
            pass_input.input(self.password)
        delay(1, 2)
        
        submit_btn = self.page.ele('@type=submit', timeout=2)
        if submit_btn and submit_btn.states.is_displayed:
            submit_btn.click(by_js=True)
        else:
            login_btns = self.page.eles('text:Přihlásit') + self.page.eles('text:Log in')
            for btn in login_btns:
                if btn.states.is_displayed:
                    btn.click(by_js=True)
                    break
            
        delay(5, 8)
        
        # 4. Úklid po přihlášení
        print("[IG] Provádím úklid po přihlášení...")
        self.handle_popups(['Nyní ne', 'Not Now', 'Uložit', 'Save'])
        print("[IG] Přihlašovací proces dokončen.")