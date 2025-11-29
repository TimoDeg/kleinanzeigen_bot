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
        # Für PC-Zubehör & Software: c3000, für Speicher: c225
        keyword_slug = self.keyword.lower().replace(" ", "-")
        if self.category == "c3000":
            category_slug = "pc-zubehoer-software"
        elif self.category == "c225":
            category_slug = "pc-zubehoer-software"  # Speicher ist Unterkategorie von PC-Zubehör
        else:
            category_slug = "anzeigen"
        
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
        # eBay Kleinanzeigen URLs haben verschiedene Formate:
        # /s-anzeige/123456789
        # /s-anzeige/titel/123456789-225-XXXX
        match = re.search(r'/s-anzeige/[^/]+/(\d+)', link)
        if match:
            return match.group(1)
        # Fallback: Suche nach ID am Anfang
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
            # Suche nach Link - verschiedene Selektoren versuchen
            link_elem = None
            link = None
            
            # Methode 1: data-href Attribut (neue Struktur)
            if ad_element.get("data-href"):
                link = urljoin(BASE_URL, ad_element["data-href"])
            # Methode 2: Direktes <a> Tag mit href
            elif ad_element.find("a", href=re.compile(r'/s-anzeige/')):
                link_elem = ad_element.find("a", href=re.compile(r'/s-anzeige/'))
                if link_elem and link_elem.get("href"):
                    link = urljoin(BASE_URL, link_elem["href"])
            # Methode 3: Link in h2 oder anderen Elementen
            else:
                title_elem = (
                    ad_element.find("h2", class_="ellipsis") or
                    ad_element.find("h2") or
                    ad_element.find("a", class_="ellipsis") or
                    ad_element.find("a", href=re.compile(r'/s-anzeige/'))
                )
                if title_elem:
                    link_elem = title_elem.find("a") if title_elem.name != "a" else title_elem
                    if link_elem and link_elem.get("href"):
                        link = urljoin(BASE_URL, link_elem["href"])
            
            if not link:
                return None
            
            ad_id = self._extract_ad_id(link)
            if not ad_id:
                return None
            
            # Titel extrahieren
            title = ""
            if link_elem:
                title = link_elem.get_text(strip=True)
            else:
                # Fallback: Suche nach Titel in verschiedenen Elementen
                title_elem = (
                    ad_element.find("h2", class_="ellipsis") or
                    ad_element.find("h2") or
                    ad_element.find("a", class_="ellipsis")
                )
                if title_elem:
                    title = title_elem.get_text(strip=True)
            
            if not title:
                title = "Kein Titel"
            
            # Preis - verschiedene Selektoren
            price = None
            # Hauptselektor: p.aditem-main--middle--price-shipping--price
            price_elem = (
                ad_element.find("p", class_="aditem-main--middle--price-shipping--price") or
                ad_element.find("div", class_="aditem-main--middle--price-shipping") or
                ad_element.find("p", class_="aditem-main--middle--price") or
                ad_element.find("p", class_="aditem-details--top--price") or
                ad_element.find("div", class_="aditem-details--top--price") or
                ad_element.find("span", class_="aditem-main--middle--price-shipping")
            )
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                # Falls es ein Container ist, suche nach dem Preis-Element darin
                if price_elem.name == "div":
                    inner_price = price_elem.find(
                        "p",
                        class_="aditem-main--middle--price-shipping--price",
                    )
                    if inner_price:
                        price_text = inner_price.get_text(strip=True)
                price = self._parse_price(price_text)

            # Versand / Abholung Informationen (shipping_type)
            shipping_type = ""
            try:
                shipping_container = (
                    ad_element.find(
                        "div",
                        class_="aditem-main--middle--price-shipping",
                    )
                    or ad_element.find(
                        "span",
                        class_="aditem-main--middle--price-shipping",
                    )
                    or price_elem
                )
                if shipping_container:
                    shipping_text = shipping_container.get_text(
                        strip=True
                    )
                    # Sehr einfache Heuristik – reicht für Filterung
                    parts = []
                    if "Versand" in shipping_text:
                        parts.append("Versand")
                    if "Abholung" in shipping_text:
                        parts.append("Abholung")
                    shipping_type = " / ".join(parts) or shipping_text
            except Exception:
                # Versand-Info ist nice-to-have, Fehler hier sind nicht kritisch
                shipping_type = ""
            
            # Ort - verschiedene Selektoren
            location = ""
            location_elem = (
                ad_element.find("div", class_="aditem-main--top--left") or
                ad_element.find("div", class_="aditem-details--top--left") or
                ad_element.find("span", class_="aditem-main--top--left")
            )
            if location_elem:
                location = location_elem.get_text(strip=True)
            
            # Zeitpunkt - verschiedene Selektoren
            posted_time = ""
            time_elem = (
                ad_element.find("div", class_="aditem-main--top--right") or
                ad_element.find("div", class_="aditem-details--top--right") or
                ad_element.find("span", class_="aditem-main--top--right")
            )
            if time_elem:
                posted_time = time_elem.get_text(strip=True)

            # Bild-URLs (für optionales OCR) – wir nehmen max. 3 sinnvolle Bilder
            images: List[str] = []
            try:
                img_tags = ad_element.find_all("img")
                for img in img_tags:
                    src = img.get("data-src") or img.get("src") or ""
                    if not src:
                        continue
                    # Icons / Platzhalter überspringen
                    if "placeholder" in src or "icon" in src:
                        continue
                    # Absolute URL bauen falls nötig
                    if src.startswith("//"):
                        src = "https:" + src
                    elif src.startswith("/"):
                        src = urljoin(BASE_URL, src)
                    images.append(src)
                    if len(images) >= 3:
                        break
            except Exception:
                images = []
            
            # Prüfe ob es ein Gesuch ist (Suchanzeige)
            is_gesuch = False
            title_lower = title.lower()
            # Prüfe Titel auf Gesuch-Indikatoren
            if any(indicator in title_lower for indicator in ["suche", "gesuch", "sucht", "wanted"]):
                is_gesuch = True
            # Prüfe auch HTML-Attribute/Klassen für Gesuch-Indikatoren
            if ad_element.find("span", class_=re.compile(r"gesuch|wanted", re.I)):
                is_gesuch = True
            if "gesuch" in str(ad_element.get("class", [])).lower():
                is_gesuch = True
            
            return {
                "id": ad_id,
                "title": title,
                "price": price,
                "location": location,
                "link": link,
                "posted_time": posted_time,
                "shipping_type": shipping_type,
                "images": images,
                "is_gesuch": is_gesuch,
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
                    soup.find_all("article", id=re.compile(r'aditem-\d+')) or
                    soup.find_all("div", class_="ad-listitem") or
                    soup.find_all("li", class_="ad-listitem") or
                    soup.find_all("li", id=re.compile(r'aditem-\d+'))
                )
                
                if not ad_elements:
                    logger.warning("Keine Anzeigen-Elemente gefunden. Versuche Fallback-Methode...")
                    # Fallback: Suche nach Links mit /s-anzeige/ und hole das Parent-Element
                    link_elements = soup.find_all("a", href=re.compile(r'/s-anzeige/\d+'))
                    ad_elements = []
                    for link in link_elements:
                        # Finde das Parent-Element (article, li, div)
                        parent = link.find_parent("article") or link.find_parent("li") or link.find_parent("div")
                        if parent and parent not in ad_elements:
                            ad_elements.append(parent)
                
                logger.info(f"Gefundene Anzeigen-Elemente: {len(ad_elements)}")
                
                parsed_count = 0
                failed_count = 0
                for elem in ad_elements:
                    ad = self._parse_ad_element(elem)
                    if ad:
                        ads.append(ad)
                        parsed_count += 1
                    else:
                        failed_count += 1
                        # Debug: Zeige warum Parsing fehlgeschlagen ist
                        logger.debug(f"Parsing fehlgeschlagen für Element: {str(elem)[:200]}")
                
                if failed_count > 0:
                    logger.warning(f"Konnte {failed_count} von {len(ad_elements)} Elementen nicht parsen")
                
                # Rate-limiting
                import random
                delay = random.uniform(self.delay_min, self.delay_max)
                time.sleep(delay)
                
                logger.info(f"Erfolgreich {len(ads)} Anzeigen abgerufen")
                return ads
                
            except requests.exceptions.Timeout as e:
                logger.warning(f"Timeout-Fehler (Versuch {attempt}/{self.max_retries}): {e}")
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"Alle Versuche fehlgeschlagen (Timeout): {e}")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request-Fehler (Versuch {attempt}/{self.max_retries}): {e}")
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"Alle Versuche fehlgeschlagen: {e}")
            except Exception as e:
                logger.error(f"Unerwarteter Fehler beim Scraping: {e}", exc_info=True)
                break
        
        return ads

