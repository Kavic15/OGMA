from src.utils.human_input import delay
from .utils import XUtils

class XProfileModule:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    def scrape_metadata(self, actual_username):
        print(f"[X-PROFILE] Těžím metadata pro @{actual_username}...")
        
        try:
            display_name_loc = self.bot.page.locator('[data-testid="UserName"]').first
            if display_name_loc.count() > 0:
                display_name = display_name_loc.inner_text().split('\n')[0]
                is_verified = 1 if display_name_loc.locator('svg[aria-label="Verified account"]').count() > 0 else 0
            else:
                display_name = actual_username
                is_verified = 0

            bio_loc = self.bot.page.locator('[data-testid="UserDescription"]').first
            bio = bio_loc.inner_text() if bio_loc.count() > 0 else ""
            
            loc_ele = self.bot.page.locator('[data-testid="UserLocation"]').first
            location = loc_ele.inner_text() if loc_ele.count() > 0 else None

            web_ele = self.bot.page.locator('[data-testid="UserUrl"]').first
            website = web_ele.inner_text() if web_ele.count() > 0 else None

            join_ele = self.bot.page.locator('[data-testid="UserJoinDate"]').first
            joined_date = join_ele.inner_text() if join_ele.count() > 0 else None

            followers_ele = self.bot.page.locator('xpath=//a[contains(@href, "/followers")]/span[1] | //a[contains(@href, "/verified_followers")]/span[1]').first
            followers_count = XUtils.parse_number(followers_ele.inner_text() if followers_ele.count() > 0 else "0")

            following_ele = self.bot.page.locator('xpath=//a[contains(@href, "/following")]/span[1]').first
            following_count = XUtils.parse_number(following_ele.inner_text() if following_ele.count() > 0 else "0")

            banner_url = None
            try:
                banner_link = self.bot.page.locator('xpath=//a[contains(@href, "/header_photo")]//img').first
                if banner_link.count() > 0:
                    banner_url = banner_link.get_attribute('src')
            except: pass

            profile_pic_url = self._get_hd_profile_pic()

        except Exception as e:
            print(f"[ERROR] Chyba čtení metadat: {e}")
            display_name = actual_username; bio = ""; followers_count = 0; following_count = 0
            location = None; website = None; joined_date = None; is_verified = 0; banner_url = None; profile_pic_url = None

        user_id = self.db.upsert_user(
            platform="X", 
            username=actual_username, 
            display_name=display_name, 
            bio=bio, 
            followers_count=followers_count, 
            following_count=following_count,
            joined_date=joined_date,
            location=location,
            website=website,
            is_verified=is_verified,
            profile_pic_url=profile_pic_url,
            banner_url=banner_url
        )
        print(f"[X-PROFILE] Uloženo. Verifikace: {is_verified} | Lokace: {location}")
        return user_id

    def _get_hd_profile_pic(self):
        profile_pic_url = None
        try:
            avatar_img = self.bot.page.locator('img[alt="Opens profile photo"]').first
            if avatar_img.count() == 0: 
                avatar_img = self.bot.page.locator('img[alt="Square profile picture and Opens profile photo"]').first
            if avatar_img.count() == 0: 
                avatar_img = self.bot.page.locator('xpath=//div[contains(@data-testid, "UserAvatar-Container")]//img').first
            
            if avatar_img.count() > 0:
                profile_pic_url = avatar_img.get_attribute('src')
                if profile_pic_url and any(x in profile_pic_url for x in ['_bigger', '_mini', '_normal']):
                    photo_link = self.bot.page.locator('xpath=//div[contains(@data-testid, "UserAvatar-Container")]//a[contains(@href, "/photo")]').first
                    if photo_link.count() > 0:
                        photo_link.click()
                        large_img = self.bot.page.locator('xpath=//div[@data-testid="swipe-to-dismiss"]//img').first
                        large_img.wait_for(state="visible", timeout=3000)
                        if large_img.count() > 0:
                            profile_pic_url = large_img.get_attribute('src')
                        
                        close_btn = self.bot.page.locator('div[aria-label="Close"], div[aria-label="Zavřít"]').first
                        if close_btn.count() > 0: 
                            close_btn.click()
                        else: 
                            self.bot.page.go_back()
                        delay(0.5)
        except: pass
        return profile_pic_url