from identity.get_userdata import get_X_password_by_ID, get_X_username_by_ID
from .X_login import login_to_x
from .X_search import search_for_account
from utils.delay import delay
from .X_multi_session import active_drivers, active_drivers_lock
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import keyboard

def X_user_behaviour(userid=0, logger=None):
    driver = None
    try:
        # Log session start
        if logger:
            logger(f"Starting X session for user {userid}")
        
        # Fetch credentials
        username = get_X_username_by_ID(userid)
        password = get_X_password_by_ID(userid)
        if logger:
            logger(f"Retrieved credentials for username: {username}")
            logger("Attempting login...")

        # Login and add driver to global list
        driver = login_to_x(username, password, userid)
        if logger:
            logger("Login successful")
        
        with active_drivers_lock:
            active_drivers.append(driver)
            if logger:
                logger(f"Active X sessions: {len(active_drivers)}")
        
        # DEBUG
        # keyboard.wait('ctrl+q')

        # Search workflow
        target_account = "prima"  # Replace with dynamic value if needed
        if logger:
            logger(f"Starting search for account: {target_account}")
        
        search_for_account(driver, search_query=target_account, logger=logger)
        
        keyboard.wait('ctrl+q')

    except Exception as e:
        error_msg = f"X error (User {userid}): {str(e)}"
        if logger:
            logger(error_msg)
        raise

    finally:
        # Cleanup
        if driver:
            if logger:
                logger("Cleaning up X browser instance")
            
            with active_drivers_lock:
                if driver in active_drivers:
                    active_drivers.remove(driver)
                    if logger:
                        logger(f"Remaining X sessions: {len(active_drivers)}")
            
            try:
                driver.quit()
                if logger:
                    logger("X browser closed successfully")
            except Exception as e:
                error_msg = f"Error closing X browser: {str(e)}"
                if logger:
                    logger(error_msg)

    if logger:
        logger(f"Completed X session for user {userid}")
    
    return driver