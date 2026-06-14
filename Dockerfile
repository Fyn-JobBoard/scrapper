# Image Python 3.13 légère
FROM python:3.13-slim AS prod

# Installe les dépendances système nécessaires à Playwright/Chromium
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gnupg \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2

# Dossier de travail dans le conteneur
WORKDIR /app
COPY requirements.txt .

# Installe Chromium pour Playwright
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium
RUN playwright install-deps chromium

# Copie et installe les dépendances Python
# Le fait de copier après l'installation permet une meilleur mise en cache
COPY . .

# Commande par défaut
ENTRYPOINT [ "python", "main.py" ]
