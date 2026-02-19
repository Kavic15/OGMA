import re

class XUtils:
    @staticmethod
    def parse_number(text):
        if not text: 
            return 0
        text = text.upper().replace(',', '').replace(' ', '').replace('.', '')
        match = re.search(r'([\d\.]+)([KMB]?)', text)
        if not match: 
            return 0
            
        num_str, suffix = match.groups()
        num = float(num_str)
        
        if suffix == 'K': num *= 1000
        elif suffix == 'M': num *= 1000000
        elif suffix == 'B': num *= 1000000000
        
        return int(num)

    @staticmethod
    def extract_media(article_locator, current_text):
        """Vrátí tuple (updated_text, media_url, is_video)"""
        media_url = None
        is_video = False
        
        try:
            # 1. Hledáme primárně explicitní video přehrávač nebo tag video
            video_loc = article_locator.locator('[data-testid="videoPlayer"], video').first
            photo_loc = article_locator.locator('[data-testid="tweetPhoto"]').first
            
            if video_loc.count() > 0:
                is_video = True
                
                # Zjištění, zda je nalezený element přímo video tag
                is_video_tag = video_loc.evaluate("el => el.tagName.toLowerCase() === 'video'")
                if is_video_tag:
                    media_url = video_loc.get_attribute('poster')
                else:
                    poster_video = video_loc.locator('video').first
                    if poster_video.count() > 0:
                        media_url = poster_video.get_attribute('poster')
                
                if not current_text.strip():
                    current_text = "[OBSAHUJE VIDEO]"
                    
            # 2. Pokud se tváří jako fotka, zkontrolujeme ji
            elif photo_loc.count() > 0:
                img_loc = photo_loc.locator('img').first
                if img_loc.count() > 0:
                    media_url = img_loc.get_attribute('src')
                    
                    # Záchranná detekce: X často lazy-loaduje videa jako statické obrázky
                    # Pokud URL obsahuje text indikující náhled videa, přehodnotíme to
                    if media_url and ('video_thumb' in media_url or 'ext_tw_video' in media_url):
                        is_video = True
                        if not current_text.strip():
                            current_text = "[OBSAHUJE VIDEO]"
                            
                # Pokud to video opravdu není, potvrdíme fotku
                if not is_video and not current_text.strip():
                    current_text = "[OBSAHUJE FOTKU]"
                    
        except Exception:
            pass
                
        return current_text, media_url, is_video