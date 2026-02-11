from src.core.base_bot import BaseBot
from .auth import InstagramAuthenticator
from .scraper import InstagramScraper

class InstagramBot(BaseBot):
    def __init__(self, username, password, user_id="default"):
        super().__init__(user_id=user_id, platform="ig") 
        self.username = username
        self.password = password
        
        # DOPLNĚNA CHYBĚJÍCÍ BASE URL
        self.base_url = "https://www.instagram.com/"
        
        self.auth = InstagramAuthenticator(self)
        self.scraper = InstagramScraper(self)

    def login(self):
        self.auth.login()