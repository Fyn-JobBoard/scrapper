from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import re
from utils.helpers import detect_contract_type, clean_text


@dataclass
class JobOffer:
    title: str
    company: str
    location: str
    contract_type: str      
    source: str                
    url: str
    description: str = ""
    salary: Optional[str] = None
    duration: Optional[str] = None
    posted_at: Optional[str] = None
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:

        return {
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "contractType": self.contract_type,
            "source": self.source,
            "sourceUrl": self.url,
            "description": self.description,
            "salary": self.salary,
            "duration": self.duration,
            "postedAt": self.posted_at,
            "tags": self.tags,
        }

@dataclass
class ScraperFilters:

    keywords: str = "stage alternance"   
    location: str = "France"            
    contract_types: list[str] = field(default_factory=lambda: ["stage", "alternance"])
    max_results: int = 50                


class BaseScraper(ABC):

    def __init__(self, filters: ScraperFilters):
        self.filters = filters
        self.offers: list[JobOffer] = []

    @abstractmethod
    def scrape(self) -> list[JobOffer]:
        pass
    def _is_relevant(self, offer: JobOffer) -> bool:
       
        if offer.contract_type == "inconnu":
            offer.contract_type = detect_contract_type(offer.title, offer.description)
        return len(offer.title) < 100 and offer.contract_type in self.filters.contract_types
    
    def _clean_title(self, title: str) -> str:
        """
        Nettoie le titre d'une offre d'emploi en supprimant les informations inutiles.
        Ex: "Alternance - Juin 2026 - Développeur web fullstack sur Paris" -> "Développeur web fullstack"
        """
        cleaned = clean_text(title)
        
        # Supprime les types de contrat au début (Alternance, Stage, CDI, CDD, etc.)
        contract_patterns = [
            r'^(alternance|stage|cdi|cdd|intérim|freelance|apprentissage|contrat pro)\s*[-–—:]?\s*',
            r'^(en|un|une)\s+(alternance|stage|cdi|cdd|intérim|freelance|apprentissage)\s*[-–—:]?\s*'
        ]
        for pattern in contract_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # Supprime les dates (mois + année ou année seule)
        months = 'janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre|janv\.?|févr\.?|avr\.?|juil\.?|août|sept\.?|oct\.?|nov\.?|déc\.?'
        date_patterns = [
            rf'\b({months}\s+\d{{4}})\b',
            rf'\b({months})\s+\d{{4}}$,'
        ]
        for pattern in date_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # Supprime les informations de localisation à la fin (sur Paris, à Lyon, etc.)
        location_patterns = [
            r'\s+sur\s+\w+$',
            r'\s+[àaA]\s+\w+$',
            r'\s+-\s*\w+$',
        ]
        for pattern in location_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # Supprime les mots isolés à la fin qui ressemblent à des villes françaises communes
        common_cities = r'Paris|Lyon|Marseille|Toulouse|Nice|Nantes|Montpellier|Strasbourg|Bordeaux|Lille|Rennes|Reims|Le Mans|Amiens|Aix|Grenoble|Toulon|Angers|Dijon|Brest|Le Havre|Saint-Étienne|Limoges|Tours|Clermont-Ferrand'
        cleaned = re.sub(rf'\s+({common_cities})$', '', cleaned, flags=re.IGNORECASE)
        
        # Supprime les tirets et espaces multiples
        cleaned = re.sub(r'[\s-]+', ' ', cleaned, flags=re.IGNORECASE).strip()
        
        # Supprime les tirets ou séparateurs isolés
        cleaned = re.sub(r'^[\s-]+|[\s-]+$', '', cleaned, flags=re.IGNORECASE)
        
        # Supprime les parenthèses vides
        cleaned = re.sub(r'\s*\(\s*\)\s*', '', cleaned, flags=re.IGNORECASE)
        
        return cleaned
    
    def _clean_offer(self, offer: JobOffer) -> JobOffer:
        offer.title = self._clean_title(offer.title)
        offer.company = clean_text(offer.company)
        offer.location = clean_text(offer.location)
        offer.description = clean_text(offer.description)
        return offer