"""
Datenbank-Management für den Kleinanzeigen-Bot.
Verwendet SQLite zur Persistierung (Multi-Search fähig).
"""

import json
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

# SQLite Schema für Multi-Search-System
DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    telegram_username TEXT,
    allowed BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS searches (
    search_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    keyword TEXT NOT NULL,
    category TEXT DEFAULT 'c225',
    price_min REAL,
    price_max REAL,
    interval_seconds INTEGER DEFAULT 300,
    shipping_preference TEXT DEFAULT 'both',
    exclude_keywords TEXT,
    active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_check TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS seen_ads (
    ad_id TEXT PRIMARY KEY,
    search_id INTEGER,
    title TEXT NOT NULL,
    price REAL,
    link TEXT,
    location TEXT,
    shipping_type TEXT,
    posted_time TEXT,
    ocr_article_nr TEXT,
    ocr_confidence REAL,
    geizhals_price REAL,
    geizhals_article_nr TEXT,
    geizhals_model TEXT,
    geizhals_link TEXT,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (search_id) REFERENCES searches(search_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_searches_user ON searches(user_id);
CREATE INDEX IF NOT EXISTS idx_searches_active ON searches(active);
CREATE INDEX IF NOT EXISTS idx_seen_ads_search ON seen_ads(search_id);
CREATE INDEX IF NOT EXISTS idx_fetched_at ON seen_ads(fetched_at);
"""


class Database:
    """Verwaltet die SQLite-Datenbank für gesehene Anzeigen."""
    
    def __init__(self, db_path: str):
        """
        Initialisiert die Datenbankverbindung.
        
        Args:
            db_path: Pfad zur SQLite-Datenbankdatei
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """
        Erstellt eine neue Datenbankverbindung.
        
        Returns:
            SQLite-Verbindungsobjekt
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self) -> None:
        """Initialisiert die Datenbank und erstellt Tabellen falls nötig."""
        try:
            with self._get_connection() as conn:
                conn.executescript(DB_SCHEMA)
                conn.commit()
            logger.info(f"Datenbank initialisiert: {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Fehler beim Initialisieren der Datenbank: {e}")
            raise
    
    def is_new_ad(self, ad_id: str) -> bool:
        """
        Prüft, ob eine Anzeige bereits gesehen wurde.
        
        Args:
            ad_id: Eindeutige ID der Anzeige
            
        Returns:
            True wenn die Anzeige neu ist, False wenn bereits gesehen
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM seen_ads WHERE ad_id = ?",
                    (ad_id,)
                )
                return cursor.fetchone() is None
        except sqlite3.Error as e:
            logger.error(f"Fehler beim Prüfen der Anzeige {ad_id}: {e}")
            # Bei Fehler als neu behandeln, um keine Anzeigen zu verpassen
            return True
    
    def mark_as_seen(self, ad_id: str, title: str, price: Optional[float] = None, 
                     link: Optional[str] = None, location: Optional[str] = None, 
                     posted_time: Optional[str] = None) -> None:
        """
        Markiert eine Anzeige als gesehen.
        
        Args:
            ad_id: Eindeutige ID der Anzeige
            title: Titel der Anzeige
            price: Optionaler Preis der Anzeige
            link: Optionaler Link zur Anzeige
            location: Optionaler Ort
            posted_time: Optionaler Zeitpunkt
        """
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO seen_ads 
                       (ad_id, title, price, link, location, posted_time, fetched_at) 
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (ad_id, title, price, link, location, posted_time, datetime.now())
                )
                conn.commit()
            logger.debug(f"Anzeige als gesehen markiert: {ad_id}")
        except sqlite3.Error as e:
            logger.error(f"Fehler beim Markieren der Anzeige {ad_id}: {e}")
    
    def get_last_ads(self, limit: int = 2) -> List[Dict]:
        """
        Gibt die letzten N Anzeigen zurück (chronologisch sortiert: ältere zuerst).
        
        Args:
            limit: Anzahl der zurückzugebenden Anzeigen (max 100)
            
        Returns:
            Liste von Anzeigen-Dictionaries (chronologisch sortiert: ältere zuerst)
        """
        # Begrenze Limit auf sinnvollen Wert
        limit = min(max(1, limit), 100)
        
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """SELECT ad_id, title, price, link, location, posted_time, fetched_at 
                       FROM seen_ads 
                       ORDER BY fetched_at ASC 
                       LIMIT ?""",
                    (limit,)
                )
                rows = cursor.fetchall()
                ads = []
                for row in rows:
                    ads.append({
                        "id": row["ad_id"],
                        "title": row["title"] or "",
                        "price": row["price"],
                        "link": row["link"] or "",
                        "location": row["location"] or "",
                        "posted_time": row["posted_time"] or ""
                    })
                return ads
        except sqlite3.Error as e:
            logger.error(f"Fehler beim Abrufen der letzten Anzeigen: {e}", exc_info=True)
            return []
    
    def get_newest_ads(self, limit: int = 5) -> List[Dict]:
        """
        Gibt die neuesten N Anzeigen zurück (sortiert: neueste zuerst).
        
        Args:
            limit: Anzahl der zurückzugebenden Anzeigen (max 100)
            
        Returns:
            Liste von Anzeigen-Dictionaries (sortiert nach fetched_at DESC, neueste zuerst)
        """
        # Begrenze Limit auf sinnvollen Wert
        limit = min(max(1, limit), 100)
        
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """SELECT ad_id, title, price, link, location, posted_time, fetched_at 
                       FROM seen_ads 
                       ORDER BY fetched_at DESC 
                       LIMIT ?""",
                    (limit,)
                )
                rows = cursor.fetchall()
                ads = []
                for row in rows:
                    ads.append({
                        "id": row["ad_id"],
                        "title": row["title"] or "",
                        "price": row["price"],
                        "link": row["link"] or "",
                        "location": row["location"] or "",
                        "posted_time": row["posted_time"] or ""
                    })
                return ads
        except sqlite3.Error as e:
            logger.error(f"Fehler beim Abrufen der neuesten Anzeigen: {e}", exc_info=True)
            return []
    
    def cleanup_old_entries(self, days: int = 30) -> int:
        """
        Löscht alte Einträge aus der Datenbank.
        
        Args:
            days: Anzahl der Tage, ab denen Einträge als alt gelten
            
        Returns:
            Anzahl der gelöschten Einträge
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM seen_ads WHERE fetched_at < ?",
                    (cutoff_date,)
                )
                deleted_count = cursor.rowcount
                conn.commit()
            if deleted_count > 0:
                logger.info(f"Alte Einträge gelöscht: {deleted_count} (älter als {days} Tage)")
            return deleted_count
        except sqlite3.Error as e:
            logger.error(f"Fehler beim Aufräumen der Datenbank: {e}")
            return 0
    
    def clear_all(self) -> int:
        """
        Löscht alle Einträge aus der Datenbank.
        
        Returns:
            Anzahl der gelöschten Einträge
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("DELETE FROM seen_ads")
                deleted_count = cursor.rowcount
                conn.commit()
            logger.info(f"Alle Einträge gelöscht: {deleted_count}")
            return deleted_count
        except sqlite3.Error as e:
            logger.error(f"Fehler beim Löschen aller Einträge: {e}")
            return 0
    
    def get_stats(self, days: int = 1) -> dict:
        """
        Gibt Statistiken über die Datenbank zurück.
        
        Args:
            days: Anzahl der Tage für die Statistik
            
        Returns:
            Dictionary mit Statistiken
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            with self._get_connection() as conn:
                total = conn.execute("SELECT COUNT(*) FROM seen_ads").fetchone()[0]
                recent = conn.execute(
                    "SELECT COUNT(*) FROM seen_ads WHERE fetched_at >= ?",
                    (cutoff_date,)
                ).fetchone()[0]
            return {
                "total": total,
                f"last_{days}_days": recent
            }
        except sqlite3.Error as e:
            logger.error(f"Fehler beim Abrufen der Statistiken: {e}")
            return {"total": 0, f"last_{days}_days": 0}


    # ============================================================
    # NEUE METHODS FÜR MULTI-SEARCH SYSTEM
    # ============================================================

    def add_user(self, user_id: str, username: str = None) -> None:
        """
        Fügt neuen User hinzu oder updated bestehenden.

        Args:
            user_id: Telegram Chat-ID
            username: Optional Telegram Username
        """
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO users (user_id, telegram_username, allowed) 
                       VALUES (?, ?, 1)""",
                    (user_id, username),
                )
                conn.commit()
            logger.debug(f"User hinzugefügt/updated: {user_id}")
        except sqlite3.Error as e:
            logger.error(f"Fehler beim Hinzufügen des Users {user_id}: {e}")

    def is_user_allowed(self, user_id: str) -> bool:
        """
        Prüft ob User autorisiert ist.

        Args:
            user_id: Telegram Chat-ID

        Returns:
            True wenn erlaubt, False sonst
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT allowed FROM users WHERE user_id = ?",
                    (user_id,),
                )
                result = cursor.fetchone()
                return bool(result[0]) if result else False
        except sqlite3.Error as e:
            logger.error(f"Fehler beim Prüfen des Users {user_id}: {e}")
            return False

    def add_search(
        self,
        user_id: str,
        keyword: str,
        price_min: Optional[float] = None,
        price_max: Optional[float] = None,
        interval_seconds: int = 300,
        category: str = "c225",
        shipping_preference: str = "both",
        exclude_keywords: Optional[List[str]] = None,
    ) -> int:
        """
        Fügt neue Suche hinzu.

        Args:
            user_id: Telegram Chat-ID
            keyword: Suchbegriff
            price_min: Min-Preis (optional)
            price_max: Max-Preis (optional)
            interval_seconds: Update-Intervall
            category: Kleinanzeigen Kategorie
            shipping_preference: "both", "pickup", "shipping"
            exclude_keywords: Liste von Ausschluss-Keywords

        Returns:
            search_id der neuen Suche
        """
        try:
            exclude_json = (
                json.dumps(exclude_keywords) if exclude_keywords else None
            )

            with self._get_connection() as conn:
                cursor = conn.execute(
                    """INSERT INTO searches 
                       (user_id, keyword, price_min, price_max, interval_seconds, 
                        category, shipping_preference, exclude_keywords)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        user_id,
                        keyword,
                        price_min,
                        price_max,
                        interval_seconds,
                        category,
                        shipping_preference,
                        exclude_json,
                    ),
                )
                search_id = cursor.lastrowid
                conn.commit()

            logger.info(f"Suche erstellt: '{keyword}' (ID: {search_id})")
            return search_id

        except sqlite3.Error as e:
            logger.error(f"Fehler beim Erstellen der Suche: {e}")
            raise

    def get_active_searches(self) -> List[Dict]:
        """
        Gibt alle aktiven Suchen zurück.

        Returns:
            Liste von Search-Dictionaries
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """SELECT search_id, user_id, keyword, category, price_min, price_max,
                              interval_seconds, shipping_preference, exclude_keywords,
                              last_check, created_at
                       FROM searches 
                       WHERE active = 1
                       ORDER BY search_id"""
                )

                searches: List[Dict] = []
                for row in cursor.fetchall():
                    exclude_keywords = (
                        json.loads(row["exclude_keywords"])
                        if row["exclude_keywords"]
                        else []
                    )

                    searches.append(
                        {
                            "search_id": row["search_id"],
                            "user_id": row["user_id"],
                            "keyword": row["keyword"],
                            "category": row["category"],
                            "price_min": row["price_min"],
                            "price_max": row["price_max"],
                            "interval_seconds": row["interval_seconds"],
                            "shipping_preference": row["shipping_preference"],
                            "exclude_keywords": exclude_keywords,
                            "last_check": row["last_check"],
                            "created_at": row["created_at"],
                        }
                    )

                return searches

        except sqlite3.Error as e:
            logger.error(f"Fehler beim Abrufen aktiver Suchen: {e}")
            return []

    def get_user_searches(self, user_id: str) -> List[Dict]:
        """
        Gibt alle Suchen eines Users zurück.

        Args:
            user_id: Telegram Chat-ID

        Returns:
            Liste von Search-Dictionaries
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """SELECT search_id, keyword, price_min, price_max, interval_seconds,
                              shipping_preference, active, last_check, created_at
                       FROM searches 
                       WHERE user_id = ?
                       ORDER BY created_at DESC""",
                    (user_id,),
                )

                searches: List[Dict] = []
                for row in cursor.fetchall():
                    searches.append(
                        {
                            "search_id": row["search_id"],
                            "keyword": row["keyword"],
                            "price_min": row["price_min"],
                            "price_max": row["price_max"],
                            "interval_seconds": row["interval_seconds"],
                            "shipping_preference": row["shipping_preference"],
                            "active": bool(row["active"]),
                            "last_check": row["last_check"],
                            "created_at": row["created_at"],
                        }
                    )

                return searches

        except sqlite3.Error as e:
            logger.error(f"Fehler beim Abrufen der User-Suchen: {e}")
            return []

    def update_search_last_check(self, search_id: int) -> None:
        """
        Updated last_check Timestamp einer Suche.

        Args:
            search_id: ID der Suche
        """
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE searches SET last_check = ? WHERE search_id = ?",
                    (datetime.now(), search_id),
                )
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Fehler beim Update von last_check: {e}")

    def pause_search(self, search_id: int, user_id: str) -> bool:
        """
        Pausiert eine Suche.

        Args:
            search_id: ID der Suche
            user_id: User-ID (für Ownership-Check)

        Returns:
            True bei Erfolg, False bei Fehler
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "UPDATE searches SET active = 0 WHERE search_id = ? AND user_id = ?",
                    (search_id, user_id),
                )
                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"Suche {search_id} pausiert")
                    return True
                logger.warning(
                    f"Suche {search_id} nicht gefunden oder falscher User ({user_id})"
                )
                return False

        except sqlite3.Error as e:
            logger.error(f"Fehler beim Pausieren der Suche: {e}")
            return False

    def resume_search(self, search_id: int, user_id: str) -> bool:
        """
        Aktiviert eine pausierte Suche.

        Args:
            search_id: ID der Suche
            user_id: User-ID (für Ownership-Check)

        Returns:
            True bei Erfolg, False bei Fehler
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "UPDATE searches SET active = 1 WHERE search_id = ? AND user_id = ?",
                    (search_id, user_id),
                )
                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"Suche {search_id} fortgesetzt")
                    return True
                return False

        except sqlite3.Error as e:
            logger.error(f"Fehler beim Fortsetzen der Suche: {e}")
            return False

    def delete_search(self, search_id: int, user_id: str) -> bool:
        """
        Löscht eine Suche und alle zugehörigen Anzeigen.

        Args:
            search_id: ID der Suche
            user_id: User-ID (für Ownership-Check)

        Returns:
            True bei Erfolg, False bei Fehler
        """
        try:
            with self._get_connection() as conn:
                # Lösche zugehörige Anzeigen
                conn.execute(
                    "DELETE FROM seen_ads WHERE search_id = ?",
                    (search_id,),
                )

                # Lösche Suche (nur wenn User = Owner)
                cursor = conn.execute(
                    "DELETE FROM searches WHERE search_id = ? AND user_id = ?",
                    (search_id, user_id),
                )
                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"Suche {search_id} gelöscht")
                    return True
                return False

        except sqlite3.Error as e:
            logger.error(f"Fehler beim Löschen der Suche: {e}")
            return False

    def update_search(
        self,
        search_id: int,
        user_id: str,
        **kwargs,
    ) -> bool:
        """
        Updated eine Suche mit neuen Werten.

        Args:
            search_id: ID der Suche
            user_id: User-ID (für Ownership-Check)
            **kwargs: Zu updatende Felder (keyword, price_min, price_max, etc.)

        Returns:
            True bei Erfolg, False bei Fehler
        """
        try:
            # Baue UPDATE Query dynamisch
            allowed_fields = [
                "keyword",
                "price_min",
                "price_max",
                "interval_seconds",
                "shipping_preference",
                "exclude_keywords",
            ]

            updates: List[str] = []
            values: List[object] = []

            for field, value in kwargs.items():
                if field in allowed_fields:
                    updates.append(f"{field} = ?")
                    if field == "exclude_keywords" and isinstance(value, list):
                        values.append(json.dumps(value))
                    else:
                        values.append(value)

            if not updates:
                return False

            query = (
                f"UPDATE searches SET {', '.join(updates)} "
                "WHERE search_id = ? AND user_id = ?"
            )
            values.extend([search_id, user_id])

            with self._get_connection() as conn:
                cursor = conn.execute(query, values)
                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"Suche {search_id} updated")
                    return True
                return False

        except sqlite3.Error as e:
            logger.error(f"Fehler beim Update der Suche: {e}")
            return False

    def mark_as_seen_with_search(
        self,
        ad_id: str,
        search_id: int,
        title: str,
        price: Optional[float] = None,
        link: Optional[str] = None,
        location: Optional[str] = None,
        shipping_type: Optional[str] = None,
        posted_time: Optional[str] = None,
        ocr_article_nr: Optional[str] = None,
        geizhals_data: Optional[Dict] = None,
    ) -> None:
        """
        Erweiterte Version von mark_as_seen mit allen neuen Feldern.

        Args:
            ad_id: Eindeutige ID der Anzeige
            search_id: ID der zugehörigen Suche
            title: Titel der Anzeige
            price: Preis
            link: Link zur Anzeige
            location: Standort
            shipping_type: "Abholung", "Versand", oder kombiniert
            posted_time: Zeitpunkt der Veröffentlichung
            ocr_article_nr: Per OCR erkannte Artikel-Nummer
            geizhals_data: Dict mit {price, article_nr, model, link}
        """
        try:
            geizhals_price = None
            geizhals_article_nr = None
            geizhals_model = None
            geizhals_link = None

            if geizhals_data:
                geizhals_price = geizhals_data.get("price")
                geizhals_article_nr = geizhals_data.get("article_nr")
                geizhals_model = geizhals_data.get("model")
                geizhals_link = geizhals_data.get("link")

            with self._get_connection() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO seen_ads 
                       (ad_id, search_id, title, price, link, location, shipping_type,
                        posted_time, ocr_article_nr, geizhals_price, geizhals_article_nr,
                        geizhals_model, geizhals_link, fetched_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        ad_id,
                        search_id,
                        title,
                        price,
                        link,
                        location,
                        shipping_type,
                        posted_time,
                        ocr_article_nr,
                        geizhals_price,
                        geizhals_article_nr,
                        geizhals_model,
                        geizhals_link,
                        datetime.now(),
                    ),
                )
                conn.commit()
            logger.debug(f"Anzeige gespeichert: {ad_id} (Search: {search_id})")

        except sqlite3.Error as e:
            logger.error(f"Fehler beim Speichern der Anzeige {ad_id}: {e}")

