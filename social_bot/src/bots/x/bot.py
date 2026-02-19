from src.core.base_bot import BaseBot
from .auth import XAuthenticator
from .scraper import XScraper

class XBot(BaseBot):
    def __init__(self, username, password, user_id="default"):
        super().__init__(user_id=user_id, platform="x")
        self.username = username
        self.password = password
        self.base_url = "https://x.com/" 
        
        self.auth = XAuthenticator(self)
        self.scraper = XScraper(self)

    def login(self):
        self.auth.login()