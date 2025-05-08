from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils.delay import delay

import time

def search_for_account(driver, search_query, logger=None):
    try:
        # Search button interaction
        if logger:
            logger("Locating search button...")
        else:
            print("Finding search input...")
            
        search_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div/div[2]/div/div/div[1]/div[1]/div[2]/div/div/div/div/div[2]/div[2]/span/div/a/div"))
        )
        search_button.click()
        if logger:
            logger("Search button clicked")

        # Search input handling
        if logger:
            logger(f"Typing search query: {search_query}")
        else:
            print("Typing search_query...")
            
        search_input = driver.find_element(By.XPATH, "/html/body/div[1]/div/div/div[2]/div/div/div[1]/div[1]/div[2]/div/div/div[2]/div/div/div/div[2]/div/div/div[1]/div/div/input")
        search_input.send_keys(search_query)
        
        if logger:
            logger("Waiting for search results...")
        delay(5)

        # Account selection
        # Account selection with improved locator
        if logger:
            logger(f"Attempting to select account: {search_query}")
            
        try:
            # More robust XPath that matches partial text and checks href
            account_xpath = (
                f"//a[contains(@href, '{search_query.lower()}')]//"  # Check profile link
                f"span[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), "  # Case-insensitive
                f"'{search_query.lower()}')]"  # Partial text match
            )
            
            account = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, account_xpath))
            )
            account.click()
            
        except Exception as e:
            # Fallback to original selector with exact match
            if logger:
                logger("Trying fallback selector...")
            account = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, f"//span[text()='{search_query}']/ancestor::a"))
            )
            account.click()
        
        return driver

    except Exception as e:
        error_msg = f"Search failed: {str(e)}"
        if logger:
            logger(error_msg)
        else:
            print(error_msg)
        raise