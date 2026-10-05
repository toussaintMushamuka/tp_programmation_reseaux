"""
Petit utilitaire pour générer le hash bcrypt d'un mot de passe, à coller
dans utilisateurs.json. À exécuter en local, jamais sur le serveur de
production (il ne fait qu'afficher le hash, il ne touche à aucun fichier).

Usage :
    python generer_utilisateur.py
"""

from auth import hacher_mot_de_passe

if __name__ == "__main__":
    mot_de_passe = input("Mot de passe à hacher : ")
    print("\nHash bcrypt à copier dans utilisateurs.json :\n")
    print(hacher_mot_de_passe(mot_de_passe))
