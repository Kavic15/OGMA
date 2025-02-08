import time
import random

class HumanBehaviorSimulator:
    @staticmethod
    def random_delay(min=1.0, max=5.0):
        time.sleep(random.uniform(min, max))
    
    @staticmethod
    def random_scroll(driver):
        scroll_amount = random.randint(300, 1000)
        driver.execute_script(f"window.scrollBy(0, {scroll_amount})")