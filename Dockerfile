# Image Python 3.13 légère
FROM python:3.13-slim

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

# Copie et installe les dépendances Python
COPY . .
RUN pip install --no-cache-dir -r requirements.txt

# Installe Chromium pour Playwright
RUN playwright install chromium
RUN playwright install-deps chromium

# Commande par défaut
ENTRYPOINT [ "python", "main.py" ]
