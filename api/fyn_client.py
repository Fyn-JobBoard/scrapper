"""
api/fyn_client.py
-----------------
Client HTTP qui envoie les offres scrapées vers l'API NestJS de Fyn.

L'API attend les offres en POST sur /offers (ou /scraping/offers selon votre backend).
Chaque offre est envoyée individuellement avec gestion des erreurs et des doublons.
"""

from httpx import Client as HttpClient
from typing import Optional

from scrapers.base_scraper import JobOffer
from config.settings import API_HOST, API_JWT
from utils.logger import logger


class FynApiClient:
    """
    Client pour communiquer avec l'API NestJS de Fyn.
    Utilise httpx (async-compatible, plus moderne que requests).
    """
    __VERSION = 1
    
    def init(self):
        self.base_url = API_HOST.rstrip("/") + f"/v{self.__VERSION}"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_JWT}"
        }
    
    @property
    def client(self) -> HttpClient:
        return HttpClient(
            base_url=self.base_url
            headers=self.headers
            timeout=10
        )

    def send_offer(self, offer: JobOffer) -> bool:
        """
        Envoie une offre unique à l'API NestJS.
        Retourne True si l'envoi est réussi, False sinon.
        """
        payload = offer.to_dict()

        try:
            with self.client as client:
                response = client.post("/jobs", json=payload)

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
            logger.error(
                f"[API] Impossible de joindre l'API ({self.base_url}). Vérifiez que NestJS tourne.")
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
                response = client.get(self.base_url)
            if response.status_code == 200:
                logger.info("[API] ✓ API Fyn accessible")
                return True
            else:
                logger.warning(
                    f"[API] Health check échoué : {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"[API] API inaccessible : {e}")
            return False
