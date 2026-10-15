#!/usr/bin/env python3
"""Retélécharge les données sources du moteur (elles ne sont pas dans le dépôt).

    python3 scripts/telecharge_donnees.py                          # le 95 seul (défaut)
    python3 scripts/telecharge_donnees.py --departements 75,77,78,91,92,93,94,95
    python3 scripts/telecharge_donnees.py --departements 27,60,76 --annees 2023,2024,2025

Prix : DVF (Demandes de valeurs foncières), Etalab/geo-dvf, un fichier compressé par département
et par millésime (environ 1,4 Mo compressé, soit 6 à 10 Mo une fois décompressé).
Loyers : carte des loyers d'annonce du ministère — le fichier couvre déjà toute la France, il n'a
pas d'URL stable : la page du jeu de données est indiquée, à déposer dans donnees/.
"""
import argparse
import os
import subprocess
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GABARIT = "https://files.data.gouv.fr/geo-dvf/latest/csv/{a}/departements/{d}.csv.gz"
PAGE_LOYERS = ("https://www.data.gouv.fr/fr/datasets/"
               "carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025/")
FICHIER_LOYERS = "loyers_12p_2025.csv"


def telecharge(url, chemin):
    """Télécharge un .csv.gz et le décompresse — c'est le format publié par geo-dvf."""
    gz = chemin + ".gz"
    r = subprocess.run(["curl", "-fL", "--max-time", "600", "-o", gz, url],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return False, (r.stderr or "").strip()[:120]
    d = subprocess.run(["gzip", "-dc", gz], capture_output=True)
    if d.returncode != 0:
        return False, "décompression impossible"
    with open(chemin, "wb") as f:
        f.write(d.stdout)
    os.remove(gz)
    return True, ""


def verifie(chemin):
    with open(chemin, encoding="utf-8", errors="replace") as f:
        entete = f.readline().strip()
        n = sum(1 for _ in f)
    ok = "valeur_fonciere" in entete and "surface_reelle_bati" in entete
    return ok, entete[:80], n


def main(argv=None):
    ap = argparse.ArgumentParser(description="Télécharge les données DVF et vérifie l'entête.")
    ap.add_argument("--departements", default="95",
                    help="codes séparés par des virgules, ex. 75,77,78,91,92,93,94,95")
    ap.add_argument("--annees", default="2021,2022,2023,2024,2025")
    ap.add_argument("--dossier", default=os.path.join(RACINE, "donnees"))
    a = ap.parse_args(argv)

    departements = [d.strip() for d in a.departements.split(",") if d.strip()]
    annees = [int(x) for x in a.annees.split(",") if x.strip()]
    os.makedirs(a.dossier, exist_ok=True)
    print(f"départements : {', '.join(departements)} · millésimes : {annees}")

    echecs, telecharges = 0, 0
    for dep in departements:
        for annee in annees:
            chemin = os.path.join(a.dossier, f"dvf{dep}_{annee}.csv")
            if os.path.exists(chemin) and os.path.getsize(chemin) > 100_000:
                print(f"  {dep} {annee} : déjà présent")
                continue
            print(f"  {dep} {annee} : téléchargement…", end=" ", flush=True)
            ok, err = telecharge(GABARIT.format(a=annee, d=dep), chemin)
            if not ok:
                print(f"échec ({err})")
                echecs += 1
                continue
            ok, entete, n = verifie(chemin)
            print(f"{n:,} lignes" + ("" if ok else f" — ENTÊTE INATTENDUE : {entete}"))
            echecs += 0 if ok else 1
            telecharges += 1

    chemin_loyers = os.path.join(a.dossier, FICHIER_LOYERS)
    if os.path.exists(chemin_loyers):
        print(f"  loyers : {FICHIER_LOYERS} présent (couvre la France entière)")
    else:
        print(f"  loyers : MANQUANT — à télécharger sur\n    {PAGE_LOYERS}\n"
              f"    puis à déposer dans donnees/ sous le nom {FICHIER_LOYERS}")
        echecs += 1

    print(f"\n{telecharges} fichier(s) téléchargé(s). "
          + ("Aucun problème." if not echecs else f"{echecs} problème(s)."))
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
