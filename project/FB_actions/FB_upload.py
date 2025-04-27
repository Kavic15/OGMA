from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def upload_picture_on_instagram(driver, image_path, caption=None, post=False):    
    try:
        # Navigate to post creation page
        driver.get("https://www.instagram.com/create")
        
        # Wait for upload form
        form = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "form[enctype='multipart/form-data']")
        ))
        
        # Find file input using class from your HTML
        file_input = form.find_element(By.CSS_SELECTOR, "input._ac69[type='file']")
        
        # Upload image
        file_input.send_keys(image_path)
        print("Image uploaded successfully")
        
        # Wait for image preview to load
        wait.until(EC.visibility_of_element_located(
            (By.XPATH, "//div[contains(@class, 'x1n2onr6')]//img")
        ))
        
        # Add caption if provided
        if caption:
            caption_box = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//div[@role='textbox']")
            ))
            caption_box.send_keys(caption)
            print("Caption added")
        
        # Submit post if requested
        if post:
            share_button = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//div[contains(text(), 'Share')]")
            ))
            share_button.click()
            print("Post shared successfully")
            time.sleep(5)  # Wait for completion
            
        return True
    
    except Exception as e:
        print(f"Upload failed: {str(e)}")
        return False

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time