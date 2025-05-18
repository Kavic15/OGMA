# FB_login.py
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils.mouse_actions import random_mouse_movement, human_typing
from utils.delay import delay
import sys
import random
import time

def login_to_facebook(username, password, logger=None):
    """Added logger parameter for logging callback"""
    driver = webdriver.Chrome()
    
    def log(message):
        if logger:
            logger(message)
        else:
            print(message, file=sys.stdout)

    driver.get("https://www.facebook.com/?hl=en")
    
    try:
        random_mouse_movement(driver, intensity=0.8)
        
        deny_cookies_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Odmítnout')]"))
        )
        random_mouse_movement(driver, movements=2)
        deny_cookies_button.click()
        log("Cookies dialog dismissed")
        
    except Exception as e:
        log(f"Cookies dialog error: {str(e)}")
    
    try:
        email_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "email"))
        )
        
        # Enter username with human-like behavior
        log(f"Entering username: {username}")
        random_mouse_movement(driver)
        human_typing(email_field, username, driver)
        delay(random.uniform(0.5, 1.2), logger=logger)
        
        # Enter password
        log(f"Entering password: {'*' * len(password)}")
        pass_field = driver.find_element(By.NAME, "pass")
        random_mouse_movement(driver, intensity=1.2)
        human_typing(pass_field, password, driver)
        delay(random.uniform(0.8, 1.5), logger=logger)
        
        # Login with natural click
        login_button = driver.find_element(By.XPATH, "//button[@type='submit']")
        random_mouse_movement(driver, movements=1)
        log("Login button clicked")
        
        # Post-login
        try:
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Not Now')]"))
            ).click()
            log("Dismissed post-login prompt")
            random_mouse_movement(driver, intensity=0.5)
        except Exception as e:
            log(f"No post-login prompt: {str(e)}")
            
    except Exception as e:
        log(f"Login failed: {str(e)}")
        raise
    
    return driver