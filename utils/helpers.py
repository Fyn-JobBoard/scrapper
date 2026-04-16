"""
utils/helpers.py
----------------
Fonctions utilitaires partagées entre les scrapers.
"""

import re
import time
import random
from config.settings import SCRAPER_DELAY


def clean_text(text: str) -> str:
    """
    Nettoie une chaîne de caractères :
    - Supprime les espaces multiples
    - Retire les sauts de ligne inutiles
    - Strip les espaces en début/fin
    """
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def random_delay(base: float = None):
    """
    Attend un délai aléatoire autour du délai de base configuré.
    Permet d'éviter les blocages par rate-limiting.
    Ex : délai de 2s → attend entre 1.5s et 3s
    """
    base = base or SCRAPER_DELAY
    delay = random.uniform(base * 0.75, base * 1.5)
    time.sleep(delay)


def detect_contract_type(title: str, description: str = "") -> str:
    """
    Détecte automatiquement si l'offre est un stage ou une alternance
    en analysant le titre et la description.
    Retourne 'stage', 'alternance' ou 'inconnu'.
    """
    text = f"{title} {description}".lower()

    if any(kw in text for kw in ["alternance", "apprentissage", "contrat pro", "apprenti"]):
        return "alternance"
    if any(kw in text for kw in ["stage", "stagiaire", "intern", "internship"]):
        return "stage"

    return "inconnu"
