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
    def extract_media(article, current_text):
        """Vrátí tuple (updated_text, media_url, is_video)"""
        media_url = None
        is_video = False
        
        try:
            # Foto
            photo_ele = article.ele('@data-testid=tweetPhoto', timeout=0.05)
            # Video
            video_ele = article.ele('@data-testid=videoPlayer', timeout=0.05)
            
            if photo_ele:
                img_ele = photo_ele.ele('tag:img', timeout=0.05)
                if img_ele:
                    media_url = img_ele.attr('src')
                if not current_text.strip():
                    current_text = "[OBSAHUJE FOTKU]"
                    
            elif video_ele:
                is_video = True
                # Zkusíme získat alespoň poster (thumbnail)
                poster_video = video_ele.ele('tag:video', timeout=0.05)
                if poster_video:
                    media_url = poster_video.attr('poster')
                
                if not current_text.strip():
                    current_text = "[OBSAHUJE VIDEO]"
                    
        except:
            pass
                
        return current_text, media_url, is_video