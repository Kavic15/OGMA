import json
import os
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from utils.log import log
from utils.delay import delay

def scrape_and_save_tweets(driver, max_posts=50):
    try:
        log("Starting tweet scraping process", tag="X SCRAPE")
        
        # Create output directory
        today = datetime.now().strftime("%Y-%m-%d")
        output_dir = os.path.join("X_scraped_data", today)
        os.makedirs(output_dir, exist_ok=True)

        # Wait for timeline container
        timeline = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[aria-label^="Timeline: "]'))
        )
        scraped_data = []
        last_position = 0
        scroll_attempts = 0

        while len(scraped_data) < max_posts and scroll_attempts < 10:
            # Find all visible tweet containers
            containers = driver.find_elements(By.CSS_SELECTOR, 'div[data-testid="cellInnerDiv"]')
            
            for container in containers[len(scraped_data):]:
                try:
                    tweet = process_tweet_container(container)
                    if tweet:
                        scraped_data.append(tweet)
                        if len(scraped_data) >= max_posts:
                            break
                except Exception as e:
                    log(f"Skipping tweet: {str(e)}", tag="X WARNING")

            # Scroll down
            driver.execute_script(
                "window.scrollBy(0, 1000);"
            )
            delay(2)
            
            # Check if new posts loaded
            if len(scraped_data) == last_position:
                scroll_attempts += 1
            else:
                scroll_attempts = 0
                last_position = len(scraped_data)

        # Save results
        filename = f"X_scraped_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(scraped_data, f, ensure_ascii=False, indent=2)
            
        log(f"Saved {len(scraped_data)} tweets to {filename}", tag="X SCRAPE")
        return scraped_data

    except Exception as e:
        log(f"Scraping failed: {str(e)}", tag="X ERROR")
        raise

def extract_media(container):
    """Extracts images and videos from tweet container"""
    media = {"images": [], "videos": []}
    
    try:
        # Extract images
        images = container.find_elements(By.CSS_SELECTOR, 'img[alt="Image"]')
        media["images"] = [img.get_attribute("src") for img in images if img.get_attribute("src")]
        
        # Extract videos
        video_components = container.find_elements(By.CSS_SELECTOR, 'div[data-testid="videoComponent"]')
        for video in video_components:
            # Try to get video URL from different potential sources
            video_url = (
                video.find_element(By.TAG_NAME, 'video').get_attribute("src") 
                or video.find_element(By.TAG_NAME, 'source').get_attribute("src")
                or video.get_attribute("data-video-url")
            )
            if video_url:
                media["videos"].append(video_url)
                
        return media
    except Exception as e:
        log(f"Media extraction error: {str(e)}", tag="X WARNING")
        return media

def process_tweet_container(container):
    return {
        "scrape_time": datetime.now().isoformat(),
        "handle": extract_author_info(container)["handle"],
        "text": extract_tweet_text(container),
        "time": extract_post_time(container),
        "media": extract_media(container),
        **extract_engagement_metrics(container)
    }

def extract_author_info(container):
    try:
        # Find the username link using href pattern
        handle_link = container.find_element(
            By.CSS_SELECTOR, 'a[href^="/"][role="link"]:not([tabindex])'
        )
        handle = handle_link.get_attribute("href").split("/")[-1]
        log(f"Extracted author handle: {handle}", tag="X SCRAPE")
        
        return {
            "handle": f"@{handle}"
        }
    except Exception as e:
        log(f"Author extraction error: {str(e)}", tag="X WARNING")
        return {"handle": None}

def extract_tweet_text(container):
    try:
        return container.find_element(By.CSS_SELECTOR, 'div[data-testid="tweetText"]').text
    except:
        return None

def extract_post_time(container):
    try:
        return container.find_element(By.TAG_NAME, 'time').get_attribute('datetime')
    except:
        return None

def extract_engagement_metrics(container):
    try:
        metrics_str = container.find_element(
            By.CSS_SELECTOR, 'div[role="group"][aria-label*="replies"]'
        ).get_attribute('aria-label')
        
        return {
            "replies": parse_metric(metrics_str, "replies"),
            "reposts": parse_metric(metrics_str, "reposts"),
            "likes": parse_metric(metrics_str, "likes"),
            "bookmarks": parse_metric(metrics_str, "bookmarks"),
            "views": parse_metric(metrics_str, "views")
        }
    except:
        return {
            "replies": None,
            "reposts": None,
            "likes": None,
            "bookmarks": None,
            "views": None
        }

def parse_metric(metrics_str, metric_name):
    try:
        parts = metrics_str.split(', ')
        for part in parts:
            if metric_name in part.lower():
                return int(''.join(filter(str.isdigit, part)))
        return None
    except:
        return None