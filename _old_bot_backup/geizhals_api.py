"""
Geizhals API - Web-Scraping für Preisvergleich.
"""

import asyncio
import logging
import re
from typing import Optional, Dict

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class GeizhalsAPI:
    """Scraper für Geizhals Preisvergleich."""

    BASE_URL = "https://geizhals.de"

    def __init__(self) -> None:
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Erstellt oder gibt bestehende Session zurück."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36"
                    )
                }
            )
        return self.session

    async def close(self) -> None:
        """Schließt Session."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def search_product(self, query: str) -> Optional[Dict]:
        """
        Sucht Produkt auf Geizhals.

        Args:
            query: Suchbegriff

        Returns:
            Dict mit {price, model, link, article_nr} oder None
        """
        try:
            session = await self._get_session()
            search_url = f"{self.BASE_URL}/?fs={query}&in="

            async with session.get(search_url, timeout=10) as response:
                if response.status != 200:
                    logger.warning(f"Geizhals HTTP {response.status}")
                    return None

                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")

                first_result = soup.select_one("div.listview__item")
                if not first_result:
                    logger.debug(f"Kein Geizhals-Ergebnis für: {query}")
                    return None

                title_elem = first_result.select_one("a.listview__name")
                price_elem = first_result.select_one("span.gh_price")

                if not title_elem or not price_elem:
                    return None

                model = title_elem.text.strip()
                link = title_elem.get("href", "")
                if link and not link.startswith("http"):
                    link = f"{self.BASE_URL}{link}"

                price_text = price_elem.text.strip()
                price_match = re.search(
                    r"[\d.,]+", price_text.replace(",", ".")
                )
                price = float(price_match.group()) if price_match else None

                article_nr = self._extract_article_nr(model)

                return {
                    "price": price,
                    "model": model,
                    "link": link,
                    "article_nr": article_nr,
                }

        except asyncio.TimeoutError:
            logger.warning(f"Geizhals Timeout für: {query}")
            return None
        except Exception as e:  # pragma: no cover - Netzfehler
            logger.error(f"Geizhals Fehler: {e}")
            return None

    def _extract_article_nr(self, title: str) -> Optional[str]:
        """
        Extrahiert Artikel-Nummer aus Titel.

        Args:
            title: Produkt-Titel

        Returns:
            Artikel-Nummer oder None
        """
        patterns = [
            r"KF\d{3}C\d{2}[A-Z]{2,4}\d?-\d{2,3}",  # Kingston Fury
            r"F\d-\d{4}[A-Z]\d{2}-\d{2}[A-Z]{2}",  # G.Skill
            r"CMK\d{2}GX\dM\dA\d{4}C\d{2}",  # Corsair
            r"BLS\d{1,2}G\d[A-Z]\d{3,4}[A-Z]\d",  # Crucial
        ]

        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                return match.group(0).upper()

        return None

    def _extract_ram_specs(self, title: str) -> Dict:
        """
        Extrahiert RAM-Spezifikationen aus Titel.

        Args:
            title: Kleinanzeigen-Titel

        Returns:
            Dict mit {brand, series, capacity, speed}
        """
        specs: Dict[str, str] = {}

        brand_match = re.search(
            r"(Kingston|Corsair|G\.?Skill|Crucial|Teamgroup|Adata)",
            title,
            re.IGNORECASE,
        )
        if brand_match:
            specs["brand"] = brand_match.group(1)

        series_match = re.search(
            r"(Fury Beast|Fury Renegade|Vengeance|Dominator|Trident Z|Ballistix|T-Force)",
            title,
            re.IGNORECASE,
        )
        if series_match:
            specs["series"] = series_match.group(1)

        capacity_match = re.search(r"(\d+)\s*GB", title, re.IGNORECASE)
        if capacity_match:
            specs["capacity"] = f"{capacity_match.group(1)}GB"

        speed_match = re.search(r"(\d{4,5})\s*MHz", title, re.IGNORECASE)
        if speed_match:
            specs["speed"] = f"{speed_match.group(1)}MHz"

        return specs

    async def match_product(self, ad: Dict) -> Optional[Dict]:
        """
        Versucht Kleinanzeigen-Ad mit Geizhals zu matchen.

        Strategie:
        1. OCR Artikel-Nr (falls vorhanden) → Exakte Suche
        2. Titel-Extraktion → Fuzzy Search
        3. Preis-Plausibilitäts-Check
        """
        if ad.get("ocr_article_nr"):
            result = await self.search_product(ad["ocr_article_nr"])
            if result:
                logger.info(f"Geizhals Match via OCR: {result['model']}")
                return result

        title = ad.get("title", "")
        specs = self._extract_ram_specs(title)

        if not specs:
            logger.debug("Konnte keine RAM-Specs aus Titel extrahieren")
            return None

        query_parts = [
            specs[key] for key in ["brand", "series", "capacity", "speed"] if key in specs
        ]
        if not query_parts:
            return None

        query = " ".join(query_parts)
        result = await self.search_product(query)

        if not result:
            return None

        ad_price = ad.get("price")
        if ad_price and result["price"]:
            if ad_price > result["price"] * 1.1:
                logger.debug(
                    "Preis-Check fehlgeschlagen: "
                    f"Kleinanzeigen {ad_price}€ > Geizhals {result['price']}€"
                )
                return None

        logger.info(f"Geizhals Match via Titel: {result['model']}")
        return result


