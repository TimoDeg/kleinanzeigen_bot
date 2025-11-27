"""
eBay Kleinanzeigen Scraper.
Extrahiert Anzeigen aus der eBay Kleinanzeigen Website.
"""

import logging
import time
import re
from typing import List, Dict, Optional
from urllib.parse import urlencode, urljoin
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Basis-URL für eBay Kleinanzeigen
BASE_URL = "https://www.kleinanzeigen.de"


class KleinanzeigenScraper:
    """Scraper für eBay Kleinanzeigen Anzeigen."""
    
    def __init__(
        self,
        keyword: str,
        category: str = "c3000",
        sort: str = "neueste",
        user_agent: str = "",
        timeout: int = 30,
        delay_min: float = 1.0,
        delay_max: float = 2.0,
        max_retries: int = 3,
        retry_delay: int = 5
    ):
        """
        Initialisiert den Scraper.
        
        Args:
            keyword: Suchbegriff
            category: Kategorie-ID (c3000 = PC-Zubehör & Software)
            sort: Sortierung ("neueste" = neueste zuerst)
            user_agent: User-Agent String für Requests
            timeout: Timeout für HTTP-Requests in Sekunden
            delay_min: Minimale Verzögerung zwischen Requests in Sekunden
            delay_max: Maximale Verzögerung zwischen Requests in Sekunden
            max_retries: Maximale Anzahl Wiederholungsversuche bei Fehlern
            retry_delay: Verzögerung zwischen Wiederholungsversuchen in Sekunden
        """
        self.keyword = keyword
        self.category = category
        self.sort = sort
        self.user_agent = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        self.timeout = timeout
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Session für persistente Verbindungen
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        })
    
    def _build_search_url(self) -> str:
        """
        Baut die Such-URL für eBay Kleinanzeigen.
        
        Returns:
            Vollständige URL für die Suche
        """
        # eBay Kleinanzeigen URL-Struktur: /s-KATEGORIE/KEYWORD/k0cCATEGORY_ID
        # Für PC-Zubehör & Software: c3000
        keyword_slug = self.keyword.lower().replace(" ", "-")
        category_slug = "pc-zubehoer-software" if self.category == "c3000" else "anzeigen"
        
        # Basis-URL
        url = f"{BASE_URL}/s-{category_slug}/{keyword_slug}/k0{self.category}"
        
        # Sortierung als Query-Parameter
        if self.sort == "neueste":
            url += "?sortingField=SORTING_DATE"
        
        return url
    
    def _parse_price(self, price_text: str) -> Optional[float]:
        """
        Parst einen Preis-String in einen Float-Wert.
        
        Args:
            price_text: Preis als String (z.B. "150,00 €" oder "150€")
            
        Returns:
            Preis als Float oder None bei Fehler
        """
        if not price_text:
            return None
        
        try:
            # Entferne alle Zeichen außer Ziffern, Komma und Punkt
            cleaned = re.sub(r'[^\d,.]', '', price_text.replace('.', '').replace(',', '.'))
            if cleaned:
                return float(cleaned)
        except (ValueError, AttributeError):
            pass
        return None
    
    def _extract_ad_id(self, link: str) -> Optional[str]:
        """
        Extrahiert die Anzeigen-ID aus einem Link.
        
        Args:
            link: URL der Anzeige
            
        Returns:
            Anzeigen-ID oder None
        """
        # eBay Kleinanzeigen URLs haben Format: /s-anzeige/123456789
        match = re.search(r'/s-anzeige/(\d+)', link)
        if match:
            return match.group(1)
        return None
    
    def _parse_ad_element(self, ad_element) -> Optional[Dict]:
        """
        Parst ein einzelnes Anzeigen-Element aus dem HTML.
        
        Args:
            ad_element: BeautifulSoup-Element einer Anzeige
            
        Returns:
            Dictionary mit Anzeigendaten oder None bei Fehler
        """
        try:
            # Titel und Link
            title_elem = ad_element.find("h2", class_="ellipsis") or ad_element.find("a", class_="ellipsis")
            if not title_elem:
                return None
            
            title = title_elem.get_text(strip=True)
            link_elem = title_elem.find("a") if title_elem.name != "a" else title_elem
            if not link_elem or not link_elem.get("href"):
                return None
            
            link = urljoin(BASE_URL, link_elem["href"])
            ad_id = self._extract_ad_id(link)
            if not ad_id:
                return None
            
            # Preis
            price = None
            price_elem = ad_element.find("p", class_="aditem-main--middle--price")
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price = self._parse_price(price_text)
            
            # Ort
            location = ""
            location_elem = ad_element.find("div", class_="aditem-main--top--left")
            if location_elem:
                location = location_elem.get_text(strip=True)
            
            # Zeitpunkt
            posted_time = ""
            time_elem = ad_element.find("div", class_="aditem-main--top--right")
            if time_elem:
                posted_time = time_elem.get_text(strip=True)
            
            return {
                "id": ad_id,
                "title": title,
                "price": price,
                "location": location,
                "link": link,
                "posted_time": posted_time
            }
        except Exception as e:
            logger.debug(f"Fehler beim Parsen einer Anzeige: {e}")
            return None
    
    def fetch_ads(self) -> List[Dict]:
        """
        Ruft Anzeigen von eBay Kleinanzeigen ab.
        
        Returns:
            Liste von Dictionaries mit Anzeigendaten
        """
        url = self._build_search_url()
        ads = []
        
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Scrape eBay Kleinanzeigen (Versuch {attempt}/{self.max_retries}): {url}")
                
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, "lxml")
                
                # Suche nach Anzeigen-Elementen
                # eBay Kleinanzeigen verwendet verschiedene Selektoren
                ad_elements = (
                    soup.find_all("article", class_="aditem") or
                    soup.find_all("div", class_="ad-listitem") or
                    soup.find_all("li", class_="ad-listitem")
                )
                
                if not ad_elements:
                    logger.warning("Keine Anzeigen-Elemente gefunden. Möglicherweise hat sich die HTML-Struktur geändert.")
                    # Fallback: Suche nach Links mit /s-anzeige/
                    ad_elements = soup.find_all("a", href=re.compile(r'/s-anzeige/\d+'))
                
                logger.info(f"Gefundene Anzeigen-Elemente: {len(ad_elements)}")
                
                for elem in ad_elements:
                    ad = self._parse_ad_element(elem)
                    if ad:
                        ads.append(ad)
                
                # Rate-limiting
                import random
                delay = random.uniform(self.delay_min, self.delay_max)
                time.sleep(delay)
                
                logger.info(f"Erfolgreich {len(ads)} Anzeigen abgerufen")
                return ads
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request-Fehler (Versuch {attempt}/{self.max_retries}): {e}")
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"Alle Versuche fehlgeschlagen: {e}")
            except Exception as e:
                logger.error(f"Unerwarteter Fehler beim Scraping: {e}")
                break
        
        return ads

