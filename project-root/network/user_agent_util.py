from fake_useragent import UserAgent

class UserAgentGenerator:
    def __init__(self):
        self.ua = UserAgent()
    
    def get_random_ua(self):
        return self.ua.random