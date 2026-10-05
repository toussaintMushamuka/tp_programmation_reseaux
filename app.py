import os
import json
import datetime
from typing import List

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import FileResponse
import jwt

from auth import verifier_identifiants, creer_jeton, decoder_jeton

app = FastAPI(title="Serveur de fichiers d'entreprise")

DOSSIER_STOCKAGE = "stockage"
os.makedirs(DOSSIER_STOCKAGE, exist_ok=True)

# Indique à FastAPI où se trouve la route de login, pour la documentation
# automatique (Swagger) et pour extraire le jeton de l'en-tête Authorization.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# --- Traçabilité : qui a déposé quel fichier (pour vérifier la propriété) ---
FICHIER_PROPRIETAIRES = "proprietaires.json"


def charger_proprietaires():
    if not os.path.exists(FICHIER_PROPRIETAIRES):
        return {}
    with open(FICHIER_PROPRIETAIRES, "r", encoding="utf-8") as f:
        return json.load(f)


def sauvegarder_proprietaires(proprietaires):
    with open(FICHIER_PROPRIETAIRES, "w", encoding="utf-8") as f:
        json.dump(proprietaires, f, indent=2)


# --- Dépendance : extraire et valider l'utilisateur à partir du jeton ---
def utilisateur_courant(jeton: str = Depends(oauth2_scheme)):
    """
    Cette fonction est appelée automatiquement par FastAPI (via Depends)
    avant d'exécuter une route protégée. Elle extrait le jeton de l'en-tête
    "Authorization: Bearer <jeton>", le décode, et retourne les infos
    de l'utilisateur. Si le jeton est invalide, elle lève une erreur 401.
    """
    try:
        payload = decoder_jeton(jeton)
        return {"nom": payload["sub"], "role": payload["role"]}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Jeton expiré")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Jeton invalide")


# --- Gestion des connexions WebSocket actives ---
class GestionnaireConnexions:
    """
    Garde la liste des clients WebSocket connectés, pour pouvoir leur
    diffuser (broadcast) une notification à tous en même temps.
    """

    def __init__(self):
        self.connexions_actives: List[WebSocket] = []

    async def connecter(self, websocket: WebSocket):
        await websocket.accept()
        self.connexions_actives.append(websocket)

    def deconnecter(self, websocket: WebSocket):
        if websocket in self.connexions_actives:
            self.connexions_actives.remove(websocket)

    async def diffuser(self, message: dict):
        """Envoie un message JSON à tous les clients connectés."""
        a_retirer = []
        for connexion in self.connexions_actives:
            try:
                await connexion.send_json(message)
            except Exception:
                a_retirer.append(connexion)
        for connexion in a_retirer:
            self.deconnecter(connexion)


gestionnaire_ws = GestionnaireConnexions()


# ============================================================
# A. API REST
# ============================================================

@app.post("/login")
def login(formulaire: OAuth2PasswordRequestForm = Depends()):
    """
    Vérifie les identifiants et retourne un jeton d'accès.
    OAuth2PasswordRequestForm attend des champs "username" et "password"
    envoyés en x-www-form-urlencoded (standard OAuth2 géré par FastAPI).
    """
    role = verifier_identifiants(formulaire.username, formulaire.password)
    if role is None:
        raise HTTPException(status_code=401, detail="Identifiants incorrects")

    jeton = creer_jeton(formulaire.username, role)
    return {"access_token": jeton, "token_type": "bearer"}


@app.get("/files")
def lister_fichiers(utilisateur: dict = Depends(utilisateur_courant)):
    """Liste les fichiers (nom, taille, date de modification)."""
    fichiers = []
    for nom_fichier in os.listdir(DOSSIER_STOCKAGE):
        chemin = os.path.join(DOSSIER_STOCKAGE, nom_fichier)
        if os.path.isfile(chemin):
            stats = os.stat(chemin)
            fichiers.append({
                "nom": nom_fichier,
                "taille_octets": stats.st_size,
                "date_modification": datetime.datetime.fromtimestamp(
                    stats.st_mtime
                ).isoformat(),
            })
    return {"fichiers": fichiers}


@app.post("/files")
async def televerser_fichier(
    fichier: UploadFile = File(...),
    utilisateur: dict = Depends(utilisateur_courant),
):
    """Téléverse un fichier (multipart/form-data)."""
    chemin_destination = os.path.join(DOSSIER_STOCKAGE, fichier.filename)

    # Écriture du fichier sur le disque, par blocs, pour ne pas charger
    # un très gros fichier entièrement en mémoire d'un coup.
    with open(chemin_destination, "wb") as f:
        while True:
            morceau = await fichier.read(1024 * 1024)  # 1 Mo à la fois
            if not morceau:
                break
            f.write(morceau)

    # On enregistre qui est le propriétaire de ce fichier
    proprietaires = charger_proprietaires()
    proprietaires[fichier.filename] = utilisateur["nom"]
    sauvegarder_proprietaires(proprietaires)

    # Notification WebSocket à tous les clients connectés
    await gestionnaire_ws.diffuser({
        "event": "uploaded",
        "file": fichier.filename,
        "user": utilisateur["nom"],
    })

    return {"message": f"Fichier '{fichier.filename}' téléversé avec succès."}


@app.get("/files/{nom}")
def telecharger_fichier(nom: str, utilisateur: dict = Depends(utilisateur_courant)):
    """Télécharge un fichier."""
    chemin = os.path.join(DOSSIER_STOCKAGE, nom)
    if not os.path.isfile(chemin):
        raise HTTPException(status_code=404, detail="Fichier introuvable")
    return FileResponse(chemin, filename=nom)


@app.delete("/files/{nom}")
async def supprimer_fichier(nom: str, utilisateur: dict = Depends(utilisateur_courant)):
    """Supprime un fichier (réservé au propriétaire ou à l'administrateur)."""
    chemin = os.path.join(DOSSIER_STOCKAGE, nom)
    if not os.path.isfile(chemin):
        raise HTTPException(status_code=404, detail="Fichier introuvable")

    proprietaires = charger_proprietaires()
    proprietaire_du_fichier = proprietaires.get(nom)

    est_proprietaire = proprietaire_du_fichier == utilisateur["nom"]
    est_admin = utilisateur["role"] == "admin"

    if not (est_proprietaire or est_admin):
        raise HTTPException(
            status_code=403,
            detail="Seul le propriétaire du fichier ou un administrateur peut le supprimer.",
        )

    os.remove(chemin)
    proprietaires.pop(nom, None)
    sauvegarder_proprietaires(proprietaires)

    await gestionnaire_ws.diffuser({
        "event": "deleted",
        "file": nom,
        "user": utilisateur["nom"],
    })

    return {"message": f"Fichier '{nom}' supprimé avec succès."}


# ============================================================
# B. WebSocket — notifications temps réel
# ============================================================

@app.websocket("/ws")
async def notifications_websocket(websocket: WebSocket):
    """
    Point d'entrée WebSocket. Tout client connecté ici recevra, en temps
    réel, les notifications JSON envoyées par gestionnaire_ws.diffuser().
    """
    await gestionnaire_ws.connecter(websocket)
    try:
        while True:
            # On ne traite pas forcément les messages entrants du client,
            # mais il faut rester en écoute pour détecter la déconnexion.
            await websocket.receive_text()
    except WebSocketDisconnect:
        gestionnaire_ws.deconnecter(websocket)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
