"""
Konfigurationsmanagement für den DDR5 RAM Bot.
Lädt Umgebungsvariablen aus .env Datei.
"""

import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# Lade .env Datei
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # Fallback: Suche im aktuellen Verzeichnis
    load_dotenv()


class Config:
    """Zentrale Konfigurationsklasse."""

    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_IDS: List[str] = [
        cid.strip()
        for cid in os.getenv("TELEGRAM_CHAT_IDS", "").split(",")
        if cid.strip()
    ]

    # Scraping
    SCAN_INTERVAL_SECONDS: int = int(os.getenv("SCAN_INTERVAL_SECONDS", "60"))
    MAX_PAGES_PER_SCAN: int = int(os.getenv("MAX_PAGES_PER_SCAN", "5"))
    REQUEST_DELAY_MIN: float = float(os.getenv("REQUEST_DELAY_MIN", "2"))
    REQUEST_DELAY_MAX: float = float(os.getenv("REQUEST_DELAY_MAX", "4"))

    # Selenium
    HEADLESS: bool = os.getenv("HEADLESS", "true").lower() == "true"
    IMPLICIT_WAIT: int = int(os.getenv("IMPLICIT_WAIT", "10"))
    PAGE_LOAD_TIMEOUT: int = int(os.getenv("PAGE_LOAD_TIMEOUT", "30"))

    # Database
    DB_PATH: str = os.getenv("DB_PATH", "./data/ads.db")

    # Filters
    MIN_PRICE: float = float(os.getenv("MIN_PRICE", "50"))
    MAX_PRICE: float = float(os.getenv("MAX_PRICE", "500"))
    EXCLUDE_DEFEKT: bool = os.getenv("EXCLUDE_DEFEKT", "true").lower() == "true"

    # Proxy (optional)
    HTTP_PROXY: str = os.getenv("HTTP_PROXY", "")

    @classmethod
    def validate(cls) -> None:
        """Validiert die Konfiguration."""
        errors = []

        if not cls.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN fehlt")

        if not cls.TELEGRAM_CHAT_IDS:
            errors.append("TELEGRAM_CHAT_IDS fehlt")

        if cls.SCAN_INTERVAL_SECONDS < 1:
            errors.append("SCAN_INTERVAL_SECONDS muss >= 1 sein")

        if cls.REQUEST_DELAY_MIN < 0 or cls.REQUEST_DELAY_MAX < cls.REQUEST_DELAY_MIN:
            errors.append("REQUEST_DELAY_MIN/MAX ungültig")

        if errors:
            raise ValueError(f"Konfigurationsfehler: {', '.join(errors)}")

    @classmethod
    def get_db_path(cls) -> Path:
        """Gibt den absoluten Pfad zur Datenbank zurück."""
        db_path = Path(cls.DB_PATH)
        if not db_path.is_absolute():
            # Relativ zum Projekt-Root
            db_path = Path(__file__).parent.parent / db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return db_path


# Globale Config-Instanz
config = Config()

