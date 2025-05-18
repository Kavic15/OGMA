import threading
from typing import Optional

class Logger:
    _instance = None
    _lock = threading.Lock()
    app = None
    log_panel = None

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

    @classmethod
    def initialize(cls, app, log_panel):
        cls.app = app
        cls.log_panel = log_panel

    @classmethod
    def log(cls, message: str, tag: Optional[str] = None):
        if cls.log_panel and cls.app:
            # Thread-safe GUI update
            cls.app.after(0, cls._queue_log, message, tag)

    @classmethod
    def _queue_log(cls, message: str, tag: Optional[str]):
        if tag:
            cls.log_panel.log(f"[{tag}] {message}")
        else:
            cls.log_panel.log(message)

def log(message: str, tag: Optional[str] = None):
    Logger.log(message, tag)