from identity.get_userdata import get_IG_password_by_ID, get_IG_username_by_ID
from .X_login import login_to_instagram
from .X_scroll_reels import scroll_reels
from .X_multi_session import active_drivers, active_drivers_lock  # Import global tracker

def IG_user_behaviour(userid=0):
    try:
        # Fetch credentials
        username = get_IG_username_by_ID(userid)
        password = get_IG_password_by_ID(userid)

        # Login and add driver to global list
        driver = login_to_instagram(username, password)
        with active_drivers_lock:
            active_drivers.append(driver)

        # Perform actions (e.g., scroll reels)
        # scroll_reels(driver)

    except Exception as e:
        print(f"Error for user {userid}: {e}")

    finally:
        # Cleanup: Remove driver from list and quit
        with active_drivers_lock:
            if driver in active_drivers:
                active_drivers.remove(driver)
        try:
            driver.quit()
        except:
            pass