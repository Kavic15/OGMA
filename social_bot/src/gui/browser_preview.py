# src/gui/browser_preview.py

import base64
from io import BytesIO
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk
from src.gui.theme import COLORS

class BrowserPreview(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["panel_bg"], **kwargs)
        self.pack_propagate(False)

        # Hlavička (Zůstává CTk pro zachování designu)
        self._header = ctk.CTkFrame(self, height=28, corner_radius=0, fg_color="transparent")
        self._header.pack(fill="x")
        self._header.pack_propagate(False)

        ctk.CTkLabel(self._header, text="NÁHLED PROHLÍŽEČE", font=("Segoe UI", 10, "bold"), text_color=COLORS["text_dim"]).pack(side="left", padx=8)
        self._status_dot = ctk.CTkLabel(self._header, text="● OFFLINE", font=("Segoe UI", 10), text_color=COLORS["text_dim"])
        self._status_dot.pack(side="right", padx=8)

        # Pro samotný obrázek použijeme "hloupý" tk.Label. 
        # Zabráníme tím double-scaling bugu při High-DPI ve Windows.
        self._image_label = tk.Label(
            self, 
            text="Stream není aktivní.\nSpusť scraping pro zobrazení prohlížeče.",
            bg=COLORS["sidebar_bg"], # Pozadí v barvě aplikace
            fg=COLORS["text_dim"],   # Barva textu
            font=("Segoe UI", 12)
        )
        self._image_label.pack(fill="both", expand=True)

    def _get_dpi_scale(self) -> float:
        """Vrátí DPI škálovací faktor okna (1.0 = 96 dpi, 1.25 = 120 dpi, atd.)."""
        try:
            # winfo_fpixels('1i') = kolik fyzických pixelů je 1 palec (96 = standard)
            return self._image_label.winfo_fpixels('1i') / 96.0
        except Exception:
            return 1.0

    def push_frame(self, image_b64_or_bytes):
        """Přijme snímek, vypočítá správný poměr stran a bezpečně jej zobrazí."""
        if not self.winfo_exists():
            return

        try:
            if isinstance(image_b64_or_bytes, str):
                image_bytes = base64.b64decode(image_b64_or_bytes)
            else:
                image_bytes = image_b64_or_bytes

            pil_img = Image.open(BytesIO(image_bytes))
        except Exception as e:
            print(f"[PREVIEW] Chyba dekódování: {e}")
            return

        # winfo_width/height vrací LOGICKÉ pixely — při DPI škálování > 100 %
        # (např. 125 %, 150 %) jsou menší než fyzické pixely obrazovky.
        # ImageTk.PhotoImage pracuje s fyzickými pixely, proto musíme převést.
        dpi_scale = self._get_dpi_scale()
        cw = int(self._image_label.winfo_width() * dpi_scale)
        ch = int(self._image_label.winfo_height() * dpi_scale)

        if cw < 10 or ch < 10:
            return

        iw, ih = pil_img.size
        
        # Matematika pro letterboxing (přizpůsobení s ohledem na poměr stran)
        scale = min(cw / iw, ch / ih)
        new_w = max(1, int(iw * scale))
        new_h = max(1, int(ih * scale))
        
        # Přeškálování v PIL (Bilinear je dostatečně rychlý a kvalitní pro stream)
        pil_img = pil_img.resize((new_w, new_h), Image.Resampling.BILINEAR)

        # Obalení do základního ImageTk (žádné nechtěné zvětšování na pozadí)
        img_tk = ImageTk.PhotoImage(pil_img)

        # Vykreslení
        self._image_label.configure(image=img_tk, text="")
        self._image_label.image = img_tk  # Držíme referenci, aby obrázek nezmizel
        self._status_dot.configure(text="● LIVE", text_color="#2eb85c")

    def set_offline(self):
        """Vrátí widget do OFFLINE stavu."""
        self._status_dot.configure(text="● OFFLINE", text_color=COLORS["text_dim"])
        
        # Smazání obrázku a vrácení textu
        self._image_label.configure(
            image="", 
            text="Stream není aktivní.\nSpusť scraping pro zobrazení prohlížeče."
        )
        self._image_label.image = None


class CDPScreencast:
    """Obaluje CDP komunikaci pro sběr screenshotů."""
    def __init__(self, page, on_frame, on_stop=None, quality=50, max_width=1280, max_height=720):
        self.page = page
        self.on_frame = on_frame
        self.on_stop = on_stop
        self.quality = quality
        self.max_width = max_width
        self.max_height = max_height
        
        self.client = None
        self._running = False

    def _handle_screencast_frame(self, event):
        if not self._running:
            return
        data = event.get("data")
        session_id = event.get("sessionId")
        if data:
            self.on_frame(data)
        if session_id:
            try:
                self.client.send("Page.screencastFrameAck", {"sessionId": session_id})
            except Exception:
                pass

    def start(self):
        try:
            self.client = self.page.context.new_cdp_session(self.page)
            self.client.on("Page.screencastFrame", self._handle_screencast_frame)
            self.client.send("Page.startScreencast", {
                "format": "jpeg",
                "quality": self.quality,
                "maxWidth": self.max_width,
                "maxHeight": self.max_height,
                "everyNthFrame": 1
            })
            self._running = True
            print("[PREVIEW] Screencast spuštěn.")
        except Exception as e:
            print(f"[PREVIEW] Nelze spustit screencast: {e}")

    def stop(self):
        self._running = False
        try:
            if self.client:
                self.client.send("Page.stopScreencast")
                self.client.detach()
        except Exception:
            pass
        if self.on_stop:
            self.on_stop()