import random

class ProxyManager:
    def __init__(self, proxy_list):
        self.proxies = proxy_list
    
    def get_random_proxy(self):
        return random.choice(self.proxies)
