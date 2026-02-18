# src/gui/utils.py
import tkinter as tk
import customtkinter as ctk
import requests
from io import BytesIO
from PIL import Image
from datetime import datetime

class PrintLogger:
    def __init__(self, textbox, tk_app):
        self.textbox = textbox
        self.tk_app = tk_app

    def write(self, text):
        self.tk_app.after(0, self._insert_text, text)

    def _insert_text(self, text):
        if not self.textbox: return # Pojistka
        
        self.textbox.configure(state="normal")
        if text.strip():
            current_time = datetime.now().strftime("[%H:%M:%S]")
            self.textbox.insert(tk.END, f"{current_time} {text}")
        else:
            self.textbox.insert(tk.END, text)
            
        self.textbox.see(tk.END)
        self.textbox.configure(state="disabled")

    def flush(self):
        pass

class AsyncImageLoader:
    def __init__(self):
        self.image_cache = {}

    def load_image(self, url, label_widget, size=(80, 80)):
        if not url: return
        
        # Pokud je v cache, použijeme ho rovnou
        if url in self.image_cache:
            self._update_label(label_widget, self.image_cache[url])
            return

        # Jinak stáhneme (toto by se mělo volat v threadu z GUI)
        try:
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                img_data = BytesIO(response.content)
                pil_img = Image.open(img_data)
                
                # Center Crop
                width, height = pil_img.size
                if width != height:
                    new_size = min(width, height)
                    left = (width - new_size) / 2
                    top = (height - new_size) / 2
                    right = (width + new_size) / 2
                    bottom = (height + new_size) / 2
                    pil_img = pil_img.crop((left, top, right, bottom))
                
                pil_img = pil_img.resize(size, Image.Resampling.LANCZOS)
                ctk_image = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)
                
                self.image_cache[url] = ctk_image
                self._update_label(label_widget, ctk_image)
        except Exception:
            pass

    def _update_label(self, label, image):
        try:
            label.configure(image=image, text="", fg_color="transparent")
        except: pass