"""
Datenbank-Management für den DDR5 RAM Bot.
Verwendet SQLite zur Persistierung.
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

from .models import Listing

logger = logging.getLogger(__name__)

# SQLite Schema
DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    ad_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    price REAL NOT NULL,
    location TEXT,
    url TEXT UNIQUE NOT NULL,
    posted_date TEXT,
    posted_timestamp TEXT,
    has_ovp BOOLEAN,
    has_invoice BOOLEAN,
    shipping_available BOOLEAN,
    model_number TEXT,
    manufacturer TEXT,
    capacity TEXT,
    speed TEXT,
    latency TEXT,
    color TEXT,
    priority_score INTEGER,
    raw_description TEXT,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_posted_timestamp ON listings(posted_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_manufacturer ON listings(manufacturer);
CREATE INDEX IF NOT EXISTS idx_first_seen ON listings(first_seen DESC);
"""


class Database:
    """Verwaltet die SQLite-Datenbank für DDR5 RAM Anzeigen."""

    def __init__(self, db_path: Path):
        """
        Initialisiert die Datenbankverbindung.

        Args:
            db_path: Pfad zur SQLite-Datenbankdatei
        """
        self.db_path = db_path
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

    def is_new_listing(self, ad_id: str) -> bool:
        """
        Prüft, ob eine Anzeige bereits in der Datenbank existiert.

        Args:
            ad_id: Eindeutige ID der Anzeige

        Returns:
            True wenn die Anzeige neu ist, False wenn bereits vorhanden
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM listings WHERE ad_id = ?",
                    (ad_id,)
                )
                return cursor.fetchone() is None
        except sqlite3.Error as e:
            logger.error(f"Fehler beim Prüfen der Anzeige {ad_id}: {e}")
            # Bei Fehler als neu behandeln, um keine Anzeigen zu verpassen
            return True

    def save_listing(self, listing: Listing) -> bool:
        """
        Speichert eine neue Anzeige in der Datenbank.

        Args:
            listing: Listing Objekt

        Returns:
            True bei Erfolg, False bei Fehler
        """
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO listings 
                       (ad_id, title, price, location, url, posted_date, posted_timestamp,
                        has_ovp, has_invoice, shipping_available, model_number, manufacturer,
                        capacity, speed, latency, color, priority_score, raw_description,
                        last_checked)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        listing.ad_id,
                        listing.title,
                        listing.price,
                        listing.location,
                        listing.url,
                        listing.posted_date,
                        listing.posted_timestamp.isoformat(),
                        listing.has_ovp,
                        listing.has_invoice,
                        listing.shipping_available,
                        listing.specs.model_number,
                        listing.specs.manufacturer,
                        listing.specs.capacity,
                        listing.specs.speed,
                        listing.specs.latency,
                        listing.specs.color,
                        listing.priority_score,
                        listing.raw_description,
                        datetime.now(),
                    ),
                )
                conn.commit()
            logger.debug(f"Anzeige gespeichert: {listing.ad_id}")
            return True
        except sqlite3.Error as e:
            logger.error(f"Fehler beim Speichern der Anzeige {listing.ad_id}: {e}")
            return False

    def get_recent_listings(self, limit: int = 5) -> List[Listing]:
        """
        Gibt die neuesten N Anzeigen zurück.

        Args:
            limit: Anzahl der zurückzugebenden Anzeigen

        Returns:
            Liste von Listing Objekten
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """SELECT * FROM listings 
                       ORDER BY first_seen DESC 
                       LIMIT ?""",
                    (limit,)
                )
                rows = cursor.fetchall()
                listings = []
                for row in rows:
                    listing = self._row_to_listing(row)
                    if listing:
                        listings.append(listing)
                return listings
        except sqlite3.Error as e:
            logger.error(f"Fehler beim Abrufen der neuesten Anzeigen: {e}")
            return []

    def get_stats(self) -> Dict:
        """
        Gibt Statistiken über die Datenbank zurück.

        Returns:
            Dictionary mit Statistiken
        """
        try:
            with self._get_connection() as conn:
                # Gesamt
                total = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]

                # Heute
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                today_count = conn.execute(
                    "SELECT COUNT(*) FROM listings WHERE first_seen >= ?",
                    (today,)
                ).fetchone()[0]

                # Hersteller-Verteilung
                manufacturer_stats = {}
                cursor = conn.execute(
                    "SELECT manufacturer, COUNT(*) as count FROM listings WHERE manufacturer IS NOT NULL GROUP BY manufacturer ORDER BY count DESC"
                )
                for row in cursor.fetchall():
                    manufacturer_stats[row["manufacturer"]] = row["count"]

                # Letzter Scan
                last_scan = conn.execute(
                    "SELECT MAX(last_checked) FROM listings"
                ).fetchone()[0]

                return {
                    "total": total,
                    "today": today_count,
                    "manufacturers": manufacturer_stats,
                    "last_scan": last_scan,
                }
        except sqlite3.Error as e:
            logger.error(f"Fehler beim Abrufen der Statistiken: {e}")
            return {
                "total": 0,
                "today": 0,
                "manufacturers": {},
                "last_scan": None,
            }

    def _row_to_listing(self, row: sqlite3.Row) -> Optional[Listing]:
        """
        Konvertiert eine Datenbank-Zeile in ein Listing Objekt.

        Args:
            row: SQLite Row Objekt

        Returns:
            Listing Objekt oder None bei Fehler
        """
        try:
            from .models import RAMSpecifications

            # Parse posted_timestamp
            posted_timestamp = datetime.now()
            if row["posted_timestamp"]:
                try:
                    posted_timestamp = datetime.fromisoformat(row["posted_timestamp"])
                except (ValueError, TypeError):
                    pass

            specs = RAMSpecifications(
                model_number=row["model_number"],
                manufacturer=row["manufacturer"],
                capacity=row["capacity"],
                speed=row["speed"],
                latency=row["latency"],
                color=row["color"],
            )

            listing = Listing(
                ad_id=row["ad_id"],
                title=row["title"],
                price=row["price"],
                location=row["location"] or "",
                url=row["url"],
                posted_date=row["posted_date"] or "",
                posted_timestamp=posted_timestamp,
                has_ovp=bool(row["has_ovp"]),
                has_invoice=bool(row["has_invoice"]),
                shipping_available=bool(row["shipping_available"]),
                specs=specs,
                raw_description=row["raw_description"] or "",
                priority_score=row["priority_score"] or 0,
            )
            return listing
        except Exception as e:
            logger.error(f"Fehler beim Konvertieren der Zeile: {e}")
            return None

