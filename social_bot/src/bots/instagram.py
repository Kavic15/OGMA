from src.core.base_bot import BaseBot
from src.utils.human_input import delay

class InstagramBot(BaseBot):
    def __init__(self, username, password, user_id="default"):
        super().__init__(user_id=user_id)
        self.username = username
        self.password = password
        self.base_url = "https://www.instagram.com/"

    def login(self):
        self.open_url(self.base_url)
        
        # 1. Kontrola, zda už nejsme přihlášeni (Session Persistence)
        # Hledáme ikonu domů nebo profilu
        if self.page.ele('@aria-label=Domů') or self.page.ele('text:Profile'):
            print("[IG] Již přihlášeno (ze session). Přeskakuji login.")
            return

        # 2. Univerzální likvidace Cookies
        self.handle_popups(['Decline', 'Odmítnout', 'Allow all', 'Povolit', 'Only allow essential'])

        # 3. Samotný Login (jen pokud vidíme inputy)
        if self.page.ele('@name=username', timeout=5):
            print("[IG] Zadávám přihlašovací údaje...")
            self.page.ele('@name=username').input(self.username)
            delay(0.5, 1)
            self.page.ele('@name=password').input(self.password)
            delay(1, 2)
            self.click_smart('@type=submit', "Login Button")
            delay(5, 8)
        
        # 4. Úklid po přihlášení (Not Now, Save Info)
        triggers = ['Not Now', 'Nyní ne', 'Not now', 'Uložit informace']
        for _ in range(2): # Zkusíme dvakrát, často jsou tam dvě okna za sebou
            self.handle_popups(triggers)

    def scrape_profile(self, target_username):
        url = f"{self.base_url}{target_username}/"
        self.open_url(url)
        
        # Klik na první post
        first_post = self.page.ele('css:article a', timeout=5) 
        if first_post:
            print(f"[IG] Otevírám první post u {target_username}...")
            first_post.click()
            delay(2)