from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from utils.mouse_actions import human_typing
from utils.delay import delay
from utils.log import log

def search_for_account(driver, search_query):
    try:
        # Click Explore button using aria-label
        log("Navigating to Explore section", tag="X SEARCH")
        explore_link = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a[aria-label='Search and explore'][href='/explore']"))
        )
        driver.execute_script("arguments[0].click();", explore_link)
        delay(1)

        # Focus on search input using placeholder attribute
        log("Activating search input", tag="X SEARCH")
        search_input = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input[placeholder='Search'][aria-label='Search query']"))
        )
        ActionChains(driver)\
            .move_to_element(search_input)\
            .pause(0.5)\
            .click()\
            .perform()

        # Input search query with human-like typing
        log(f"Inputting search term: {search_query}", tag="X SEARCH")
        human_typing(search_input, search_query, driver)
        delay(1)

        # Wait for results listbox to appear
        log("Waiting for search results", tag="X SEARCH")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='listbox']"))
        )
        delay(1)
        # Find and click first account result using data-testid
        log("Selecting first account result", tag="X SEARCH")
        first_account = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "div[role='listbox'] button[data-testid='TypeaheadUser']"))
        )
        first_account.click()

        log("Successfully navigated to target account", tag="X SEARCH")
        delay(2)

    except Exception as e:
        error_msg = f"Search operation failed: {str(e)}"
        log(error_msg, tag="X ERROR")
        raise