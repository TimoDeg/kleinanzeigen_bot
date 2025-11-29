# Projektstruktur

## Hauptverzeichnis
- `src/` - Source Code des DDR5 RAM Bots
- `data/` - SQLite Datenbank (ads.db)
- `.env` - Umgebungsvariablen (nicht in Git)
- `.env.example` - Template für .env
- `requirements.txt` - Python Dependencies
- `Dockerfile` - Docker Image Definition
- `docker-compose.yml` - Docker Compose Konfiguration
- `README.md` - Dokumentation

## Backup
- `_old_bot_backup/` - Alte Bot-Dateien (kann gelöscht werden wenn nicht mehr benötigt)

## Source Code (src/)
- `main.py` - Entry Point + Orchestration
- `config.py` - Konfigurationsmanagement
- `scraper.py` - Selenium Scraper für eBay Kleinanzeigen
- `parser.py` - RAM Datenextraktion
- `database.py` - SQLite Datenbank
- `telegram_bot.py` - Telegram Integration
- `models.py` - Pydantic Datenmodelle
- `utils.py` - Helper Funktionen
