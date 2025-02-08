from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains

class BrowserController:
    def __init__(self, proxy=None, headless=True):
        options = webdriver.ChromeOptions()
        if proxy:
            options.add_argument(f'--proxy-server={proxy}')
        if headless:
            options.add_argument("--headless=new")
        
        self.driver = webdriver.Chrome(options=options)
        self.actions = ActionChains(self.driver)

    def human_like_movement(self):
        # Simulace lidského pohybu myší
        self.actions.move_by_offset(
            xoffset=random.randint(5, 15),
            yoffset=random.randint(5, 15)
        ).perform()