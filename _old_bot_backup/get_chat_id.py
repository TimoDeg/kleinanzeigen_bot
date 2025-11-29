#!/usr/bin/env python3
"""
Hilfsskript zum Abrufen der Telegram Chat-ID.
Sende zuerst eine Nachricht an deinen Bot, dann führe dieses Skript aus.
"""

import json
import sys
import requests

BOT_TOKEN = "8285898160:AAEt992_pmQ0QwVE__gLRUOoBkhgc_zNs-U"

def get_chat_id():
    """Ruft die Chat-ID aus den Telegram Updates ab."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data.get("ok"):
            print(f"❌ Fehler: {data.get('description', 'Unbekannter Fehler')}")
            return None
        
        updates = data.get("result", [])
        
        if not updates:
            print("⚠️  Keine Updates gefunden!")
            print("\n📝 Bitte sende zuerst eine Nachricht an deinen Bot:")
            print("   1. Öffne Telegram")
            print("   2. Suche nach deinem Bot")
            print("   3. Sende eine Nachricht (z.B. 'Hallo' oder '/start')")
            print("   4. Führe dieses Skript erneut aus")
            return None
        
        # Nehme die neueste Nachricht
        latest_update = updates[-1]
        message = latest_update.get("message", {})
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        chat_type = chat.get("type")
        chat_title = chat.get("title") or chat.get("first_name", "Unbekannt")
        
        if chat_id:
            print(f"\n✅ Chat-ID gefunden!")
            print(f"   Chat-ID: {chat_id}")
            print(f"   Typ: {chat_type}")
            print(f"   Name: {chat_title}")
            print(f"\n📋 Füge diese Chat-ID in config.json ein:")
            print(f'   "chat_id": "{chat_id}"')
            return chat_id
        else:
            print("❌ Keine Chat-ID in den Updates gefunden")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Fehler beim Abrufen der Updates: {e}")
        return None
    except Exception as e:
        print(f"❌ Unerwarteter Fehler: {e}")
        return None

if __name__ == "__main__":
    print("🔍 Suche nach Chat-ID...\n")
    chat_id = get_chat_id()
    
    if chat_id:
        sys.exit(0)
    else:
        sys.exit(1)

