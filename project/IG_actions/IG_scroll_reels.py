import keyboard
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from utils.delay import delay

def scroll_reels(driver, logger=None):
    global stop_scrolling, pause_scrolling
    stop_scrolling = False
    pause_scrolling = False
    
    def toggle_pause():
        global pause_scrolling
        pause_scrolling = not pause_scrolling
    
    try:
        # Register hotkeys
        keyboard.add_hotkey('Alt+n', lambda: globals().update(stop_scrolling=True))
        keyboard.add_hotkey('ALT+p', toggle_pause)

        if logger:
            logger("Starting reel scroll...")
            logger("Controls: [Alt+P] Pause/Resume | [Alt+N] Stop")

        try:
            if logger:
                logger("Navigating to Reels section...")
            reels_button = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, 
                    "//a[contains(@href, '/reels/')] | "  
                    "//div[text()='Reels'] | "  
                    "//div[@aria-label='Reels']"  
                ))
            )
            reels_button.click()
            if logger:
                logger("Successfully opened Reels section")
            
            main_content = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, 'body'))
            )
            driver.execute_script("arguments[0].focus();", main_content)

            if logger:
                logger("Starting automatic scrolling...")
            
            while not stop_scrolling:
                # Check pause state
                if pause_scrolling:
                    if logger:
                        logger("Scrolling paused")
                    while pause_scrolling and not stop_scrolling:
                        time.sleep(0.5)  # Check every 500ms
                    if logger and not stop_scrolling:
                        logger("Scrolling resumed")
                
                # Perform scroll action
                ActionChains(driver).send_keys(Keys.ARROW_DOWN).perform()
                if logger:
                    logger("Loading new reel...")
                delay(10)  # Time between scrolls

            if logger:
                logger("Auto-scroll stopped by user")
                
        except Exception as e:
            error_msg = f"Error during reel scrolling: {str(e)}"
            if logger:
                logger(error_msg)
            raise
                
    except Exception as e:
        error_msg = f"Critical scroll error: {str(e)}"
        if logger:
            logger(error_msg)
        raise
        
    finally:
        # Reset states
        stop_scrolling = False
        pause_scrolling = False
        
    return driver