"""
Datenbank-Management für bereits gesehene Anzeigen.
Verwendet SQLite zur Persistierung.
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

# SQLite Schema für die Tabelle der gesehenen Anzeigen
DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_ads (
    ad_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    price REAL,
    link TEXT,
    location TEXT,
    posted_time TEXT,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

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
                # Migration: Füge neue Spalten hinzu falls sie nicht existieren
                try:
                    conn.execute("ALTER TABLE seen_ads ADD COLUMN link TEXT")
                except sqlite3.OperationalError:
                    pass  # Spalte existiert bereits
                try:
                    conn.execute("ALTER TABLE seen_ads ADD COLUMN location TEXT")
                except sqlite3.OperationalError:
                    pass  # Spalte existiert bereits
                try:
                    conn.execute("ALTER TABLE seen_ads ADD COLUMN posted_time TEXT")
                except sqlite3.OperationalError:
                    pass  # Spalte existiert bereits
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


