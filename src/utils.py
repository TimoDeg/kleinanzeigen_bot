"""
Helper-Funktionen für den DDR5 RAM Bot.
"""

import re
import random
from datetime import datetime, timedelta
from typing import Optional

from .models import Listing


# User-Agent Liste für Rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
]


def rotate_user_agent() -> str:
    """
    Gibt einen zufälligen User-Agent zurück.

    Returns:
        User-Agent String
    """
    return random.choice(USER_AGENTS)


def is_ddr5(title: str, description: str) -> bool:
    """
    Prüft ob DDR5 im Titel oder Beschreibung vorhanden ist.

    Args:
        title: Titel der Anzeige
        description: Beschreibung der Anzeige

    Returns:
        True wenn DDR5 gefunden wurde
    """
    text = f"{title} {description}".lower()
    # Suche nach DDR5 (verschiedene Schreibweisen)
    patterns = [
        r"ddr5",
        r"ddr\s*5",
        r"ddr-5",
        r"d5",
    ]
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def parse_relative_date(text: str) -> Optional[datetime]:
    """
    Konvertiert relativen Datums-String in absolutes datetime.

    Args:
        text: Relativer String wie "vor 2 Stunden", "vor 3 Tagen"

    Returns:
        datetime Objekt oder None bei Fehler
    """
    if not text:
        return None

    text_lower = text.lower().strip()

    # Pattern für "vor X Minuten/Stunden/Tagen"
    patterns = [
        (r"vor\s+(\d+)\s+minuten?", timedelta(minutes=1)),
        (r"vor\s+(\d+)\s+stunden?", timedelta(hours=1)),
        (r"vor\s+(\d+)\s+tagen?", timedelta(days=1)),
        (r"vor\s+(\d+)\s+wochen?", timedelta(weeks=1)),
        (r"vor\s+(\d+)\s+monaten?", timedelta(days=30)),
        (r"vor\s+(\d+)\s+jahren?", timedelta(days=365)),
    ]

    for pattern, unit in patterns:
        match = re.search(pattern, text_lower)
        if match:
            try:
                amount = int(match.group(1))
                return datetime.now() - (unit * amount)
            except (ValueError, OverflowError):
                continue

    # Fallback: Heute
    return datetime.now()


def calculate_priority_score(listing: Listing) -> int:
    """
    Berechnet Priority Score für eine Anzeige.

    Args:
        listing: Listing Objekt

    Returns:
        Priority Score (0-16)
    """
    score = 0

    # +5: Modellnummer erkannt
    if listing.specs.model_number:
        score += 5

    # +3: OVP vorhanden
    if listing.has_ovp:
        score += 3

    # +3: Rechnung vorhanden
    if listing.has_invoice:
        score += 3

    # +2: Versand möglich
    if listing.shipping_available:
        score += 2

    # +2: Alle Specs vollständig
    if all([
        listing.specs.manufacturer,
        listing.specs.capacity,
        listing.specs.speed,
        listing.specs.latency,
    ]):
        score += 2

    # +1: Farbe angegeben
    if listing.specs.color:
        score += 1

    # -2: "defekt" oder "kaputt" im Text
    text = f"{listing.title} {listing.raw_description}".lower()
    if any(keyword in text for keyword in ["defekt", "kaputt", "beschädigt", "schaden"]):
        score -= 2

    return max(0, score)  # Mindestens 0

