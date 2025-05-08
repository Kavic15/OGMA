# utils/mouse_actions.py
from selenium.webdriver.common.action_chains import ActionChains
import random
import time
from .delay import delay

def random_mouse_movement(driver, movements=4, intensity=1.0):
    """
    Generate human-like random mouse movements
    Parameters:
    - driver: WebDriver instance
    - movements: Number of movement sequences (default 3)
    - intensity: Movement scale multiplier (0.5-2.0)
    """
    try:
        window_size = driver.get_window_size()
        actions = ActionChains(driver)
        
        base_speed = 0.2 * intensity
        move_range = int(300 * intensity)
        
        # Start from current position
        actions.move_by_offset(0, 0)
        
        for _ in range(movements):
            # Generate random offsets with natural decay
            x_offset = random.randint(-move_range, move_range)
            y_offset = random.randint(-move_range, move_range)
            
            # Add smooth movement with intermediate steps
            steps = random.randint(2, 5)
            for _ in range(steps):
                partial_x = x_offset // steps
                partial_y = y_offset // steps
                actions.move_by_offset(partial_x, partial_y)
                actions.pause(random.uniform(base_speed*0.8, base_speed*1.2))
            
            # Random small adjustments
            for _ in range(random.randint(0, 2)):
                actions.move_by_offset(
                    random.randint(-10, 10),
                    random.randint(-10, 10)
                )
                actions.pause(random.uniform(0.1, 0.3))
            
            # Random pause between movements
            actions.pause(random.uniform(0.2, 0.5)*intensity)
        
        actions.perform()
        delay(1*intensity)
        
    except Exception as e:
        pass  # Silent fail to prevent detection

def human_typing(element, text, driver=None):
    """
    Simulate human-like typing with random delays
    Parameters:
    - element: WebElement to type into
    - text: Text to input
    - driver: Optional WebDriver for combined mouse+typing
    """
    try:
        # Focus on element
        if driver:
            actions = ActionChains(driver)
            actions.move_to_element(element).pause(0.2).click().perform()
            time.sleep(0.3)
        
        # Type with random delays and occasional corrections
        for i, char in enumerate(text):
            element.send_keys(char)
            delay = random.uniform(0.05, 0.18)
            
            # Random longer pause every 3-5 characters
            if i % random.randint(3, 5) == 0:
                delay += random.uniform(0.1, 0.3)
            
            time.sleep(delay)
            
            # Random backspace chance (5%)
            if random.random() < 0.05:
                element.send_keys(Keys.BACKSPACE)
                time.sleep(random.uniform(0.2, 0.4))
                element.send_keys(char)
                time.sleep(random.uniform(0.1, 0.2))
    
    except Exception as e:
        element.send_keys(text)  # Fallback