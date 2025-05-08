from identity.get_userdata import get_FB_password_by_ID, get_FB_username_by_ID
from .FB_login import login_to_facebook
from .FB_scroll_reels import scroll_reels
from .FB_multi_session import active_drivers, active_drivers_lock

def FB_user_behaviour(userid=0, logger=None):
    driver = None
    try:
        # Fetch credentials
        username = get_FB_username_by_ID(userid)
        password = get_FB_password_by_ID(userid)
        
        if logger:
            logger(f"Starting Facebook session for user {userid}")
            logger(f"Retrieved credentials for username: {username}")

        # Login and add driver to global list
        driver = login_to_facebook(username, password, logger)
        
        with active_drivers_lock:
            active_drivers.append(driver)
            if logger:
                logger(f"Active sessions: {len(active_drivers)}")

        # Perform actions
        if logger:
            logger("Starting reel scrolling behavior")
        scroll_reels(driver, logger=logger)
        if logger:
            logger("Completed reel scrolling session")

    except Exception as e:
        error_msg = f"Facebook error (User {userid}): {str(e)}"
        if logger:
            logger(error_msg)
        else:
            print(error_msg)
        raise

    finally:
        # Cleanup
        if driver:
            if logger:
                logger("Cleaning up browser instance")
                
            with active_drivers_lock:
                if driver in active_drivers:
                    active_drivers.remove(driver)
                    if logger:
                        logger(f"Remaining active sessions: {len(active_drivers)}")
            
            try:
                driver.quit()
                if logger:
                    logger("Browser closed successfully")
            except Exception as e:
                error_msg = f"Error closing browser: {str(e)}"
                if logger:
                    logger(error_msg)
                else:
                    print(error_msg)

    if logger:
        logger(f"Completed Facebook session for user {userid}")
    
    return driver