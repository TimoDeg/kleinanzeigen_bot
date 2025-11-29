"""
Telegram Bot Integration für DDR5 RAM Bot.
Handhabt Commands und Benachrichtigungen.
"""

import logging
from typing import List

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from .models import Listing
from .database import Database

logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram Bot für DDR5 RAM Benachrichtigungen."""

    def __init__(self, token: str, chat_ids: List[str], database: Database):
        """
        Initialisiert den Telegram Bot.

        Args:
            token: Telegram Bot Token
            chat_ids: Liste von Chat-IDs
            database: Database Instanz
        """
        self.token = token
        self.chat_ids = chat_ids
        self.database = database
        self.application = Application.builder().token(token).build()

        # Registriere Commands
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("test", self.test_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))

    def format_listing_message(self, listing: Listing) -> str:
        """
        Formatiert ein Listing als Telegram-Nachricht.

        Args:
            listing: Listing Objekt

        Returns:
            Formatierte Nachricht
        """
        msg = f"🔷 *DDR5 RAM Alert* [Priority Score: {listing.priority_score}/16]\n\n"

        # Specs
        msg += f"📦 *Modell:* {listing.specs.model_number or 'Unbekannt'}\n"
        msg += f"🏭 *Hersteller:* {listing.specs.manufacturer or 'Unbekannt'}\n"
        msg += f"💾 *Kapazität:* {listing.specs.capacity or 'Unbekannt'}\n"
        msg += f"⚡ *Takt:* {listing.specs.speed or 'Unbekannt'}\n"
        msg += f"⏱️ *Latenz:* {listing.specs.latency or 'Unbekannt'}\n"
        msg += f"🎨 *Farbe:* {listing.specs.color or 'Unbekannt'}\n\n"

        # Details
        msg += f"💰 *Preis:* {listing.price:.2f}€\n"
        msg += f"📍 *Ort:* {listing.location}\n"
        msg += f"✅ *OVP:* {'Ja' if listing.has_ovp else 'Nein'}\n"
        msg += f"📄 *Rechnung:* {'Ja' if listing.has_invoice else 'Nein'}\n"
        msg += f"📮 *Versand:* {'Möglich' if listing.shipping_available else 'Nur Abholung'}\n"
        msg += f"🕐 *Online seit:* {listing.posted_date}\n\n"

        msg += f"🔗 [Zur Anzeige]({listing.url})"

        return msg

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handler für /start Command."""
        if str(update.effective_chat.id) not in self.chat_ids:
            await update.message.reply_text("❌ Nicht autorisiert")
            return

        welcome_text = (
            "🤖 *DDR5 RAM Bot*\n\n"
            "Ich durchsuche eBay Kleinanzeigen nach DDR5 RAM und benachrichtige dich bei neuen Funden.\n\n"
            "*Commands:*\n"
            "/start - Diese Nachricht\n"
            "/status - Aktuelle Statistiken\n"
            "/test - Letzte 5 Anzeigen anzeigen\n"
            "/stats - Detaillierte Statistiken\n\n"
            "Der Bot läuft permanent und scannt alle 60 Sekunden."
        )

        await update.message.reply_text(welcome_text, parse_mode="Markdown")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handler für /status Command."""
        if str(update.effective_chat.id) not in self.chat_ids:
            await update.message.reply_text("❌ Nicht autorisiert")
            return

        stats = self.database.get_stats()

        status_text = (
            "📊 *Status*\n\n"
            f"📦 *Gesamt:* {stats['total']} Anzeigen\n"
            f"📅 *Heute:* {stats['today']} Anzeigen\n"
            f"🕐 *Letzter Scan:* {stats['last_scan'] or 'Nie'}\n\n"
            "Der Bot läuft und scannt kontinuierlich."
        )

        await update.message.reply_text(status_text, parse_mode="Markdown")

    async def test_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handler für /test Command."""
        if str(update.effective_chat.id) not in self.chat_ids:
            await update.message.reply_text("❌ Nicht autorisiert")
            return

        listings = self.database.get_recent_listings(limit=5)

        if not listings:
            await update.message.reply_text("❌ Keine Anzeigen in der Datenbank")
            return

        await update.message.reply_text(
            f"📋 *Letzte {len(listings)} Anzeigen:*\n\n"
            "Sende Details...",
            parse_mode="Markdown"
        )

        for listing in listings:
            try:
                msg = self.format_listing_message(listing)
                await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=False)
            except Exception as e:
                logger.error(f"Fehler beim Senden der Test-Nachricht: {e}")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handler für /stats Command."""
        if str(update.effective_chat.id) not in self.chat_ids:
            await update.message.reply_text("❌ Nicht autorisiert")
            return

        stats = self.database.get_stats()

        stats_text = "📊 *Detaillierte Statistiken*\n\n"
        stats_text += f"📦 *Gesamt:* {stats['total']} Anzeigen\n"
        stats_text += f"📅 *Heute:* {stats['today']} Anzeigen\n"
        stats_text += f"🕐 *Letzter Scan:* {stats['last_scan'] or 'Nie'}\n\n"

        if stats['manufacturers']:
            stats_text += "🏭 *Hersteller-Verteilung:*\n"
            for manufacturer, count in list(stats['manufacturers'].items())[:10]:
                stats_text += f"   • {manufacturer}: {count}\n"

        await update.message.reply_text(stats_text, parse_mode="Markdown")

    async def send_listing(self, listing: Listing) -> bool:
        """
        Sendet eine einzelne Anzeige an alle konfigurierten Chat-IDs.

        Args:
            listing: Listing Objekt

        Returns:
            True wenn mindestens eine Nachricht gesendet wurde
        """
        msg = self.format_listing_message(listing)
        success = False

        for chat_id in self.chat_ids:
            try:
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text=msg,
                    parse_mode="Markdown",
                    disable_web_page_preview=False
                )
                success = True
                logger.info(f"Telegram-Nachricht gesendet an {chat_id}: {listing.ad_id}")
            except Exception as e:
                logger.error(f"Fehler beim Senden an {chat_id}: {e}")

        return success

    async def send_listings(self, listings: List[Listing], max_count: int = 10) -> int:
        """
        Sendet mehrere Anzeigen (mit Batch-Limit).

        Args:
            listings: Liste von Listing Objekten
            max_count: Maximale Anzahl zu sendender Nachrichten

        Returns:
            Anzahl gesendeter Nachrichten
        """
        sent_count = 0

        # Sortiere nach Priority Score (höchste zuerst)
        sorted_listings = sorted(listings, key=lambda x: x.priority_score, reverse=True)

        for listing in sorted_listings[:max_count]:
            if await self.send_listing(listing):
                sent_count += 1

        return sent_count

    async def send_welcome_message(self) -> None:
        """Sendet Willkommens-Nachricht beim Start."""
        # Hole Top 3 neueste Anzeigen
        listings = self.database.get_recent_listings(limit=3)

        welcome_text = (
            "🤖 *DDR5 RAM Bot gestartet!*\n\n"
            f"Der Bot läuft und scannt kontinuierlich nach DDR5 RAM.\n"
            f"Aktuell {len(listings)} Anzeigen in der Datenbank.\n\n"
            "Verwende /start für das Hauptmenü."
        )

        for chat_id in self.chat_ids:
            try:
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text=welcome_text,
                    parse_mode="Markdown"
                )

                # Sende Top 3 Anzeigen als Vorschau
                if listings:
                    await self.application.bot.send_message(
                        chat_id=chat_id,
                        text="📋 *Top 3 neueste Anzeigen:*",
                        parse_mode="Markdown"
                    )
                    for listing in listings[:3]:
                        await self.send_listing(listing)

            except Exception as e:
                logger.warning(f"Konnte Welcome-Message nicht senden an {chat_id}: {e}")

    async def start(self) -> None:
        """Startet den Telegram Bot."""
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(drop_pending_updates=True)
        logger.info("Telegram Bot gestartet")

    async def stop(self) -> None:
        """Stoppt den Telegram Bot."""
        if self.application.updater.running:
            await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()
        logger.info("Telegram Bot gestoppt")

