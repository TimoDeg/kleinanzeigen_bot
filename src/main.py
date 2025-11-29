"""
Hauptprogramm für den DDR5 RAM Bot.
Orchestriert Scraping, Parsing und Telegram-Benachrichtigungen.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

from .config import config, Config
from .database import Database
from .scraper import KleinanzeigenScraper
from .parser import RAMParser
from .telegram_bot import TelegramBot

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


class DDR5RAMBot:
    """Hauptklasse für den DDR5 RAM Bot."""

    def __init__(self):
        """Initialisiert den Bot."""
        # Validiere Konfiguration
        Config.validate()

        # Initialisiere Komponenten
        self.database = Database(config.get_db_path())
        self.scraper = KleinanzeigenScraper()
        self.parser = RAMParser()
        self.telegram_bot = TelegramBot(
            token=config.TELEGRAM_BOT_TOKEN,
            chat_ids=config.TELEGRAM_CHAT_IDS,
            database=self.database,
        )

        self.running = True

        # Signal Handler für graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Signal Handler für graceful shutdown."""
        logger.info(f"Signal {signum} empfangen. Beende Bot...")
        self.running = False

    def _filter_listing(self, listing) -> bool:
        """
        Filtert Anzeigen nach Konfiguration.

        Args:
            listing: Listing Objekt

        Returns:
            True wenn Anzeige behalten werden soll
        """
        # Preis-Filter
        if listing.price < config.MIN_PRICE:
            return False
        if listing.price > config.MAX_PRICE:
            return False

        # Defekt-Filter
        if config.EXCLUDE_DEFEKT:
            text = f"{listing.title} {listing.raw_description}".lower()
            if any(keyword in text for keyword in ["defekt", "kaputt", "beschädigt"]):
                return False

        return True

    async def _process_ads(self, ads: list) -> list:
        """
        Verarbeitet rohe Anzeigen-Daten.

        Args:
            ads: Liste von rohen Anzeigen-Dictionaries

        Returns:
            Liste von Listing Objekten
        """
        listings = []

        for ad in ads:
            try:
                # Parse Anzeige
                listing = self.parser.parse_listing(
                    ad_id=ad["id"],
                    title=ad["title"],
                    description=ad.get("description", ""),
                    price=ad["price"],
                    location=ad.get("location", ""),
                    url=ad["link"],
                    posted_date=ad.get("posted_time", ""),
                )

                if not listing:
                    continue

                # Filter
                if not self._filter_listing(listing):
                    continue

                listings.append(listing)

            except Exception as e:
                logger.error(f"Fehler beim Verarbeiten der Anzeige {ad.get('id', 'unknown')}: {e}")
                continue

        return listings

    async def _scan_cycle(self) -> None:
        """Führt einen Scan-Zyklus durch."""
        logger.info("Starte Scan-Zyklus...")

        try:
            # Scrape Anzeigen
            ads = self.scraper.fetch_ads()
            logger.info(f"Gefundene Anzeigen: {len(ads)}")

            if not ads:
                logger.info("Keine Anzeigen gefunden")
                return

            # Parse und Filter
            listings = await self._process_ads(ads)
            logger.info(f"Nach Parsing/Filter: {len(listings)} Anzeigen")

            if not listings:
                logger.info("Keine gültigen Anzeigen nach Parsing/Filter")
                return

            # Prüfe auf neue Anzeigen
            new_listings = []
            for listing in listings:
                if self.database.is_new_listing(listing.ad_id):
                    new_listings.append(listing)
                    self.database.save_listing(listing)

            logger.info(f"Neue Anzeigen: {len(new_listings)}")

            # Sende Telegram-Benachrichtigungen
            if new_listings:
                sent_count = await self.telegram_bot.send_listings(new_listings, max_count=10)
                logger.info(f"Telegram-Benachrichtigungen gesendet: {sent_count}")

        except Exception as e:
            logger.error(f"Fehler im Scan-Zyklus: {e}", exc_info=True)

    async def run(self) -> None:
        """Hauptschleife des Bots."""
        logger.info("🚀 DDR5 RAM Bot gestartet")

        # Starte Telegram Bot
        await self.telegram_bot.start()

        # Sende Welcome-Message
        await self.telegram_bot.send_welcome_message()

        # Hauptschleife
        while self.running:
            try:
                await self._scan_cycle()

                # Warte 60 Sekunden (1 Minute Pause)
                logger.info(f"Warte {config.SCAN_INTERVAL_SECONDS} Sekunden bis zum nächsten Scan...")
                await asyncio.sleep(config.SCAN_INTERVAL_SECONDS)

            except KeyboardInterrupt:
                logger.info("KeyboardInterrupt empfangen")
                break
            except Exception as e:
                logger.error(f"Fehler in Hauptschleife: {e}", exc_info=True)
                await asyncio.sleep(60)  # Warte 60s bei Fehler

        # Cleanup
        logger.info("Beende Bot...")
        self.scraper.close()
        await self.telegram_bot.stop()
        logger.info("Bot beendet")


async def main():
    """Hauptfunktion."""
    try:
        bot = DDR5RAMBot()
        await bot.run()
    except KeyboardInterrupt:
        logger.info("Bot wird beendet...")
    except Exception as e:
        logger.error(f"Kritischer Fehler: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

