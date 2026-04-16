"""
config/settings.py
------------------
Charge toutes les variables d'environnement depuis le fichier .env
et les expose comme constantes utilisables dans tout le projet.
"""

import os
from dotenv import load_dotenv

# Charge le fichier .env situé à la racine du projet
load_dotenv()


# --- API NestJS ---
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:3000")
API_SECRET_KEY = os.getenv("API_SECRET_KEY", "")

# --- Comportement du scraper ---
SCRAPER_DELAY = float(os.getenv("SCRAPER_DELAY", 2))          # secondes entre chaque requête
MAX_OFFERS_PER_RUN = int(os.getenv("MAX_OFFERS_PER_RUN", 100)) # limite par session

# --- Playwright ---
PLAYWRIGHT_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"

# --- Headers HTTP communs (pour paraître comme un vrai navigateur) ---
DEFAULT_HEADERS = {
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
