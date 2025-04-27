import threading
from selenium.webdriver.remote.webdriver import WebDriver

# Global thread-safe list to track all active drivers
active_drivers: list[WebDriver] = []
active_drivers_lock = threading.Lock()

def quit_all_sessions():
    """Terminate all active Instagram sessions."""
    with active_drivers_lock:
        for driver in active_drivers:
            try:
                driver.quit()
            except Exception as e:
                print(f"Error closing driver: {e}")
        active_drivers.clear()
        print("All Instagram sessions terminated.")