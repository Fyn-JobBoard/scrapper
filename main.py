"""
main.py
-------
Point d'entrée principal du scraper Fyn.

Utilisation :
    python main.py
    python main.py --source indeed --keywords "développeur stage" --location Paris
    python main.py --source linkedin --max 30

Options disponibles :
    --source     : 'indeed', 'linkedin' ou 'all' (défaut: all)
    --keywords   : mots-clés de recherche (défaut: "stage alternance")
    --location   : lieu de recherche (défaut: "France")
    --max        : nombre max d'offres par source (défaut: 50)
    --no-api     : scrape sans envoyer à l'API (utile pour tester)
"""

import argparse
import sys

from scrapers.indeed_scraper import IndeedScraper
from scrapers.linkedin_scraper import LinkedInScraper
from scrapers.base_scraper import ScraperFilters
from api.fyn_client import FynApiClient
from utils.logger import logger


def parse_args():
    """Parse les arguments passés en ligne de commande."""
    parser = argparse.ArgumentParser(
        description="Scraper Fyn — collecte des offres de stage et alternance"
    )
    parser.add_argument(
        "--source",
        choices=["indeed", "linkedin", "all"],
        default="all",
        help="Source à scraper (défaut: all)"
    )
    parser.add_argument(
        "--keywords",
        type=str,
        default="stage alternance",
        help="Mots-clés de recherche (défaut: 'stage alternance')"
    )
    parser.add_argument(
        "--location",
        type=str,
        default="France",
        help="Lieu de recherche (défaut: France)"
    )
    parser.add_argument(
        "--max",
        type=int,
        default=50,
        help="Nombre max d'offres par source (défaut: 50)"
    )
    parser.add_argument(
        "--no-api",
        action="store_true",
        help="Désactive l'envoi vers l'API (mode test)"
    )
    return parser.parse_args()


def run_scraper(source: str, filters: ScraperFilters):
    """Instancie et lance le bon scraper selon la source."""
    scrapers = {
        "indeed": IndeedScraper,
        "linkedin": LinkedInScraper,
    }
    scraper_class = scrapers.get(source)
    if not scraper_class:
        logger.error(f"Source inconnue : {source}")
        return []

    scraper = scraper_class(filters)
    return scraper.scrape()


def main():
    args = parse_args()

    # --- Définit les filtres communs aux deux scrapers ---
    filters = ScraperFilters(
        keywords=args.keywords,
        location=args.location,
        max_results=args.max,
    )

    logger.info("=" * 50)
    logger.info("🚀 Démarrage du scraper Fyn")
    logger.info(f"   Source    : {args.source}")
    logger.info(f"   Mots-clés : {filters.keywords}")
    logger.info(f"   Lieu      : {filters.location}")
    logger.info(f"   Max offres: {filters.max_results} par source")
    logger.info("=" * 50)

    # --- Initialise le client API ---
    api_client = FynApiClient()

    if not args.no_api:
        # Vérifie que l'API est bien disponible avant de commencer
        if not api_client.health_check():
            logger.error("L'API Fyn est inaccessible. Lance NestJS ou utilise --no-api pour tester.")
            sys.exit(1)

    # --- Lance les scrapers selon la source choisie ---
    sources = ["indeed", "linkedin"] if args.source == "all" else [args.source]
    all_offers = []

    for source in sources:
        logger.info(f"\n📡 Scraping {source.upper()}...")
        offers = run_scraper(source, filters)
        all_offers.extend(offers)
        logger.info(f"   → {len(offers)} offres récupérées depuis {source}")

    logger.info(f"\n📦 Total : {len(all_offers)} offres collectées toutes sources confondues")

    # --- Envoie les offres à l'API NestJS ---
    if args.no_api:
        logger.info("Mode --no-api : affichage des offres sans envoi")
        for offer in all_offers:
            logger.info(f"  [{offer.source}] {offer.contract_type.upper()} | {offer.title} @ {offer.company} ({offer.location})")
    else:
        logger.info("\n📤 Envoi des offres vers l'API Fyn...")
        results = api_client.send_offers_bulk(all_offers)
        logger.success(
            f"\n✅ Terminé ! {results['success']} offres envoyées, "
            f"{results['failed']} échecs sur {results['total']} total."
        )


if __name__ == "__main__":
    main()
