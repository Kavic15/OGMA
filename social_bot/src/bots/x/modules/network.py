from src.utils.human_input import delay
import re

class XNetworkModule:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    def scrape_followers(self, username, limit=50):
        self._scrape_users_list(username, "followers", "follower", limit)

    def scrape_following(self, username, limit=50):
        self._scrape_users_list(username, "following", "following", limit)

    def _scrape_users_list(self, username, endpoint, conn_type, limit):
        if limit <= 0: return
        
        type_cs = "Sledujících" if conn_type == "follower" else "Sledovaných"
        print(f"\n[X-NETWORK] --- Těžba {type_cs} pro @{username} (Limit: {limit}) ---")
        
        try:
            self.bot.page.goto(f"https://x.com/{username}/{endpoint}", wait_until="domcontentloaded", timeout=15000)
            self.bot.page.locator('[data-testid="primaryColumn"]').first.wait_for(state="visible", timeout=10000)
            delay(2, 4)
        except Exception as e:
            print(f"[X-NETWORK] Nelze načíst seznam {type_cs}: {e}")
            return

        collected = 0
        processed = set()
        scroll_attempts = 0

        while collected < limit and scroll_attempts < 15:
            cells = self.bot.page.locator('[data-testid="UserCell"]').all()
            new_found = False

            for cell in cells:
                if collected >= limit: break
                try:
                    # Načteme veškerý text z buňky daného uživatele
                    text_content = cell.inner_text()
                    
                    # Robustní hledání handle pomocí regulárního výrazu (hledá slovo začínající na @)
                    match = re.search(r'@([a-zA-Z0-9_]+)', text_content)
                    
                    if match:
                        target_user = match.group(1).strip()
                        
                        # Zabráníme uložení sebe sama a duplikátů
                        if target_user and target_user.lower() != username.lower() and target_user not in processed:
                            processed.add(target_user)
                            new_found = True
                            
                            # Uložení do databáze do naší sítě (Connections)
                            self.db.upsert_connection("X", username, target_user, conn_type)
                            
                            collected += 1
                            print(f"  -> Uložen záznam ({conn_type}): @{target_user} ({collected}/{limit})")
                except Exception: 
                    continue

            if not new_found: 
                scroll_attempts += 1
            else: 
                scroll_attempts = 0

            if collected < limit:
                self.bot.page.evaluate("window.scrollBy(0, 1000)")
                delay(1.5, 3.0)

        print(f"[X-NETWORK] Těžba {type_cs} dokončena.")