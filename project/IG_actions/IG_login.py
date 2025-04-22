from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
import time

def login_to_instagram(username, password):
    # Set up the WebDriver
    driver = webdriver.Chrome()
    
    # Open Instagram's homepage
    driver.get("https://www.instagram.com/?hl=en")
    time.sleep(3)
    
    try:
        # Deny cookies
        deny_cookies_button = driver.find_element(By.XPATH, "/html/body/div[3]/div[1]/div/div[2]/div/div/div/div/div[2]/div/button[2]")
        deny_cookies_button.click()
        time.sleep(3)
    except:
        pass
    
    # Enter username
    print("Entering username: " + username)
    username_input_box = driver.find_element(By.XPATH, "//*[@id=\"loginForm\"]/div[1]/div[1]/div/label/input")
    username_input_box.send_keys(username)
    time.sleep(1)
    
    # Enter password
    print("Entering password: " + password)
    password_input_box = driver.find_element(By.XPATH, "//*[@id=\"loginForm\"]/div[1]/div[2]/div/label/input")
    password_input_box.send_keys(password)
    time.sleep(1)
    
    # Click login button
    login_button = driver.find_element(By.XPATH, "//*[@id=\"loginForm\"]/div[1]/div[3]/button")
    login_button.click()
    time.sleep(5)

    try:
        not_now_button = driver.find_element(By.XPATH, "/html/body/div[1]/div/div/div[2]/div/div/div[1]/div[1]/div[1]/section/main/div/div/div/div")
        not_now_button.click()
        time.sleep(5)
    except:
        pass

    # Return the driver instance for further actions
    return driver