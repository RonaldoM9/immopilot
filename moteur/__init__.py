"""ImmoPilot — moteur d'aide à la décision en investissement immobilier.

Le paquet expose les briques du moteur. Le modèle de langage ne calcule jamais :
il appelle `moteur.dossier.construire()` et met le verdict en mots.

    from moteur import dossier
    dos = dossier.construire({"commune": "Groslay", "prix_demande": 95000, "surface": 30})
    print(dos["verdict"]["verdict"])
"""
from . import analyse, donnees, dossier, financement, fiscalite, verdict  # noqa: F401

__all__ = ["analyse", "donnees", "dossier", "financement", "fiscalite", "verdict"]
__version__ = donnees.VERSION
