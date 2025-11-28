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
    
    def __init__(self, token: str, chat_ids, message_delay: float = 0.5):
        """
        Initialisiert den Notifier.
        
        Args:
            token: Telegram Bot Token
            chat_ids: Telegram Chat ID(s) für Benachrichtigungen (String oder Liste von Strings)
            message_delay: Verzögerung zwischen Nachrichten in Sekunden
        """
        if Bot is None:
            raise ImportError("python-telegram-bot ist nicht installiert. Installiere es mit: pip install python-telegram-bot")
        
        self.token = token
        # Unterstütze sowohl einzelne Chat-ID (String) als auch mehrere (Liste)
        if isinstance(chat_ids, str):
            self.chat_ids = [chat_ids] if chat_ids else []
        elif isinstance(chat_ids, list):
            self.chat_ids = [str(cid) for cid in chat_ids if cid]
        else:
            self.chat_ids = []
        self.message_delay = message_delay
        self.bot: Optional[Bot] = None
        
        if not self.chat_ids:
            logger.warning("Keine chat_ids konfiguriert. Benachrichtigungen werden nicht gesendet.")
        else:
            logger.info(f"Notifier konfiguriert für {len(self.chat_ids)} Chat-ID(s)")
    
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
        Sendet Telegram-Benachrichtigungen für neue Anzeigen an alle konfigurierten Chat-IDs.
        
        Args:
            ads: Liste von Anzeigen-Dictionaries
            
        Returns:
            Anzahl erfolgreich gesendeter Nachrichten (gesamt über alle Chat-IDs)
        """
        if not self.chat_ids:
            logger.warning("Keine chat_ids konfiguriert. Überspringe Benachrichtigungen.")
            return 0
        
        if not ads:
            return 0
        
        bot = await self._get_bot()
        total_sent = 0
        max_retries = 3
        
        # Sende jede Anzeige an alle konfigurierten Chat-IDs
        for ad in ads:
            for chat_id in self.chat_ids:
                ad_sent = await self._send_ad_to_chat(bot, ad, chat_id, max_retries)
                total_sent += ad_sent
                
                # Rate-limiting zwischen Chat-IDs
                if chat_id != self.chat_ids[-1]:  # Nicht nach der letzten Chat-ID
                    await asyncio.sleep(self.message_delay)
            
            # Rate-limiting zwischen Anzeigen
            if ad != ads[-1]:  # Nicht nach der letzten Anzeige
                await asyncio.sleep(self.message_delay)
        
        logger.info(f"Telegram-Benachrichtigungen gesendet: {total_sent} Nachrichten ({len(ads)} Anzeigen × {len(self.chat_ids)} Chat-IDs)")
        return total_sent
    
    async def _send_ad_to_chat(self, bot: Bot, ad: Dict, chat_id: str, max_retries: int = 3) -> int:
        """
        Sendet eine einzelne Anzeige an eine Chat-ID mit Retry-Logik.
        
        Args:
            bot: Telegram Bot-Objekt
            ad: Anzeigen-Dictionary
            chat_id: Chat-ID zum Senden
            max_retries: Maximale Anzahl Wiederholungsversuche
            
        Returns:
            1 wenn erfolgreich, 0 wenn fehlgeschlagen
        """
        retry_count = 0
        success = False
        
        while retry_count <= max_retries and not success:
            try:
                message = self._format_ad_message(ad)
                
                await bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode="Markdown",
                    disable_web_page_preview=False
                )
                
                success = True
                logger.info(f"Telegram-Nachricht gesendet an {chat_id}: {ad.get('title', 'Unbekannt')[:50]}...")
                
            except TelegramError as e:
                error_msg = str(e).lower()
                # Rate Limiting: Warte länger bei 429 Fehlern und versuche erneut
                if "429" in error_msg or "rate limit" in error_msg or "too many requests" in error_msg:
                    retry_count += 1
                    if retry_count <= max_retries:
                        wait_time = 60 * retry_count  # Exponentielles Backoff: 60s, 120s, 180s
                        logger.warning(f"Telegram Rate Limit erreicht (Chat-ID: {chat_id}). Warte {wait_time} Sekunden und versuche erneut ({retry_count}/{max_retries})...")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"Telegram Rate Limit: Nach {max_retries} Versuchen aufgegeben für Chat-ID {chat_id}: {ad.get('title', 'Unbekannt')[:50]}...")
                        break
                else:
                    # Andere Telegram-Fehler: Versuche mit normalem Retry
                    retry_count += 1
                    if retry_count <= max_retries:
                        wait_time = 2 * retry_count  # Kurzes Backoff: 2s, 4s, 6s
                        logger.warning(f"Telegram-Fehler (Chat-ID: {chat_id}), Wiederholung {retry_count}/{max_retries} nach {wait_time}s: {e}")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"Telegram-Fehler nach {max_retries} Versuchen (Chat-ID: {chat_id}): {e}")
                        break
                        
            except Exception as e:
                logger.error(f"Unerwarteter Fehler beim Senden der Telegram-Nachricht (Chat-ID: {chat_id}): {e}")
                break
        
        return 1 if success else 0
    
    async def send_test_message(self) -> bool:
        """
        Sendet eine Test-Nachricht an alle konfigurierten Chat-IDs.
        
        Returns:
            True wenn mindestens eine Nachricht erfolgreich gesendet wurde, False sonst
        """
        if not self.chat_ids:
            logger.error("Keine chat_ids konfiguriert.")
            return False
        
        try:
            bot = await self._get_bot()
            success_count = 0
            
            for chat_id in self.chat_ids:
                try:
                    await bot.send_message(
                        chat_id=chat_id,
                        text="✅ *Kleinanzeigen-Bot Test*\n\nDer Bot funktioniert korrekt!",
                        parse_mode="Markdown"
                    )
                    logger.info(f"Test-Nachricht erfolgreich gesendet an Chat-ID: {chat_id}")
                    success_count += 1
                except TelegramError as e:
                    logger.error(f"Fehler beim Senden der Test-Nachricht an Chat-ID {chat_id}: {e}")
                except Exception as e:
                    logger.error(f"Unerwarteter Fehler beim Senden an Chat-ID {chat_id}: {e}")
            
            return success_count > 0
        except Exception as e:
            logger.error(f"Unerwarteter Fehler: {e}")
            return False


