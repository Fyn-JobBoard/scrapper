import requests
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper, ScraperFilters, JobOffer
from utils.helpers import random_delay, detect_contract_type
from utils.logger import logger

INDEED_URL = "https://fr.indeed.com/jobs"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://fr.indeed.com/",
    "DNT": "1",
}


class IndeedScraper(BaseScraper):

    def __init__(self, filters: ScraperFilters):
        super().__init__(filters)
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def scrape(self) -> list[JobOffer]:
        logger.info(f"[Indeed] Démarrage — mots-clés: '{self.filters.keywords}', lieu: '{self.filters.location}'")

        # Visite la page d'accueil d'abord pour obtenir les cookies
        try:
            self.session.get("https://fr.indeed.com/", timeout=10)
            random_delay(1.5)
        except Exception as e:
            logger.warning(f"[Indeed] Impossible de charger la page d'accueil : {e}")

        current_page = 0

        while len(self.offers) < self.filters.max_results:
            url = self._build_url(current_page)
            logger.debug(f"[Indeed] Page {current_page // 10 + 1} → {url}")

            try:
                response = self.session.get(url, timeout=15)

                if response.status_code != 200:
                    logger.warning(f"[Indeed] Status {response.status_code} — arrêt")
                    break

                new_offers = self._parse_results_page(response.text)

                if not new_offers:
                    logger.info("[Indeed] Aucune offre trouvée sur cette page, arrêt")
                    break

                for offer in new_offers:
                    if len(self.offers) >= self.filters.max_results:
                        break
                    offer = self._clean_offer(offer)
                    if self._is_relevant(offer):
                        self.offers.append(offer)
                        logger.info(f"[Indeed] ✓ {offer.title} — {offer.company}")
                    else:
                        logger.debug(f"[Indeed] ✗ Ignorée : {offer.title}")
                    random_delay()

                current_page += 10

            except requests.Timeout:
                logger.warning("[Indeed] Timeout — arrêt")
                break
            except Exception as e:
                logger.error(f"[Indeed] Erreur : {e}")
                break

        logger.success(f"[Indeed] Terminé — {len(self.offers)} offres collectées")
        return self.offers

    def _build_url(self, start: int = 0) -> str:
        params = (
            f"?q={self.filters.keywords.replace(' ', '+')}"
            f"&l={self.filters.location.replace(' ', '+')}"
            f"&start={start}"
            f"&fromage=14" 
        )
        return INDEED_URL + params

    def _parse_results_page(self, html: str) -> list[JobOffer]:
        soup = BeautifulSoup(html, "lxml")
        cards = soup.select(".job_seen_beacon")
        offers = []

        if not cards:
            # Essaie un sélecteur alternatif
            cards = soup.select("[data-jk]")

        for card in cards:
            try:
                title_el = card.select_one("h2.jobTitle span[title]") or card.select_one("h2.jobTitle")
                company_el = card.select_one("[data-testid='company-name']")
                location_el = card.select_one("[data-testid='text-location']")
                link_el = card.select_one("h2.jobTitle a")

                if not title_el:
                    continue

                title = title_el.get("title") or title_el.get_text()
                url = "https://fr.indeed.com" + link_el.get("href", "") if link_el else ""

                offer = JobOffer(
                    title=title,
                    company=company_el.get_text() if company_el else "Non précisé",
                    location=location_el.get_text() if location_el else self.filters.location,
                    contract_type=detect_contract_type(title),
                    source="indeed",
                    url=url,
                )
                offers.append(offer)

            except Exception as e:
                logger.warning(f"[Indeed] Erreur parsing carte : {e}")
                continue

        return offers