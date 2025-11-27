# eBay Kleinanzeigen Scraper-Bot

Ein produktionsreifer Python-Bot zum automatischen Scraping von eBay Kleinanzeigen mit Telegram-Benachrichtigungen bei neuen Anzeigen.

## Features

- 🔍 Automatisches Scraping nach konfigurierbaren Suchkriterien
- 🔔 Telegram-Benachrichtigungen bei neuen Anzeigen
- 💾 SQLite-Datenbank zur Vermeidung von Duplikaten
- ⚙️ Konfigurierbare Filter (Preis, Keywords)
- 🔄 Endlosschleife mit konfigurierbarem Intervall
- 🛡️ Robuste Fehlerbehandlung und Retry-Logik
- 📊 Rate-Limiting zum Schutz der Website
- 🚀 Systemd-Service für Auto-Start

## Voraussetzungen

- Python 3.9 oder höher
- Linux-Server (Ubuntu/Debian empfohlen)
- Telegram Bot Token (siehe unten)
- Internetverbindung

## Installation

### 1. Repository klonen oder Dateien kopieren

```bash
cd ~
mkdir kleinanzeigen_scraper
cd kleinanzeigen_scraper
# Dateien hier hinein kopieren
```

### 2. Python Virtual Environment erstellen

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Dependencies installieren

```bash
pip install -r requirements.txt
```

### 4. Telegram Bot erstellen

1. Öffne Telegram und suche nach **@BotFather**
2. Sende `/newbot` und folge den Anweisungen
3. Speichere den **Bot Token** (z.B. `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
4. Sende `/mybots` → wähle deinen Bot → **API Token** kopieren

### 5. Chat-ID herausfinden

**Methode 1: Über einen anderen Bot**
- Suche nach **@userinfobot** in Telegram
- Starte den Bot und sende `/start`
- Die Chat-ID wird angezeigt (z.B. `123456789`)

**Methode 2: Über die API**
```bash
# Ersetze YOUR_BOT_TOKEN mit deinem Token
curl https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates
```
Sende eine Nachricht an deinen Bot und führe den Befehl erneut aus. Die `chat.id` findest du in der JSON-Antwort.

### 6. Konfiguration

Öffne `config.json` und passe die Einstellungen an:

```json
{
  "telegram": {
    "token": "DEIN_BOT_TOKEN",
    "chat_id": "DEINE_CHAT_ID"
  },
  "search": {
    "keyword": "DDR5",
    "price_min": 70,
    "price_max": 251
  }
}
```

**Wichtige Einstellungen:**
- `telegram.token`: Dein Bot Token von BotFather
- `telegram.chat_id`: Deine Chat-ID (siehe Schritt 5)
- `search.keyword`: Suchbegriff
- `search.price_min` / `price_max`: Preisbereich in Euro
- `scraper.interval_seconds`: Wartezeit zwischen Scraping-Durchläufen (Standard: 300 = 5 Minuten)

## Verwendung

### Test-Modus (einmaliges Scraping)

```bash
python3 main.py --test
```

### Telegram-Test

```bash
python3 main.py --test-telegram
```

### Normaler Betrieb (Endlosschleife)

```bash
python3 main.py
```

### Mit Screen (für Hintergrund-Betrieb)

```bash
screen -S kleinanzeigen-bot
source venv/bin/activate
python3 main.py
# Strg+A, dann D zum Detachen
```

Zum Wiederanheften:
```bash
screen -r kleinanzeigen-bot
```

### Systemd Service (Auto-Start)

1. **Service-Datei anpassen:**

Öffne `kleinanzeigen-bot.service` und passe die Pfade an:
- `User=%i` → `User=dein_benutzername` (z.B. `User=ubuntu`)
- `WorkingDirectory` → Vollständiger Pfad zum Projekt
- `ExecStart` → Vollständiger Pfad zur Python-Datei

**Beispiel:**
```ini
[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/kleinanzeigen_scraper
ExecStart=/home/ubuntu/kleinanzeigen_scraper/venv/bin/python3 /home/ubuntu/kleinanzeigen_scraper/main.py
```

2. **Service installieren:**

```bash
sudo cp kleinanzeigen-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable kleinanzeigen-bot.service
sudo systemctl start kleinanzeigen-bot.service
```

3. **Service verwalten:**

```bash
# Status prüfen
sudo systemctl status kleinanzeigen-bot.service

# Logs anzeigen
sudo journalctl -u kleinanzeigen-bot.service -f

# Service stoppen
sudo systemctl stop kleinanzeigen-bot.service

# Service starten
sudo systemctl start kleinanzeigen-bot.service

# Service neu starten
sudo systemctl restart kleinanzeigen-bot.service
```

## CLI-Befehle

### Datenbank-Statistiken

```bash
python3 main.py --stats
```

### Datenbank leeren

```bash
python3 main.py --clear-db
```

## Projektstruktur

```
kleinanzeigen_scraper/
├── config.json              # Konfigurationsdatei
├── requirements.txt         # Python-Dependencies
├── database.py              # SQLite-Datenbank-Management
├── scraper.py               # eBay Kleinanzeigen Scraper
├── notifier.py              # Telegram-Benachrichtigungen
├── main.py                  # Hauptprogramm
├── kleinanzeigen-bot.service # Systemd Service
├── README.md                # Diese Datei
└── kleinanzeigen.db         # SQLite-Datenbank (wird automatisch erstellt)
```

## Fehlerbehebung

### Problem: "Keine chat_id konfiguriert"

**Lösung:** Stelle sicher, dass in `config.json` die `chat_id` gesetzt ist (siehe Installation, Schritt 5).

### Problem: "Telegram-Fehler: Unauthorized"

**Lösung:** 
- Prüfe, ob der Bot Token korrekt ist
- Stelle sicher, dass du eine Nachricht an den Bot gesendet hast (für Chat-ID)

### Problem: "Keine Anzeigen gefunden"

**Mögliche Ursachen:**
- HTML-Struktur von eBay Kleinanzeigen hat sich geändert (Scraper muss aktualisiert werden)
- Keine Anzeigen entsprechen den Suchkriterien
- Rate-Limiting oder IP-Block

**Lösung:**
- Prüfe die Logs: `tail -f logs/kleinanzeigen.log` (falls Logging konfiguriert)
- Teste die Suche manuell auf eBay Kleinanzeigen
- Erhöhe `request_delay_min` und `request_delay_max` in `config.json`

### Problem: "ModuleNotFoundError"

**Lösung:**
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Problem: Service startet nicht

**Lösung:**
```bash
# Prüfe Logs
sudo journalctl -u kleinanzeigen-bot.service -n 50

# Prüfe Pfade in der Service-Datei
sudo systemctl status kleinanzeigen-bot.service

# Teste manuell
cd /pfad/zum/projekt
source venv/bin/activate
python3 main.py --test
```

### Problem: Bot sendet keine Nachrichten

**Lösung:**
1. Teste Telegram-Verbindung: `python3 main.py --test-telegram`
2. Prüfe, ob Chat-ID korrekt ist
3. Prüfe, ob Bot Token korrekt ist
4. Stelle sicher, dass du dem Bot erlaubt hast, dir Nachrichten zu senden

## Konfiguration

### Suchparameter

```json
"search": {
  "keyword": "DDR5",                    // Suchbegriff
  "category": "c3000",                  // Kategorie (c3000 = PC-Zubehör)
  "sort": "neueste",                    // Sortierung
  "price_min": 70,                      // Mindestpreis in Euro
  "price_max": 251,                     // Höchstpreis in Euro
  "exclude_keywords": ["defekt", "kaputt"]  // Auszuschließende Keywords
}
```

### Scraper-Einstellungen

```json
"scraper": {
  "interval_seconds": 300,              // Wartezeit zwischen Durchläufen (Sekunden)
  "request_timeout": 30,                 // Timeout für HTTP-Requests
  "request_delay_min": 1,               // Minimale Verzögerung zwischen Requests
  "request_delay_max": 2,               // Maximale Verzögerung zwischen Requests
  "max_retries": 3,                     // Maximale Wiederholungsversuche
  "retry_delay": 5                      // Verzögerung zwischen Wiederholungen
}
```

## Sicherheit

- **Bot Token:** Niemals öffentlich teilen oder in Git committen
- **Rate-Limiting:** Respektiere die Website (min. 1-2 Sekunden zwischen Requests)
- **User-Agent:** Verwendet einen realistischen Browser-User-Agent

## Lizenz

Dieses Projekt ist für den persönlichen Gebrauch bestimmt. Beachte die Nutzungsbedingungen von eBay Kleinanzeigen.

## Support

Bei Problemen:
1. Prüfe die Logs
2. Teste mit `--test` Flag
3. Prüfe die Konfiguration
4. Stelle sicher, dass alle Dependencies installiert sind

## Changelog

### Version 1.0
- Initiale Version
- Scraping von eBay Kleinanzeigen
- Telegram-Benachrichtigungen
- SQLite-Datenbank
- Systemd-Service
- Preis- und Keyword-Filter


