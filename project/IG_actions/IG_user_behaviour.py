from identity.get_userdata import get_IG_password_by_ID, get_IG_username_by_ID
from .IG_login import login_to_instagram
from .IG_search import search_for_account
from .IG_scrape import find_and_click_first_post, scrape_post_description
from utils.delay import delay
from .IG_multi_session import active_drivers, active_drivers_lock
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import keyboard

def IG_user_behaviour(userid=0, logger=None):
    driver = None
    try:
        # Log session start
        if logger:
            logger(f"Starting Instagram session for user {userid}")
        
        # Fetch credentials
        username = get_IG_username_by_ID(userid)
        password = get_IG_password_by_ID(userid)
        if logger:
            logger(f"Retrieved credentials for username: {username}")
            logger("Attempting login...")

        # Login and add driver to global list
        driver = login_to_instagram(username, password)
        if logger:
            logger("Login successful")
        
        with active_drivers_lock:
            active_drivers.append(driver)
            if logger:
                logger(f"Active Instagram sessions: {len(active_drivers)}")

        # Search workflow
        target_account = "prima"  # Replace with dynamic value if needed
        if logger:
            logger(f"Starting search for account: {target_account}")
        
        search_for_account(driver, search_query=target_account, logger=logger)
        
        # Scraping workflow
        if logger:
            logger("Attempting to scrape first post...")
        
        if find_and_click_first_post(driver, logger):
            
            post_data = scrape_post_description(driver, logger)  # Pass account name
            
            if logger:
                logger(f"Scraped description: {post_data['description'][:50]}...")
                logger(f"Found {len(post_data['hashtags'])} hashtags")
                logger(f"Found {len(post_data['mentions'])} mentions")
            
            # Close post view
            ActionChains(driver).send_keys(Keys.ESCAPE).perform()
            if logger:
                logger("Closed post view")
            delay(1)
        else:
            if logger:
                logger("No posts found to scrape")


        keyboard.wait('ctrl+q')


        # Additional actions
        if logger:
            logger("Starting reel scrolling behavior")
        # scroll_reels(driver, logger=logger)
        
        if logger:
            logger("Completed reel scrolling session")

    except Exception as e:
        error_msg = f"Instagram error (User {userid}): {str(e)}"
        if logger:
            logger(error_msg)
        raise

    finally:
        # Cleanup
        if driver:
            if logger:
                logger("Cleaning up Instagram browser instance")
            
            with active_drivers_lock:
                if driver in active_drivers:
                    active_drivers.remove(driver)
                    if logger:
                        logger(f"Remaining Instagram sessions: {len(active_drivers)}")
            
            try:
                driver.quit()
                if logger:
                    logger("Instagram browser closed successfully")
            except Exception as e:
                error_msg = f"Error closing Instagram browser: {str(e)}"
                if logger:
                    logger(error_msg)

    if logger:
        logger(f"Completed Instagram session for user {userid}")
    
    return driver