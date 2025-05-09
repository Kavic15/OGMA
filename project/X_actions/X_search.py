# X_search.py
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils.delay import delay
from utils.mouse_actions import human_typing, random_mouse_movement
import time

def search_for_account(driver, search_query, logger=None):
    def log(message):
        if logger:
            logger(message)
        else:
            print(message)

    try:
        # Navigate to explore page
        log("Navigating to Explore section...")
        try:
            explore_button = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a[data-testid='AppTabBar_Explore_Link']"))
            )
            random_mouse_movement(driver, intensity=0.8)
            explore_button.click()
            delay(2)
        except Exception as e:
            log("Couldn't find explore button, trying direct search...")
            driver.get("https://x.com/explore")
            delay(3)

        # Activate search input
        log("Activating search input...")
        search_container = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-testid='SearchBox_Search_Input_container']"))
        )
        random_mouse_movement(driver, movements=2)
        search_container.click()
        delay(1)

        # Input search query
        log(f"Searching for: {search_query}")
        search_input = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input[data-testid='SearchBox_Search_Input']"))
        )
        human_typing(search_input, search_query, driver)
        random_mouse_movement(driver, intensity=0.5)
        delay(2)

        # Wait for results
        log("Waiting for search results...")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-testid='typeaheadResult']"))
        )
        random_mouse_movement(driver, movements=3)
        delay(1)

        # Select account from results
        log(f"Selecting account: {search_query}")
        account_xpath = f"//div[@data-testid='TypeaheadUser']//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{search_query.lower()}')]"
        
        try:
            account_element = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, account_xpath))
            )
            # Scroll into view and human-like click
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", account_element)
            random_mouse_movement(driver, intensity=0.7)
            account_element.click()
        except Exception as e:
            log("Primary selection failed, trying fallback...")
            accounts = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='TypeaheadUser']")
            if accounts:
                random_mouse_movement(driver, intensity=1.2)
                accounts[0].click()
            else:
                raise

        # Verify successful navigation
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-testid='UserName']"))
        )
        random_mouse_movement(driver, intensity=0.9)
        delay(2)

        return driver

    except Exception as e:
        error_msg = f"Search failed: {str(e)}"
        log(error_msg)
        driver.save_screenshot("search_error.png")
        raise