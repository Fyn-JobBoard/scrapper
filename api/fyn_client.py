"""
api/fyn_client.py
-----------------
Client HTTP qui envoie les offres scrapées vers l'API NestJS de Fyn.

L'API attend les offres en POST sur /v1/jobs selon le schema OpenAPI.
Chaque offre est envoyée individuellement avec gestion des erreurs et des doublons.
"""

from typing import Optional
from datetime import datetime
from string import ascii_letters, digits, punctuation
from secrets import choice
from random import randint
import re
import httpx

from scrapers.base_scraper import JobOffer
from config.settings import API_HOST, API_JWT
from utils.logger import logger

VALID_PASSWORD_CHARS = ascii_letters, digits, punctuation


class FynApiClient:
    """
    Client pour communiquer avec l'API NestJS de Fyn.
    Utilise httpx (async-compatible, plus moderne que requests).
    """
    __VERSION = 1

    @staticmethod
    def _get_company_email(name: str):
        return f"{name.lower().replace(' ', '.')}@scraper.fyn.com"

    @staticmethod
    def _get_new_company_logins(name: str):
        """Génère un objet {email, password} valide pour l'API en fonction du nom de l'entreprise

        Args:
            name (str): Le nom de l'entreprise à qui créer les identifiants

        Returns:
            {
                "email": "<name>@scraper.fyn.com",
                "password": "(7+ chars, 1+ symbole, 1+ chiffre)"
            }
        """
        email = FynApiClient._get_company_email(name)

        password = ""
        size = randint(7, 12)
        while (
            not password
            or not any(c.isdigit() for c in password)
            or not any(c in punctuation for c in password)
        ):
            password = ''.join(
                choice(VALID_PASSWORD_CHARS)
                for _ in range(size)
            )

        return {"email": email, "password": password}

    def __init__(self):
        self.base_url = API_HOST.rstrip("/") + f"/v{self.__VERSION}"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_JWT}"
        }

    @property
    def client(self) -> httpx.Client:
        """Return a new httpx Client with correct authorization & base url
        """
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
            offer.salary
        )
        period_duration, min_formation_duration = self._parse_duration(
            offer.duration
        )

        payload = {
            "title": offer.title,
            "description": offer.description if offer.description else "",
            "apply_link": offer.url,
            # Par défaut français, à adapter si nécessaire
            "languages": ["fr"],
            "mode": self._map_mode(offer.location),
            "scrapped_from": offer.url,
            "remuneration": remuneration if remuneration is not None else 0,
            "remuneration_period": remuneration_period,
            "contract": self._map_contract_type(offer.contract_type),
            "period_start": offer.posted_at if offer.posted_at else None,
            # 6 mois par défaut
            "period_duration": period_duration if period_duration is not None else 6,
            "min_formation_duration": min_formation_duration,
            "active": True,
            "activity_domain_id": self._get_or_create_activity_domain(offer.company),
            "moderation_feedback": None,
        }

        # Filtrer les valeurs None pour éviter de les envoyer
        # Mais certains champs sont requis, donc on garde les valeurs par défaut
        return payload

    def _job_exists(self, offer: JobOffer) -> bool:
        """Vérifie si une offre avec le même titre existe déjà dans l'API."""
        try:
            with self.client as client:
                response = client.get(
                    "/jobs",
                    params={"limit": 1, "search": offer.title}
                )
            if response.status_code == 200:
                data = response.json()
                # Si la liste n'est pas vide, l'offre existe
                return len(data.get("list", [])) > 0
            return False
        except Exception as e:
            logger.warning(
                f"[API] Erreur lors de la vérification de l'offre : {e}")
            # En cas d'erreur, on considère que l'offre n'existe pas pour éviter de bloquer
            return False

    def _company_exists(self, company_name: str) -> Optional[str]:
        """Recherche une entreprise par nom. Retourne son ID si trouvée, None sinon."""
        try:
            with self.client as client:
                response = client.get(
                    "/accounts/companies",
                    params={"limit": 1,
                            "search": self._get_company_email(company_name)}
                )
            if response.status_code == 200:
                data = response.json()
                companies = data.get("list", [])
                if companies:
                    return companies[0].get("id")
            return None
        except Exception as e:
            logger.warning(
                f"[API] Erreur lors de la recherche de l'entreprise {company_name} : {e}")
            return None

    def _get_or_create_activity_domain(self, domain_name: str) -> int:
        """Trouve ou crée un domaine d'activité. Retourne son ID."""
        try:
            with self.client as client:
                # Rechercher le domaine
                response = client.get(
                    "/activity-domains",
                    params={"limit": 1, "query": domain_name}
                )
            if response.status_code == 200:
                data = response.json()
                domains = data.get("list", [])
                if domains:
                    return domains[0].get("id")

            # Créer le domaine s'il n'existe pas
            try:
                with self.client as client:
                    response = client.post(
                        "/activity-domains",
                        json={"name": domain_name},
                    )
                if response.status_code in (200, 201):
                    domain = response.json()
                    return domain.get("id")

            except httpx.HTTPError as e:
                logger.error(
                    f"[API] Erreur lors de la création du domaine {domain_name} : {e}")
        except httpx.HTTPError as e:
            logger.error(
                f"[API] Erreur lors de la recherche du domaine {domain_name} : {e}")

    def _create_company(self, company_name: str, offer: JobOffer) -> Optional[str]:
        """Crée une nouvelle entreprise avec les informations de l'offre."""
        # Extraire un nom de domaine à partir du nom de l'entreprise
        # On utilise une logique simple : premier mot ou nom complet
        domain_name = company_name.split()[0] if company_name else "Inconnu"

        # Obtenir l'ID du domaine d'activité
        activity_domain_id = self._get_or_create_activity_domain(domain_name)
        if activity_domain_id is None:
            logger.error(
                f"Unable to get the activity domain for '{domain_name}'.")
            return None

        payload = {
            "company": {
                "name": company_name,
                "creation_date": datetime.now().isoformat(),
                "activity_domain_id": activity_domain_id,
                "scrapped_from": offer.url,
            }
        } | self._get_new_company_logins(company_name)

        try:
            with self.client as client:
                response = client.post("/accounts", json=payload)
            if response.status_code in (200, 201):
                company_data = response.json()
                logger.debug(f"[API] ✓ Entreprise créée : {company_name}")
                return company_data.get("account", {}).get("id")
            else:
                logger.warning(
                    f"[API] ✗ Erreur {response.status_code} lors de la création de l'entreprise {company_name} : {response.text}"
                )
                return None
        except Exception as e:
            logger.error(
                f"[API] Erreur lors de la création de l'entreprise {company_name} : {e}")
            return None

    def send_offer(self, offer: JobOffer) -> bool:
        """
        Envoie une offre unique à l'API NestJS.

        Logique:
        1. Vérifie que l'offre n'existe pas déjà
        2. Trouve ou crée l'entreprise associée
        3. Envoie l'offre avec l'ID de l'entreprise

        Retourne True si l'envoi est réussi, False sinon.
        """
        # 1. Vérifier que l'offre n'existe pas déjà
        if self._job_exists(offer):
            logger.debug(f"[API] ~ Offre existe déjà : {offer.title}")
            return True

        # 2. Trouver ou créer l'entreprise
        company_id = self._company_exists(offer.company)
        if not company_id:
            company_id = self._create_company(offer.company, offer)
            if not company_id:
                logger.error(
                    f"[API] ✗ Impossible de créer l'entreprise pour {offer.title}")
                return False

        # 3. Envoyer l'offre
        payload = self._build_payload(offer)

        try:
            with self.client as client:
                response = client.post(f"/jobs/{company_id}", json=payload)

            if response.status_code in (200, 201):
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
                response = client.get("/accounts/me")
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
