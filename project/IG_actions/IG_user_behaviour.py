from .IG_login import login_to_instagram
from .IG_quit import quit_instagram
from identity.get_userdata import get_IG_password_by_ID, get_IG_username_by_ID
from .IG_search import search_for_account
from .IG_scroll_reels import scroll_reels
import keyboard
import threading
from utils.delay import delay

def IG_user_behaviour(userid=0):
    ID_to_find = userid
    selected_username = get_IG_username_by_ID(ID_to_find)
    selected_password = get_IG_password_by_ID(ID_to_find)

    print("------------------------------------------")
    print("Acting as: " + selected_username)
    print("------------------------------------------")

    driver = login_to_instagram(username=selected_username, password=selected_password)
    delay(5)  # Wait for the page to load

    # Define the Instagram actions to perform in a thread
    def run_actions():
        try:
            scroll_reels(driver=driver)
            # Add other functions like search_for_account here if needed
        except Exception as e:
            print(f"Action interrupted: {e}")

    # Start the actions in a background thread
    action_thread = threading.Thread(target=run_actions)
    action_thread.start()

    # Register hotkey to quit Instagram immediately
    keyboard.add_hotkey('ctrl+q', lambda: quit_instagram(driver))

    # Wait for the action thread to complete (or be interrupted)
    action_thread.join()

    # Ensure the driver is properly closed after thread completion
    quit_instagram(driver)