"""
api/fyn_client.py
-----------------
Client HTTP qui envoie les offres scrapées vers l'API NestJS de Fyn.

L'API attend les offres en POST sur /v1/jobs selon le schema OpenAPI.
Chaque offre est envoyée individuellement avec gestion des erreurs et des doublons.
"""

import httpx
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

    def __init__(self):
        self.base_url = API_HOST.rstrip("/") + f"/v{self.__VERSION}"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_JWT}"
        }

    @property
    def client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            headers=self.headers,
            timeout=10
        )

    def _map_contract_type(self, contract_type: str) -> str:
        """Mappe le type de contrat du scraper vers les valeurs attendues par l'API."""
        mapping = {
            "stage": "stage",
            "alternance": "alternating_stage",
            "internship": "internship",
            "alternating_stage": "alternating_stage",
        }
        return mapping.get(contract_type.lower(), "stage")

    def _map_mode(self, location: str) -> str:
        """Détermine le mode de travail (remote, onsite, hybrid) depuis la localisation."""
        location_lower = location.lower()
        if "remote" in location_lower or "télétravail" in location_lower:
            return "remote"
        elif "hybrid" in location_lower or "hybride" in location_lower:
            return "hybrid"
        else:
            return "onsite"

    def _map_remuneration_period(self, salary: Optional[str]) -> tuple[Optional[float], str]:
        """Extrait la rémunération et sa période depuis le salaire."""
        if not salary:
            return None, "monthly"

        salary_lower = salary.lower()

        # Par défaut, mensuel
        period = "monthly"

        # Détecter la période
        if any(p in salary_lower for p in ["jour", "day", "/j"]):
            period = "dayly"
        elif any(p in salary_lower for p in ["semaine", "week", "/s"]):
            period = "weekly"
        elif any(p in salary_lower for p in ["an", "year", "annuel", "/a"]):
            period = "annualy"

        # Extraire le montant numérique
        import re
        amounts = re.findall(r'[\d,]+(\.\d+)?', salary)
        if amounts:
            # Prendre le premier montant trouvé et le convertir en float
            try:
                amount = float(amounts[0].replace(',', '.'))
                return amount, period
            except ValueError:
                pass

        return None, period

    def _parse_duration(self, duration: Optional[str]) -> tuple[Optional[int], Optional[int]]:
        """
        Parse la durée de l'offre.
        Retourne (period_duration en mois, min_formation_duration en mois).
        """
        if not duration:
            return None, None

        duration_lower = duration.lower()

        # period_duration: durée du stage en mois
        period_duration = None
        # min_formation_duration: durée minimale de formation requise en mois
        min_formation_duration = None

        # Essayer de trouver des nombres suivis de "mois" ou "months"
        import re

        # Chercher des patterns comme "3 mois", "6 months", "12m", etc.
        month_patterns = re.findall(
            r'(\d+)\s*(mois|months|m)\b', duration_lower)
        if month_patterns:
            for num, unit in month_patterns:
                if unit.startswith('m'):
                    period_duration = int(num)
                    break

        # Chercher des patterns pour la formation minimale
        # Si non trouvé, essayer de deviner à partir du type de contrat
        if period_duration is None:
            # Durée par défaut selon le type de contrat
            # C'est une estimation grossière
            pass

        return period_duration, min_formation_duration

    def _build_payload(self, offer: JobOffer) -> dict:
        """Construis le payload conforme au schema CreateJobDto de l'API Fyn."""
        remuneration, remuneration_period = self._map_remuneration_period(
            offer.salary)
        period_duration, min_formation_duration = self._parse_duration(
            offer.duration)

        payload = {
            "title": offer.title,
            "description": offer.description if offer.description else "",
            "apply_link": offer.url,
            # Par défaut français, à adapter si nécessaire
            "languages": ["fr"],
            "mode": self._map_mode(offer.location),
            "scrapped_from": offer.source,
            "remuneration": remuneration if remuneration is not None else 0,
            "remuneration_period": remuneration_period,
            "contract": self._map_contract_type(offer.contract_type),
            "period_start": offer.posted_at if offer.posted_at else None,
            # 6 mois par défaut
            "period_duration": period_duration if period_duration is not None else 6,
            "min_formation_duration": min_formation_duration if min_formation_duration is not None else 0,
            "active": True,
            "activity_domain_id": 1,  # ID par défaut, à adapter selon la logique métier
            "moderation_feedback": None,
        }

        # Filtrer les valeurs None pour éviter de les envoyer
        # Mais certains champs sont requis, donc on garde les valeurs par défaut
        return payload

    def send_offer(self, offer: JobOffer) -> bool:
        """
        Envoie une offre unique à l'API NestJS.
        Retourne True si l'envoi est réussi, False sinon.
        """
        payload = self._build_payload(offer)

        try:
            with self.client as client:
                response = client.post("/jobs", json=payload)

            if response.status_code == 200:
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
        Appelle GET /v1 (endpoint de ping de l'API Fyn).
        """
        try:
            with self.client as client:
                response = client.get("/")
            ok = response.status_code == 200

            if ok:
                logger.info("[API] ✓ API Fyn accessible")
            else:
                logger.warning(
                    f"[API] Health check échoué : {response.status_code}")

            return ok
        except Exception as e:
            logger.error(f"[API] API inaccessible : {e}")
            return False
