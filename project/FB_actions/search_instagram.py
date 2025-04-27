#/html/body/div[1]/div/div/div[2]/div/div/div[1]/div[1]/div[2]/div/div/div/div/div[2]/div[2]/span/div/a/div/div[1]/div/div/svg

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
import time


def search_profile(driver, username):
    search_button = driver.find_element(By.XPATH, "/html/body/div[1]/div/div/div[2]/div/div/div[1]/div[1]/div[2]/div/div/div/div/div[2]/div[2]/span/div/a/div/div[1]/div/div/svg")
    search_button.click()
    time.sleep(2)
    
    search_input = driver.find_element(By.XPATH, "//input[@placeholder='Search']")
    search_input.send_keys(username)
    time.sleep(2)