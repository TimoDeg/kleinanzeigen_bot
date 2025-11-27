# eBay Kleinanzeigen Scraper-Bot - Einfache Ubuntu Installation

Ein produktionsreifer Python-Bot zum automatischen Scraping von eBay Kleinanzeigen mit Telegram-Benachrichtigungen bei neuen DDR5 RAM Anzeigen.

## 📋 Voraussetzungen

- Ubuntu 20.04 oder höher
- Python 3.9 oder höher
- Internetverbindung
- Telegram Account

---

## 🚀 Installation (5 Minuten)

### Schritt 1: System vorbereiten

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv git -y
```

### Schritt 2: Projekt herunterladen

```bash
cd ~
git clone https://github.com/TimoDeg/kleinanzeigen_bot.git
cd kleinanzeigen_bot
```

**Falls Git nicht installiert ist oder du die Dateien manuell kopieren willst:**
- Lade das Projekt als ZIP von GitHub herunter
- Entpacke es in `~/kleinanzeigen_bot`

### Schritt 3: Virtual Environment erstellen

```bash
python3 -m venv venv
source venv/bin/activate
```

**Wichtig:** Du musst das Virtual Environment jedes Mal aktivieren:
```bash
source venv/bin/activate
```

### Schritt 4: Dependencies installieren

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Schritt 5: Chat-ID herausfinden (30 Sekunden)

**Einfachste Methode:**

1. Öffne Telegram
2. Suche nach **@userinfobot**
3. Starte den Bot und sende `/start`
4. Der Bot zeigt dir deine Chat-ID an (z.B. `123456789`)
5. **Kopiere diese Nummer**

**Alternative Methode (falls @userinfobot nicht funktioniert):**

1. Sende eine Nachricht an deinen Bot
2. Führe diesen Befehl aus (ersetze `DEIN_BOT_TOKEN` mit deinem Token):

```bash
curl https://api.telegram.org/botDEIN_BOT_TOKEN/getUpdates
```

3. Suche nach `"chat":{"id":123456789}` - das ist deine Chat-ID

### Schritt 6: Konfiguration anpassen

Öffne `config.json`:

```bash
nano config.json
```

**Ändere nur diese beiden Werte:**

```json
{
  "telegram": {
    "token": "DEIN_BOT_TOKEN_HIER",
    "chat_id": "DEINE_CHAT_ID_HIER"
  }
}
```

**Speichern:** `Strg+O`, dann `Enter`, dann `Strg+X`

**Hinweis:** Der Bot Token ist bereits in der `config.json` eingetragen. Du musst nur deine Chat-ID eintragen!

### Schritt 7: Testen

**Telegram-Verbindung testen:**
```bash
source venv/bin/activate
python3 main.py --test-telegram
```

Du solltest eine Test-Nachricht in Telegram erhalten.

**Einmaliges Scraping testen:**
```bash
source venv/bin/activate
python3 main.py --test
```

---

## 🎯 Bot starten

### Option 1: Manuell (für Tests)

```bash
cd ~/kleinanzeigen_bot
source venv/bin/activate
python3 main.py
```

**Stoppen:** `Strg+C`

### Option 2: Im Hintergrund mit Screen (Empfohlen)

```bash
# Screen installieren (falls nicht vorhanden)
sudo apt install screen -y

# Screen-Session starten
cd ~/kleinanzeigen_bot
screen -S kleinanzeigen-bot

# Bot starten
source venv/bin/activate
python3 main.py

# Screen verlassen (Bot läuft weiter): Strg+A, dann D
```

**Screen wieder anheften:**
```bash
screen -r kleinanzeigen-bot
```

**Screen beenden:**
```bash
screen -r kleinanzeigen-bot
# Dann Strg+C zum Stoppen
```

### Option 3: Als Systemd Service (Auto-Start beim Boot)

**1. Service-Datei anpassen:**

```bash
nano kleinanzeigen-bot.service
```

**Ändere folgende Zeilen** (ersetze `dein_benutzername` mit deinem Ubuntu-Benutzernamen - finde ihn mit `whoami`):

```ini
[Service]
User=dein_benutzername
WorkingDirectory=/home/dein_benutzername/kleinanzeigen_bot
ExecStart=/home/dein_benutzername/kleinanzeigen_bot/venv/bin/python3 /home/dein_benutzername/kleinanzeigen_bot/main.py
```

**Speichern:** `Strg+O`, dann `Enter`, dann `Strg+X`

**2. Service installieren:**

```bash
sudo cp kleinanzeigen-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable kleinanzeigen-bot.service
sudo systemctl start kleinanzeigen-bot.service
```

**3. Service verwalten:**

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

---

## 📱 Telegram-Befehle

Sende diese Nachrichten an deinen Bot:

- **`test`** oder **`/test`** → Sendet die 5 neuesten DDR5 RAM Anzeigen
- **`status`** oder **`/status`** → Zeigt Bot-Status, Statistiken und Details

---

## ⚙️ Konfiguration

### Wichtige Einstellungen in `config.json`

```json
{
  "search": {
    "keyword": "DDR5 RAM",           // Suchbegriff
    "category": "c225",              // Kategorie (c225 = PC-Zubehör)
    "price_min": 70,                 // Mindestpreis in Euro
    "price_max": 251,                // Höchstpreis in Euro
    "exclude_keywords": [...]        // Auszuschließende Keywords
  },
  "scraper": {
    "interval_seconds": 300,         // Wartezeit zwischen Durchläufen (5 Min)
    "request_timeout": 30,           // Timeout für HTTP-Requests
    "request_delay_min": 1,          // Minimale Verzögerung zwischen Requests
    "request_delay_max": 2           // Maximale Verzögerung zwischen Requests
  }
}
```

---

## 🔧 CLI-Befehle

```bash
# Test-Modus (einmaliges Scraping)
python3 main.py --test

# Telegram-Test
python3 main.py --test-telegram

# Datenbank-Statistiken
python3 main.py --stats

# Datenbank leeren
python3 main.py --clear-db
```

---

## 🐛 Fehlerbehebung

### Problem: "ModuleNotFoundError"

**Lösung:**
```bash
cd ~/kleinanzeigen_bot
source venv/bin/activate
pip install -r requirements.txt
```

### Problem: "Keine chat_id konfiguriert"

**Lösung:**
1. Öffne `config.json`
2. Füge deine Chat-ID ein (siehe Schritt 5)
3. Speichere die Datei

### Problem: "Telegram-Fehler: Unauthorized"

**Lösung:**
1. Prüfe, ob der Bot Token korrekt ist
2. Stelle sicher, dass du eine Nachricht an den Bot gesendet hast
3. Teste mit: `python3 main.py --test-telegram`

### Problem: "Keine Anzeigen gefunden"

**Mögliche Ursachen:**
- HTML-Struktur von eBay Kleinanzeigen hat sich geändert
- Keine Anzeigen entsprechen den Suchkriterien
- Rate-Limiting oder IP-Block

**Lösung:**
```bash
# Prüfe Logs
tail -f bot.log

# Erhöhe Verzögerung in config.json
# "request_delay_min": 2
# "request_delay_max": 3
```

### Problem: Service startet nicht

**Lösung:**
```bash
# Prüfe Logs
sudo journalctl -u kleinanzeigen-bot.service -n 50

# Prüfe Pfade in der Service-Datei
cat /etc/systemd/system/kleinanzeigen-bot.service

# Teste manuell
cd ~/kleinanzeigen_bot
source venv/bin/activate
python3 main.py --test
```

### Problem: Bot sendet keine Nachrichten

**Lösung:**
1. Teste Telegram: `python3 main.py --test-telegram`
2. Prüfe Chat-ID in `config.json`
3. Prüfe Bot Token in `config.json`
4. Stelle sicher, dass du dem Bot erlaubt hast, dir Nachrichten zu senden

---

## 📁 Projektstruktur

```
kleinanzeigen_bot/
├── config.json              # Konfigurationsdatei
├── requirements.txt         # Python-Dependencies
├── database.py              # SQLite-Datenbank-Management
├── scraper.py               # eBay Kleinanzeigen Scraper
├── notifier.py              # Telegram-Benachrichtigungen
├── main.py                  # Hauptprogramm
├── kleinanzeigen-bot.service # Systemd Service
├── README.md                # Diese Datei
├── venv/                    # Virtual Environment (wird erstellt)
└── kleinanzeigen.db         # SQLite-Datenbank (wird automatisch erstellt)
```

---

## 🔒 Sicherheit

- **Bot Token:** Niemals öffentlich teilen oder in Git committen
- **Rate-Limiting:** Respektiere die Website (min. 1-2 Sekunden zwischen Requests)
- **User-Agent:** Verwendet einen realistischen Browser-User-Agent

---

## 📊 Was macht der Bot?

1. **Automatisches Scraping:** Sucht alle 5 Minuten nach neuen DDR5 RAM Anzeigen
2. **Intelligente Filterung:**
   - Preisbereich: 70€ - 251€
   - Nur Angebote (keine Gesuche)
   - Ausschluss von defekten/kaputten Artikeln
   - Nur DDR5 RAM Anzeigen
3. **Duplikat-Vermeidung:** Speichert bereits gesehene Anzeigen in SQLite
4. **Telegram-Benachrichtigungen:** Sendet dir sofort eine Nachricht bei neuen Anzeigen
5. **Beim Start:** Sendet die letzten 3 DDR5 RAM Anzeigen (chronologisch: alt zu neu)

---

## 🆘 Support

Bei Problemen:
1. Prüfe die Logs: `tail -f bot.log` oder `sudo journalctl -u kleinanzeigen-bot.service -f`
2. Teste mit `--test` Flag
3. Prüfe die Konfiguration in `config.json`
4. Stelle sicher, dass alle Dependencies installiert sind

---

## 📝 Lizenz

Dieses Projekt ist für den persönlichen Gebrauch bestimmt. Beachte die Nutzungsbedingungen von eBay Kleinanzeigen.

---

## ✅ Checkliste für die Installation

- [ ] Ubuntu aktualisiert
- [ ] Python 3 und pip installiert
- [ ] Projekt heruntergeladen (`git clone` oder ZIP)
- [ ] Virtual Environment erstellt (`python3 -m venv venv`)
- [ ] Dependencies installiert (`pip install -r requirements.txt`)
- [ ] Chat-ID herausgefunden (@userinfobot)
- [ ] `config.json` angepasst (Chat-ID eingetragen)
- [ ] Telegram-Test erfolgreich (`--test-telegram`)
- [ ] Scraping-Test erfolgreich (`--test`)
- [ ] Bot gestartet (Screen oder Systemd)

**Fertig! Der Bot läuft jetzt und sendet dir automatisch Benachrichtigungen bei neuen DDR5 RAM Anzeigen.** 🎉
