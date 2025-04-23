from selenium import webdriver

driver = webdriver.Chrome()
driver.get("https://www.instagram.com/reels/DIYYtScPch3/")

# Wait for the video element to load (adjust selectors if needed)
video = driver.find_element("tag name", "video")

# Get duration using JS
duration = driver.execute_script("return arguments[0].duration;", video)
print(f"Reel duration: {duration:.2f} seconds")
