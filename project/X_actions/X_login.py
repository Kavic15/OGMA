# X_login.py
import os
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils.delay import delay
from utils.mouse_actions import human_typing, random_mouse_movement
from identity.get_userdata import get_user_email
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
    """Enhanced login function with human-like interactions"""
    # Retrieve credentials
    try:
        email = get_user_email(user_id)
    except Exception as e:
        print(f"Error retrieving credentials: {e}")
        return

    # Set up WebDriver
    driver = webdriver.Chrome()
    
    try:
        # Open X homepage
        driver.get("https://x.com/?hl=en")
        random_mouse_movement(driver)
        delay(2)

        # Handle cookies
        try:
            deny_cookies = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Refuse non-essential cookies')]"))
            )
            deny_cookies.click()
            random_mouse_movement(driver)
            delay(1)
        except Exception as e:
            print("Cookie handling skipped:", e)

        # Initiate login
        try:
            login_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//a[@data-testid='loginButton']"))
            )
            random_mouse_movement(driver)
            login_btn.click()
            delay(1)
        except Exception as e:
            print("Login initiation failed:", e)
            raise

        # Username entry
        try:
            username_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "text"))
            )
            human_typing(username_field, username, driver)
            delay(1)
            username_field.send_keys(Keys.RETURN)
            #username_field.send_keys(Keys.RETURN) # Instant typing
            random_mouse_movement(driver)
            delay(2)
        except Exception as e:
            print("Username entry failed:", e)
            raise

        # Handle possible email prompt
        try:
            email_prompt = WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.XPATH, "//span[contains(text(), 'Telefon nebo e-mail')]"))
            )
            email_field = driver.find_element(By.XPATH, "//input[@name='text' and @type='email']")
            human_typing(email_field, email, driver)
            email_field.send_keys(Keys.RETURN)
            # email_field.send_keys(Keys.RETURN) # Instant typing
            random_mouse_movement(driver)
            delay(2)
        except Exception as e:
            print("No email prompt detected, proceeding to password")

        # Password entry
        try:
            password_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "password"))
            )
            human_typing(password_field, password, driver)
            password_field.send_keys(Keys.RETURN)
            random_mouse_movement(driver)
            delay(3)  # This should now use the correct delay function
        except Exception as e:
            print("Password entry failed:", e)
            raise

        # Post-login prompts
        try:
            not_now_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[@role='button' and .//span[text()='Not Now']]"))
            )
            not_now_btn.click()
            delay(1)
        except Exception as e:
            print("No post-login prompt:", e)

        return driver

    except Exception as e:
        print(f"Login failed: {e}")
        driver.quit()
        return None