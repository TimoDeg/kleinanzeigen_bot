"""
Datenbank-Management für bereits gesehene Anzeigen.
Verwendet SQLite zur Persistierung.
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# SQLite Schema für die Tabelle der gesehenen Anzeigen
DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_ads (
    ad_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    price REAL,
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
    
    def mark_as_seen(self, ad_id: str, title: str, price: Optional[float] = None) -> None:
        """
        Markiert eine Anzeige als gesehen.
        
        Args:
            ad_id: Eindeutige ID der Anzeige
            title: Titel der Anzeige
            price: Optionaler Preis der Anzeige
        """
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO seen_ads (ad_id, title, price, fetched_at) VALUES (?, ?, ?, ?)",
                    (ad_id, title, price, datetime.now())
                )
                conn.commit()
            logger.debug(f"Anzeige als gesehen markiert: {ad_id}")
        except sqlite3.Error as e:
            logger.error(f"Fehler beim Markieren der Anzeige {ad_id}: {e}")
    
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


