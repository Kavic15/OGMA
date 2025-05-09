import json
import os
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urljoin
import re

def scrape_comments(driver, logger=None):
    """Scrape comments while excluding post description"""
    try:
        if logger:
            logger("Scraping comments...")

        comments = []
        
        # Target ONLY the comments section (not the main post)
        comments_section = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, 
                "//div[@role='dialog']//ul[contains(@class, '_a9z6')]"
            ))
        )

        # Find individual comment elements
        comment_elements = comments_section.find_elements(By.XPATH,
            ".//div[contains(@class, '_a9zr') and .//span[@dir='auto']"
        )

        for comment in comment_elements:
            try:
                # Extract username from specific nested element
                username_element = comment.find_element(By.XPATH,
                    ".//div[contains(@class, 'x9f619')]/a[contains(@class, 'x1i10hfl')]"
                )
                username = username_element.text.strip()
                profile_url = username_element.get_attribute('href')

                # Extract comment text from specific span
                text_element = comment.find_element(By.XPATH,
                    ".//span[contains(@class, '_ap3a') and @dir='auto']"
                )
                comment_text = text_element.text.strip()

                comments.append({
                    "username": username,
                    "profile_url": profile_url,
                    "text": comment_text
                })

            except Exception as e:
                if logger:
                    logger(f"Skipping invalid comment: {str(e)}")
                continue

        if logger:
            logger(f"Found {len(comments)} valid comments")

        return comments

    except Exception as e:
        if logger:
            logger(f"Comment scraping failed: {str(e)}")
        return []
    
    
def find_and_click_first_post(driver, logger=None):
    """Check for posts in search results and click the first one"""
    try:
        if logger:
            logger("Looking for posts in search results...")

        post_selector = "//div[contains(@class, 'x1lliihq') and contains(@class, 'x1n2onr6')]/a"
        first_post = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, post_selector))
        )
        
        if logger:
            logger("Found posts. Clicking first post...")
        first_post.click()
        return True
        
    except Exception as e:
        if logger:
            logger(f"Error finding/clicking post: {str(e)}")
        return False

def ensure_scraped_data_dir():
    """Create directory for scraped data if it doesn't exist"""
    os.makedirs("IG_scraped_data", exist_ok=True)

def get_filename():
    """Generate filename based on current date"""
    return datetime.now().strftime("%Y-%m-%d") + ".json"

def save_to_json(data, account_name):
    """Save scraped data to JSON file"""
    try:
        ensure_scraped_data_dir()
        filename = os.path.join("IG_scraped_data", get_filename())
        
        existing_data = []
        # Load existing data if file exists and is valid
        if os.path.exists(filename):
            try:
                if os.path.getsize(filename) > 0:
                    with open(filename, "r", encoding="utf-8") as f:
                        existing_data = json.load(f)
                        # Ensure loaded data is a list
                        if not isinstance(existing_data, list):
                            existing_data = []
            except (json.JSONDecodeError, Exception) as e:
                print(f"Error loading existing data: {str(e)} - Resetting data")
                existing_data = []
        
        # Create new entry
        entry = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M:%S"),
            "account": account_name,
            "post_description": data["description"],
            "hashtags": data["hashtags"],
            "mentions": data["mentions"],
            "full_text": data["full_text"],
            "comments": data["comments"]
        }
        
        existing_data.append(entry)
        
        # Save updated data
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)
            
        return True
    except Exception as e:
        print(f"Error saving data: {str(e)}")
        return False

def scrape_post_description(driver, logger=None):
    """Scrape post author and description from current post page"""
    try:
        if logger:
            logger("Scraping post data...")
            
        # Wait for main content
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, 'article'))
        )

        # Scrape post author from h2
        author_element = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, 
                "//h2[contains(@class, 'x6s0dn4') and contains(@class, 'x3nfvp2')]//a[contains(@href, '/')]"
            ))
        )
        account_name = author_element.text.strip()
        profile_url = author_element.get_attribute('href')
        
        if logger:
            logger(f"Found post author: {account_name}")

        # Scrape description from h1
        # Find image element with description
        img_element = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, 
                "//img[contains(@class, 'x5yr21d') and contains(@class, 'xu96u03')]"
            ))
        )
        
        full_text = img_element.get_attribute('alt') or ''
        
        # Extract structured data
        hashtags = []
        mentions = []
        
        for word in re.findall(r'[\#\@]\w+', full_text):
            if word.startswith('#'):
                hashtags.append({
                    "tag": word[1:],
                    "url": urljoin('https://www.instagram.com', f'/explore/tags/{word[1:]}')
                })
            elif word.startswith('@'):
                mentions.append({
                    "username": word[1:],
                    "profile_url": urljoin('https://www.instagram.com', f'/{word[1:]}')
                })
                
        clean_description = re.sub(r'[\#\@]\w+', '', full_text).strip()
        print(f"Cleaned description: {clean_description}")
        print(f"Hashtags: {hashtags}")
        print(f"Mentions: {mentions}")
        print(f"Full text: {full_text}")
        
        # Scrape comments
        comments = scrape_comments(driver, logger=logger)
        
        data = {
            "description": clean_description,
            "hashtags": hashtags,
            "mentions": mentions,
            "full_text": full_text,
            "comments": comments  # Add comments to data
        }
        
        # Save to JSON
        if save_to_json(data, account_name):
            if logger:
                logger("Data successfully saved to JSON file")
        else:
            if logger:
                logger("Failed to save data to JSON file")
        
        return data
        
    except Exception as e:
        if logger:
            logger(f"Scraping failed: {str(e)}")
        raise
        
    except Exception as e:
        if logger:
            logger(f"Scraping failed: {str(e)}")
        raise