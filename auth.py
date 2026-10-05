import json
import os
import datetime
import jwt
import bcrypt

# --- Configuration JWT ---
# Clé secrète utilisée pour signer les jetons : lue depuis une variable
# d'environnement en production (jamais laissée en dur dans le code déployé).
CLE_SECRETE = os.environ.get("JWT_SECRET_KEY", "cle_de_secours_dev_uniquement")
ALGORITHME = "HS256"
DUREE_VALIDITE_MINUTES = 60

FICHIER_UTILISATEURS = "utilisateurs.json"

# NB : on utilise directement le module "bcrypt" plutôt que "passlib",
# car passlib (non maintenu depuis 2020) est incompatible avec les
# versions récentes de bcrypt (>= 4.1) qui ont supprimé l'attribut
# interne sur lequel passlib s'appuyait pour détecter sa version.


def hacher_mot_de_passe(mot_de_passe):
    """Retourne le hash bcrypt (str) d'un mot de passe en clair."""
    sel = bcrypt.gensalt()
    return bcrypt.hashpw(mot_de_passe.encode("utf-8"), sel).decode("utf-8")


def charger_utilisateurs():
    """Lit le fichier JSON des utilisateurs et le retourne sous forme de dict."""
    with open(FICHIER_UTILISATEURS, "r", encoding="utf-8") as fichier:
        return json.load(fichier)


def verifier_identifiants(nom_utilisateur, mot_de_passe):
    """
    Vérifie que l'utilisateur existe et que le mot de passe fourni
    correspond au hash stocké. Retourne le rôle de l'utilisateur si
    c'est le cas, sinon None.
    """
    utilisateurs = charger_utilisateurs()
    utilisateur = utilisateurs.get(nom_utilisateur)
    if utilisateur is None:
        return None

    hash_stocke = utilisateur["mot_de_passe_hache"].encode("utf-8")
    if not bcrypt.checkpw(mot_de_passe.encode("utf-8"), hash_stocke):
        return None
    return utilisateur["role"]


def creer_jeton(nom_utilisateur, role):
    """
    Construit un jeton JWT signé, contenant le nom d'utilisateur, son rôle,
    et une date d'expiration.
    """
    expiration = datetime.datetime.utcnow() + datetime.timedelta(
        minutes=DUREE_VALIDITE_MINUTES
    )
    payload = {
        "sub": nom_utilisateur,   # "subject" : à qui appartient ce jeton
        "role": role,
        "exp": expiration,        # date d'expiration, vérifiée automatiquement par pyjwt
    }
    return jwt.encode(payload, CLE_SECRETE, algorithm=ALGORITHME)


def decoder_jeton(jeton):
    """
    Décode et vérifie un jeton JWT. Lève une exception si le jeton est
    invalide, expiré ou falsifié.
    """
    return jwt.decode(jeton, CLE_SECRETE, algorithms=[ALGORITHME])
