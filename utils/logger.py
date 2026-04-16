"""
utils/logger.py
---------------
Configuration du logger avec loguru.
Les logs s'affichent dans la console ET sont sauvegardés dans logs/scraper.log.
"""

import sys
from loguru import logger

# Supprime le handler par défaut
logger.remove()

# Affichage console (coloré, lisible)
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - {message}",
    level="DEBUG",
    colorize=True,
)

# Fichier de log rotatif (max 5 Mo, garde 7 jours)
logger.add(
    "logs/scraper.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name} - {message}",
    level="INFO",
    rotation="5 MB",
    retention="7 days",
    encoding="utf-8",
)
