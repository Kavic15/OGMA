from identity.get_userdata import get_X_password_by_ID, get_X_username_by_ID
from .X_login import login_to_x
from .X_search import search_for_account
from .X_scrape import scrape_and_save_tweets
from utils.delay import delay
from .X_multi_session import active_drivers, active_drivers_lock
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from utils.log import log
import keyboard

def X_user_behaviour(userid=0, target_accounts=None, max_posts=50):
    driver = None
    try:
        if not target_accounts:
            log("No target accounts specified!", tag="X ERROR")
            return

        # Log session start
        log(f"Starting X session for user {userid}", tag="X")
        
        # Fetch credentials
        username = get_X_username_by_ID(userid)
        password = get_X_password_by_ID(userid)
        log(f"Retrieved credentials for username: {username}", tag="X")
        log("Attempting login...", tag="X")

        # Login and add driver to global list
        driver = login_to_x(username, password, userid)
        log("Login successful", tag="X")
        
        with active_drivers_lock:
            active_drivers.append(driver)
            log(f"Active X sessions: {len(active_drivers)}", tag="X SESSIONS")

        # Process each target account
        for target_account in target_accounts:
            try:
                log(f"Starting search for account: {target_account}", tag="X SEARCH")
                search_for_account(driver, search_query=target_account)
                delay(3)
                scrape_and_save_tweets(driver, max_posts=max_posts)
                
                # Reset for next account
                driver.get("https://x.com/")
                delay(3)
            except Exception as e:
                log(f"Failed to process {target_account}: {str(e)}", tag="X ERROR")
                continue

    except Exception as e:
        error_msg = f"Operation failed: {str(e)}"
        log(error_msg, tag="X ERROR")
        raise

    finally:
        # Cleanup
        if driver:
            log("Cleaning up X browser instance", tag="X CLEANUP")
            
            with active_drivers_lock:
                if driver in active_drivers:
                    active_drivers.remove(driver)
                    log(f"Remaining X sessions: {len(active_drivers)}", tag="X SESSIONS")
            
            try:
                driver.quit()
                log("X browser closed successfully", tag="X CLEANUP")
            except Exception as e:
                error_msg = f"Error closing browser: {str(e)}"
                log(error_msg, tag="X ERROR")

    log(f"Completed X session for user {userid}", tag="X")
    return driver