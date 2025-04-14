from IG_login import login_to_instagram
from IG_quit import quit_instagram
from identity.get_userdata import get_IG_password_by_ID, get_IG_username_by_ID
from IG_search import search_for_account


ID_to_find = 0
selected_username = get_IG_username_by_ID(ID_to_find)
selected_password = get_IG_password_by_ID(ID_to_find)

print(selected_username)
print(selected_password)

driver = login_to_instagram(username=selected_username, password=selected_password)
search_for_account(driver=driver, search_query="primaftv")
quit_instagram(driver)