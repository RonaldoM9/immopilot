#!/usr/bin/env python3
"""Génère les données de marché que sert la webapp : communes + voies, avec loyer et rendement.

    python3 scripts/exporte_marche.py

Sortie : webapp/data/marche.json (lu par le serveur, jamais calculé par le modèle de langage).

Une seule passe sur les ventes actualisées : on calcule, par commune et par voie, la médiane du
prix au m², les quartiles, l'écart interquartile, le nombre de ventes, et on rattache le loyer
de référence du ministère pour obtenir le rendement brut.
"""
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


def main():
    print("Chargement des ventes DVF (Val-d'Oise, 2021-2025)…")
    idx = D.indice_annuel("Appartement")
    idx_maison = D.indice_annuel("Maison")
    print("  indice appartements :", {a: round(v, 3) for a, v in idx["indice"].items()})
    print("  indice maisons      :", {a: round(v, 3) for a, v in idx_maison["indice"].items()})

    communes = defaultdict(lambda: {"appart": [], "maison": []})
    for t, cle in (("Appartement", "appart"), ("Maison", "maison")):
        for v in D.ventes_actualisees(D.ANNEES, t):
            if cle == "appart" and not (D.SURF_APPART[0] <= v["surface"] <= D.SURF_APPART[1]):
                continue
            communes[(v["commune"], v["insee"])][cle].append(v)

    sortie = {"genere_le": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
              "source": "DVF Etalab (fichiers 2021-2025) + carte des loyers (ministère du Logement)",
              "annees_reference": list(D.ANNEES_REFERENCE),
              "annees_modele": list(D.ANNEES),
              "indice_appartements": {str(a): round(v, 3) for a, v in idx["indice"].items()},
              "indice_maisons": {str(a): round(v, 3) for a, v in idx_maison["indice"].items()},
              "communes": []}

    for (nom, insee), lots in sorted(communes.items()):
        ref = loyer_de(nom, insee)
        bloc = {"nom": nom, "insee": insee, "loyer": ref}
        for cle, type_local in (("appart", "Appartement"), ("maison", "Maison")):
            ventes = lots[cle]
            ventes = [v for v in ventes
                      if v["annee"] in D.ANNEES_REFERENCE or v["annee"] in D.ANNEES]
            recents = [v for v in ventes if v["annee"] in D.ANNEES_REFERENCE]
            base = recents if len(recents) >= MIN_VENTES_COMMUNE else ventes
            s = stats(sorted(v["eur_m2"] for v in base), [v["valeur_actualisee"] for v in base],
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
            bloc[cle] = s
        if "appart" in bloc or "maison" in bloc:
            sortie["communes"].append(bloc)

    sortie["nb_communes"] = len(sortie["communes"])
    sortie["nb_voies"] = sum(len(c.get("appart", {}).get("voies", []))
                             + len(c.get("maison", {}).get("voies", []))
                             for c in sortie["communes"])
    dossier = os.path.join(RACINE, "webapp", "data")
    os.makedirs(dossier, exist_ok=True)
    chemin = os.path.join(dossier, "marche.json")
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(sortie, f, ensure_ascii=False, separators=(",", ":"))
    print(f"\n{sortie['nb_communes']} communes, {sortie['nb_voies']} voies -> {chemin} "
          f"({os.path.getsize(chemin)/1024:.0f} Ko)")
    for c in sortie["communes"]:
        if c["nom"].upper() in ("ÉCOUEN", "GROSLAY", "GARGES-LÈS-GONESSE", "VILLIERS-LE-BEL"):
            a = c.get("appart")
            print(f"  {c['nom']:22s} apparts n={a['n']:3d} mediane {a['median_m2']:5d} EUR/m2 "
                  f"dispersion {a['dispersion']:4.1f} % rendement {a.get('rendement_brut', 0):5.2f} %"
                  f" | {len(a['voies'])} voies" if a else f"  {c['nom']}: pas d'appartement")


if __name__ == "__main__":
    main()
