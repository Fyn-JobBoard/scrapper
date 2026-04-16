# 🎓 Fyn Scraper

Module de scraping des offres de **stages et alternances** depuis **LinkedIn** (et Indeed), développé dans le cadre de la plateforme **Fyn**.

Les offres collectées sont envoyées automatiquement à l'API NestJS de Fyn pour être enregistrées dans la base de données PostgreSQL.

> Projet développé en équipe de 3 développeurs. Ce module couvre la partie **scraping et intégration API**.

---

##  Structure du projet

```
fyn-scraper/
│
├── scrapers/
│   ├── base_scraper.py        # Classe abstraite + modèles JobOffer et ScraperFilters
│   ├── indeed_scraper.py      # Scraper Indeed (bloqué côté serveur, voir limitations)
│   └── linkedin_scraper.py    # Scraper LinkedIn fonctionnel
│
├── api/
│   └── fyn_client.py          # Client HTTP vers l'API NestJS
│
├── config/
│   └── settings.py            # Chargement des variables d'environnement
│
├── utils/
│   ├── helpers.py             # Fonctions utilitaires (nettoyage texte, délai, détection contrat)
│   └── logger.py              # Configuration des logs (console + fichier rotatif)
│
├── logs/                      # Fichiers de log générés automatiquement au lancement
│
├── main.py                    # Point d'entrée — orchestre le scraping
├── requirements.txt           # Dépendances Python
├── .env.example               # Modèle de configuration (copier en .env)
└── .gitignore
```

---

## ⚙️ Installation

### Prérequis

- Python **3.11+** (testé sur Python 3.13)
- Node.js (requis par Playwright en arrière-plan)

### 1. Cloner le repo

```bash
git clone https://github.com/<ton-username>/fyn-scraper.git
cd fyn-scraper
```

### 2. Créer un environnement virtuel

```bash
python -m venv venv
```

L'activer :

```bash
# Windows
venv\Scripts\activate

# Mac / Linux
source venv/bin/activate
```

Tu dois voir `(venv)` apparaître au début de la ligne dans le terminal.

### 3. Installer les dépendances

```bash
pip install playwright beautifulsoup4 httpx python-dotenv lxml fake-useragent loguru requests
```

> ⚠️ Ne pas utiliser directement `pip install -r requirements.txt` si tu es sur Python 3.13 — certaines versions fixées sont incompatibles. La commande ci-dessus laisse pip choisir les bonnes versions automatiquement.

Une fois installé, régénère le fichier requirements avec les versions réelles :

```bash
pip freeze > requirements.txt
```

### 4. Installer le navigateur Chromium (pour Playwright)

```bash
playwright install chromium
```

### 5. Configurer les variables d'environnement

```bash
# Windows
copy .env.example .env

# Mac / Linux
cp .env.example .env
```

Puis édite le fichier `.env` :

```env
API_BASE_URL=http://localhost:3000       # URL de l'API NestJS
API_SECRET_KEY=your_secret_key_here     # Clé partagée avec le backend
SCRAPER_DELAY=2                         # Délai en secondes entre chaque requête
MAX_OFFERS_PER_RUN=100                  # Limite d'offres par session
PLAYWRIGHT_HEADLESS=true                # Mettre false pour voir le navigateur s'ouvrir
```

> ⚠️ Ne jamais commiter le fichier `.env` — il est dans le `.gitignore`.

---

##  Utilisation

### Tester sans envoyer à l'API (recommandé pour commencer)

```bash
python main.py --source linkedin --max 5 --no-api
```

### Scraper LinkedIn uniquement

```bash
python main.py --source linkedin
```

### Scraper avec des filtres personnalisés

```bash
python main.py --source linkedin --keywords "développeur web stage" --location Paris --max 30
```

### Scraper toutes les sources

```bash
python main.py
```

## 🔗 Format d'envoi à l'API NestJS

Chaque offre est envoyée en **POST** sur `/offers` avec ce corps JSON :

```json
{
  "title": "Alternance - Assistant(e) Revue de presse (F/H)",
  "company": "GIVENCHY",
  "location": "Paris, France",
  "contractType": "alternance",
  "source": "linkedin",
  "sourceUrl": "https://www.linkedin.com/jobs/view/...",
  "description": "Nous recherchons un(e) alternant(e)...",
  "salary": null,
  "duration": "12 mois",
  "postedAt": "2026-04-10",
  "tags": []
}
```

### Codes de réponse attendus côté NestJS

| Code | Signification |
|------|---------------|
| `201 Created` | Offre créée avec succès |
| `409 Conflict` | Doublon — offre déjà présente en base |
| `401 Unauthorized` | Clé API incorrecte |
| `500` | Erreur serveur NestJS |

---

## ⚠️ Limitations connues

### Indeed — bloqué (erreur 403)

Indeed protège agressivement son site contre le scraping automatique depuis 2024. Le scraper Indeed est présent dans le code mais retourne 0 résultats car Indeed bloque les requêtes avec un code 403.

**Solutions envisagées pour la production :**
- **Indeed Publisher API** (officielle et gratuite) : https://ads.indeed.com/jobroll/xmlfeed
- **ScraperAPI** ou **BrightData** (services tiers payants) pour contourner le blocage

### LinkedIn — fonctionnel 

Le scraper LinkedIn cible les offres publiques accessibles sans compte. Il fonctionne correctement en local (testé : 5 offres récupérées en ~90 secondes).



##  Stack technique

| Outil | Rôle |
|-------|------|
| Python 3.13 | Langage principal |
| Playwright | Navigation et rendu JavaScript |
| BeautifulSoup4 | Parsing HTML |
| httpx | Requêtes HTTP vers l'API NestJS |
| requests | Requêtes HTTP simples (Indeed) |
| loguru | Logs colorés en console + fichier rotatif |
| python-dotenv | Gestion des variables d'environnement |

---

## 👥 Architecture du projet Fyn

Ce module s'intègre dans l'architecture globale :

```
fyn-scraper (Python)
       │
       │  POST /offers (JSON)
       ▼
  API NestJS  ──────────────►  PostgreSQL
       │
       │
  fyn-frontend 
```