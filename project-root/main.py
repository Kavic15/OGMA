from browser_engine.selenium_driver import BrowserController
from network.proxy_rotator import ProxyManager
from network.user_agent_util import UserAgentGenerator

def social_media_bot(config):
    proxy = ProxyManager(config['proxies']).get_random_proxy()
    user_agent = UserAgentGenerator().get_random_ua()
    
    with BrowserController(proxy=proxy, user_agent=user_agent) as bot:
        bot.login(config['credentials'])
        bot.collect_posts(keywords=config['keywords'])
        bot.interact_with_content()
        bot.save_data(format='json')