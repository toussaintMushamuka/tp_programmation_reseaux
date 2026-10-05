# TP Programmation Réseaux — Serveur de fichiers HTTP + WebSocket

Université Catholique de Bukavu — M2 Informatique (IL & SI-RTL)

## 1. Description

Serveur de fichiers en Python (FastAPI + Uvicorn) permettant à des
utilisateurs authentifiés (JWT) de déposer, lister, télécharger et
supprimer des fichiers, avec notifications temps réel par WebSocket.

## 2. Structure du projet

```
tp_fileserver/
├── app.py                  # routes REST + WebSocket
├── auth.py                 # JWT + vérification des mots de passe
├── generer_utilisateur.py  # utilitaire pour hacher un mot de passe
├── utilisateurs.json       # "base de données" des utilisateurs
├── proprietaires.json      # créé automatiquement (propriétaire de chaque fichier)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .gitignore / .dockerignore
└── stockage/                # fichiers déposés par les utilisateurs
```

## 3. Préparer les utilisateurs

```bash
pip install -r requirements.txt
python generer_utilisateur.py
```

Copiez le hash affiché dans `utilisateurs.json`, pour chaque utilisateur :

```json
{
  "alice": { "mot_de_passe_hache": "<hash généré>", "role": "utilisateur" },
  "admin": { "mot_de_passe_hache": "<hash généré>", "role": "admin" }
}
```

## 4. Lancer en local (sans Docker)

```bash
export JWT_SECRET_KEY="une_cle_secrete_aleatoire"
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Documentation interactive : http://localhost:8000/docs

## 5. Lancer en local avec Docker

```bash
export JWT_SECRET_KEY="une_cle_secrete_aleatoire"
docker compose up --build
```

## 6. Déployer sur un serveur distant

### Option A — Render.com (sans Docker, le plus simple)

1. Poussez ce dossier sur un dépôt GitHub.
2. Sur render.com : **New → Web Service**, connectez le dépôt.
3. Build Command : `pip install -r requirements.txt`
4. Start Command : `uvicorn app:app --host 0.0.0.0 --port $PORT`
5. Ajoutez la variable d'environnement `JWT_SECRET_KEY`.
6. Déployez : vous obtenez une URL `https://<nom>.onrender.com`.

### Option B — Render / Railway / Fly.io avec Docker

Ces plateformes détectent automatiquement le `Dockerfile` à la racine :
poussez simplement le dépôt, choisissez "Docker" comme environnement si
demandé, et ajoutez `JWT_SECRET_KEY` dans les variables d'environnement.

**Fly.io (CLI) :**
```bash
fly launch        # détecte le Dockerfile, génère fly.toml
fly secrets set JWT_SECRET_KEY="une_cle_secrete_aleatoire"
fly deploy
```

### Option C — Votre propre VPS (Docker)

```bash
git clone <votre-depot>
cd tp_fileserver
echo "JWT_SECRET_KEY=une_cle_secrete_aleatoire" > .env
docker compose up -d --build
```

Pensez à placer un reverse proxy (Nginx, Caddy) devant le conteneur pour
servir le site en HTTPS (`wss://` pour le WebSocket côté client).

## 7. Notes de sécurité / limites

- Sur les plans gratuits (Render, Railway, Fly.io), le disque est
  généralement éphémère : les fichiers dans `stockage/` disparaissent à
  chaque redéploiement, sauf à utiliser un volume/disque persistant
  (payant chez la plupart des hébergeurs, sauf le volume local en
  Docker Compose sur VPS, qui persiste nativement).
- `JWT_SECRET_KEY` ne doit jamais être commité dans Git ni laissée à sa
  valeur par défaut en production.
