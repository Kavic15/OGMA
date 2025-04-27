# utils/logger.py
import logging
import sys
from datetime import datetime
from pathlib import Path

def setup_logger(name: str, log_level: str = "INFO", log_to_file: bool = True):
    """Initialize and configure the logger."""
    logger = logging.getLogger(name)
    logger.setLevel(log_level.upper())

    # Format: [Timestamp] [Module] [Level] Message
    formatter = logging.Formatter(
        '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console Handler (Always enabled)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler (Optional)
    if log_to_file:
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        
        log_file = logs_dir / f"instagram_automation_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger