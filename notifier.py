"""
Telegram-Benachrichtigungen für neue Anzeigen.
Verwendet python-telegram-bot für asynchrone Nachrichten.
"""

import logging
import asyncio
from typing import List, Dict, Optional

try:
    from telegram import Bot  # type: ignore
    from telegram.error import TelegramError  # type: ignore
except ImportError:
    Bot = None  # type: ignore
    TelegramError = Exception

logger = logging.getLogger(__name__)


class Notifier:
    """Verwaltet Telegram-Benachrichtigungen."""
    
    def __init__(self, token: str, chat_id: str, message_delay: float = 0.5):
        """
        Initialisiert den Notifier.
        
        Args:
            token: Telegram Bot Token
            chat_id: Telegram Chat ID für Benachrichtigungen
            message_delay: Verzögerung zwischen Nachrichten in Sekunden
        """
        if Bot is None:
            raise ImportError("python-telegram-bot ist nicht installiert. Installiere es mit: pip install python-telegram-bot")
        
        self.token = token
        self.chat_id = chat_id
        self.message_delay = message_delay
        self.bot: Optional[Bot] = None
        
        if not self.chat_id:
            logger.warning("Keine chat_id konfiguriert. Benachrichtigungen werden nicht gesendet.")
    
    async def _get_bot(self) -> Bot:
        """
        Gibt das Bot-Objekt zurück (lazy initialization).
        
        Returns:
            Telegram Bot-Objekt
        """
        if self.bot is None:
            self.bot = Bot(token=self.token)
        return self.bot
    
    def _format_price(self, price: Optional[float]) -> str:
        """
        Formatiert einen Preis für die Anzeige.
        
        Args:
            price: Preis als Float
            
        Returns:
            Formatierter Preis-String
        """
        if price is None:
            return "Preis auf Anfrage"
        return f"{price:.2f} €".replace(".", ",")
    
    def _format_ad_message(self, ad: Dict) -> str:
        """
        Formatiert eine Anzeige als Telegram-Nachricht.
        
        Args:
            ad: Dictionary mit Anzeigendaten
            
        Returns:
            Formatierte Nachricht als String
        """
        title = ad.get("title", "Kein Titel")
        price = self._format_price(ad.get("price"))
        location = ad.get("location", "Unbekannt")
        link = ad.get("link", "")
        posted_time = ad.get("posted_time", "")
        
        message = f"🔔 *Neue Anzeige gefunden!*\n\n"
        message += f"*{title}*\n\n"
        message += f"💰 Preis: {price}\n"
        message += f"📍 Ort: {location}\n"
        if posted_time:
            message += f"🕐 {posted_time}\n"
        message += f"\n🔗 [Zur Anzeige]({link})"
        
        return message
    
    async def send_telegram(self, ads: List[Dict]) -> int:
        """
        Sendet Telegram-Benachrichtigungen für neue Anzeigen.
        
        Args:
            ads: Liste von Anzeigen-Dictionaries
            
        Returns:
            Anzahl erfolgreich gesendeter Nachrichten
        """
        if not self.chat_id:
            logger.warning("Keine chat_id konfiguriert. Überspringe Benachrichtigungen.")
            return 0
        
        if not ads:
            return 0
        
        bot = await self._get_bot()
        sent_count = 0
        
        for ad in ads:
            try:
                message = self._format_ad_message(ad)
                
                await bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode="Markdown",
                    disable_web_page_preview=False
                )
                
                sent_count += 1
                logger.info(f"Telegram-Nachricht gesendet: {ad.get('title', 'Unbekannt')[:50]}...")
                
                # Rate-limiting zwischen Nachrichten
                if sent_count < len(ads):
                    await asyncio.sleep(self.message_delay)
                    
            except TelegramError as e:
                error_msg = str(e).lower()
                # Rate Limiting: Warte länger bei 429 Fehlern
                if "429" in error_msg or "rate limit" in error_msg or "too many requests" in error_msg:
                    logger.warning(f"Telegram Rate Limit erreicht. Warte 60 Sekunden...")
                    await asyncio.sleep(60)
                else:
                    logger.error(f"Telegram-Fehler beim Senden der Nachricht: {e}")
            except Exception as e:
                logger.error(f"Unerwarteter Fehler beim Senden der Telegram-Nachricht: {e}")
        
        logger.info(f"Telegram-Benachrichtigungen gesendet: {sent_count}/{len(ads)}")
        return sent_count
    
    async def send_test_message(self) -> bool:
        """
        Sendet eine Test-Nachricht an die konfigurierte Chat-ID.
        
        Returns:
            True wenn erfolgreich, False sonst
        """
        if not self.chat_id:
            logger.error("Keine chat_id konfiguriert.")
            return False
        
        try:
            bot = await self._get_bot()
            await bot.send_message(
                chat_id=self.chat_id,
                text="✅ *Kleinanzeigen-Bot Test*\n\nDer Bot funktioniert korrekt!",
                parse_mode="Markdown"
            )
            logger.info("Test-Nachricht erfolgreich gesendet")
            return True
        except TelegramError as e:
            logger.error(f"Fehler beim Senden der Test-Nachricht: {e}")
            return False
        except Exception as e:
            logger.error(f"Unerwarteter Fehler: {e}")
            return False


