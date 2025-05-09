from selenium import webdriver

def quit_x(driver: webdriver.Chrome, verbose: bool = True) -> None:
    """Gracefully close the X browser session"""
    if driver is not None:
        try:
            driver.quit()
            if verbose:
                print("✅ Browser closed successfully")
        except Exception as e:
            if verbose:
                print(f"⚠️ Error closing browser: {str(e)}")
    else:
        if verbose:
            print("⚠️ No active browser session to close")