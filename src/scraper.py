"""
Selenium-basierter Scraper für eBay Kleinanzeigen DDR5 RAM.
Verwendet undetected-chromedriver für Anti-Bot-Umgehung.
"""

import time
import random
import logging
from typing import List, Dict, Optional
from urllib.parse import urljoin

import ssl
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException

from .config import config
from .utils import rotate_user_agent

# SSL-Zertifikatsproblem auf macOS beheben
ssl._create_default_https_context = ssl._create_unverified_context

logger = logging.getLogger(__name__)

# Base URL für DDR5 RAM Suche
BASE_URL = "https://www.kleinanzeigen.de/s-pc-zubehoer-software/ddr5/k0c225"


class KleinanzeigenScraper:
    """Scraper für eBay Kleinanzeigen DDR5 RAM Anzeigen."""

    def __init__(self):
        """Initialisiert den Scraper."""
        self.driver: Optional[uc.Chrome] = None
        self.request_count = 0
        self.max_requests_per_session = 50

    def _create_driver(self) -> uc.Chrome:
        """
        Erstellt einen neuen Chrome-Driver mit Anti-Bot-Umgehung.

        Returns:
            Chrome WebDriver
        """
        options = uc.ChromeOptions()

        if config.HEADLESS:
            options.add_argument("--headless=new")

        # Anti-Bot Umgehung
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-setuid-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        # User-Agent
        user_agent = rotate_user_agent()
        options.add_argument(f"--user-agent={user_agent}")

        # Proxy (optional)
        if config.HTTP_PROXY:
            options.add_argument(f"--proxy-server={config.HTTP_PROXY}")

        # Shared memory optimization
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")

        try:
            driver = uc.Chrome(options=options, version_main=None)
            driver.set_page_load_timeout(config.PAGE_LOAD_TIMEOUT)
            driver.implicitly_wait(config.IMPLICIT_WAIT)

            # Anti-detection Script
            driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {
                    "source": """
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined
                        });
                    """
                },
            )

            logger.info("Chrome-Driver erstellt")
            return driver

        except Exception as e:
            logger.error(f"Fehler beim Erstellen des Chrome-Drivers: {e}")
            raise

    def _get_driver(self) -> uc.Chrome:
        """
        Gibt den aktuellen Driver zurück oder erstellt einen neuen.

        Returns:
            Chrome WebDriver
        """
        if self.driver is None or self.request_count >= self.max_requests_per_session:
            self._close_driver()
            self.driver = self._create_driver()
            self.request_count = 0
            logger.info("Neue Session gestartet")

        return self.driver

    def _close_driver(self) -> None:
        """Schließt den aktuellen Driver."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.warning(f"Fehler beim Schließen des Drivers: {e}")
            finally:
                self.driver = None

    def _wait_and_retry(self, func, max_retries: int = 3, delay: float = 2.0):
        """
        Führt eine Funktion mit Retry-Logik aus.

        Args:
            func: Funktion zum Ausführen
            max_retries: Maximale Anzahl Wiederholungen
            delay: Verzögerung zwischen Wiederholungen

        Returns:
            Ergebnis der Funktion
        """
        for attempt in range(1, max_retries + 1):
            try:
                return func()
            except (TimeoutException, StaleElementReferenceException) as e:
                if attempt < max_retries:
                    wait_time = delay * (2 ** (attempt - 1))  # Exponential backoff
                    logger.warning(f"Retry {attempt}/{max_retries} nach {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Alle Retries fehlgeschlagen: {e}")
                    raise
            except Exception as e:
                logger.error(f"Unerwarteter Fehler: {e}")
                raise

    def _extract_ad_id(self, url: str) -> Optional[str]:
        """
        Extrahiert die Anzeigen-ID aus einer URL.

        Args:
            url: URL der Anzeige

        Returns:
            Anzeigen-ID oder None
        """
        import re
        match = re.search(r'/s-anzeige/[^/]+/(\d+)', url)
        if match:
            return match.group(1)
        match = re.search(r'/s-anzeige/(\d+)', url)
        if match:
            return match.group(1)
        return None

    def _parse_ad_element(self, element) -> Optional[Dict]:
        """
        Parst ein einzelnes Anzeigen-Element.

        Args:
            element: Selenium WebElement

        Returns:
            Dictionary mit Anzeigendaten oder None
        """
        try:
            # Link und ID
            link_elem = element.find_element(By.TAG_NAME, "a")
            link = link_elem.get_attribute("href")
            if not link:
                return None

            ad_id = self._extract_ad_id(link)
            if not ad_id:
                return None

            # Titel
            try:
                title = link_elem.text.strip()
            except:
                title = element.find_element(By.CSS_SELECTOR, "h2, .ellipsis").text.strip()

            # Preis
            price = None
            try:
                price_elem = element.find_element(
                    By.CSS_SELECTOR,
                    ".aditem-main--middle--price-shipping--price, .aditem-details--top--price"
                )
                price_text = price_elem.text.strip()
                # Parse Preis
                import re
                price_match = re.search(r'[\d,]+', price_text.replace(".", "").replace(",", "."))
                if price_match:
                    price = float(price_match.group(0))
            except:
                pass

            if price is None or price <= 0:
                return None

            # Ort
            location = ""
            try:
                location_elem = element.find_element(
                    By.CSS_SELECTOR,
                    ".aditem-main--top--left, .aditem-details--top--left"
                )
                location = location_elem.text.strip()
            except:
                pass

            # Zeitpunkt
            posted_time = ""
            try:
                time_elem = element.find_element(
                    By.CSS_SELECTOR,
                    ".aditem-main--top--right, .aditem-details--top--right"
                )
                posted_time = time_elem.text.strip()
            except:
                pass

            # Beschreibung (vereinfacht - wird später aus Detailseite geholt)
            description = title

            # Prüfe ob Gesuch
            is_gesuch = False
            title_lower = title.lower()
            if any(keyword in title_lower for keyword in ["suche", "gesuch", "sucht", "wanted"]):
                is_gesuch = True

            if is_gesuch:
                return None

            return {
                "id": ad_id,
                "title": title,
                "price": price,
                "location": location,
                "link": link,
                "posted_time": posted_time,
                "description": description,
            }

        except Exception as e:
            logger.debug(f"Fehler beim Parsen einer Anzeige: {e}")
            return None

    def _fetch_page(self, page: int = 1) -> List[Dict]:
        """
        Ruft eine einzelne Seite ab.

        Args:
            page: Seitennummer

        Returns:
            Liste von Anzeigen-Dictionaries
        """
        driver = self._get_driver()

        # URL mit Pagination
        if page == 1:
            url = BASE_URL
        else:
            url = f"{BASE_URL}?seite={page}"

        logger.info(f"Scrape Seite {page}: {url}")

        def _fetch():
            driver.get(url)
            # Warte auf Anzeigen-Elemente
            WebDriverWait(driver, config.PAGE_LOAD_TIMEOUT).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "article.aditem, li.ad-listitem"))
            )
            time.sleep(2)  # Zusätzliche Wartezeit für dynamische Inhalte

        self._wait_and_retry(_fetch, max_retries=3)

        # Finde alle Anzeigen-Elemente
        ad_elements = driver.find_elements(
            By.CSS_SELECTOR,
            "article.aditem, li.ad-listitem, div.ad-listitem"
        )

        ads = []
        for elem in ad_elements:
            ad = self._parse_ad_element(elem)
            if ad:
                ads.append(ad)

        self.request_count += 1

        # Rate Limiting
        delay = random.uniform(config.REQUEST_DELAY_MIN, config.REQUEST_DELAY_MAX)
        time.sleep(delay)

        logger.info(f"Seite {page}: {len(ads)} Anzeigen gefunden")
        return ads

    def fetch_ads(self) -> List[Dict]:
        """
        Ruft alle Anzeigen von eBay Kleinanzeigen ab.

        Returns:
            Liste von Anzeigen-Dictionaries
        """
        all_ads = []

        try:
            # Scrape erste Seite
            ads = self._fetch_page(page=1)
            all_ads.extend(ads)

            # Scrape weitere Seiten (bis MAX_PAGES_PER_SCAN)
            for page in range(2, config.MAX_PAGES_PER_SCAN + 1):
                if not ads:  # Keine Anzeigen mehr = Ende
                    break

                ads = self._fetch_page(page=page)
                if not ads:
                    break

                all_ads.extend(ads)

            logger.info(f"Gesamt: {len(all_ads)} Anzeigen abgerufen")

        except Exception as e:
            logger.error(f"Fehler beim Scraping: {e}", exc_info=True)

        return all_ads

    def close(self) -> None:
        """Schließt den Scraper und räumt auf."""
        self._close_driver()

