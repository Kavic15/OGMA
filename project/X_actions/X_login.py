# X_login.py
import os
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from utils.delay import delay
from utils.mouse_actions import human_typing, random_mouse_movement
from identity.get_userdata import get_user_email
from utils.log import log
import time

def get_X_credentials(user_id):
    """Retrieve X username and password from users.json"""
    try:
        current_dir = os.path.dirname(__file__)
        json_path = os.path.join(current_dir, 'users.json')
        
        with open(json_path, 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        raise FileNotFoundError("The file users.json was not found.")
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON format in users.json.")
    
    users = data.get('users', [])
    
    if user_id < 0 or user_id >= len(users):
        raise ValueError("Invalid user ID provided.")
    
    user = users[user_id]
    x_account = user.get('social_media', {}).get('X', {})
    
    return {
        'username': x_account.get('username'),
        'password': x_account.get('password')
    }

def login_to_x(username, password, user_id):
    """Handles multiple verification steps dynamically"""
    driver = webdriver.Chrome()
    email = get_user_email(user_id)
    
    try:
        driver.get("https://x.com/?hl=en")
        handle_cookies(driver)
        
        # Initiate login
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//a[@data-testid='loginButton']"))
        ).click()

        verification_steps = 0
        max_verification_steps = 3  # Prevent infinite loops

        while verification_steps < max_verification_steps:
            try:
                # Check for password field first
                WebDriverWait(driver, 2).until(
                    EC.presence_of_element_located((By.NAME, "password"))
                )
                break  # Exit loop if password field appears
                
            except TimeoutException:
                # Handle verification step
                input_field = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='text']"))
                )
                
                # Determine required information
                label = get_input_label(driver)
                input_type = input_field.get_attribute("type").lower()
                
                if any(x in label for x in ["uživatelské", "username", "handle", "nutzername"]):
                    value = username
                elif any(x in label for x in ["email", "e-mail", "mail"]):
                    value = email
                elif any(x in label for x in ["telefon", "phone", "nummer", "téléphone"]):
                    raise Exception("Phone verification required")
                else:
                    # Fallback to email if label not recognized
                    value = email

                # Enter value and submit
                human_typing(input_field, value, driver)
                input_field.send_keys(Keys.RETURN)
                delay(2)
                verification_steps += 1

        # Final password entry
        password_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "password"))
        )
        human_typing(password_field, password, driver)
        password_field.send_keys(Keys.RETURN)
        delay(3)

        # Handle post-login prompts
        dismiss_post_login_prompts(driver)
        return driver

    except Exception as e:
        log(f"Login failed: {e}", tag="X ERROR")
        driver.quit()
        return None

def get_input_label(driver):
    """Get contextual label text using multiple strategies"""
    try:
        # Strategy 1: Nearby span element
        label = driver.execute_script(
            "return arguments[0].closest('label')?.querySelector('span')?.innerText",
            driver.find_element(By.CSS_SELECTOR, "input[name='text']")
        ) or ""
        
        # Strategy 2: Placeholder text
        if not label:
            label = driver.find_element(
                By.CSS_SELECTOR, "input[name='text']"
            ).get_attribute("placeholder") or ""
            
        return label.strip().lower()
    
    except:
        return ""

def handle_cookies(driver):
    """Handle cookie consent dialog if present"""
    try:
        WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Refuse')]"))
        ).click()
        delay(1)
    except:
        pass

def dismiss_post_login_prompts(driver):
    """Dismiss any post-login modals"""
    try:
        WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.XPATH, "//div[@role='dialog']//div[@role='button'][contains(., 'Not Now')]"))
        ).click()
        delay(1)
    except:
        pass