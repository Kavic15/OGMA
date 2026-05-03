# src/gui/frames/metrics.py
"""
Metriky aplikace — síťový provoz POUZE bota (přes Playwright response listener),
rychlost scrapu a další statistiky.

Architektura:
  - BotTrafficCounter  — jednoduchý čítač, volá se z Playwright response handleru
  - MetricsFrame       — GUI, čte data z čítače každou sekundu přes after()
"""

import time
import threading
import customtkinter as ctk
from tkinter import Canvas
from src.gui.theme import COLORS


# ══════════════════════════════════════════════════════════════════════
# Čítač provozu — thread-safe, bez psutil
# ══════════════════════════════════════════════════════════════════════

class BotTrafficCounter:
    """
    Sbírá bajty z Playwright response/request eventů.
    Volat attach(page) po každém spuštění bota, detach() po zastavení.
    """

    HISTORY_SIZE = 60

    def __init__(self):
        self._lock        = threading.Lock()
        self._running     = False

        # Aktuální sekundu
        self._rx_bucket   = 0   # bajty přijaté v aktuální sekundě
        self._tx_bucket   = 0   # bajty odeslané v aktuální sekundě
        self._bucket_time = time.time()

        # Veřejné hodnoty (aktualizuje _tick())
        self.rx_speed     = 0.0
        self.tx_speed     = 0.0
        self.rx_total     = 0
        self.tx_total     = 0
        self.rx_history   = [0.0] * self.HISTORY_SIZE
        self.tx_history   = [0.0] * self.HISTORY_SIZE

        self._page        = None
        self._on_response = None
        self._on_request  = None
        self._tick_thread = None

    # ------------------------------------------------------------------
    def attach(self, page):
        """Napojí se na Playwright page. Volat ze stejného vlákna jako bot."""
        self.detach()
        self._page    = page
        self._running = True
        self.reset()

        def on_response(response):
            try:
                # content-length header — nejrychlejší, bez čtení body
                cl = response.headers.get("content-length")
                if cl:
                    with self._lock:
                        self._rx_bucket += int(cl)
            except Exception:
                pass

        def on_request(request):
            try:
                # Velikost POST dat — aproximace přes headers
                headers = request.headers
                cl = headers.get("content-length")
                if cl:
                    with self._lock:
                        self._tx_bucket += int(cl)
                else:
                    # Přidat alespoň hlavičky (~200–600 B typicky)
                    header_size = sum(len(k) + len(v) + 4
                                      for k, v in headers.items())
                    with self._lock:
                        self._tx_bucket += header_size
            except Exception:
                pass

        self._on_response = on_response
        self._on_request  = on_request
        page.on("response", on_response)
        page.on("request",  on_request)

        # Tick vlákno — každou sekundu přepočítá speed a posune historii
        self._tick_thread = threading.Thread(
            target=self._tick_loop, daemon=True, name="traffic-tick")
        self._tick_thread.start()

    def detach(self):
        """Odpojí listenery. Volat ze stejného vlákna jako bot."""
        self._running = False
        if self._page and self._on_response:
            try:
                self._page.remove_listener("response", self._on_response)
                self._page.remove_listener("request",  self._on_request)
            except Exception:
                pass
        self._page        = None
        self._on_response = None
        self._on_request  = None

    def reset(self):
        with self._lock:
            self.rx_total   = 0
            self.tx_total   = 0
            self.rx_speed   = 0.0
            self.tx_speed   = 0.0
            self._rx_bucket = 0
            self._tx_bucket = 0
            self.rx_history = [0.0] * self.HISTORY_SIZE
            self.tx_history = [0.0] * self.HISTORY_SIZE

    def _tick_loop(self):
        while self._running:
            time.sleep(1)
            with self._lock:
                rx = self._rx_bucket
                tx = self._tx_bucket
                self._rx_bucket = 0
                self._tx_bucket = 0

                self.rx_speed  = float(rx)
                self.tx_speed  = float(tx)
                self.rx_total += rx
                self.tx_total += tx

                self.rx_history.append(self.rx_speed)
                self.rx_history = self.rx_history[-self.HISTORY_SIZE:]
                self.tx_history.append(self.tx_speed)
                self.tx_history = self.tx_history[-self.HISTORY_SIZE:]


# ══════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════

def _fmt_bytes(b: float) -> str:
    if b < 1024:        return f"{b:.0f} B"
    elif b < 1024**2:   return f"{b/1024:.1f} KB"
    elif b < 1024**3:   return f"{b/1024**2:.1f} MB"
    else:               return f"{b/1024**3:.2f} GB"

def _fmt_speed(bps: float) -> str:
    return _fmt_bytes(bps) + "/s"


# ══════════════════════════════════════════════════════════════════════
# GUI Frame
# ══════════════════════════════════════════════════════════════════════

class MetricsFrame(ctk.CTkFrame):

    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.traffic    = BotTrafficCounter()
        self._start_time = time.time()
        self._poll_id   = None
        self._build_ui()
        self._poll()      # spustí periodické čtení dat

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 24))
        ctk.CTkLabel(header, text="Metriky", font=("Segoe UI", 24, "bold"),
                     text_color=COLORS["text_main"]).pack(side="left")
        ctk.CTkButton(
            header, text="Reset session", width=110, height=30,
            fg_color=COLORS["panel_bg"], hover_color=COLORS["border"],
            text_color=COLORS["text_dim"], font=("Segoe UI", 12),
            command=self._reset_session
        ).pack(side="right")

        # ── Síťový provoz ───────────────────────────────────────────
        self._section("SÍŤOVÝ PROVOZ  (pouze bot)")

        cards_row = ctk.CTkFrame(self, fg_color="transparent")
        cards_row.pack(fill="x", pady=(0, 20))
        cards_row.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self._rx_speed_var = ctk.StringVar(value="—")
        self._tx_speed_var = ctk.StringVar(value="—")
        self._rx_total_var = ctk.StringVar(value="—")
        self._tx_total_var = ctk.StringVar(value="—")

        self._stat_card(cards_row, "↓ DOWNLOAD",  self._rx_speed_var, "#175DDC", 0)
        self._stat_card(cards_row, "↑ UPLOAD",    self._tx_speed_var, "#2eb85c", 1)
        self._stat_card(cards_row, "∑ STAŽENO",   self._rx_total_var, "#5a9bd4", 2)
        self._stat_card(cards_row, "∑ ODESLÁNO",  self._tx_total_var, "#9b59b6", 3)

        # Sparkline
        graph_card = ctk.CTkFrame(self, fg_color=COLORS["panel_bg"],
                                  corner_radius=8, border_width=1,
                                  border_color=COLORS["border"])
        graph_card.pack(fill="x", pady=(0, 24))

        graph_header = ctk.CTkFrame(graph_card, fg_color="transparent")
        graph_header.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(graph_header, text="RYCHLOST — posledních 60s",
                     font=("Segoe UI", 10, "bold"),
                     text_color=COLORS["text_dim"]).pack(side="left")

        legend = ctk.CTkFrame(graph_header, fg_color="transparent")
        legend.pack(side="right")
        for lbl, color in [("↓ Download", "#175DDC"), ("↑ Upload", "#2eb85c")]:
            dot = Canvas(legend, width=8, height=8,
                         bg=COLORS["panel_bg"], highlightthickness=0)
            dot.pack(side="left", padx=(0, 3))
            dot.create_oval(0, 0, 8, 8, fill=color, outline="")
            ctk.CTkLabel(legend, text=lbl, font=("Segoe UI", 10),
                         text_color=COLORS["text_dim"]).pack(side="left", padx=(0, 12))

        self._sparkline = Canvas(graph_card, height=80,
                                 bg=COLORS["panel_bg"],
                                 highlightthickness=0, bd=0)
        self._sparkline.pack(fill="x", padx=14, pady=(0, 12))
        self._sparkline.bind("<Configure>", lambda e: self._draw_sparkline())

        # ── Výkon scrapu ────────────────────────────────────────────
        self._section("VÝKON SCRAPU")

        perf_row = ctk.CTkFrame(self, fg_color="transparent")
        perf_row.pack(fill="x", pady=(0, 20))
        perf_row.grid_columnconfigure((0, 1, 2), weight=1)

        self._profiles_var = ctk.StringVar(value="0")
        self._posts_var    = ctk.StringVar(value="0")
        self._uptime_var   = ctk.StringVar(value="00:00:00")

        self._stat_card(perf_row, "PROFILY / SESSION", self._profiles_var, "#e0a040", 0)
        self._stat_card(perf_row, "PŘÍSPĚVKY / SESSION", self._posts_var,  "#175DDC", 1)
        self._stat_card(perf_row, "UPTIME",              self._uptime_var, "#2eb85c", 2)

        # Stav bota
        status_row = ctk.CTkFrame(self, fg_color="transparent")
        status_row.pack(fill="x")
        self._bot_status_var = ctk.StringVar(value="● Bot neběží")
        ctk.CTkLabel(status_row, textvariable=self._bot_status_var,
                     font=("Segoe UI", 12), text_color=COLORS["text_dim"]).pack(side="left")

    # ------------------------------------------------------------------
    def _section(self, title):
        ctk.CTkLabel(self, text=title, font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w", pady=(0, 8))

    def _stat_card(self, parent, label, var, color, col):
        card = ctk.CTkFrame(parent, fg_color=COLORS["panel_bg"],
                            corner_radius=8, border_width=1,
                            border_color=COLORS["border"])
        card.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 6, 0))
        ctk.CTkLabel(card, text=label, font=("Segoe UI", 10, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w", padx=14, pady=(12, 2))
        ctk.CTkLabel(card, textvariable=var, font=("Segoe UI", 22, "bold"),
                     text_color=color).pack(anchor="w", padx=14, pady=(0, 12))

    # ------------------------------------------------------------------
    # Sparkline
    # ------------------------------------------------------------------
    def _draw_sparkline(self):
        c = self._sparkline
        w = c.winfo_width()
        h = c.winfo_height()
        if w <= 1 or h <= 1:
            return
        c.delete("all")

        with self.traffic._lock:
            rx = list(self.traffic.rx_history)
            tx = list(self.traffic.tx_history)

        def draw_line(history, color):
            peak = max(history) or 1
            n    = len(history)
            pts  = []
            for i, v in enumerate(history):
                x = int(i / (n - 1) * w) if n > 1 else w // 2
                y = int(h - (v / peak) * (h - 4))
                pts.extend([x, y])
            if len(pts) >= 4:
                c.create_line(pts, fill=color, width=2, smooth=True)

        draw_line(rx, "#175DDC")
        draw_line(tx, "#2eb85c")

    # ------------------------------------------------------------------
    # Polling — čte data každou sekundu, nezávisle na botu
    # ------------------------------------------------------------------
    def _poll(self):
        with self.traffic._lock:
            rx_s = self.traffic.rx_speed
            tx_s = self.traffic.tx_speed
            rx_t = self.traffic.rx_total
            tx_t = self.traffic.tx_total
            active = self.traffic._running

        if active:
            self._rx_speed_var.set(_fmt_speed(rx_s))
            self._tx_speed_var.set(_fmt_speed(tx_s))
        else:
            self._rx_speed_var.set("—")
            self._tx_speed_var.set("—")

        self._rx_total_var.set(_fmt_bytes(rx_t) if rx_t > 0 else "—")
        self._tx_total_var.set(_fmt_bytes(tx_t) if tx_t > 0 else "—")

        uptime = int(time.time() - self._start_time)
        h, rem = divmod(uptime, 3600)
        m, s   = divmod(rem, 60)
        self._uptime_var.set(f"{h:02d}:{m:02d}:{s:02d}")

        self._draw_sparkline()

        self._poll_id = self.after(1000, self._poll)

    # ------------------------------------------------------------------
    # Veřejné API — volat z app.py
    # ------------------------------------------------------------------
    def bot_started(self, page):
        """Zavolat po bot.login() — předá Playwright page pro traffic monitoring."""
        self.traffic.attach(page)
        self._bot_status_var.set("● Bot běží  —  měřím provoz")
        self._bot_status_var._label_widget = None  # reset barvy
        try:
            # Najít label a změnit barvu
            for w in self.winfo_children():
                pass  # barva přes configure níže
        except Exception:
            pass

    def bot_stopped(self):
        """Zavolat po dokončení / zastavení bota."""
        self.traffic.detach()
        self._bot_status_var.set("● Bot neběží")

    def increment_profiles(self, n: int = 1):
        val = int(self._profiles_var.get() or 0)
        self._profiles_var.set(str(val + n))

    def increment_posts(self, n: int = 1):
        val = int(self._posts_var.get() or 0)
        self._posts_var.set(str(val + n))

    def _reset_session(self):
        self.traffic.reset()
        self._start_time = time.time()
        self._profiles_var.set("0")
        self._posts_var.set("0")

    # ------------------------------------------------------------------
    def destroy(self):
        if self._poll_id:
            self.after_cancel(self._poll_id)
        self.traffic.detach()
        super().destroy()