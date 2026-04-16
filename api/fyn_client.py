"""
api/fyn_client.py
-----------------
Client HTTP qui envoie les offres scrapées vers l'API NestJS de Fyn.

L'API attend les offres en POST sur /offers (ou /scraping/offers selon votre backend).
Chaque offre est envoyée individuellement avec gestion des erreurs et des doublons.
"""

import httpx
from typing import Optional

from scrapers.base_scraper import JobOffer
from config.settings import API_BASE_URL, API_SECRET_KEY
from utils.logger import logger


class FynApiClient:
    """
    Client pour communiquer avec l'API NestJS de Fyn.
    Utilise httpx (async-compatible, plus moderne que requests).
    """

    def __init__(self):
        self.base_url = API_BASE_URL.rstrip("/")
        self.headers = {
            "Content-Type": "application/json",
            "x-api-key": API_SECRET_KEY,   # Header d'authentification
        }

    def send_offer(self, offer: JobOffer) -> bool:
        """
        Envoie une offre unique à l'API NestJS.
        Retourne True si l'envoi est réussi, False sinon.
        """
        endpoint = f"{self.base_url}/offers"
        payload = offer.to_dict()

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(endpoint, json=payload, headers=self.headers)

            if response.status_code == 201:
                logger.debug(f"[API] ✓ Offre créée : {offer.title}")
                return True

            elif response.status_code == 409:
                # 409 Conflict = l'offre existe déjà en base (doublon)
                logger.debug(f"[API] ~ Doublon ignoré : {offer.title}")
                return True  # Pas une erreur, on continue

            else:
                logger.warning(
                    f"[API] ✗ Erreur {response.status_code} pour '{offer.title}' : {response.text}"
                )
                return False

        except httpx.ConnectError:
            logger.error(f"[API] Impossible de joindre l'API ({self.base_url}). Vérifiez que NestJS tourne.")
            return False
        except httpx.TimeoutException:
            logger.error(f"[API] Timeout lors de l'envoi de '{offer.title}'")
            return False
        except Exception as e:
            logger.error(f"[API] Erreur inattendue : {e}")
            return False

    def send_offers_bulk(self, offers: list[JobOffer]) -> dict:
        """
        Envoie une liste d'offres une par une et retourne un résumé.

        Retourne un dict avec :
        - success : nombre d'offres envoyées avec succès
        - failed  : nombre d'échecs
        - total   : total traité
        """
        results = {"success": 0, "failed": 0, "total": len(offers)}

        for offer in offers:
            ok = self.send_offer(offer)
            if ok:
                results["success"] += 1
            else:
                results["failed"] += 1

        logger.info(
            f"[API] Résumé envoi : {results['success']}/{results['total']} offres envoyées "
            f"({results['failed']} échecs)"
        )
        return results

    def health_check(self) -> bool:
        """
        Vérifie que l'API NestJS est bien accessible avant de lancer le scraping.
        Appelle GET /health (endpoint standard NestJS).
        """
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.base_url}/health")
            if response.status_code == 200:
                logger.info("[API] ✓ API Fyn accessible")
                return True
            else:
                logger.warning(f"[API] Health check échoué : {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"[API] API inaccessible : {e}")
            return False

