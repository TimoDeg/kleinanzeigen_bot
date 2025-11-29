# DDR5 RAM Bot für eBay Kleinanzeigen

Ein produktionsreifer Python Bot, der eBay Kleinanzeigen nach DDR5 RAM durchsucht, strukturierte Daten extrahiert und per Telegram ausgibt. Docker-basiert, modular und robust.

## Features

- 🔍 Automatische Suche nach DDR5 RAM auf eBay Kleinanzeigen
- 🤖 Selenium + undetected-chromedriver für Anti-Bot-Umgehung
- 📊 Strukturierte Datenextraktion (Modellnummern, Specs, Metadaten)
- 📱 Telegram-Benachrichtigungen für neue Anzeigen
- 🐳 Docker-basiert für einfaches Deployment
- 💾 SQLite-Datenbank für Duplikat-Tracking
- ⚡ Priority-Scoring für relevante Anzeigen

## Tech Stack

- Python 3.11+
- Selenium + undetected-chromedriver
- Docker + Docker Compose
- SQLite
- python-telegram-bot
- Pydantic für Datenvalidierung

## Projektstruktur

```
kleinanzeigen_ddr5_bot/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── README.md
├── src/
│   ├── __init__.py
│   ├── main.py              # Entry point + orchestration
│   ├── config.py            # Config management (env vars)
│   ├── scraper.py           # Selenium-based scraper
│   ├── parser.py            # RAM data extraction logic
│   ├── database.py          # SQLite operations
│   ├── telegram_bot.py      # Telegram integration
│   ├── models.py            # Pydantic data models
│   └── utils.py             # Helper functions
└── data/
    └── ads.db               # SQLite database (auto-created)
```

## Installation & Setup

### 1. Repository klonen/erstellen

```bash
cd kleinanzeigen_ddr5_bot
```

### 2. Umgebungsvariablen konfigurieren

```bash
cp .env.example .env
```

Editiere `.env` und setze:

```bash
# Telegram
TELEGRAM_BOT_TOKEN=dein_bot_token_hier
TELEGRAM_CHAT_IDS=123456789,987654321

# Scraping (optional)
SCAN_INTERVAL_SECONDS=60
MAX_PAGES_PER_SCAN=5
REQUEST_DELAY_MIN=2
REQUEST_DELAY_MAX=4

# Selenium (optional)
HEADLESS=true
IMPLICIT_WAIT=10
PAGE_LOAD_TIMEOUT=30

# Database (optional)
DB_PATH=./data/ads.db

# Filters (optional)
MIN_PRICE=50
MAX_PRICE=500
EXCLUDE_DEFEKT=true
```

### 3. Docker Build & Start

```bash
# Build
docker-compose build

# Start (im Hintergrund)
docker-compose up -d

# Logs anzeigen
docker-compose logs -f bot
```

## Telegram Commands

- `/start` - Bot starten + Info
- `/status` - Aktuelle Statistiken (gesamt, heute, letzter Scan)
- `/test` - Sende letzte 5 erkannte Anzeigen
- `/stats` - Detaillierte DB Stats (RAM Hersteller Verteilung)

## Nachrichtenformat

```
🔷 DDR5 RAM Alert [Priority Score: X/16]
📦 Modell: {model_number oder "Unbekannt"}
🏭 Hersteller: {manufacturer}
💾 Kapazität: {capacity}
⚡ Takt: {speed}
⏱️ Latenz: {latency}
🎨 Farbe: {color}
💰 Preis: {price}€
📍 Ort: {location}
✅ OVP: {Ja/Nein}
📄 Rechnung: {Ja/Nein}
📮 Versand: {Möglich/Nur Abholung}
🕐 Online seit: {posted_date}
🔗 {url}
```

## Priority Score

Der Bot berechnet einen Priority Score für jede Anzeige:

- +5 Punkte: Modellnummer erkannt
- +3 Punkte: OVP vorhanden
- +3 Punkte: Rechnung vorhanden
- +2 Punkte: Versand möglich
- +2 Punkte: Alle Specs vollständig
- +1 Punkt: Farbe angegeben
- -2 Punkte: "defekt" oder "kaputt" im Text

## Datenbank-Schema

Die SQLite-Datenbank speichert:

- Anzeigen-ID, Titel, Preis, Ort, URL
- RAM-Spezifikationen (Modellnummer, Hersteller, Kapazität, Takt, Latenz, Farbe)
- Metadaten (OVP, Rechnung, Versand)
- Priority Score
- Timestamps (first_seen, last_checked)

## Monitoring

```bash
# Logs in Echtzeit
docker-compose logs -f bot

# Container-Status
docker-compose ps

# Container neu starten
docker-compose restart bot

# Container stoppen
docker-compose down
```

## Anti-Ban Maßnahmen

- User-Agent Rotation (10+ reale Browser UAs)
- Request Delays (2-4 Sekunden zufällig)
- Session Management (neue Session alle 50 Requests)
- Undetected Chrome (verhindert WebDriver detection)
- Proxy Support (optional via `HTTP_PROXY` env var)

## Troubleshooting

### Bot startet nicht

- Prüfe `.env` Datei (Token, Chat IDs)
- Prüfe Docker-Logs: `docker-compose logs bot`
- Prüfe ob Ports frei sind

### Keine Anzeigen gefunden

- Prüfe ob eBay Kleinanzeigen erreichbar ist
- Prüfe Selenium-Logs für Fehler
- Erhöhe `PAGE_LOAD_TIMEOUT` in `.env`

### Telegram-Nachrichten kommen nicht an

- Prüfe Bot Token
- Prüfe Chat IDs (müssen als String mit Komma getrennt sein)
- Teste mit `/start` Command

## Entwicklung

### Lokale Entwicklung (ohne Docker)

```bash
# Virtual Environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# oder
venv\Scripts\activate  # Windows

# Dependencies installieren
pip install -r requirements.txt

# Bot starten
python -m src.main
```

**Hinweis:** Für lokale Entwicklung benötigst du Chrome/Chromium und ChromeDriver.

## Erfolgskriterien

- ✅ Bot läuft stabil 24/7 ohne Crash
- ✅ Erkennt >80% der Modellnummern bei aktuellen Anzeigen
- ✅ <5% False Positives (keine DDR4, keine Gesuche)
- ✅ Telegram Nachrichten innerhalb 1 Minute nach Veröffentlichung
- ✅ Docker Container Start <30 Sekunden
- ✅ Memory Usage <500MB steady state
- ✅ 1 Minute Pause zwischen jedem Refresh

## Lizenz

Siehe LICENSE Datei.

## Support

Bei Problemen oder Fragen, erstelle ein Issue im Repository.

