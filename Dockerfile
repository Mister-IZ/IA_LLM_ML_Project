# Image de base Python
FROM python:3.12-slim

# Définir le répertoire de travail
WORKDIR /app

# Copier les dépendances
COPY requirements.txt .

# Installer les dépendances
RUN pip install --no-cache-dir -r requirements.txt

# Copier tout le code de l'application
COPY . .

# Exposer le port Flask
EXPOSE 5000

# Variable d'environnement pour Flask
ENV FLASK_APP=newapp.py
ENV FLASK_ENV=production

# Commande de démarrage
CMD ["python", "newapp.py"]
