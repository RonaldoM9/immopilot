#!/usr/bin/env python3
"""Génère les données de marché servies à la webapp et au site publié, département par département.

    python3 scripts/exporte_marche.py                     # tous les départements chargés
    python3 scripts/exporte_marche.py --departements 95   # un seul

Sortie : webapp/data/marche_<dep>.json et docs/data/marche_<dep>.json, plus un index
docs/data/index.json qui liste les départements disponibles et leurs volumes.

Une seule passe sur les ventes actualisées par département : médiane du prix au m², quartiles,
écart interquartile, nombre de ventes, loyer de référence du ministère et rendement brut.
"""
import argparse
import json
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
from moteur import analyse, donnees as D  # noqa: E402

MIN_VENTES_COMMUNE = 5
MIN_VENTES_VOIE = 3


def mediane(xs):
    return statistics.median(xs) if xs else 0.0


def stats(m2, prix, surfaces):
    if not m2:
        return None
    m2 = sorted(m2)
    med = mediane(m2)
    q1, q3 = m2[len(m2) // 4], m2[3 * len(m2) // 4]
    return {"n": len(m2), "median_m2": round(med), "q1": round(q1), "q3": round(q3),
            "dispersion": round((q3 - q1) / med * 100, 1) if med else 0,
            "median_prix": round(mediane(prix)),
            "median_surface": round(mediane(surfaces), 1)}


def loyer_de(commune, insee):
    l = analyse.loyer_reference(commune=commune, insee=insee)
    if not l or not l.get("loyer_m2"):
        return None
    return {"loyer_m2": round(l["loyer_m2"], 2), "observations": l["observations"],
            "fiabilite": l.get("fiabilite", "inconnue")}


def construit(dep):
    """Bloc de marché complet pour un département — le moteur est cadré sur ce périmètre."""
    D.fixe_perimetre((dep,))
    idx = D.indice_annuel("Appartement")
    idx_maison = D.indice_annuel("Maison")
    print(f"  {dep} — indice appartements :",
          {a: round(v, 3) for a, v in idx["indice_regional"].items()})

    communes = defaultdict(lambda: {"appart": [], "maison": []})
    for t, cle in (("Appartement", "appart"), ("Maison", "maison")):
        for v in D.ventes_actualisees(D.ANNEES, t):
            if cle == "appart" and not (D.SURF_APPART[0] <= v["surface"] <= D.SURF_APPART[1]):
                continue
            communes[(v["commune"], v["insee"])][cle].append(v)

    bloc = {"departement": dep,
            "genere_le": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "source": "DVF Etalab (fichiers 2021-2025) + carte des loyers (ministère du Logement)",
            "annees_reference": list(D.ANNEES_REFERENCE), "annees_modele": list(D.ANNEES),
            "indice_appartements": {str(a): round(v, 3)
                                    for a, v in idx["indice_regional"].items()},
            "indice_maisons": {str(a): round(v, 3)
                               for a, v in idx_maison["indice_regional"].items()},
            "communes": []}

    for (nom, insee), lots in sorted(communes.items()):
        ref = loyer_de(nom, insee)
        ligne = {"nom": nom, "insee": insee, "loyer": ref}
        for cle, type_local in (("appart", "Appartement"), ("maison", "Maison")):
            ventes = lots[cle]
            recents = [v for v in ventes if v["annee"] in D.ANNEES_REFERENCE]
            base = recents if len(recents) >= MIN_VENTES_COMMUNE else ventes
            s = stats([v["eur_m2"] for v in base], [v["valeur_actualisee"] for v in base],
                      [v["surface"] for v in base])
            if not s:
                continue
            s["solide"] = s["n"] >= MIN_VENTES_COMMUNE and s["dispersion"] <= 45
            s["annees_retenues"] = sorted({v["annee"] for v in base})
            if ref and cle == "appart":
                s["rendement_brut"] = round(ref["loyer_m2"] * 12 / s["median_m2"] * 100, 2)
            voies = defaultdict(list)
            for v in base:
                voies[v["voie"] or "(sans voie)"].append(v)
            s["voies"] = sorted(
                [{"nom": k, "n": len(w), "median_m2": round(mediane([x["eur_m2"] for x in w])),
                  "median_prix": round(mediane([x["valeur_actualisee"] for x in w])),
                  "annees": f"{min(x['annee'] for x in w)}-{max(x['annee'] for x in w)}"}
                 for k, w in voies.items() if len(w) >= MIN_VENTES_VOIE],
                key=lambda x: -x["n"])
            ligne[cle] = s
        if "appart" in ligne or "maison" in ligne:
            bloc["communes"].append(ligne)

    bloc["nb_communes"] = len(bloc["communes"])
    bloc["nb_voies"] = sum(len(c.get("appart", {}).get("voies", []))
                           + len(c.get("maison", {}).get("voies", []))
                           for c in bloc["communes"])
    return bloc


def main(argv=None):
    ap = argparse.ArgumentParser(description="Exporte le marché par département.")
    ap.add_argument("--departements", default=None,
                    help="codes séparés par des virgules (défaut : tous ceux téléchargés)")
    a = ap.parse_args(argv)

    departements = ([d.strip() for d in a.departements.split(",") if d.strip()]
                    if a.departements else list(D.departements_disponibles()))
    print(f"départements traités : {', '.join(departements)}")
    for nom_dossier in ("webapp/data", "docs/data"):
        os.makedirs(os.path.join(RACINE, nom_dossier), exist_ok=True)

    index = {"genere_le": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
             "departements": []}
    for dep in departements:
        bloc = construit(dep)
        for nom_dossier in ("webapp/data", "docs/data"):
            chemin = os.path.join(RACINE, nom_dossier, f"marche_{dep}.json")
            with open(chemin, "w", encoding="utf-8") as f:
                json.dump(bloc, f, ensure_ascii=False, separators=(",", ":"))
        print(f"  {dep} : {bloc['nb_communes']} communes, {bloc['nb_voies']} voies")
        index["departements"].append({"code": dep, "communes": bloc["nb_communes"],
                                     "voies": bloc["nb_voies"]})

    with open(os.path.join(RACINE, "docs/data/index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(RACINE, "webapp/data/index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))

    D.fixe_perimetre(None)
    # Le 95 reste le fichier de référence pour la compatibilité (site et serveur).
    if "95" in departements:
        for nom_dossier in ("webapp/data", "docs/data"):
            src = os.path.join(RACINE, nom_dossier, "marche_95.json")
            dst = os.path.join(RACINE, nom_dossier, "marche.json")
            with open(src, encoding="utf-8") as fi, open(dst, "w", encoding="utf-8") as fo:
                fo.write(fi.read())

    total = sum(d["communes"] for d in index["departements"])
    print(f"\n{len(departements)} départements, {total} communes au total.")
    for dep in departements:
        exemple = ["Écouen", "Paris 11e", "Montreuil", "Saint-Denis"] if dep in ("95", "75", "93") else []
        bloc = json.load(open(os.path.join(RACINE, "webapp/data", f"marche_{dep}.json"),
                              encoding="utf-8"))
        for c in bloc["communes"]:
            if c["nom"] in exemple and c.get("appart"):
                a = c["appart"]
                print(f"  ex. {dep} {c['nom']:14s} n={a['n']:4d} médiane {a['median_m2']:5d} €/m² "
                      f"rendement {a.get('rendement_brut', 0):5.2f} %")
    return 0


if __name__ == "__main__":
    sys.exit(main())
