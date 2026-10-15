#!/usr/bin/env python3
"""Retélécharge les données sources du moteur (elles ne sont pas dans le dépôt : 52 Mo).

    python3 scripts/telecharge_donnees.py

Prix : DVF (Demandes de valeurs foncières), Etalab/geo-dvf, fichier départemental par millésime.
Loyers : carte des loyers d'annonce du ministère chargé du Logement — le fichier n'a pas d'URL
stable, la page du jeu de données est indiquée ; déposer le CSV dans donnees/ sous le nom attendu.
"""
import os
import subprocess
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DONNEES = os.path.join(RACINE, "donnees")
ANNNEES = (2021, 2022, 2023, 2024, 2025)
DEPARTEMENT = "95"
# Les fichiers departementaux sont publies compresses (.csv.gz) sur geo-dvf.
GABARIT = "https://files.data.gouv.fr/geo-dvf/latest/csv/{a}/departements/{d}.csv.gz"
PAGE_LOYERS = ("https://www.data.gouv.fr/fr/datasets/"
               "carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025/")
ATTENDU_LOYERS = "loyers_12p_2025.csv"


def telecharge(url, chemin):
    """Télécharge un .csv.gz et le décompresse — c'est le format publié par geo-dvf."""
    gz = chemin + ".gz"
    r = subprocess.run(["curl", "-fL", "--max-time", "600", "-o", gz, url],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return False, (r.stderr or "").strip()[:120]
    d = subprocess.run(["gzip", "-dc", gz], capture_output=True)
    if d.returncode != 0:
        return False, "decompression impossible"
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


def main():
    global DONNEES
    if len(sys.argv) > 1:
        DONNEES = sys.argv[1]
    os.makedirs(DONNEES, exist_ok=True)
    echecs = 0
    for annee in ANNNEES:
        chemin = os.path.join(DONNEES, f"dvf{DEPARTEMENT}_{annee}.csv")
        if os.path.exists(chemin) and os.path.getsize(chemin) > 100_000:
            ok, entete, n = verifie(chemin)
            print(f"  {annee} : déjà présent ({n:,} lignes)")
            continue
        print(f"  {annee} : téléchargement…", end=" ", flush=True)
        ok, err = telecharge(GABARIT.format(a=annee, d=DEPARTEMENT), chemin)
        if not ok:
            print(f"échec ({err})")
            echecs += 1
            continue
        ok, entete, n = verifie(chemin)
        print(f"{n:,} lignes, entête conforme : {ok}" if ok else f"entête inattendue : {entete}")
        echecs += 0 if ok else 1

    chemin_loyers = os.path.join(DONNEES, ATTENDU_LOYERS)
    if os.path.exists(chemin_loyers):
        print(f"  loyers : {ATTENDU_LOYERS} présent")
    else:
        print(f"  loyers : MANQUANT — à télécharger sur\n    {PAGE_LOYERS}\n"
              f"    puis à déposer dans donnees/ sous le nom {ATTENDU_LOYERS}")
        echecs += 1

    print("\nAucun problème." if not echecs else f"\n{echecs} élément(s) à compléter.")
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
