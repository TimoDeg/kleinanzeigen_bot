"""
OCR Service für Artikel-Nummer-Erkennung auf Produktbildern.
"""

import io
import logging
import re
from typing import Optional

import aiohttp
from PIL import Image

logger = logging.getLogger(__name__)

try:
    import pytesseract
    import cv2
    import numpy as np

    OCR_AVAILABLE = True
except ImportError:  # pragma: no cover - optionale Dependencies
    OCR_AVAILABLE = False
    logger.warning(
        "⚠️  OCR Dependencies nicht installiert "
        "(pytesseract, opencv-python, numpy, pillow)"
    )


class ArticleNumberOCR:
    """OCR für Artikel-Nummern auf RAM/Hardware-Bildern."""

    def __init__(self) -> None:
        if not OCR_AVAILABLE:
            raise ImportError(
                "OCR nicht verfügbar. Installiere: "
                "tesseract-ocr + pytesseract pillow opencv-python numpy"
            )

        self.patterns = [
            r"KF\d{3}C\d{2}[A-Z]{2,4}\d?-\d{2,3}",  # Kingston Fury
            r"F\d-\d{4}[A-Z]\d{2}-\d{2}[A-Z]{2}",  # G.Skill
            r"CMK\d{2}GX\dM\dA\d{4}C\d{2}",  # Corsair
            r"CMT\d{2}GX\dM\dA\d{4}C\d{2}",  # Corsair
            r"BLS\d{1,2}G\d[A-Z]\d{3,4}[A-Z]\d",  # Crucial Ballistix
            r"TF\d{2}D\d{2}[A-Z]\d{4}C\d{2}",  # Teamgroup
            r"AX\d[A-Z]\d{4}[A-Z]\d{4}[A-Z]?\d{2}",  # ADATA
        ]

    async def extract_article_number(self, image_url: str) -> Optional[str]:
        """
        Lädt Bild und extrahiert Artikel-Nummer via OCR.

        Args:
            image_url: URL zum Bild

        Returns:
            Erkannte Artikel-Nummer oder None
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url, timeout=10) as response:
                    if response.status != 200:
                        return None

                    image_data = await response.read()

            image = Image.open(io.BytesIO(image_data))
            image = self._preprocess_image(image)

            text = pytesseract.image_to_string(
                image,
                lang="eng",
                config="--psm 11",
            )

            logger.debug(f"OCR Text: {text[:100]}")

            for pattern in self.patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    article_nr = match.group(0).upper()
                    logger.info(f"✅ OCR Erfolg: {article_nr}")
                    return article_nr

            logger.debug("Keine Artikel-Nummer im OCR-Text gefunden")
            return None

        except Exception as e:  # pragma: no cover - Netz/OCR Fehler
            logger.error(f"OCR Fehler: {e}")
            return None

    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        Preprocessing: Kontrast, Schärfe, Noise Reduction.
        """
        max_size = 1600
        if max(image.size) > max_size:
            image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

        img_array = np.array(image.convert("RGB"))
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

        gray = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11,
            2,
        )

        gray = cv2.fastNlMeansDenoising(gray, h=10)

        kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
        gray = cv2.filter2D(gray, -1, kernel)

        return Image.fromarray(gray)


