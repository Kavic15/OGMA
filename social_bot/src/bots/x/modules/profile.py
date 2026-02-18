from src.utils.human_input import delay
from .utils import XUtils

class XProfileModule:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    def scrape_metadata(self, actual_username):
        """Vytěží bio, followers, location, web, datum registrace atd."""
        print(f"[X-PROFILE] Těžím metadata pro @{actual_username}...")
        
        try:
            # Display Name + Verifikace
            display_name_ele = self.bot.page.ele('@data-testid=UserName', timeout=3)
            if display_name_ele:
                display_name = display_name_ele.text.split('\n')[0]
                is_verified = 1 if display_name_ele.ele('tag:svg@aria-label=Verified account', timeout=0.1) else 0
            else:
                display_name = actual_username
                is_verified = 0

            # Bio
            bio_ele = self.bot.page.ele('@data-testid=UserDescription', timeout=2)
            bio = bio_ele.text if bio_ele else ""
            
            # Location
            loc_ele = self.bot.page.ele('@data-testid=UserLocation', timeout=1)
            location = loc_ele.text if loc_ele else None

            # Website
            web_ele = self.bot.page.ele('@data-testid=UserUrl', timeout=1)
            website = web_ele.text if web_ele else None

            # Joined Date
            join_ele = self.bot.page.ele('@data-testid=UserJoinDate', timeout=1)
            joined_date = join_ele.text if join_ele else None

            # Followers
            followers_ele = self.bot.page.ele('xpath://a[contains(@href, "/followers")]/span[1]|//a[contains(@href, "/verified_followers")]/span[1]', timeout=2)
            followers_count = XUtils.parse_number(followers_ele.text if followers_ele else "0")

            # Following
            following_ele = self.bot.page.ele('xpath://a[contains(@href, "/following")]/span[1]', timeout=2)
            following_count = XUtils.parse_number(following_ele.text if following_ele else "0")

            # Banner
            banner_url = None
            try:
                banner_link = self.bot.page.ele('xpath://a[contains(@href, "/header_photo")]//img', timeout=1)
                if banner_link: banner_url = banner_link.attr('src')
            except: pass

            # Profile Pic (s HD logikou)
            profile_pic_url = self._get_hd_profile_pic()

        except Exception as e:
            print(f"[ERROR] Chyba čtení metadat: {e}")
            # Fallback hodnoty
            display_name = actual_username; bio = ""; followers_count = 0; following_count = 0
            location = None; website = None; joined_date = None; is_verified = 0; banner_url = None; profile_pic_url = None

        # Uložení do DB
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
            avatar_img = self.bot.page.ele('css:img[alt="Opens profile photo"]', timeout=1)
            if not avatar_img: avatar_img = self.bot.page.ele('css:img[alt="Square profile picture and Opens profile photo"]', timeout=1)
            if not avatar_img: avatar_img = self.bot.page.ele('xpath://div[contains(@data-testid, "UserAvatar-Container")]//img', timeout=1)
            
            if avatar_img:
                profile_pic_url = avatar_img.attr('src')
                # Pokus o HD verzi
                if profile_pic_url and any(x in profile_pic_url for x in ['_bigger', '_mini', '_normal']):
                    photo_link = self.bot.page.ele('xpath://div[contains(@data-testid, "UserAvatar-Container")]//a[contains(@href, "/photo")]', timeout=2)
                    if photo_link:
                        photo_link.click()
                        large_img = self.bot.page.ele('xpath://div[@data-testid="swipe-to-dismiss"]//img', timeout=3)
                        if large_img: profile_pic_url = large_img.attr('src')
                        
                        close_btn = self.bot.page.ele('css:div[aria-label="Close"]', timeout=1) or self.bot.page.ele('css:div[aria-label="Zavřít"]', timeout=1)
                        if close_btn: close_btn.click()
                        else: self.bot.page.back()
                        delay(0.5)
        except: pass
        return profile_pic_url