# X_search.py
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils.delay import delay
from utils.mouse_actions import human_typing, random_mouse_movement
import time

def search_for_account(driver, search_query, logger=None):
    def log(*messages):
        message = " ".join(str(m) for m in messages)
        if logger:
            logger(message)
        else:
            print(message)

    try:
        # Navigate to explore
        log("Accessing search functionality...")
        try:
            driver.get("https://x.com/explore")
            delay(2)
        except Exception as e:
            log("Couldn't navigate directly to explore:", e)
            raise

        # Find and activate search input using placeholder
        log("Locating search input...")
        search_input = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//input[@placeholder='Search']"))
        )
        
        # Human-like interaction sequence
        random_mouse_movement(driver, intensity=0.7)
        for _ in range(2):  # Double click to simulate real user
            search_input.click()
            delay(0.3)
        
        # Type search query
        log(f"Searching for: {search_query}")
        human_typing(search_input, search_query, driver)
        delay(1.5)  # Wait for results to populate

        # Account selection with improved matching
        log(f"Selecting account: {search_query}")
        try:
            # Case-insensitive match with partial text
            account_xpath = (
                f"//div[@data-testid='TypeaheadUser']//"
                f"span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÀÈÌÒÙÄËÏÖÜ', 'abcdefghijklmnopqrstuvwxyzáéíóúàèìòùäëïöü'), "
                f"'{search_query.lower()}')]"
            )
            account = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, account_xpath))
            )
            random_mouse_movement(driver, intensity=0.9)
            account.click()
        except Exception as e:
            log("Primary selection failed, trying username match...")
            # Fallback to @username match
            account = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, f"//span[contains(text(), '@{search_query.lower()}')]"))
            )
            account.click()

        # Verify navigation to profile
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Follow')]"))
        )
        delay(2)
        log("Successfully navigated to profile")

        return driver

    except Exception as e:
        error_msg = f"Search failed: {str(e)}"
        log(error_msg)
        driver.save_screenshot("x_search_error.png")
        raise