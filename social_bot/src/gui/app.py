# src/gui/app.py
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import threading
import json
import os
import time
import sys
from pathlib import Path

from src.core.watchlist_scheduler import WatchlistScheduler
from src.gui.frames.watchlist import WatchlistFrame
from src.bots.instagram.scraper import InstagramScraper

from src.gui.theme import COLORS
from src.gui.utils import PrintLogger
from src.gui.frames.dashboard import DashboardFrame
from src.gui.frames.profiles import ProfilesFrame
from src.gui.frames.database import DatabaseFrame
from src.gui.frames.analysis import AnalysisFrame
from src.gui.frames.metrics import MetricsFrame, _fmt_speed
from src.gui.frames.sessions import SessionsFrame

from src.core.session_logger import SessionLogger
from src.gui.browser_preview import CDPScreencast

from src.bots.instagram.bot import InstagramBot
from src.bots.x.bot import XBot
from src.bots.youtube.bot import YouTubeBot  # Import YouTube bota

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        def _make_watchlist_bot(self):
            """Vrátí InstagramBot pro watchlist scheduler — použije první IG identitu."""
            for key, user in self.users_map.items():
                ig = user.get("social_media", {}).get("instagram")
                if ig:
                    uid = key.split()[0]  # "0 - Jan" → "0"
                    return InstagramBot(ig["username"], ig["password"], uid)
            raise RuntimeError("Žádná Instagram identita nenalezena v users.json")

        self.scheduler = WatchlistScheduler(
            scraper_factory=lambda: self._make_watchlist_bot()
        )

        self.title("Ogma 0.0")
        self.geometry("1200x800")
        self.minsize(1000, 700)

        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        self.data_path = project_root / "data" / "users.json"
        self.db_path   = project_root / "data" / "osint.db"

        icon_path = project_root / "src" / "gui" / "ogma_ai_logo.ico"
        if icon_path.exists():
            self.iconbitmap(str(icon_path))

        self.users_map          = {}
        self.current_bot        = None
        self.current_screencast = None
        self.is_running         = False

        # Session počítadla
        self._session_posts     = 0
        self._session_comments  = 0
        self._session_followers = 0
        self._session_following = 0

        self.load_users()

        # Session logger
        self.session_logger = SessionLogger()

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        # ── Sidebar ──────────────────────────────────────────────────
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0,
                                    fg_color=COLORS["sidebar_bg"])
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.pack_propagate(False)

        # ── Main area ────────────────────────────────────────────────
        self.main_area = ctk.CTkFrame(self, corner_radius=0,
                                      fg_color=COLORS["main_bg"])
        self.main_area.grid(row=0, column=1, sticky="nsew")
        self.main_area.grid_rowconfigure(0, weight=1)
        self.main_area.grid_columnconfigure(0, weight=1)

        # ── Bottom bar (progress) ─────────────────────────────────────
        self._bottom_bar = ctk.CTkFrame(
            self, height=28, corner_radius=0,
            fg_color=COLORS["sidebar_bg"]
        )
        self._bottom_bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        self._bottom_bar.grid_propagate(False)
        self._bottom_bar.grid_columnconfigure(1, weight=1)

        self._progress_label = ctk.CTkLabel(
            self._bottom_bar, text="Připraveno",
            font=("Segoe UI", 10), text_color=COLORS["text_dim"],
            width=120, anchor="w"
        )
        self._progress_label.grid(row=0, column=0, padx=(12, 8), pady=4)

        self._global_progress = ctk.CTkProgressBar(
            self._bottom_bar, height=8, corner_radius=4,
            fg_color=COLORS["main_bg"], progress_color=COLORS["primary"]
        )
        self._global_progress.set(0)
        self._global_progress.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=9)

        self._progress_pct = ctk.CTkLabel(
            self._bottom_bar, text="",
            font=("Consolas", 10), text_color=COLORS["text_dim"],
            width=40, anchor="e"
        )
        self._progress_pct.grid(row=0, column=2, padx=(0, 12), pady=4)

        # ── Frames ──
        self.frame_dash     = DashboardFrame(self.main_area, self)
        self.frame_prof     = ProfilesFrame(self.main_area, self)
        self.frame_db       = DatabaseFrame(self.main_area, self)
        self.frame_analysis = AnalysisFrame(self.main_area, self)
        self.frame_metrics  = MetricsFrame(self.main_area, self)
        self.frame_sessions = SessionsFrame(self.main_area, self)
        self.frame_watchlist = WatchlistFrame(self.main_area, self.scheduler)

        sys.stdout = PrintLogger(self.frame_dash.log_box, self)
        sys.stderr = PrintLogger(self.frame_dash.log_box, self)

        self.setup_sidebar()
        self.show_frame("dashboard")

    def setup_sidebar(self):
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.pack(pady=(25, 20), padx=20, fill="x")
        ctk.CTkLabel(logo_frame, text="Ogma 0.0", font=("Segoe UI", 22, "bold"),
                     text_color=COLORS["text_main"], anchor="w").pack(fill="x")
        ctk.CTkLabel(logo_frame, text="OSINT Automation Tool",
                     font=("Segoe UI", 12),
                     text_color=COLORS["text_dim"], anchor="w").pack(fill="x")

        ctk.CTkFrame(self.sidebar, height=1,
                     fg_color=COLORS["border"]).pack(fill="x", pady=10)

        self.btn_nav_dash     = self.create_nav_btn("Přehled (Dashboard)", "dashboard")
        self.btn_nav_prof     = self.create_nav_btn("Scrapnuté Profily",   "profiles")
        self.btn_nav_db       = self.create_nav_btn("Databáze (Vault)",    "database")
        self.btn_nav_analysis = self.create_nav_btn("Analýza",             "analysis")
        self.btn_nav_metrics  = self.create_nav_btn("Metriky",             "metrics")
        self.btn_nav_sessions = self.create_nav_btn("Historie běhů",       "sessions")
        self.btn_nav_watchlist = self.create_nav_btn("Watchlist",          "watchlist")

        self._sidebar_traffic_frame = ctk.CTkFrame(
            self.sidebar, fg_color=COLORS["panel_bg"],
            corner_radius=6, border_width=1, border_color=COLORS["border"]
        )
        self._sidebar_traffic_frame.pack(side="bottom", fill="x",
                                         padx=14, pady=(0, 8))

        _hdr = ctk.CTkFrame(self._sidebar_traffic_frame, fg_color="transparent")
        _hdr.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(_hdr, text="SÍŤOVÝ PROVOZ",
                     font=("Segoe UI", 9, "bold"),
                     text_color=COLORS["text_dim"]).pack(side="left")
        self._traffic_status_dot = ctk.CTkLabel(
            _hdr, text="●", font=("Segoe UI", 9),
            text_color=COLORS["text_dim"])
        self._traffic_status_dot.pack(side="right")

        def _traffic_row(parent, label, color):
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=1)
            ctk.CTkLabel(row, text=label, font=("Segoe UI", 9),
                         text_color=COLORS["text_dim"],
                         width=14, anchor="w").pack(side="left")
            var = ctk.StringVar(value="—")
            ctk.CTkLabel(row, textvariable=var, font=("Consolas", 10),
                         text_color=color, anchor="e").pack(side="right")
            return var

        self._sidebar_rx_var = _traffic_row(self._sidebar_traffic_frame, "↓", "#175DDC")
        self._sidebar_tx_var = _traffic_row(self._sidebar_traffic_frame, "↑", "#2eb85c")

        self._sidebar_sparkline = tk.Canvas(
            self._sidebar_traffic_frame, height=28,
            bg=COLORS["panel_bg"], highlightthickness=0, bd=0)
        self._sidebar_sparkline.pack(fill="x", padx=8, pady=(2, 6))

        self._sidebar_traffic_poll()

        bottom_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom_frame.pack(side="bottom", fill="x", padx=14, pady=(0, 8))

        self.status_label = ctk.CTkLabel(
            bottom_frame, text="● Připraveno",
            text_color="#2eb85c", font=("Segoe UI", 12), anchor="w"
        )
        self.status_label.pack(fill="x", pady=(0, 8))

    def _sidebar_traffic_poll(self):
        try:
            t = self.frame_metrics.traffic
            with t._lock:
                rx_s    = t.rx_speed
                tx_s    = t.tx_speed
                running = t._running
                rx_hist = list(t.rx_history)
                tx_hist = list(t.tx_history)

            if running:
                self._sidebar_rx_var.set(_fmt_speed(rx_s))
                self._sidebar_tx_var.set(_fmt_speed(tx_s))
                self._traffic_status_dot.configure(text_color="#2eb85c")
            else:
                self._sidebar_rx_var.set("—")
                self._sidebar_tx_var.set("—")
                self._traffic_status_dot.configure(text_color=COLORS["text_dim"])

            self._sidebar_draw_sparkline(rx_hist, tx_hist)
        except Exception:
            pass
        self.after(1000, self._sidebar_traffic_poll)

    def _sidebar_draw_sparkline(self, rx, tx):
        c = self._sidebar_sparkline
        w = c.winfo_width()
        h = c.winfo_height()
        if w <= 1 or h <= 1: return
        c.delete("all")

        def draw(history, color):
            peak = max(history) or 1
            n    = len(history)
            pts  = []
            for i, v in enumerate(history):
                x = int(i / (n - 1) * w) if n > 1 else w // 2
                y = int(h - (v / peak) * (h - 2))
                pts.extend([x, y])
            if len(pts) >= 4:
                c.create_line(pts, fill=color, width=1, smooth=True)

        draw(rx, "#175DDC")
        draw(tx, "#2eb85c")

    def create_nav_btn(self, text, view_name):
        return (
            ctk.CTkButton(
                self.sidebar, text=text,
                command=lambda: self.show_frame(view_name),
                fg_color="transparent", text_color=COLORS["text_dim"],
                hover_color=COLORS["panel_bg"], anchor="w",
                height=45, font=("Segoe UI", 14), corner_radius=4
            ).pack(fill="x", padx=10, pady=2)
            or self.sidebar.winfo_children()[-1]
        )

    def show_frame(self, name):
        all_btns = [
            self.btn_nav_dash, self.btn_nav_prof, self.btn_nav_db,
            self.btn_nav_analysis, self.btn_nav_metrics, self.btn_nav_sessions,
            self.btn_nav_watchlist
        ]
        for btn in all_btns:
            btn.configure(fg_color="transparent", text_color=COLORS["text_dim"])

        all_frames = [
            self.frame_dash, self.frame_prof, self.frame_db,
            self.frame_analysis, self.frame_metrics, self.frame_sessions,
            self.frame_watchlist
        ]
        for f in all_frames:
            f.grid_forget()

        pad = dict(row=0, column=0, sticky="nsew", padx=30, pady=30)

        if name == "dashboard":
            self.frame_dash.grid(**pad)
            self.btn_nav_dash.configure(fg_color=COLORS["panel_bg"], text_color=COLORS["primary"])
        elif name == "profiles":
            self.frame_prof.grid(**pad)
            self.btn_nav_prof.configure(fg_color=COLORS["panel_bg"], text_color=COLORS["primary"])
            self.frame_prof.refresh_data()
        elif name == "database":
            self.frame_db.grid(**pad)
            self.btn_nav_db.configure(fg_color=COLORS["panel_bg"], text_color=COLORS["primary"])
            self.frame_db.refresh_data()
        elif name == "analysis":
            self.frame_analysis.grid(**pad)
            self.btn_nav_analysis.configure(fg_color=COLORS["panel_bg"], text_color=COLORS["primary"])
            self.frame_analysis.refresh_results()
        elif name == "metrics":
            self.frame_metrics.grid(**pad)
            self.btn_nav_metrics.configure(fg_color=COLORS["panel_bg"], text_color=COLORS["primary"])
        elif name == "sessions":
            self.frame_sessions.grid(**pad)
            self.btn_nav_sessions.configure(fg_color=COLORS["panel_bg"], text_color=COLORS["primary"])
            self.frame_sessions.refresh_data()
        elif name == "watchlist":
            self.frame_watchlist.grid(**pad)
            self.btn_nav_watchlist.configure(fg_color=COLORS["panel_bg"], text_color=COLORS["primary"])
            self.frame_watchlist._refresh_list()

    def set_progress(self, current: int, total: int, label: str = ""):
        if total <= 0:
            self._global_progress.set(0)
            self._progress_pct.configure(text="")
            self._progress_label.configure(text=label or "Připraveno")
            return
        pct = min(current / total, 1.0)
        self._global_progress.set(pct)
        self._progress_pct.configure(text=f"{int(pct * 100)} %")
        self._progress_label.configure(text=label or f"{current} / {total}")

    def reset_progress(self):
        self._global_progress.set(0)
        self._progress_pct.configure(text="")
        self._progress_label.configure(text="Připraveno")

    def update_sidebar_progress(self, key: str, current: int, total: int):
        labels = {
            "posts":     "Příspěvky",
            "comments":  "Komentáře",
            "followers": "Sledující",
            "following": "Sleduje",
            "sentiment": "Analýza sentimentu",
            "batch":     "Cíle",
        }
        lbl = f"{labels.get(key, key)}  {current}/{total}"
        self.set_progress(current, total, lbl)

    def load_users(self):
        if not os.path.exists(self.data_path):
            return
        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for user in data.get("users", []):
                self.users_map[f"{user['ID']} - {user['name']}"] = user
        except Exception:
            pass

    def start_thread(self, platform, action):
        if self.is_running:
            messagebox.showwarning("Busy", "Bot již běží.")
            return

        key = self.frame_dash.user_var.get()
        if not key:
            messagebox.showerror("Chyba", "Vyber identitu.")
            return

        user_data = self.users_map[key]
        social    = user_data.get("social_media", {}).get(platform)
        
        # YouTube nevyžaduje uložené heslo v identitě
        if not social and platform != "youtube":
            messagebox.showerror("Chyba", f"Identita nemá {platform}.")
            return

        target_input = self.frame_dash.target_var.get().strip()
        if action == "scrape" and not target_input:
            messagebox.showwarning("Chyba", "Zadej cíl.")
            return

        u = social["username"] if social else None
        p = social["password"] if social else None

        limit = 10
        if self.frame_dash.scrape_all_var.get():
            limit = -1
        else:
            try:
                limit = int(self.frame_dash.limit_var.get())
            except ValueError:
                messagebox.showerror("Chyba", "Limit příspěvků musí být číslo.")
                return

        try:
            comments_limit = int(self.frame_dash.comments_limit_var.get())
        except ValueError:
            messagebox.showerror("Chyba", "Limit komentářů musí být číslo.")
            return

        try:
            followers_limit = int(self.frame_dash.followers_limit_var.get())
        except ValueError:
            messagebox.showerror("Chyba", "Limit sledujících musí být číslo.")
            return

        try:
            following_limit = int(self.frame_dash.following_limit_var.get())
        except ValueError:
            messagebox.showerror("Chyba", "Limit 'Sleduje' musí být číslo.")
            return

        self.is_running = True
        txt_limit = "VŠE" if limit == -1 else str(limit)
        self.status_label.configure(
            text=f"● Běží: {platform} (P:{txt_limit} K:{comments_limit})",
            text_color=COLORS["primary"]
        )

        self.frame_dash.log_box.configure(state="normal")
        self.frame_dash.log_box.delete(1.0, tk.END)
        self.frame_dash.log_box.configure(state="disabled")

        headless = self.frame_dash.headless_var.get()

        threading.Thread(
            target=self.run_bot,
            args=(platform, u, p,
                  key.split()[0], action, target_input,
                  limit, comments_limit, followers_limit, following_limit,
                  headless),
            daemon=True
        ).start()

    def run_bot(self, platform, u, p, uid, action, target_input,
                limit, comments_limit, followers_limit, following_limit,
                headless=True):
        try:
            # ── Vytvoření bota ──
            if platform == "instagram":
                bot = InstagramBot(u, p, uid, headless=headless)
            elif platform == "youtube":
                bot = YouTubeBot(u, p, uid, headless=headless)
            else:
                bot = XBot(u, p, uid, headless=headless)
                
            self.current_bot = bot
            bot.login()

            # ── Progress callback ──
            self._session_posts     = 0
            self._session_comments  = 0
            self._session_followers = 0
            self._session_following = 0

            if hasattr(bot, "scraper"):
                labels = {
                    "posts":     "Příspěvky",
                    "comments":  "Komentáře",
                    "followers": "Sledující",
                    "following": "Sleduje",
                    "sentiment": "Analýza sentimentu",
                    "batch":     "Cíle",
                }
                def _progress_cb(key, current, total):
                    if key == "posts":     self._session_posts     = current
                    if key == "comments":  self._session_comments  = current
                    if key == "followers": self._session_followers  = current
                    if key == "following": self._session_following  = current
                    lbl = f"{labels.get(key, key)}  {current}/{total}"
                    self.after(0, lambda c=current, t=total, l=lbl:
                        self.set_progress(c, t, l))
                bot.scraper.progress_callback = _progress_cb

            # ── CDP Screencast ──
            try:
                self.current_screencast = CDPScreencast(
                    page=bot.page,
                    on_frame=lambda img: self.after(
                        0, lambda i=img:
                        self.frame_dash.browser_preview.push_frame(i)),
                    on_stop=lambda: self.after(
                        0, self.frame_dash.browser_preview.set_offline)
                )
                self.current_screencast.start()
            except Exception as e:
                print(f"[PREVIEW] Nelze spustit náhled: {e}")

            # ── Traffic monitoring ──
            try:
                self.frame_metrics.traffic.attach(bot.page)
                self.after(0, lambda: self.frame_metrics._bot_status_var.set(
                    "● Bot běží  —  měřím provoz"))
            except Exception as e:
                print(f"[METRICS] Nelze spustit monitoring: {e}")

            # ── Scraping ──
            if action == "scrape":
                targets = [t.strip() for t in target_input.replace("\n", ",").split(",") if t.strip()]
                total = len(targets)
                self.after(0, lambda: self.set_progress(0, total, f"Cíle  0/{total}"))

                for i, target in enumerate(targets):
                    if not self.is_running: break

                    self.after(0, lambda idx=i, tot=total, t=target: [
                        self.status_label.configure(text=f"● Težím {idx+1}/{tot}: {t}", text_color=COLORS["primary"]),
                        self.set_progress(idx, tot, f"Cíle  {idx}/{tot}: {t}"),
                    ])

                    # Reset session
                    self.frame_metrics.traffic.reset()
                    self.session_logger.start_session(
                        platform=platform, bot_identity=uid, target_username=target,
                        limit_posts=limit, limit_comments=comments_limit,
                        limit_followers=followers_limit, limit_following=following_limit
                    )

                    interrupted = False
                    try:
                        bot.scraper.scrape_profile(target, limit, comments_limit)
                    except Exception as e:
                        self.session_logger.log_error()
                        print(f"[ERROR] Chyba u cíle {target}: {e}")

                    if not self.is_running: interrupted = True

                    with self.frame_metrics.traffic._lock:
                        rx = self.frame_metrics.traffic.rx_total
                        tx = self.frame_metrics.traffic.tx_total

                    self.session_logger.set_traffic(rx_bytes=rx, tx_bytes=tx)
                    self.session_logger.set_counts(posts=self._session_posts, comments=self._session_comments)
                    self.session_logger.finish_session(interrupted=interrupted)

                    if not interrupted and i < total - 1:
                        time.sleep(3)

            elif action == "scrape_trending":
                bot.scraper.scrape_trending()

            # ── Post-processing ──
            if action == "scrape":
                print("[INFO] Spouštím automatickou sentiment analýzu...")
                try:
                    from src.analysis.sentiment import SentimentAnalyzer
                    sa = SentimentAnalyzer()
                    sa.analyze_pending()
                except: pass

        except Exception as e:
            print(f"CHYBA: {e}")
        finally:
            try:
                if self.current_screencast: self.current_screencast.stop()
                self.frame_metrics.traffic.detach()
                self.after(0, self.frame_metrics.bot_stopped)
            except: pass

            if self.current_bot: self.current_bot.close()
            self.current_bot = None
            self.is_running  = False
            self.after(0, self.reset_progress)
            self.after(0, lambda: self.status_label.configure(text="● Připraveno", text_color="#2eb85c"))

    def stop_bot(self):
        self.is_running = False
        if self.current_bot:
            try: self.current_bot.close()
            except: pass
            self.current_bot = None


if __name__ == "__main__":
    app = App()
    app.mainloop()