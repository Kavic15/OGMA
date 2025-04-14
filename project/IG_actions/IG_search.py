from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def search_for_account(driver, search_query):
    # Wait for the search bar to be clickable
    search_input = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//input[@placeholder='Search']")))
    search_input.click()
    search_input.send_keys(search_query)
    time.sleep(5)  # Wait for search results
    
    # Click the matching account from results
    account = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, f"//span[text()='{search_query}']/ancestor::a")))
    account.click()
    time.sleep(5)
    
    return driver  # Return driver for further actions