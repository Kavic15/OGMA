from src.utils.human_input import delay
from src.core.database import DatabaseManager
import re
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

class InstagramScraper:
    def __init__(self, bot):
        self.bot = bot
        self.db = DatabaseManager()

    def parse_number(self, text):
        if not text: 
            return 0
        
        # Odstranění nedělitelných mezer (\xa0) a všech dalších whitespace znaků
        text = str(text).upper().replace('\xa0', '').replace('&NBSP;', '')
        text = re.sub(r'\s+', '', text)
        
        if 'TIS' in text:
            text = text.replace('TIS.', 'K').replace('TIS', 'K')
            
        text = text.replace('TOSEMILÍBÍ', '').replace('LIKES', '')
        text = text.replace(',', '.')
        
        match = re.search(r'([\d\.]+)([KMB]?)', text)
        if not match: 
            return 0
            
        num_str, suffix = match.groups()
        try:
            num = float(num_str)
        except:
            return 0
        
        if suffix == 'K': num *= 1000
        elif suffix == 'M': num *= 1000000
        elif suffix == 'B': num *= 1000000000
        
        return int(num)

    def scrape_post_and_comments(self, db_user_id, post_url, comments_limit=50):
        print(f"\n  -> [IG-SCRAPER] Otevírám příspěvek: {post_url}")
        self.bot.open_url(post_url)
        delay(3, 5)

        platform_post_id = post_url.rstrip('/').split('/')[-1]
        
        current_url = self.bot.page.url
        try:
            actual_username = current_url.split('instagram.com/')[-1].split('/')[0].split('?')[0]
        except:
            actual_username = ""

        post_container = self.bot.page.locator('main, article, [role="dialog"]').first
        
        # 1. Extrakce textu příspěvku
        post_text = ""
        h1_els = post_container.locator('h1[dir="auto"]').all()
        for h1 in h1_els:
            txt = h1.inner_text()
            if txt and txt != actual_username:
                post_text += txt + "\n"
                
        if not post_text.strip():
            span_els = post_container.locator('span[dir="auto"]').all()
            for sp in span_els[:5]:
                txt = sp.inner_text()
                if txt and txt != actual_username and len(txt) > 5 and not re.match(r'^\d+\s+[hdwmsčty]$', txt, re.IGNORECASE):
                    post_text = txt
                    break
        post_text = post_text.strip()

        # 2. Extrakce média (Podpora kolotočů s využitím JS evaluace pro ignorování mřížky)
        media_urls = []
        is_video = False
        
        for _ in range(15):
            # Videa
            for v in post_container.locator('video').all():
                try:
                    if v.evaluate("el => el.closest('a') !== null"):
                        continue
                        
                    src = v.get_attribute('src') or v.get_attribute('poster')
                    if src and not src.startswith('blob:'):
                        src = src.replace('&amp;', '&')
                        if src not in media_urls:
                            media_urls.append(src)
                            is_video = True
                except:
                    pass
            
            # Fotky
            for img in post_container.locator('div._aagv img, ul li img').all():
                try:
                    if img.evaluate("el => el.closest('a') !== null"):
                        continue
                        
                    alt = (img.get_attribute('alt') or "").lower()
                    src = img.get_attribute('src') or ""
                    
                    if "profile" not in alt and "profilov" not in alt and "data:image" not in src:
                        src = src.replace('&amp;', '&')
                        if src and src not in media_urls:
                            media_urls.append(src)
                except:
                    pass
            
            # Pokus o posun kolotoče na další fotku
            try:
                next_btn = post_container.locator('button[aria-label="Další"], button[aria-label="Next"]').first
                if next_btn.is_visible(timeout=500):
                    next_btn.click(force=True)
                    self.bot.page.wait_for_timeout(800)
                else:
                    break
            except:
                break

        if not post_text:
            if is_video:
                post_text = "[OBSAHUJE VIDEO]"
            elif media_urls:
                post_text = "[OBSAHUJE FOTKU]"

        final_media_url = ";".join(media_urls) if media_urls else None

        # 3. Extrakce statistik
        stats_js = """
        (container) => {
            let likes = "0";
            let comments = "0";
            if(!container) container = document;
            
            let svgs = container.querySelectorAll('svg');
            for(let svg of svgs) {
                let label = svg.getAttribute('aria-label');
                if (label === 'To se mi líbí' || label === 'Like') {
                    let btn = svg.closest('div[role="button"], a');
                    if (btn && btn.innerText.match(/\\d/)) {
                        likes = btn.innerText;
                    }
                } else if (label === 'Komentář' || label === 'Comment') {
                    let btn = svg.closest('div[role="button"], a');
                    if (btn && btn.innerText.match(/\\d/)) {
                        comments = btn.innerText;
                    }
                }
            }
            return {likes, comments};
        }
        """
        try:
            post_element_handle = post_container.element_handle()
            stats_data = self.bot.page.evaluate(stats_js, post_element_handle)
            likes_count = self.parse_number(stats_data.get('likes', '0'))
            comments_count = self.parse_number(stats_data.get('comments', '0'))
        except:
            likes_count, comments_count = 0, 0

        time_loc = post_container.locator('time').first
        timestamp = time_loc.get_attribute('datetime') if time_loc.count() > 0 else ""

        db_post_id = self.db.upsert_post(
            user_id=db_user_id,
            platform="IG",
            platform_post_id=platform_post_id,
            text_content=post_text,
            timestamp_posted=timestamp,
            likes_count=likes_count,
            shares_count=0, 
            comments_count=comments_count, 
            url=post_url,
            media_url=final_media_url
        )
        print(f"  -> [IG-SCRAPER] Uložen příspěvek ID: {platform_post_id} | Lajky: {likes_count} | Komentáře: {comments_count} | Média: {len(media_urls)}")

        # --- Těžba komentářů ---
        print(f"  -> [IG-SCRAPER] Těžím komentáře k tomuto příspěvku (Limit: {comments_limit})...")
        comments_collected = 0
        processed_comment_ids = set()
        
        max_comments = comments_limit

        # OPRAVENÝ SKRIPT PRO KOMENTÁŘE
        js_extract_comments = """
        () => {
            var results = [];
            var times = document.querySelectorAll('time');
            for (var i = 0; i < times.length; i++) {
                var timeEl = times[i];
                var timestamp = timeEl.getAttribute('datetime');
                if (!timestamp) continue;
                
                var block = timeEl;
                for(var j=0; j<8; j++) {
                    if(block.parentElement) block = block.parentElement;
                }
                
                var author = "";
                var links = block.querySelectorAll('a');
                for (var k = 0; k < links.length; k++) {
                    var href = links[k].getAttribute('href');
                    var txt = links[k].innerText.trim();
                    if (href && href.startsWith('/') && txt) {
                        author = txt;
                        break;
                    }
                }
                
                var textContent = "";
                var dirEls = block.querySelectorAll('span[dir="auto"], div[dir="auto"], span');
                for (var k = 0; k < dirEls.length; k++) {
                    var txt = dirEls[k].innerText.trim();
                    var ignoreWords = ['Odpovědět', 'Reply', 'Zobrazit překlad', 'See translation', 'Skrýt odpovědi', 'Hide replies'];
                    
                    var isTimeStr = /^\\d+\\s*[hdwmsčty]$/i.test(txt) || /^před\\s+\\d+/i.test(txt);
                    // Nový filtr pro skrytí textů "Zobrazit odpovědi"
                    var isReplyStr = /zobrazit\\s+všech/i.test(txt) || /view\\s+all/i.test(txt) || /odpovědí/i.test(txt) || /replies/i.test(txt);
                    
                    if (txt && txt !== author && !ignoreWords.includes(txt) && !txt.includes('To se mi líbí') && !txt.includes(' like') && !isTimeStr && !isReplyStr) {
                        // Zabráníme čtení textu z obrovských rodičovských divů
                        if (author && txt.includes(author) && txt.length > author.length + 5) continue;
                        
                        if (!textContent.includes(txt) && txt.length > 1) {
                            textContent += txt + " ";
                        }
                    }
                }
                
                var likesStr = "0";
                var allTextEls = block.querySelectorAll('span, div');
                for (var k = 0; k < allTextEls.length; k++) {
                    var txt = allTextEls[k].innerText.trim();
                    if ((txt.includes('To se mi líbí') || txt.includes(' like') || txt.includes('Likes') || txt.includes('likes')) && /\\d/.test(txt)) {
                        // KLÍČOVÁ OCHRANA: List lajků má pár znaků, rodičovský div s celým komentářem jich má spoustu.
                        // Omezíme to na 40 znaků, takže se uloží jen konkrétní element "33 To se mi líbí".
                        if (txt.length < 40) {
                            likesStr = txt;
                            break;
                        }
                    }
                }
                
                results.push({
                    timestamp: timestamp,
                    author: author,
                    text: textContent.trim(),
                    likesStr: likesStr
                });
            }
            return results;
        }
        """

        js_scroll_comments = """
        () => {
            var times = document.querySelectorAll('time');
            if (times.length > 1) {
                var el = times[times.length - 1]; 
                for (var i = 0; i < 15; i++) {
                    if (!el.parentElement || el.tagName === 'BODY' || el.tagName === 'HTML') break;
                    el = el.parentElement;
                    var style = window.getComputedStyle(el);
                    if (style.overflowY === 'auto' || style.overflowY === 'scroll' || style.overflowY === 'hidden') {
                        if (el.scrollHeight > el.clientHeight + 10) {
                            el.scrollTop = el.scrollHeight;
                            return true;
                        }
                    }
                }
            }
            var divs = document.querySelectorAll('div, ul');
            for (var i=0; i<divs.length; i++) {
                var style = window.getComputedStyle(divs[i]);
                if ((style.overflowY === 'auto' || style.overflowY === 'scroll') && divs[i].scrollHeight > divs[i].clientHeight) {
                    divs[i].scrollTop = divs[i].scrollHeight;
                }
            }
            return false;
        }
        """

        for scroll_attempt in range(12):
            try:
                load_more = self.bot.page.locator('svg[aria-label="Načíst další komentáře"], svg[aria-label="Load more comments"]').first
                if load_more.is_visible(timeout=500):
                    load_more.locator('xpath=./ancestor::button | ./ancestor::div[@role="button"]').first.click(force=True)
                    delay(1.5, 2.5)
            except: pass

            extracted_data = self.bot.page.evaluate(js_extract_comments)
            
            if extracted_data:
                for data in extracted_data:
                    if comments_collected >= max_comments: break
                    
                    c_timestamp = data.get('timestamp')
                    author_username = data.get('author')
                    c_text = data.get('text')
                    likes_str = data.get('likesStr', "0")
                    
                    if not c_timestamp or c_timestamp == timestamp: continue
                    if not author_username: continue
                        
                    platform_comment_id = f"{platform_post_id}_{author_username}_{c_timestamp}"
                    
                    if platform_comment_id in processed_comment_ids: continue
                    processed_comment_ids.add(platform_comment_id)
                    
                    if not c_text: c_text = "[OBSAHUJE MÉDIA/GIF]"
                    c_likes = self.parse_number(likes_str)
                    
                    self.db.upsert_comment(
                        post_id=db_post_id,
                        platform="IG",
                        platform_comment_id=platform_comment_id,
                        author_username=author_username,
                        author_display_name="",
                        text_content=c_text,
                        timestamp_posted=c_timestamp,
                        likes_count=c_likes,
                        shares_count=0,
                        replies_count=0,
                        media_url=None
                    )
                    comments_collected += 1

            if comments_collected >= max_comments: break
            try:
                self.bot.page.evaluate(js_scroll_comments)
            except: pass
            delay(1.5, 2.5)

    def scrape_profile(self, target_query, limit=10, comments_limit=50, followers_limit=50, following_limit=50):
        limit_text = "NEOMEZENO" if limit == -1 else str(limit)
        print(f"[IG-SCRAPER] Zahajuji simulaci lidského vyhledávání: '{target_query}' (Limit: {limit_text} P / {comments_limit} K / {followers_limit} S / {following_limit} S)")

        if "instagram.com" not in self.bot.page.url:
            self.bot.open_url(self.bot.base_url)
            delay(2, 4)

        search_icon = self.bot.page.locator('svg[aria-label="Hledat"]').first
        if search_icon.count() == 0:
            search_icon = self.bot.page.locator('svg[aria-label="Search"]').first

        if search_icon.count() > 0:
            print("[IG-SCRAPER] Klikám na záložku Hledání (Lupa)...")
            try:
                search_icon.locator('xpath=./ancestor::a').first.click(force=True)
            except:
                search_icon.click(force=True)
            delay(2, 4)

            search_box = self.bot.page.locator('input').first
            
            if search_box.count() > 0:
                print("[IG-SCRAPER] Vyhledávací pole nalezeno, simuluji psaní...")
                search_box.click()
                delay(0.5, 1.5)
                
                search_box.fill("")
                search_box.press_sequentially(target_query, delay=150)
                print("[IG-SCRAPER] Dopsáno, čekám na dynamické výsledky...")
                delay(4, 6)
                
                found_profile = False
                ignore_list = ['explore', 'reels', 'direct', 'stories', 'tags', 'locations', 'p', 'your_activity', 'saved', 'settings', 'accounts', 'language']
                
                current_links = self.bot.page.locator('a').all()
                for link in current_links:
                    if link.is_visible():
                        href = link.get_attribute('href')
                        if href and (href.startswith('https://www.instagram.com/') or href.startswith('/')):
                            path = href.replace('https://www.instagram.com', '').split('?')[0].strip('/')
                            
                            if path and '/' not in path:
                                if path not in ignore_list and path != self.bot.username:
                                    if link.inner_text().strip():
                                        print(f"[IG-SCRAPER] Nalezen profil (/{path}/), přecházím na něj.")
                                        link.click(force=True)
                                        found_profile = True
                                        delay(4, 6)
                                        break 
                
                if not found_profile:
                    print("[WARNING] Profil nenalezen v našeptávači, zkouším Direct URL.")
                    clean_target = target_query.replace('@', '').replace(' ', '')
                    self.bot.open_url(f"{self.bot.base_url}{clean_target}/")
                    delay(4, 6)
            else:
                self.bot.open_url(f"{self.bot.base_url}{target_query.replace('@', '').replace(' ', '')}/")
        else:
            self.bot.open_url(f"{self.bot.base_url}{target_query.replace('@', '').replace(' ', '')}/")
            delay(4, 6)

        current_url = self.bot.page.url
        try:
            actual_username = current_url.split('instagram.com/')[-1].split('/')[0].split('?')[0]
        except:
            actual_username = target_query.replace('@', '').replace(' ', '')

        print("[IG-SCRAPER] Stahuji data o uživateli...")
        
        # Komplexní extrakce profilu přes Javascript s lepším filtrováním
        profile_js = """
        () => {
            let header = document.querySelector('header');
            if (!header) return {};
            
            let data = {
                followers: "0",
                following: "0",
                bio: "",
                display_name: "",
                website: "",
                profile_pic_url: "",
                is_verified: 0,
                texts: []
            };
            
            // Followers
            let flw_link = header.querySelector('a[href*="/followers/"]');
            if (flw_link) {
                let span = flw_link.querySelector('span[title]');
                if (span) data.followers = span.getAttribute('title');
                else data.followers = flw_link.innerText;
            }
            
            // Following
            let flg_link = header.querySelector('a[href*="/following/"]');
            if (flg_link) {
                let span = flg_link.querySelector('span:not([dir])');
                if (span) data.following = span.innerText;
                else data.following = flg_link.innerText;
            }
            
            // Verifikace
            if (header.querySelector('svg[aria-label="Ověřeno"], svg[aria-label="Verified"]')) {
                data.is_verified = 1;
            }
            
            // Web
            let web_link = header.querySelector('a[target="_blank"]');
            if (web_link) {
                data.website = web_link.innerText.trim();
            }
            
            // Profilovka
            let img = header.querySelector('img');
            if (img) data.profile_pic_url = img.getAttribute('src');
            
            // Extrakce všech textových elementů pro jméno a bio
            let dirEls = Array.from(header.querySelectorAll('span[dir="auto"], h1[dir="auto"], h2[dir="auto"], div[dir="auto"]'));
            
            for(let el of dirEls) {
                let t = el.innerText.trim();
                if(!t) continue;
                
                let tLow = t.toLowerCase();
                
                // Opravené a přísnější filtrování tlačítek a statistik (zachytí i "Sleduji (47)")
                let isStat = tLow.includes('příspěvky') || tLow.includes('sledující') || tLow.includes('sleduji') ||
                             tLow.includes('posts') || tLow.includes('followers') || tLow.includes('following');
                
                let isBtn = ['sledovat', 'zpráva', 'follow', 'message', 'přidat do příběhu', 'add to story'].includes(tLow);
                
                if (isStat || isBtn) continue;
                
                if (!data.texts.includes(t)) {
                    data.texts.push(t);
                }
            }
            
            return data;
        }
        """
        
        try:
            profile_data = self.bot.page.evaluate(profile_js)
            
            followers_count = self.parse_number(profile_data.get('followers', '0'))
            following_count = self.parse_number(profile_data.get('following', '0'))
            
            display_name = actual_username
            bio = ""
            website = profile_data.get('website', None)
            
            # Očištění posbíraných textů a jejich přiřazení
            texts = profile_data.get('texts', [])
            clean_texts = []
            for t in texts:
                if t.lower() == actual_username.lower(): continue # Vynecháme username
                if website and t == website: continue             # Vynecháme web
                if re.match(r'^[\d\s,]+(?:mil\.|tis\.|m|k)?$', t.lower().replace('\xa0', ' ')): continue # Zbloudilá čísla
                clean_texts.append(t)
                
            # Pokud zbyly texty: první je obvykle jméno (display name), druhý a další je bio
            if len(clean_texts) > 0:
                display_name = clean_texts[0]
                if len(clean_texts) > 1:
                    bio = "\n".join(clean_texts[1:])
            
            is_verified = profile_data.get('is_verified', 0)
            profile_pic_url = profile_data.get('profile_pic_url', None)

        except Exception as e:
            print(f"[ERROR] Selhala extrakce metadat profilu: {e}")
            followers_count, following_count, is_verified = 0, 0, 0
            display_name = actual_username
            bio, website, profile_pic_url = "", None, None

        # Uložení rozšířených dat do DB
        user_id = self.db.upsert_user(
            platform="IG",
            username=actual_username,
            display_name=display_name,
            bio=bio,
            followers_count=followers_count,
            following_count=following_count,
            website=website,
            is_verified=is_verified,
            profile_pic_url=profile_pic_url
        )
        print(f"[IG-SCRAPER] Profil uložen do DB (Sledujících: {followers_count}). Interní ID: {user_id}")

        print("[IG-SCRAPER] Skenuji zeď a sbírám URL příspěvků...")
        
        urls_to_scrape = []
        scroll_attempts_without_new = 0
        max_scroll_loops = 500 if limit == -1 else 100 
        
        loop_counter = 0
        while True:
            all_links = self.bot.page.locator('a').all()
            new_found = False
            
            for link in all_links:
                href = link.get_attribute('href')
                if href and ('/p/' in href or '/reel/' in href):
                    clean_href = href.split('?')[0]
                    full_url = f"https://www.instagram.com{clean_href}" if clean_href.startswith('/') else clean_href
                    
                    if full_url not in urls_to_scrape:
                        urls_to_scrape.append(full_url)
                        new_found = True
                        
                        if limit != -1 and len(urls_to_scrape) >= limit:
                            break
            
            print(f"  -> Nalezeno {len(urls_to_scrape)} unikátních příspěvků...")

            if limit != -1 and len(urls_to_scrape) >= limit:
                print(f"[IG-SCRAPER] Dosažen požadovaný limit {limit}.")
                break
            
            if not new_found:
                scroll_attempts_without_new += 1
                if scroll_attempts_without_new >= 4:
                    print("[IG-SCRAPER] Zdá se, že jsme na konci profilu (žádné nové příspěvky).")
                    break
            else:
                scroll_attempts_without_new = 0

            loop_counter += 1
            if limit == -1 and loop_counter > max_scroll_loops:
                print("[WARNING] Dosažen interní bezpečnostní limit scrollu.")
                break

            self.bot.page.evaluate("window.scrollBy(0, 800)")
            delay(1.5, 3.0)

        final_urls = urls_to_scrape[:limit] if limit != -1 else urls_to_scrape
        
        if not final_urls:
            print("[IG-SCRAPER] Nebyly nalezeny žádné příspěvky (profil je soukromý nebo prázdný).")
            return
            
        if followers_limit > 0:
            self._scrape_network(actual_username, followers_limit, "followers")
        if following_limit > 0:
            self._scrape_network(actual_username, following_limit, "following")

        print(f"\n[IG-SCRAPER] Zahajuji hloubkovou těžbu {len(final_urls)} příspěvků...")
        for i, url in enumerate(final_urls):
            print(f"--- Zpracovávám {i+1} z {len(final_urls)} ---")
            try:
                self.scrape_post_and_comments(user_id, url, comments_limit)
            except Exception as e:
                print(f"[IG-SCRAPER] Chyba při těžbě příspěvku {url}: {e}")

        print("\n[IG-SCRAPER] Kompletní těžba cílového IG profilu a komentářů byla úspěšně dokončena.")

    def _scrape_network(self, username, limit, mode):
        if limit <= 0: return
        
        conn_type = "follower" if mode == "followers" else "following"
        type_cs = "Sledujících" if mode == "followers" else "Sledovaných"
        print(f"\n[IG-NETWORK] --- Těžba {type_cs} pro @{username} (Limit: {limit}) ---")
        
        try:
            if f"/{username}/" not in self.bot.page.url:
                self.bot.open_url(f"{self.bot.base_url}{username}/")
                delay(2, 4)

            link = self.bot.page.locator(f'header a[href*="/{mode}/"]').first
            if link.is_visible(timeout=5000):
                link.click()
            else:
                print(f"[IG-NETWORK] Tlačítko {type_cs} nebylo nalezeno.")
                return

            dialog = self.bot.page.locator('div[role="dialog"]').first
            dialog.wait_for(state="visible", timeout=8000)
            delay(2, 4)

        except Exception as e:
            print(f"[IG-NETWORK] Nelze otevřít seznam {type_cs}: {e}")
            return

        collected = 0
        processed = set()
        scroll_attempts = 0

        # JS injekce zaměřená čistě na izolované posouvání uvnitř Modalu
        js_extract = """
        () => {
            let dialog = document.querySelector('div[role="dialog"]');
            if (!dialog) return {users: [], scrolled: false};

            let users = [];
            let links = dialog.querySelectorAll('a[href]');
            for (let a of links) {
                let href = a.getAttribute('href');
                if (href && href.startsWith('/') && href.split('/').length === 3) {
                    let un = href.replace(/\\//g, '');
                    if (un && !['explore', 'reels', 'direct', 'stories'].includes(un)) {
                        users.push(un);
                    }
                }
            }

            let scrolled = false;
            let divs = dialog.querySelectorAll('div');
            for (let d of divs) {
                let style = window.getComputedStyle(d);
                if (style.overflowY === 'auto' || style.overflowY === 'scroll') {
                    if (d.scrollHeight > d.clientHeight + 10) {
                        d.scrollTop += 600; 
                        scrolled = true;
                        break;
                    }
                }
            }
            return {users: [...new Set(users)], scrolled: scrolled};
        }
        """

        while collected < limit and scroll_attempts < 10:
            try:
                data = self.bot.page.evaluate(js_extract)
                new_found = False

                for target_user in data.get('users', []):
                    if target_user == username: continue
                    if collected >= limit: break

                    if target_user not in processed:
                        processed.add(target_user)
                        new_found = True
                        self.db.upsert_connection("IG", username, target_user, conn_type)
                        collected += 1
                        print(f"  -> Uložen záznam ({conn_type}): @{target_user} ({collected}/{limit})")

                if not new_found: scroll_attempts += 1
                else: scroll_attempts = 0

                delay(1.5, 3.0)
            except Exception as e:
                print(f"[IG-NETWORK] Chyba při těžbě modal okna: {e}")
                break

        print(f"[IG-NETWORK] Těžba {type_cs} dokončena.")
        
        try:
            close_btn = self.bot.page.locator('div[role="dialog"] button, css:svg[aria-label="Zavřít"], css:svg[aria-label="Close"]').first
            if close_btn.is_visible(timeout=1000): close_btn.click(force=True)
            delay(1)
        except: pass