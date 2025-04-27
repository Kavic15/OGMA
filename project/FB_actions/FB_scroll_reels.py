import keyboard
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains  # Add this import
from utils.delay import delay

def scroll_reels(driver):
    global stop_scrolling
    stop_scrolling = False
    
    try:
        print("Navigating to Reels...")
        reels_button = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, 
                "//a[contains(@href, '/reels/')] | "  
                "//div[text()='Reels'] | "  
                "//div[@aria-label='Reels']"  
            ))
        )
        reels_button.click()
        print("Reels section opened")
        
        # Wait for body and ensure focus
        main_content = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, 'body'))
        )
        
        # Explicitly focus using JavaScript
        driver.execute_script("arguments[0].focus();", main_content)
        
        # Optional: Click to focus if needed
        # main_content.click()
        
        print("Starting auto-scroll (Press Ctrl+N to stop)...")
        while not stop_scrolling:
            delay(10)
            
            # Use ActionChains for reliable key press
            ActionChains(driver)\
                .send_keys(Keys.ARROW_DOWN)\
                .perform()
            
            print("Loading new reel...")
            
        print("Auto-scroll stopped")
            
    except Exception as e:
        print(f"Error during reel scrolling: {str(e)}")
        
    return driver