"""
scrapers/linkedin_scraper.py
-----------------------------
Scraper pour LinkedIn Jobs (offres publiques, sans connexion requise).

Stratégie :
- On utilise l'URL publique LinkedIn Jobs qui ne nécessite pas de compte
- Playwright charge la page avec le JS rendu
- BeautifulSoup parse les cartes d'offres
- On récupère la description depuis le panneau latéral ou la page détail
"""

from urllib.parse import urlparse, urljoin

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper, ScraperFilters, JobOffer
from config.settings import PLAYWRIGHT_HEADLESS
from utils.helpers import random_delay, detect_contract_type
from utils.logger import logger


# URL publique LinkedIn Jobs (pas besoin de compte)
LINKEDIN_BASE_URL = "https://www.linkedin.com/jobs/search"


class LinkedInScraper(BaseScraper):
    """
    Scraper LinkedIn Jobs — hérite de BaseScraper.
    Cible les offres publiques accessibles sans authentification.
    """

    def __init__(self, filters: ScraperFilters):
        super().__init__(filters)

    def scrape(self) -> list[JobOffer]:
        """
        Point d'entrée principal.
        Lance Playwright, fait défiler la liste d'offres et collecte les données.
        """
        logger.info(
            f"[LinkedIn] Démarrage du scraping — mots-clés: '{self.filters.keywords}', lieu: '{self.filters.location}'")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=PLAYWRIGHT_HEADLESS)
            page = browser.new_page()

            page.set_extra_http_headers({
                "Accept-Language": "fr-FR,fr;q=0.9",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
            })

            url = self._build_url()
            logger.debug(f"[LinkedIn] Chargement URL : {url}")

            try:
                page.goto(url, timeout=15000)
                page.wait_for_selector(
                    ".jobs-search__results-list", timeout=12000)
            except PlaywrightTimeout:
                logger.error(
                    "[LinkedIn] Impossible de charger la page de résultats")
                browser.close()
                return []

            # LinkedIn charge les offres en lazy loading → on scroll pour les afficher
            self._scroll_to_load(page)

            html = page.content()
            raw_offers = self._parse_results_page(html)
            logger.debug(f"[LinkedIn] {len(raw_offers)} cartes détectées")

            for offer in raw_offers:
                if len(self.offers) >= self.filters.max_results:
                    break

                offer = self._fetch_description(page, offer)
                offer = self._clean_offer(offer)

                if self._is_relevant(offer):
                    self.offers.append(offer)
                    logger.info(
                        f"[LinkedIn] ✓ Offre trouvée : {offer.title} — {offer.company}")
                else:
                    logger.debug(f"[LinkedIn] ✗ Offre ignorée : {offer.title}")

                random_delay()

            browser.close()

        logger.success(
            f"[LinkedIn] Scraping terminé — {len(self.offers)} offres collectées")
        return self.offers

    # -------------------------------------------------------------------------
    # Méthodes privées
    # -------------------------------------------------------------------------

    def _build_url(self) -> str:
        """
        Construit l'URL de recherche LinkedIn.
        f_E=1%2C3 = filtres secteur étudiant (optionnel)
        f_JT=I = Internship (stage), f_JT=O = Other peut inclure alternance
        """
        keywords = self.filters.keywords.replace(" ", "%20")
        location = self.filters.location.replace(" ", "%20")
        return (
            f"{LINKEDIN_BASE_URL}?"
            f"keywords={keywords}"
            f"&location={location}"
            f"&f_JT=I"          # Filtre type : Internship (stage/alternance)
            f"&sortBy=DD"        # Tri par date décroissante
        )

    def _scroll_to_load(self, page):
        """
        Fait défiler la page progressivement pour déclencher
        le chargement lazy des offres LinkedIn.
        """
        for _ in range(5):
            page.evaluate("window.scrollBy(0, 800)")
            random_delay(0.8)

    def _parse_results_page(self, html: str) -> list[JobOffer]:
        """
        Parse la liste des offres depuis la page de résultats LinkedIn.
        Retourne des offres partielles (sans description).
        """
        soup = BeautifulSoup(html, "lxml")
        cards = soup.select(".jobs-search__results-list li")
        offers = []

        for card in cards:
            try:
                title_el = card.select_one(".base-search-card__title")
                company_el = card.select_one(".base-search-card__subtitle")
                location_el = card.select_one(".job-search-card__location")
                link_el = card.select_one("a.base-card__full-link")
                date_el = card.select_one("time")

                if not title_el or not link_el:
                    continue

                url = link_el.get("href", "")
                url = urljoin(url, urlparse(url).path)

                offer = JobOffer(
                    title=title_el.text,
                    company=company_el.text if company_el else "Non précisé",
                    location=location_el.text if location_el else self.filters.location,
                    contract_type=detect_contract_type(title_el.text),
                    source="linkedin",
                    url=url,
                    posted_at=date_el.get("datetime") if date_el else None,
                )
                offers.append(offer)

            except Exception as e:
                logger.warning(f"[LinkedIn] Erreur parsing carte : {e}")
                continue

        return offers

    def _fetch_description(self, page, offer: JobOffer) -> JobOffer:
        """
        Ouvre la page détail de l'offre LinkedIn pour récupérer la description.
        """
        if not offer.url:
            return offer

        try:
            page.goto(offer.url, timeout=12000)
            page.wait_for_selector(
                ".show-more-less-html__markup", timeout=8000)

            html = page.content()
            soup = BeautifulSoup(html, "lxml")

            desc_el = soup.select_one(".show-more-less-html__markup")
            if desc_el:
                offer.description = desc_el.get_text(separator=" ")

            # Récupère le type de contrat depuis la section critères LinkedIn
            criteria = soup.select(".description__job-criteria-item")
            for item in criteria:
                label_el = item.select_one(
                    ".description__job-criteria-subheader")
                value_el = item.select_one(".description__job-criteria-text")
                if label_el and value_el:
                    label = label_el.text.strip().lower()
                    value = value_el.text.strip()
                    if "type" in label:
                        offer.contract_type = detect_contract_type(
                            value, offer.description)
                    if "durée" in label or "duration" in label:
                        offer.duration = value

        except PlaywrightTimeout:
            logger.warning(
                f"[LinkedIn] Timeout sur la page détail : {offer.url}")
        except Exception as e:
            logger.warning(f"[LinkedIn] Erreur description : {e}")

        return offer
