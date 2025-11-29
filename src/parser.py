"""
RAM Datenextraktion aus Anzeigen-Texten.
Erkennt Modellnummern, Spezifikationen und Metadaten.
"""

import re
import logging
from typing import Optional

from .models import RAMSpecifications, Listing
from .utils import parse_relative_date, calculate_priority_score, is_ddr5

logger = logging.getLogger(__name__)

# Regex-Patterns für Modellnummern nach Hersteller
MODEL_PATTERNS = {
    "Corsair": [
        r"CMK\w+",
        r"CMT\w+",
        r"CMH\w+",
        r"CMR\w+",
        r"CMW\w+",
    ],
    "G.Skill": [
        r"F5-\d+\w+",
        r"F5\w+",
        r"F4-\d+\w+",
    ],
    "Kingston": [
        r"KF\w+",
        r"KVR\w+",
        r"KF\w+",
    ],
    "Crucial": [
        r"CT\w+",
        r"BL\w+",
    ],
    "TeamGroup": [
        r"TF\d+D\w+",
        r"TF\w+",
    ],
    "Patriot": [
        r"PV\w+",
        r"PVB\w+",
    ],
    "ADATA": [
        r"AX5U\w+",
        r"AD5U\w+",
    ],
    "Corsair Vengeance": [
        r"CMK\d+GX5M\d+\w+",
    ],
}

# Hersteller-Keywords für Fallback
MANUFACTURER_KEYWORDS = {
    "Corsair": ["corsair"],
    "G.Skill": ["g.skill", "gskill", "g skill"],
    "Kingston": ["kingston"],
    "Crucial": ["crucial"],
    "TeamGroup": ["teamgroup", "team group"],
    "Patriot": ["patriot"],
    "ADATA": ["adata"],
    "Samsung": ["samsung"],
    "SK Hynix": ["sk hynix", "hynix"],
    "Micron": ["micron"],
}

# Farb-Keywords
COLOR_KEYWORDS = {
    "Schwarz": ["schwarz", "black"],
    "Weiß": ["weiß", "white", "weiss"],
    "RGB": ["rgb", "led"],
    "Silber": ["silber", "silver"],
    "Grau": ["grau", "grey", "gray"],
}


class RAMParser:
    """Parser für RAM-Spezifikationen aus Anzeigen-Texten."""

    @staticmethod
    def extract_model_number(text: str) -> tuple:
        """
        Extrahiert Modellnummer und Hersteller aus Text.

        Args:
            text: Text zum Durchsuchen

        Returns:
            Tuple (model_number, manufacturer) oder (None, None)
        """
        text_upper = text.upper()

        for manufacturer, patterns in MODEL_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, text_upper, re.IGNORECASE)
                if match:
                    model_number = match.group(0)
                    return model_number, manufacturer

        return None, None

    @staticmethod
    def extract_manufacturer(text: str) -> Optional[str]:
        """
        Extrahiert Hersteller aus Text (Fallback-Methode).

        Args:
            text: Text zum Durchsuchen

        Returns:
            Hersteller-Name oder None
        """
        text_lower = text.lower()

        for manufacturer, keywords in MANUFACTURER_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return manufacturer

        return None

    @staticmethod
    def extract_capacity(text: str) -> Optional[str]:
        """
        Extrahiert Kapazität aus Text.

        Args:
            text: Text zum Durchsuchen

        Returns:
            Kapazität-String (z.B. "32GB", "2x16GB") oder None
        """
        # Pattern: 32GB, 2x16GB, 64 GB, etc.
        patterns = [
            r"(\d+x?\d*)\s*GB",
            r"(\d+x?\d*)\s*gb",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                capacity = match.group(0).upper()
                return capacity

        return None

    @staticmethod
    def extract_speed(text: str) -> Optional[str]:
        """
        Extrahiert Taktfrequenz aus Text.

        Args:
            text: Text zum Durchsuchen

        Returns:
            Speed-String (z.B. "5200 MHz", "6000MT/s") oder None
        """
        # Pattern: 5200 MHz, 6000MT/s, 4800 MHz, etc.
        patterns = [
            r"(\d{4,5})\s*(MHz|MT/s|MT/s)",
            r"(\d{4,5})\s*(mhz)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                speed = match.group(0)
                return speed

        return None

    @staticmethod
    def extract_latency(text: str) -> Optional[str]:
        """
        Extrahiert Latenz aus Text.

        Args:
            text: Text zum Durchsuchen

        Returns:
            Latency-String (z.B. "CL40", "CL36") oder None
        """
        # Pattern: CL40, CL36, CL32, etc.
        patterns = [
            r"CL\s*(\d{2,3})",
            r"C(\d{2,3})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                latency = f"CL{match.group(1)}"
                return latency

        return None

    @staticmethod
    def extract_color(text: str) -> Optional[str]:
        """
        Extrahiert Farbe aus Text.

        Args:
            text: Text zum Durchsuchen

        Returns:
            Farbe-String oder None
        """
        text_lower = text.lower()

        for color, keywords in COLOR_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return color

        return None

    @staticmethod
    def extract_metadata(text: str) -> dict:
        """
        Extrahiert Metadaten (OVP, Rechnung, Versand) aus Text.

        Args:
            text: Text zum Durchsuchen

        Returns:
            Dictionary mit has_ovp, has_invoice, shipping_available
        """
        text_lower = text.lower()

        # OVP Detection
        ovp_keywords = ["ovp", "originalverpackung", "original verpackt", "versiegelt", "unverschweißt"]
        has_ovp = any(keyword in text_lower for keyword in ovp_keywords)

        # Rechnung Detection
        invoice_keywords = ["rechnung", "kassenbon", "beleg", "garantie", "kaufbeleg"]
        has_invoice = any(keyword in text_lower for keyword in invoice_keywords)

        # Versand Detection
        shipping_keywords = ["versand möglich", "versandkosten", "dhl", "porto", "versand"]
        no_shipping_keywords = ["nur abholung", "kein versand", "abholung nur"]
        
        has_shipping_keywords = any(keyword in text_lower for keyword in shipping_keywords)
        has_no_shipping_keywords = any(keyword in text_lower for keyword in no_shipping_keywords)
        
        shipping_available = has_shipping_keywords and not has_no_shipping_keywords

        return {
            "has_ovp": has_ovp,
            "has_invoice": has_invoice,
            "shipping_available": shipping_available,
        }

    def parse_listing(
        self,
        ad_id: str,
        title: str,
        description: str,
        price: float,
        location: str,
        url: str,
        posted_date: str,
    ) -> Optional[Listing]:
        """
        Parst eine Anzeige und erstellt ein Listing Objekt.

        Args:
            ad_id: Eindeutige ID der Anzeige
            title: Titel der Anzeige
            description: Beschreibung der Anzeige
            price: Preis
            location: Standort
            url: URL zur Anzeige
            posted_date: Relativer Datums-String

        Returns:
            Listing Objekt oder None bei Fehler
        """
        # Kombinierter Text für Suche
        full_text = f"{title} {description}".strip()

        # Prüfe ob DDR5 vorhanden
        if not is_ddr5(title, description):
            logger.debug(f"Kein DDR5 gefunden in Anzeige {ad_id}")
            return None

        # Extrahiere Modellnummer (Primärstrategie)
        model_number, manufacturer = self.extract_model_number(full_text)

        # Erstelle RAMSpecifications
        specs = RAMSpecifications(
            model_number=model_number,
            manufacturer=manufacturer,
        )

        # Wenn Modellnummer gefunden, versuche weitere Specs zu extrahieren
        if model_number:
            # Specs aus Modellnummer ableiten (falls möglich)
            # Zusätzlich aus Beschreibung extrahieren
            if not specs.capacity:
                specs.capacity = self.extract_capacity(full_text)
            if not specs.speed:
                specs.speed = self.extract_speed(full_text)
            if not specs.latency:
                specs.latency = self.extract_latency(full_text)
        else:
            # Fallback-Strategie: Keyword-Extraktion
            if not specs.manufacturer:
                specs.manufacturer = self.extract_manufacturer(full_text)
            specs.capacity = self.extract_capacity(full_text)
            specs.speed = self.extract_speed(full_text)
            specs.latency = self.extract_latency(full_text)

        # Farbe extrahieren
        specs.color = self.extract_color(full_text)

        # Metadaten extrahieren
        metadata = self.extract_metadata(full_text)

        # Posted timestamp parsen
        posted_timestamp = parse_relative_date(posted_date) or parse_relative_date(title)

        # Erstelle Listing
        listing = Listing(
            ad_id=ad_id,
            title=title,
            price=price,
            location=location,
            url=url,
            posted_date=posted_date,
            posted_timestamp=posted_timestamp or parse_relative_date("vor 0 Stunden"),
            has_ovp=metadata["has_ovp"],
            has_invoice=metadata["has_invoice"],
            shipping_available=metadata["shipping_available"],
            specs=specs,
            raw_description=description,
        )

        # Berechne Priority Score
        listing.priority_score = calculate_priority_score(listing)

        return listing

