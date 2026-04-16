from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
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
        return offer.contract_type in self.filters.contract_types
    
    def _clean_offer(self, offer: JobOffer) -> JobOffer:
        offer.title = clean_text(offer.title)
        offer.company = clean_text(offer.company)
        offer.location = clean_text(offer.location)
        offer.description = clean_text(offer.description)
        return offer