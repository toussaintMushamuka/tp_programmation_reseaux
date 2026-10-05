# Image de base légère avec Python 3.11
FROM python:3.11-slim

# Empêche Python de bufferiser stdout/stderr : les logs apparaissent
# immédiatement dans la console de l'hébergeur (utile pour déboguer).
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# On copie d'abord uniquement requirements.txt pour profiter du cache
# Docker : si le code change mais pas les dépendances, l'étape
# "pip install" n'est pas refaite à chaque build.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# On copie ensuite le reste du projet
COPY . .

# Crée le dossier de stockage s'il n'existe pas déjà dans l'image
RUN mkdir -p stockage

# Port d'écoute par défaut à l'intérieur du conteneur.
# La plupart des hébergeurs (Render, Railway, Fly.io) imposent leur
# propre port via la variable d'environnement $PORT au démarrage.
EXPOSE 8000

# Au démarrage : on utilise $PORT si l'hébergeur le fournit, sinon 8000.
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
