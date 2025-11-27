#!/usr/bin/env python3
"""
Hauptprogramm für den eBay Kleinanzeigen Scraper-Bot.
Läuft als endlose Schleife und sendet Benachrichtigungen bei neuen Anzeigen.
"""

import asyncio
import json
import logging
import signal
import sys
import argparse
from pathlib import Path
from typing import List, Dict

from scraper import KleinanzeigenScraper
from notifier import Notifier
from database import Database


class KleinanzeigenBot:
    """Hauptklasse für den Kleinanzeigen-Bot."""
    
    def __init__(self, config_path: str = "config.json"):
        """
        Initialisiert den Bot mit Konfiguration.
        
        Args:
            config_path: Pfad zur Konfigurationsdatei
        """
        self.config = self._load_config(config_path)
        self._setup_logging()
        self._validate_config()
        
        # Initialisiere Komponenten
        search_config = self.config["search"]
        scraper_config = self.config["scraper"]
        telegram_config = self.config["telegram"]
        db_config = self.config["database"]
        
        self.scraper = KleinanzeigenScraper(
            keyword=search_config["keyword"],
            category=search_config["category"],
            sort=search_config["sort"],
            user_agent=scraper_config["user_agent"],
            timeout=scraper_config["request_timeout"],
            delay_min=scraper_config["request_delay_min"],
            delay_max=scraper_config["request_delay_max"],
            max_retries=scraper_config["max_retries"],
            retry_delay=scraper_config["retry_delay"]
        )
        
        self.notifier = Notifier(
            token=telegram_config["token"],
            chat_id=telegram_config["chat_id"]
        )
        
        self.database = Database(db_config["path"])
        
        # Konfiguration
        self.interval = scraper_config["interval_seconds"]
        self.price_min = search_config.get("price_min")
        self.price_max = search_config.get("price_max")
        self.exclude_keywords = search_config.get("exclude_keywords", [])
        
        # Shutdown-Flag
        self.running = True
        
        # Signal-Handler für graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _load_config(self, config_path: str) -> dict:
        """
        Lädt die Konfiguration aus einer JSON-Datei.
        
        Args:
            config_path: Pfad zur Konfigurationsdatei
            
        Returns:
            Konfigurations-Dictionary
        """
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Konfigurationsdatei nicht gefunden: {config_path}")
        
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config
        except json.JSONDecodeError as e:
            raise ValueError(f"Ungültige JSON-Konfiguration: {e}")
    
    def _setup_logging(self) -> None:
        """Konfiguriert das Logging-System."""
        log_config = self.config.get("logging", {})
        level = getattr(logging, log_config.get("level", "INFO").upper())
        format_str = log_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        
        logging.basicConfig(
            level=level,
            format=format_str,
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    def _validate_config(self) -> None:
        """Validiert die Konfiguration und gibt Warnungen aus."""
        logger = logging.getLogger(__name__)
        
        # Prüfe Telegram-Konfiguration
        telegram_config = self.config.get("telegram", {})
        if not telegram_config.get("token"):
            logger.warning("⚠️  Telegram Token ist nicht gesetzt! Benachrichtigungen werden nicht funktionieren.")
        if not telegram_config.get("chat_id"):
            logger.warning("⚠️  Telegram Chat-ID ist nicht gesetzt! Benachrichtigungen werden nicht gesendet.")
            logger.warning("   Verwende 'python3 main.py --test-telegram' nach dem Setzen der Chat-ID.")
        
        # Prüfe Suchparameter
        search_config = self.config.get("search", {})
        if not search_config.get("keyword"):
            logger.warning("⚠️  Kein Suchbegriff konfiguriert!")
        
        # Prüfe Scraper-Einstellungen
        scraper_config = self.config.get("scraper", {})
        if scraper_config.get("interval_seconds", 0) < 60:
            logger.warning("⚠️  Intervall ist sehr kurz (< 60s). Das könnte zu Rate-Limiting führen.")
        
        # Prüfe Datenbank
        db_config = self.config.get("database", {})
        if not db_config.get("path"):
            logger.warning("⚠️  Kein Datenbankpfad konfiguriert!")
    
    def _signal_handler(self, signum, frame) -> None:
        """
        Signal-Handler für graceful shutdown.
        
        Args:
            signum: Signal-Nummer
            frame: Frame-Objekt
        """
        logger = logging.getLogger(__name__)
        logger.info(f"Signal {signum} empfangen. Beende Bot...")
        self.running = False
    
    def _filter_ads(self, ads: List[Dict]) -> List[Dict]:
        """
        Filtert Anzeigen nach verschiedenen Kriterien.
        
        Args:
            ads: Liste von Anzeigen
            
        Returns:
            Gefilterte Liste von Anzeigen
        """
        filtered = []
        
        for ad in ads:
            # Preis-Filter
            price = ad.get("price")
            if price is not None:
                if self.price_min is not None and price < self.price_min:
                    continue
                if self.price_max is not None and price > self.price_max:
                    continue
            
            # Keyword-Ausschluss
            title = ad.get("title", "").lower()
            if any(keyword.lower() in title for keyword in self.exclude_keywords):
                logger.debug(f"Anzeige ausgeschlossen (Keyword-Filter): {ad.get('title', '')[:50]}")
                continue
            
            filtered.append(ad)
        
        return filtered
    
    def _get_new_ads(self, ads: List[Dict]) -> List[Dict]:
        """
        Filtert neue Anzeigen (noch nicht in der Datenbank).
        
        Args:
            ads: Liste von Anzeigen
            
        Returns:
            Liste von neuen Anzeigen
        """
        new_ads = []
        
        for ad in ads:
            ad_id = ad.get("id")
            if not ad_id:
                continue
            
            if self.database.is_new_ad(ad_id):
                new_ads.append(ad)
                # Sofort als gesehen markieren, um Duplikate zu vermeiden
                self.database.mark_as_seen(ad_id, ad.get("title", ""), ad.get("price"))
        
        return new_ads
    
    async def _run_once(self) -> None:
        """Führt einen einzelnen Scraping-Zyklus aus."""
        logger = logging.getLogger(__name__)
        
        try:
            # Scrape Anzeigen
            ads = self.scraper.fetch_ads()
            logger.info(f"Gefundene Anzeigen: {len(ads)}")
            
            if not ads:
                logger.warning("Keine Anzeigen gefunden")
                return
            
            # Filtere Anzeigen
            filtered_ads = self._filter_ads(ads)
            logger.info(f"Nach Filterung: {len(filtered_ads)} Anzeigen")
            
            # Finde neue Anzeigen
            new_ads = self._get_new_ads(filtered_ads)
            logger.info(f"Neue Anzeigen: {len(new_ads)}")
            
            # Sende Benachrichtigungen
            if new_ads:
                await self.notifier.send_telegram(new_ads)
            else:
                logger.info("Keine neuen Anzeigen")
            
            # Datenbank aufräumen (einmal pro Tag)
            if hasattr(self, "_last_cleanup"):
                from datetime import datetime, timedelta
                if datetime.now() - self._last_cleanup > timedelta(days=1):
                    self.database.cleanup_old_entries(self.config["database"]["cleanup_days"])
                    self._last_cleanup = datetime.now()
            else:
                from datetime import datetime
                self._last_cleanup = datetime.now()
                
        except Exception as e:
            logger.error(f"Fehler im Scraping-Zyklus: {e}", exc_info=True)
    
    async def run(self, test_mode: bool = False) -> None:
        """
        Hauptschleife des Bots.
        
        Args:
            test_mode: Wenn True, wird nur einmal gescraped und dann beendet
        """
        logger = logging.getLogger(__name__)
        logger.info("Kleinanzeigen-Bot gestartet")
        
        if test_mode:
            logger.info("Test-Modus: Einmaliges Scraping")
            await self._run_once()
            logger.info("Test-Modus beendet")
            return
        
        logger.info(f"Intervall: {self.interval} Sekunden")
        
        while self.running:
            try:
                await self._run_once()
            except Exception as e:
                logger.error(f"Unerwarteter Fehler: {e}", exc_info=True)
            
            if not self.running:
                break
            
            # Warte auf nächstes Intervall
            logger.info(f"Warte {self.interval} Sekunden bis zum nächsten Durchlauf...")
            for _ in range(self.interval):
                if not self.running:
                    break
                await asyncio.sleep(1)
        
        logger.info("Kleinanzeigen-Bot beendet")


async def main():
    """Hauptfunktion."""
    parser = argparse.ArgumentParser(description="eBay Kleinanzeigen Scraper-Bot")
    parser.add_argument(
        "--config",
        default="config.json",
        help="Pfad zur Konfigurationsdatei (Standard: config.json)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test-Modus: Nur einmal scrapen, keine Endlosschleife"
    )
    parser.add_argument(
        "--clear-db",
        action="store_true",
        help="Löscht alle Einträge aus der Datenbank"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Zeigt Statistiken über die Datenbank"
    )
    parser.add_argument(
        "--test-telegram",
        action="store_true",
        help="Sendet eine Test-Nachricht an Telegram"
    )
    
    args = parser.parse_args()
    
    try:
        bot = KleinanzeigenBot(args.config)
        
        if args.clear_db:
            deleted = bot.database.clear_all()
            print(f"Gelöscht: {deleted} Einträge")
            return
        
        if args.stats:
            stats = bot.database.get_stats(days=1)
            print(f"Statistiken:")
            print(f"  Gesamt: {stats['total']} Anzeigen")
            print(f"  Letzte 24h: {stats['last_1_days']} Anzeigen")
            return
        
        if args.test_telegram:
            success = await bot.notifier.send_test_message()
            if success:
                print("✅ Test-Nachricht erfolgreich gesendet")
            else:
                print("❌ Fehler beim Senden der Test-Nachricht")
            return
        
        await bot.run(test_mode=args.test)
        
    except KeyboardInterrupt:
        print("\nBot wird beendet...")
    except Exception as e:
        logging.error(f"Kritischer Fehler: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())


