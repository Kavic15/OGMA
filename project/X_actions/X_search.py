from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
import time

def search_for_account(driver, search_query):
    # Wait for the search bar to be clickable
    print("Finding search input...")
    search_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div/div[2]/div/div/div[1]/div[1]/div[2]/div/div/div/div/div[2]/div[2]/span/div/a/div")))
    search_button.click()

    # search_button = driver.find_element(By.XPATH, "/html/body/div[1]/div/div/div[2]/div/div/div[1]/div[1]/div[2]/div/div/div/div/div[2]/div[2]/span/div/a/div")
    # search_button.click()
    
    print("Typing search_query...")
    search_input_box = driver.find_element(By.XPATH, "/html/body/div[1]/div/div/div[2]/div/div/div[1]/div[1]/div[2]/div/div/div[2]/div/div/div/div[2]/div/div/div[1]/div/div/input")
    search_input_box.send_keys(search_query)
    time.sleep(5)  # Wait for search results
    
    # Click the matching account from results
    account = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, f"//span[text()='{search_query}']/ancestor::a")))
    account.click()
    time.sleep(5)
    
    return driver  # Return driver for further actions