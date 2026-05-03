from src.core.base_bot import BaseBot
from .scraper import YouTubeScraper

class YouTubeBot(BaseBot):
    def __init__(self, username=None, password=None, user_id="default", headless=True):
        super().__init__(user_id=user_id, platform="youtube", headless=headless)
        
        # Uložíme i když je nevyužijeme (pro zachování stejného rozhraní jako XBot/IGBot)
        self.username = username
        self.password = password
        
        self.base_url = "https://www.youtube.com/"
        
        # Pro YT nepoužíváme Authenticator, jelikož těžíme veřejná data bez přihlášení
        self.scraper = YouTubeScraper(self)

    def login(self):
        # Přepíšeme metodu login, aby nepadala chyba, ale jen bot oznámil přeskočení
        print("[YT] Přihlašování přeskočeno (veřejná data).")
        pass