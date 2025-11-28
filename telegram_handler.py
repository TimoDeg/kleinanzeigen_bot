"""
Telegram Bot Command Handler mit sauberem UI.
Handhabt alle Nutzer-Interaktionen über Telegram.
"""

import logging
from typing import Dict, Optional, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

logger = logging.getLogger(__name__)

# Conversation States
(
    SELECT_ACTION,
    INPUT_KEYWORD,
    INPUT_PRICE_MIN,
    INPUT_PRICE_MAX,
    INPUT_INTERVAL,
    INPUT_SHIPPING,
    SELECT_SEARCH,
    EDIT_SELECT_FIELD,
    EDIT_INPUT_VALUE,
) = range(9)


class TelegramHandler:
    """Handhabt Telegram Bot Commands und Conversations."""

    def __init__(self, database, allowed_chat_ids: List[str]) -> None:
        """
        Initialisiert den Telegram Handler.

        Args:
            database: Database Instance
            allowed_chat_ids: Liste erlaubter Telegram Chat-IDs
        """
        self.db = database
        self.allowed_chat_ids = [str(cid) for cid in allowed_chat_ids]

        # Registriere erlaubte User in DB
        for chat_id in self.allowed_chat_ids:
            self.db.add_user(chat_id)

    def is_authorized(self, chat_id: str) -> bool:
        """Prüft ob User autorisiert ist."""
        return str(chat_id) in self.allowed_chat_ids

    async def unauthorized_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handler für unautorisierte Zugriffe."""
        if update.message:
            await update.message.reply_text(
                "❌ *Nicht autorisiert*\n\n"
                "Du hast keinen Zugriff auf diesen Bot.",
                parse_mode="Markdown",
            )

    # ============================================================
    # MAIN MENU
    # ============================================================

    async def start_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        /start - Zeigt Hauptmenü mit allen Optionen.
        """
        if not self.is_authorized(str(update.effective_chat.id)):
            await self.unauthorized_handler(update, context)
            return

        keyboard = [
            [
                InlineKeyboardButton("➕ Neue Suche", callback_data="menu_add"),
                InlineKeyboardButton("📋 Meine Suchen", callback_data="menu_list"),
            ],
            [
                InlineKeyboardButton("📊 Statistiken", callback_data="menu_stats"),
                InlineKeyboardButton("ℹ️ Hilfe", callback_data="menu_help"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        welcome_text = (
            "🤖 *Kleinanzeigen Bot*\n\n"
            "Verwalte deine Suchen und erhalte Benachrichtigungen "
            "bei neuen Anzeigen.\n\n"
            "Was möchtest du tun?"
        )

        if update.message:
            await update.message.reply_text(
                welcome_text,
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )
        elif update.callback_query:
            await update.callback_query.edit_message_text(
                welcome_text,
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )

    # ============================================================
    # LIST SEARCHES
    # ============================================================

    async def list_searches(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Zeigt alle Suchen des Users mit Management-Optionen."""
        query = update.callback_query
        await query.answer()

        chat_id = str(update.effective_chat.id)
        searches = self.db.get_user_searches(chat_id)

        if not searches:
            keyboard = [
                [InlineKeyboardButton("➕ Erste Suche erstellen", callback_data="menu_add")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "📋 *Meine Suchen*\n\n"
                "Du hast noch keine Suchen erstellt.",
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )
            return

        text = "📋 *Meine Suchen*\n\n"
        keyboard: List[List[InlineKeyboardButton]] = []

        for idx, search in enumerate(searches, 1):
            status_icon = "✅" if search["active"] else "⏸️"
            price_range = ""
            if search["price_min"] and search["price_max"]:
                price_range = f" ({search['price_min']}-{search['price_max']}€)"
            elif search["price_min"]:
                price_range = f" (ab {search['price_min']}€)"
            elif search["price_max"]:
                price_range = f" (bis {search['price_max']}€)"

            interval_min = search["interval_seconds"] // 60

            text += (
                f"{status_icon} *{idx}. {search['keyword']}*{price_range}\n"
                f"   ⏱ Alle {interval_min} Min  |  🚚 {search['shipping_preference']}\n\n"
            )

            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{status_icon} {search['keyword'][:20]}",
                        callback_data=f"search_manage_{search['search_id']}",
                    )
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton("➕ Neue Suche", callback_data="menu_add"),
                InlineKeyboardButton("🔙 Zurück", callback_data="menu_back"),
            ]
        )

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    # ============================================================
    # MANAGE SINGLE SEARCH
    # ============================================================

    async def manage_search(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Detail-Ansicht und Management für einzelne Suche."""
        query = update.callback_query
        await query.answer()

        search_id = int(query.data.split("_")[-1])
        chat_id = str(update.effective_chat.id)

        searches = self.db.get_user_searches(chat_id)
        search = next((s for s in searches if s["search_id"] == search_id), None)

        if not search:
            await query.edit_message_text("❌ Suche nicht gefunden.")
            return

        status = "✅ Aktiv" if search["active"] else "⏸️ Pausiert"
        price_info = "Keine Einschränkung"
        if search["price_min"] and search["price_max"]:
            price_info = f"{search['price_min']} - {search['price_max']}€"
        elif search["price_min"]:
            price_info = f"Ab {search['price_min']}€"
        elif search["price_max"]:
            price_info = f"Bis {search['price_max']}€"

        interval_min = search["interval_seconds"] // 60

        shipping_map = {
            "both": "Abholung & Versand",
            "pickup": "Nur Abholung",
            "shipping": "Nur Versand",
        }
        shipping_pref = shipping_map.get(search["shipping_preference"], "Egal")

        text = (
            f"🔍 *{search['keyword']}*\n\n"
            f"📊 *Status:* {status}\n"
            f"💶 *Preis:* {price_info}\n"
            f"⏱ *Intervall:* Alle {interval_min} Minuten\n"
            f"🚚 *Versand:* {shipping_pref}\n"
        )

        keyboard: List[List[InlineKeyboardButton]] = []

        if search["active"]:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "⏸️ Pausieren", callback_data=f"search_pause_{search_id}"
                    )
                ]
            )
        else:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "▶️ Fortsetzen", callback_data=f"search_resume_{search_id}"
                    )
                ]
            )

        keyboard.extend(
            [
                [
                    InlineKeyboardButton(
                        "✏️ Bearbeiten", callback_data=f"search_edit_{search_id}"
                    ),
                    InlineKeyboardButton(
                        "🗑️ Löschen", callback_data=f"search_delete_{search_id}"
                    ),
                ],
                [InlineKeyboardButton("🔙 Zurück", callback_data="menu_list")],
            ]
        )

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    # ============================================================
    # PAUSE / RESUME / DELETE
    # ============================================================

    async def pause_search(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Pausiert eine Suche."""
        query = update.callback_query
        await query.answer()

        search_id = int(query.data.split("_")[-1])
        chat_id = str(update.effective_chat.id)

        success = self.db.pause_search(search_id, chat_id)

        if success:
            await query.answer("⏸️ Suche pausiert", show_alert=True)
            query.data = f"search_manage_{search_id}"
            await self.manage_search(update, context)
        else:
            await query.answer("❌ Fehler beim Pausieren", show_alert=True)

    async def resume_search(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Aktiviert eine pausierte Suche."""
        query = update.callback_query
        await query.answer()

        search_id = int(query.data.split("_")[-1])
        chat_id = str(update.effective_chat.id)

        success = self.db.resume_search(search_id, chat_id)

        if success:
            await query.answer("▶️ Suche fortgesetzt", show_alert=True)
            query.data = f"search_manage_{search_id}"
            await self.manage_search(update, context)
        else:
            await query.answer("❌ Fehler beim Fortsetzen", show_alert=True)

    async def delete_search_confirm(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Bestätigungs-Dialog für Löschen."""
        query = update.callback_query
        await query.answer()

        search_id = int(query.data.split("_")[-1])

        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Ja, löschen",
                    callback_data=f"search_delete_confirm_{search_id}",
                ),
                InlineKeyboardButton(
                    "❌ Abbrechen", callback_data=f"search_manage_{search_id}"
                ),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "🗑️ *Suche wirklich löschen?*\n\n"
            "Alle zugehörigen Anzeigen werden ebenfalls gelöscht.",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    async def delete_search_execute(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Führt Löschen aus."""
        query = update.callback_query
        await query.answer()

        search_id = int(query.data.split("_")[-1])
        chat_id = str(update.effective_chat.id)

        success = self.db.delete_search(search_id, chat_id)

        if success:
            await query.answer("🗑️ Suche gelöscht", show_alert=True)
            query.data = "menu_list"
            await self.list_searches(update, context)
        else:
            await query.answer("❌ Fehler beim Löschen", show_alert=True)

    # ============================================================
    # ADD NEW SEARCH (Conversation)
    # ============================================================

    async def add_search_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Startet Conversation für neue Suche."""
        query = update.callback_query
        if query:
            await query.answer()
            await query.edit_message_text(
                "➕ *Neue Suche erstellen*\n\n"
                "Nach welchem Produkt suchst du?\n"
                "(z.B. 'DDR5 RAM', 'RTX 4070', 'iPhone 15')",
                parse_mode="Markdown",
            )

        return INPUT_KEYWORD

    async def add_search_keyword(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Speichert Keyword und fragt nach Preis-Min."""
        keyword = update.message.text.strip()
        context.user_data["new_search_keyword"] = keyword

        await update.message.reply_text(
            f"✅ Suche nach: *{keyword}*\n\n"
            "💶 Minimaler Preis? (oder 'skip' für keine Einschränkung)",
            parse_mode="Markdown",
        )

        return INPUT_PRICE_MIN

    async def add_search_price_min(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Speichert Price-Min und fragt nach Price-Max."""
        text = update.message.text.strip().lower()

        if text != "skip":
            try:
                price_min = float(text)
                context.user_data["new_search_price_min"] = price_min
            except ValueError:
                await update.message.reply_text(
                    "❌ Ungültige Zahl. Versuche nochmal oder 'skip':"
                )
                return INPUT_PRICE_MIN
        else:
            context.user_data["new_search_price_min"] = None

        await update.message.reply_text(
            "💶 Maximaler Preis? (oder 'skip')",
            parse_mode="Markdown",
        )

        return INPUT_PRICE_MAX

    async def add_search_price_max(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Speichert Price-Max und fragt nach Intervall."""
        text = update.message.text.strip().lower()

        if text != "skip":
            try:
                price_max = float(text)
                context.user_data["new_search_price_max"] = price_max
            except ValueError:
                await update.message.reply_text(
                    "❌ Ungültige Zahl. Versuche nochmal oder 'skip':"
                )
                return INPUT_PRICE_MAX
        else:
            context.user_data["new_search_price_max"] = None

        await update.message.reply_text(
            "⏱ Update-Intervall in Minuten?\n"
            "(Standard: 5, empfohlen: 5-30)",
            parse_mode="Markdown",
        )

        return INPUT_INTERVAL

    async def add_search_interval(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Speichert Intervall und fragt nach Shipping."""
        text = update.message.text.strip()

        try:
            interval_min = int(text)
            if interval_min < 1:
                raise ValueError
            context.user_data["new_search_interval"] = interval_min * 60
        except ValueError:
            await update.message.reply_text(
                "❌ Ungültige Zahl (min. 1). Versuche nochmal:"
            )
            return INPUT_INTERVAL

        keyboard = [
            [InlineKeyboardButton("📦 Egal", callback_data="shipping_both")],
            [InlineKeyboardButton("🚚 Nur Versand", callback_data="shipping_shipping")],
            [InlineKeyboardButton("🏠 Nur Abholung", callback_data="shipping_pickup")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "🚚 Versand-Präferenz?",
            reply_markup=reply_markup,
        )

        return INPUT_SHIPPING

    async def add_search_shipping(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Speichert Shipping und erstellt Suche."""
        query = update.callback_query
        await query.answer()

        shipping_map = {
            "shipping_both": "both",
            "shipping_shipping": "shipping",
            "shipping_pickup": "pickup",
        }

        shipping_pref = shipping_map.get(query.data, "both")

        chat_id = str(update.effective_chat.id)

        try:
            search_id = self.db.add_search(
                user_id=chat_id,
                keyword=context.user_data["new_search_keyword"],
                price_min=context.user_data.get("new_search_price_min"),
                price_max=context.user_data.get("new_search_price_max"),
                interval_seconds=context.user_data.get("new_search_interval", 300),
                shipping_preference=shipping_pref,
            )

            keyword = context.user_data["new_search_keyword"]
            price_min = context.user_data.get("new_search_price_min")
            price_max = context.user_data.get("new_search_price_max")
            interval_min = context.user_data.get("new_search_interval", 300) // 60

            price_text = "Keine Einschränkung"
            if price_min and price_max:
                price_text = f"{price_min} - {price_max}€"
            elif price_min:
                price_text = f"Ab {price_min}€"
            elif price_max:
                price_text = f"Bis {price_max}€"

            shipping_names = {
                "both": "Egal",
                "shipping": "Nur Versand",
                "pickup": "Nur Abholung",
            }

            await query.edit_message_text(
                "✅ *Suche erstellt!*\n\n"
                f"🔍 *Keyword:* {keyword}\n"
                f"💶 *Preis:* {price_text}\n"
                f"⏱ *Intervall:* Alle {interval_min} Min\n"
                f"🚚 *Versand:* {shipping_names[shipping_pref]}\n\n"
                "Du erhältst ab jetzt Benachrichtigungen bei neuen Anzeigen!",
                parse_mode="Markdown",
            )

            context.user_data.clear()
            logger.info(f"Neue Suche erstellt (ID: {search_id}) für User {chat_id}")

        except Exception as e:  # pragma: no cover - Netz/DB Fehler
            logger.error(f"Fehler beim Erstellen der Suche: {e}")
            await query.edit_message_text(
                "❌ Fehler beim Erstellen der Suche. Bitte versuche es später nochmal."
            )

        return ConversationHandler.END

    async def cancel_conversation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Bricht Conversation ab."""
        if update.message:
            await update.message.reply_text(
                "❌ Abgebrochen.",
                parse_mode="Markdown",
            )
        context.user_data.clear()
        return ConversationHandler.END

    # ============================================================
    # STATS
    # ============================================================

    async def show_stats(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Zeigt Statistiken."""
        query = update.callback_query
        await query.answer()

        chat_id = str(update.effective_chat.id)

        searches = self.db.get_user_searches(chat_id)
        active_count = sum(1 for s in searches if s["active"])

        db_stats = self.db.get_stats(days=1)

        text = (
            "📊 *Statistiken*\n\n"
            f"🔍 *Deine Suchen:*\n"
            f"   • Gesamt: {len(searches)}\n"
            f"   • Aktiv: {active_count}\n"
            f"   • Pausiert: {len(searches) - active_count}\n\n"
            f"📦 *Datenbank:*\n"
            f"   • Gesamt: {db_stats['total']} Anzeigen\n"
            f"   • Letzte 24h: {db_stats['last_1_days']} Anzeigen\n"
        )

        keyboard = [[InlineKeyboardButton("🔙 Zurück", callback_data="menu_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    # ============================================================
    # HELP
    # ============================================================

    async def show_help(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Zeigt Hilfe."""
        query = update.callback_query
        await query.answer()

        text = (
            "ℹ️ *Hilfe*\n\n"
            "*Befehle:*\n"
            "/start - Hauptmenü\n"
            "/list - Meine Suchen\n"
            "/add - Neue Suche\n"
            "/stats - Statistiken\n\n"
            "*Features:*\n"
            "• Automatische Benachrichtigung bei neuen Anzeigen\n"
            "• Preis-Filter und Versand-Präferenz\n"
            "• Individuelle Update-Intervalle\n"
            "• Geizhals-Preisvergleich (optional)\n\n"
            "*Tipps:*\n"
            "• Verwende spezifische Keywords für bessere Ergebnisse\n"
            "• Setze realistische Preis-Spannen\n"
            "• Intervall nicht zu kurz (min. 5 Min empfohlen)\n"
        )

        keyboard = [[InlineKeyboardButton("🔙 Zurück", callback_data="menu_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    # ============================================================
    # ROUTER
    # ============================================================

    def get_handlers(self) -> List:
        """
        Gibt alle Handler für Application zurück.

        Returns:
            Liste von Handlers
        """
        add_search_conv = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.add_search_start, pattern="^menu_add$")
            ],
            states={
                INPUT_KEYWORD: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_search_keyword)
                ],
                INPUT_PRICE_MIN: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND, self.add_search_price_min
                    )
                ],
                INPUT_PRICE_MAX: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND, self.add_search_price_max
                    )
                ],
                INPUT_INTERVAL: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND, self.add_search_interval
                    )
                ],
                INPUT_SHIPPING: [
                    CallbackQueryHandler(
                        self.add_search_shipping, pattern="^shipping_"
                    )
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_conversation)],
            allow_reentry=True,
        )

        return [
            CommandHandler("start", self.start_command),
            add_search_conv,
            CallbackQueryHandler(self.start_command, pattern="^menu_back$"),
            CallbackQueryHandler(self.list_searches, pattern="^menu_list$"),
            CallbackQueryHandler(self.manage_search, pattern="^search_manage_"),
            CallbackQueryHandler(self.pause_search, pattern="^search_pause_"),
            CallbackQueryHandler(self.resume_search, pattern="^search_resume_"),
            CallbackQueryHandler(
                self.delete_search_confirm, pattern="^search_delete_[0-9]+$"
            ),
            CallbackQueryHandler(
                self.delete_search_execute, pattern="^search_delete_confirm_"
            ),
            CallbackQueryHandler(self.show_stats, pattern="^menu_stats$"),
            CallbackQueryHandler(self.show_help, pattern="^menu_help$"),
        ]


