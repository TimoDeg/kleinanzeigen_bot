#!/usr/bin/env python3
"""
Migration Script: Alte DB-Struktur → Neue Multi-Search Struktur
Einmalig ausführen vor dem ersten Start der neuen Version.
"""

import argparse
import json
import logging
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseMigration:
    """Migriert die Datenbank zur neuen Multi-Search-Struktur."""

    def __init__(self, db_path: str = "kleinanzeigen.db") -> None:
        self.db_path = Path(db_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_path = Path(f"{db_path}.backup_{timestamp}")

    def backup_database(self) -> None:
        """Erstellt Backup der aktuellen Datenbank."""
        if self.db_path.exists():
            shutil.copy2(self.db_path, self.backup_path)
            logger.info(f"✅ Backup erstellt: {self.backup_path}")
        else:
            logger.info("Keine existierende Datenbank gefunden - starte fresh")

    def migrate(self) -> None:
        """Führt Migration durch."""
        logger.info("🔄 Starte Datenbank-Migration...")

        # Backup erstellen
        self.backup_database()

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            # Prüfe ob alte Struktur existiert
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='seen_ads'"
            )
            old_table_exists = cursor.fetchone() is not None

            if old_table_exists:
                logger.info("📊 Alte Struktur gefunden - migriere Daten...")
                self._migrate_from_old_schema(conn)
            else:
                logger.info("🆕 Erstelle neue Datenbankstruktur...")
                self._create_new_schema(conn)

            conn.commit()
            logger.info("✅ Migration erfolgreich abgeschlossen!")

        except Exception as e:  # pragma: no cover - sicherheitsrelevant
            logger.error(f"❌ Migration fehlgeschlagen: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def _create_new_schema(self, conn: sqlite3.Connection) -> None:
        """Erstellt neue Tabellen von Grund auf."""

        # Users Tabelle (für Multi-User später)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                telegram_username TEXT,
                allowed BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Searches Tabelle (Herzstück des neuen Systems)
        conn.execute(
            """
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
            )
            """
        )

        # Seen Ads Tabelle (erweitert)
        conn.execute(
            """
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
            )
            """
        )

        # Indices für Performance
        conn.execute("CREATE INDEX IF NOT EXISTS idx_searches_user ON searches(user_id)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_searches_active ON searches(active)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_seen_ads_search ON seen_ads(search_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_seen_ads_fetched ON seen_ads(fetched_at)"
        )

        logger.info("✅ Neue Tabellen erstellt")

    def _migrate_from_old_schema(self, conn: sqlite3.Connection) -> None:
        """Migriert Daten von alter zu neuer Struktur."""

        # Erstelle neue Tabellen
        self._create_new_schema(conn)

        # Erstelle Default-User und Default-Suche aus config.json (falls möglich)
        default_search_id = None

        try:
            with open("config.json", "r", encoding="utf-8") as f:
                config = json.load(f)

            telegram_cfg = config.get("telegram", {})
            chat_ids = telegram_cfg.get("chat_ids", [])
            if chat_ids:
                default_user_id = str(chat_ids[0])
            else:
                default_user_id = "default_user"

            conn.execute(
                "INSERT OR IGNORE INTO users (user_id, allowed) VALUES (?, 1)",
                (default_user_id,),
            )
            logger.info(f"✅ Default User erstellt: {default_user_id}")

            search_config = config.get("search", {}) or {}

            conn.execute(
                """
                INSERT INTO searches 
                (user_id, keyword, category, price_min, price_max, interval_seconds, exclude_keywords)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    default_user_id,
                    search_config.get("keyword", "") or "",
                    search_config.get("category", "c225"),
                    search_config.get("price_min"),
                    search_config.get("price_max"),
                    config.get("scraper", {}).get("interval_seconds", 300),
                    json.dumps(search_config.get("exclude_keywords", [])),
                ),
            )

            default_search_id = conn.execute(
                "SELECT last_insert_rowid()"
            ).fetchone()[0]
            logger.info(f"✅ Default Search erstellt (ID: {default_search_id})")

        except Exception as e:
            logger.warning(f"⚠️  Konnte config.json nicht lesen oder auswerten: {e}")

        # Migriere alte seen_ads (falls vorhanden)
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM seen_ads")
            old_count = cursor.fetchone()[0]

            if old_count > 0 and default_search_id:
                # Rename alte Tabelle
                conn.execute("ALTER TABLE seen_ads RENAME TO seen_ads_old")

                # Neue Tabelle existiert bereits (durch _create_new_schema)

                # Kopiere Daten mit default search_id
                conn.execute(
                    """
                    INSERT INTO seen_ads 
                    (ad_id, search_id, title, price, link, location, posted_time, fetched_at)
                    SELECT 
                        ad_id, 
                        ?,
                        title, 
                        price, 
                        COALESCE(link, ''),
                        COALESCE(location, ''),
                        COALESCE(posted_time, ''),
                        fetched_at
                    FROM seen_ads_old
                    """,
                    (default_search_id,),
                )

                # Lösche alte Tabelle
                conn.execute("DROP TABLE seen_ads_old")

                logger.info(f"✅ {old_count} alte Anzeigen migriert")
        except Exception as e:
            logger.warning(f"⚠️  Konnte alte Daten nicht migrieren: {e}")

        logger.info("✅ Migration abgeschlossen")


def main() -> None:
    """Hauptfunktion für Migration."""
    parser = argparse.ArgumentParser(description="Migriere Kleinanzeigen-Bot Datenbank")
    parser.add_argument(
        "--db-path",
        default="kleinanzeigen.db",
        help="Pfad zur Datenbank (default: kleinanzeigen.db)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Führe Migration auch bei Fehlern durch",
    )

    args = parser.parse_args()

    try:
        migration = DatabaseMigration(args.db_path)
        migration.migrate()

        print("\n" + "=" * 60)
        print("✅ Migration erfolgreich!")
        print("=" * 60)
        print("\nNächste Schritte:")
        print("1. Prüfe die neue Datenbank: sqlite3 kleinanzeigen.db")
        print("2. Starte den Bot: python main.py")
        print("3. Teste Telegram Commands: /start, /add")
        print(f"\n💾 Backup gespeichert: {migration.backup_path}")
        print("=" * 60 + "\n")

    except Exception as e:  # pragma: no cover - CLI-Fehlerfall
        logger.error(f"❌ Migration fehlgeschlagen: {e}")
        if not args.force:
            print("\n⚠️  Migration abgebrochen. Backup wurde erstellt.")
            print("Versuche: python migrate_db.py --force")
        raise


if __name__ == "__main__":
    main()


