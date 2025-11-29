#!/usr/bin/env python3
"""
Hauptprogramm für den eBay Kleinanzeigen Scraper-Bot (Multi-Search).
"""

import argparse
import asyncio
import json
import logging
import signal
import sys
from pathlib import Path
from typing import Dict, List

from database import Database
from notifier import Notifier
from scraper import KleinanzeigenScraper
from telegram_handler import TelegramHandler


class KleinanzeigenBot:
    """Hauptklasse für den Kleinanzeigen-Bot mit Multi-Search Support."""

    def __init__(self, config_path: str = "config.json") -> None:
        """
        Initialisiert den Bot mit Konfiguration.
        """
        self.config = self._load_config(config_path)
        self._setup_logging()
        self._validate_config()

        telegram_config = self.config["telegram"]
        scraper_config = self.config["scraper"]
        db_config = self.config["database"]

        self.database = Database(db_config["path"])

        chat_ids = telegram_config.get("chat_ids", [])
        self.chat_ids = [str(cid) for cid in chat_ids]

        self.notifier = Notifier(
            token=telegram_config["token"],
            chat_ids=chat_ids,
        )

        self.scraper_config = scraper_config

        # Geizhals API (optional)
        try:
            from geizhals_api import GeizhalsAPI

            self.geizhals = GeizhalsAPI()
            self.geizhals_enabled = True
            logging.getLogger(__name__).info("✅ Geizhals-Integration aktiviert")
        except ImportError:
            self.geizhals = None
            self.geizhals_enabled = False
            logging.getLogger(__name__).info("⚠️  Geizhals-Integration nicht verfügbar")

        # OCR Service (optional)
        try:
            from ocr_service import ArticleNumberOCR

            self.ocr = ArticleNumberOCR()
            self.ocr_enabled = True
            logging.getLogger(__name__).info("✅ OCR-Service aktiviert")
        except Exception:
            self.ocr = None
            self.ocr_enabled = False
            logging.getLogger(__name__).info("⚠️  OCR-Service nicht verfügbar")

        self.running = True

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        from telegram.ext import Application

        self.telegram_app = Application.builder().token(telegram_config["token"]).build()

        self.telegram_handler = TelegramHandler(
            database=self.database,
            allowed_chat_ids=self.chat_ids,
        )
        for handler in self.telegram_handler.get_handlers():
            self.telegram_app.add_handler(handler)

        from datetime import datetime

        self.start_time = datetime.now()

    def _load_config(self, config_path: str) -> dict:
        """Lädt Konfiguration."""
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
        """Konfiguriert Logging."""
        log_config = self.config.get("logging", {})
        level = getattr(logging, log_config.get("level", "INFO").upper())
        format_str = log_config.get(
            "format",
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        logging.basicConfig(
            level=level,
            format=format_str,
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def _validate_config(self) -> None:
        """Validiert Konfiguration."""
        logger = logging.getLogger(__name__)

        telegram_config = self.config.get("telegram", {})
        if not telegram_config.get("token"):
            logger.warning("⚠️  Telegram Token fehlt!")

        chat_ids = telegram_config.get("chat_ids", [])
        if not chat_ids:
            logger.warning("⚠️  Keine Chat-IDs konfiguriert!")
        else:
            logger.info(f"✅ Telegram konfiguriert für {len(chat_ids)} Chat-ID(s)")

    def _signal_handler(self, signum, frame) -> None:  # type: ignore[override]
        """Signal Handler für graceful shutdown."""
        logger = logging.getLogger(__name__)
        logger.info(f"Signal {signum} empfangen. Beende Bot...")
        self.running = False

    def _should_run_search(self, search: Dict) -> bool:
        """
        Prüft ob Suche ausgeführt werden soll (Intervall abgelaufen).
        """
        if not search.get("last_check"):
            return True

        from datetime import datetime

        try:
            if isinstance(search["last_check"], str):
                last_check = datetime.fromisoformat(search["last_check"])
            else:
                last_check = search["last_check"]

            elapsed = datetime.now() - last_check
            return elapsed.total_seconds() >= search["interval_seconds"]
        except Exception as e:
            logging.getLogger(__name__).warning(
                f"Fehler beim Prüfen des Intervalls: {e}"
            )
            return True

    async def _execute_search(self, search: Dict) -> None:
        """
        Führt eine einzelne Suche aus.
        """
        logger = logging.getLogger(__name__)

        try:
            scraper = KleinanzeigenScraper(
                keyword=search["keyword"],
                category=search.get("category", "c225"),
                sort="neueste",
                user_agent=self.scraper_config["user_agent"],
                timeout=self.scraper_config["request_timeout"],
                delay_min=self.scraper_config["request_delay_min"],
                delay_max=self.scraper_config["request_delay_max"],
                max_retries=self.scraper_config["max_retries"],
                retry_delay=self.scraper_config["retry_delay"],
            )

            ads = scraper.fetch_ads()
            logger.info(f"[Search {search['search_id']}] Gefundene Anzeigen: {len(ads)}")

            if not ads:
                return

            filtered_ads = self._filter_ads(ads, search)
            logger.info(
                f"[Search {search['search_id']}] Nach Filterung: {len(filtered_ads)} Anzeigen"
            )

            new_ads = self._get_new_ads(filtered_ads, search["search_id"])
            logger.info(
                f"[Search {search['search_id']}] Neue Anzeigen: {len(new_ads)}"
            )

            if self.ocr_enabled and new_ads:
                await self._process_ocr(new_ads)

            if self.geizhals_enabled and new_ads:
                await self._process_geizhals(new_ads)

            if new_ads:
                new_ads_sorted = list(reversed(new_ads))
                await self.notifier.send_telegram(new_ads_sorted)

            self.database.update_search_last_check(search["search_id"])

        except Exception as e:  # pragma: no cover - Netz/HTML Fehler
            logger.error(f"[Search {search['search_id']}] Fehler: {e}", exc_info=True)

    def _filter_ads(self, ads: List[Dict], search: Dict) -> List[Dict]:
        """
        Filtert Anzeigen nach Search-Kriterien.
        """
        logger = logging.getLogger(__name__)
        filtered: List[Dict] = []

        for ad in ads:
            price = ad.get("price")
            if price is not None:
                if search.get("price_min") is not None and price < search["price_min"]:
                    continue
                if search.get("price_max") is not None and price > search["price_max"]:
                    continue

            if ad.get("is_gesuch", False):
                logger.debug(f"Gesuch ausgeschlossen: {ad.get('title', '')[:50]}")
                continue

            title_lower = ad.get("title", "").lower()
            excluded = False
            for keyword in search.get("exclude_keywords", []):
                if keyword.lower() in title_lower:
                    logger.debug(
                        f"Keyword-Filter '{keyword}': "
                        f"{ad.get('title', '')[:50]}"
                    )
                    excluded = True
                    break
            if excluded:
                continue

            shipping_pref = search.get("shipping_preference", "both")
            if shipping_pref != "both":
                shipping_type = ad.get("shipping_type", "")
                if shipping_pref == "pickup" and "Abholung" not in shipping_type:
                    continue
                if shipping_pref == "shipping" and "Versand" not in shipping_type:
                    continue

            filtered.append(ad)

        return filtered

    def _get_new_ads(self, ads: List[Dict], search_id: int) -> List[Dict]:
        """
        Filtert neue Anzeigen und speichert sie in DB.
        """
        new_ads: List[Dict] = []

        for ad in ads:
            ad_id = ad.get("id")
            if not ad_id:
                continue

            if self.database.is_new_ad(ad_id):
                new_ads.append(ad)
                self.database.mark_as_seen_with_search(
                    ad_id=ad_id,
                    search_id=search_id,
                    title=ad.get("title", ""),
                    price=ad.get("price"),
                    link=ad.get("link"),
                    location=ad.get("location"),
                    shipping_type=ad.get("shipping_type"),
                    posted_time=ad.get("posted_time"),
                )

        return new_ads

    async def _process_ocr(self, ads: List[Dict]) -> None:
        """
        Führt OCR auf Bildern aus (sequenziell).
        """
        logger = logging.getLogger(__name__)

        if not self.ocr:
            return

        for ad in ads:
            images = ad.get("images") or []
            images = images[:3]

            if not images:
                continue

            for img_url in images:
                try:
                    article_nr = await self.ocr.extract_article_number(img_url)
                    if article_nr:
                        ad["ocr_article_nr"] = article_nr
                        logger.info(f"OCR erkannt: {article_nr}")
                        break
                except Exception as e:  # pragma: no cover
                    logger.warning(f"OCR Fehler: {e}")
                    continue

    async def _process_geizhals(self, ads: List[Dict]) -> None:
        """
        Führt Geizhals-Lookup aus.
        """
        logger = logging.getLogger(__name__)

        if not self.geizhals:
            return

        for ad in ads:
            try:
                geizhals_data = await self.geizhals.match_product(ad)
                if geizhals_data:
                    ad["geizhals_data"] = geizhals_data
                    logger.info(
                        "Geizhals Match: %s - %s€",
                        geizhals_data.get("model"),
                        geizhals_data.get("price"),
                    )
            except Exception as e:  # pragma: no cover
                logger.warning(f"Geizhals Fehler: {e}")
                continue

    async def run(self) -> None:
        """Hauptschleife des Bots."""
        logger = logging.getLogger(__name__)
        logger.info("🚀 Kleinanzeigen Bot gestartet")

        async with self.telegram_app:
            await self.telegram_app.initialize()
            await self.telegram_app.start()
            logger.info("✅ Telegram Bot bereit")

            welcome_msg = (
                "🤖 *Bot gestartet!*\n\n"
                "Verwende /start für das Hauptmenü."
            )
            for chat_id in self.chat_ids:
                try:
                    await self.telegram_app.bot.send_message(
                        chat_id=chat_id,
                        text=welcome_msg,
                        parse_mode="Markdown",
                    )
                except Exception as e:  # pragma: no cover
                    logger.warning(f"Konnte Welcome-Message nicht senden: {e}")

            while self.running:
                try:
                    active_searches = self.database.get_active_searches()

                    if not active_searches:
                        logger.info("Keine aktiven Suchen. Warte 60 Sekunden...")
                        await asyncio.sleep(60)
                        continue

                    for search in active_searches:
                        if not self.running:
                            break

                        if self._should_run_search(search):
                            logger.info(
                                "Führe Suche aus: %s (ID: %s)",
                                search["keyword"],
                                search["search_id"],
                            )
                            await self._execute_search(search)

                    await asyncio.sleep(30)

                except Exception as e:  # pragma: no cover
                    logger.error(f"Fehler in Main Loop: {e}", exc_info=True)
                    await asyncio.sleep(60)

            await self.telegram_app.stop()
            await self.telegram_app.shutdown()

        logger.info("Bot beendet")


async def main() -> None:
    """Hauptfunktion."""
    parser = argparse.ArgumentParser(description="eBay Kleinanzeigen Scraper-Bot")
    parser.add_argument(
        "--config",
        default="config.json",
        help="Pfad zur Konfigurationsdatei (Standard: config.json)",
    )
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="Führt Datenbank-Migration aus vor dem Start",
    )

    args = parser.parse_args()

    try:
        if args.migrate:
            from migrate_db import DatabaseMigration

            migration = DatabaseMigration()
            migration.migrate()
            print("✅ Migration abgeschlossen")
            return

        bot = KleinanzeigenBot(args.config)
        await bot.run()

    except KeyboardInterrupt:
        print("\n Bot wird beendet...")
    except Exception as e:
        logging.error(f"Kritischer Fehler: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

