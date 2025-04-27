from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils.delay import delay
import time

def login_to_facebook(username, password):
    # Set up the WebDriver
    driver = webdriver.Chrome()
    
    # Open Instagram's homepage
    driver.get("https://www.facebook.com/?hl=en")
    
    try:
        # Wait for and deny cookies
        deny_cookies_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Decline optional cookies')]"))
        )
        deny_cookies_button.click()
    except Exception as e:
        print("Cookies dialog not found or could not be clicked:", e)
    
    # Wait for login form to be present
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.NAME, "username"))
    )
    
    # Enter username
    print("Entering username:", username)
    username_input = driver.find_element(By.NAME, "username")
    username_input.send_keys(username)
    delay(1)
    
    # Enter password
    print("Entering password:", password)
    password_input = driver.find_element(By.NAME, "password")
    password_input.send_keys(password)
    delay(1)
    
    # Click login button
    login_button = driver.find_element(By.XPATH, "//button[@type='submit']")
    login_button.click()
    delay(1)
    
    # Handle post-login prompts (e.g., "Save Login Info" or "Turn on Notifications")
    try:
        # Wait for "Not Now" button after login
        not_now_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Not Now')]"))
        )
        not_now_button.click()
    except Exception as e:
        print("No post-login prompt found:", e)
    
    # Return the driver instance for further actions
    return driver