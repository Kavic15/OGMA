from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

def search_for_account(driver, search_query):
    try:
        # Wait for and find the search input using placeholder text
        search_input = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//input[@placeholder='Search Facebook']")
            )
        )
        
        # Type search query and press Enter
        print(f"Searching for: {search_query}")
        search_input.send_keys(search_query)
        search_input.send_keys(Keys.RETURN)
        
        # Wait for results and click matching account
        account = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable(
                (By.XPATH, f"//span[contains(text(), '{search_query}')]/ancestor::a")
            )
        )
        account.click()
        
        # Wait for profile page to load
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//div[@role='main']"))
        )
        
        return driver

    except Exception as e:
        print(f"Search failed: {str(e)}")
        raise