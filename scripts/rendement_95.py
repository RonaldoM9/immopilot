#!/usr/bin/env python3
"""Immopilot — reproduction des chiffres du 14/10/2026 (Telegram).

Sources (toutes ouvertes, téléchargées le 14/10/2026) :
  - DVF 2025, Val-d'Oise           : files.data.gouv.fr/geo-dvf/latest/csv/2025/departements/95.csv.gz
  - Carte des loyers 2025 (1-2 p.) : data.gouv.fr, indicateurs de loyers d'annonce par commune

Usage :
  python3 rendement_95.py                # rendements bruts par commune du 95
  python3 rendement_95.py --autour       # 16 communes les plus proches d'Ecouen
  python3 rendement_95.py --rue "VILLIERS-LE-BEL"   # prix au m2 par rue
"""
import csv, sys, statistics, math, io
from collections import defaultdict

DOSSIER = "/root/projects/immopilot/donnees"
DVF = f"{DOSSIER}/dvf95_2025.csv"
LOY = f"{DOSSIER}/loyers_12p_2025.csv"
ECOUEN = (49.0186, 2.3775)          # lat, lon
SURF_MIN, SURF_MAX = 15.0, 45.0     # appartements 15-45 m2
RAYON_KM = 8.0                      # "autour de chez toi"

def bien_logement(row):
    """Un appartement, vendu, dont la surface declaree est bien celle du logement."""
    if row.get("nature_mutation") != "Vente":
        return False
    if row.get("type_local") != "Appartement":
        return False
    if not row.get("surface_reelle_bati") or not row.get("valeur_fonciere"):
        return False
    return True

def charge_dvf():
    """Retourne {code_commune: {'nom':…, 'ventes': [(eur_m2, surf, voie, lat, lon), …]}}"""
    par_mutation = defaultdict(list)
    with open(DVF, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if bien_logement(row):
                par_mutation[row["id_mutation"]].append(row)

    communes = defaultdict(lambda: {"nom": "", "ventes": [], "lat": [], "lon": []})
    for lignes in par_mutation.values():
        # Total de surface du bati de la mutation : sert a ecarter les ventes ou
        # l'appartement ne represente qu'une fraction du prix (immeuble, lots multiples).
        surf_totale = sum(float(l["surface_reelle_bati"]) for l in lignes)
        for l in lignes:
            surf = float(l["surface_reelle_bati"])
            if not (SURF_MIN <= surf <= SURF_MAX):
                continue
            if surf_totale > 0 and surf / surf_totale < 0.8:
                continue          # immeuble entier : le prix n'est pas celui du logement (seuil 0.8 cale sur les chiffres du 14/10)
            prix = float(l["valeur_fonciere"])
            eur_m2 = prix / surf
            if not (500 <= eur_m2 <= 25000):
                continue          # artefacts (lots 1 EUR, ventes en bloc)
            c = l["code_commune"]
            e = communes[c]
            e["nom"] = l["nom_commune"]
            e["ventes"].append((eur_m2, surf, l.get("adresse_nom_voie") or "", ))
            for lat, lon in ((l.get("latitude"), l.get("longitude")),):
                if lat and lon:
                    e["lat"].append(float(lat)); e["lon"].append(float(lon))
    return communes

def _ouvre(path):
    """Les fichiers de la carte des loyers sont en latin-1, les fichiers DVF en utf-8."""
    brut = open(path, "rb").read()
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return io.StringIO(brut.decode(enc))
        except UnicodeDecodeError:
            continue
    return io.StringIO(brut.decode("utf-8", errors="replace"))


def charge_loyers():
    """{code_insee: (loyer_m2, nb_observations)} — carte des loyers 2025, appartements 1-2 pieces."""
    out = {}
    with _ouvre(LOY) as f:
        for row in csv.DictReader(f, delimiter=";"):
            if row["DEP"] != "95":
                continue
            try:
                loy = float(row["loypredm2"].replace(",", "."))
            except ValueError:
                continue
            out[row["INSEE_C"]] = (loy, int(row["nbobs_com"] or 0))
    return out

def distance_km(lat, lon):
    return math.hypot((lat - ECOUEN[0]) * 111.32,
                      (lon - ECOUEN[1]) * 111.32 * math.cos(math.radians(ECOUEN[0])))

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    communes, loyers = charge_dvf(), charge_loyers()
    lignes = []
    for code, e in communes.items():
        ventes = e["ventes"]
        if len(ventes) < 5:
            continue                      # moins de 5 ventes : echantillon trop mince
        prix_m2 = statistics.median(v[0] for v in ventes)
        loy = loyers.get(code)
        if not loy or loy[0] <= 0:
            continue
        loyer_m2, obs_loyer = loy
        rendement = loyer_m2 * 12 / prix_m2 * 100
        d = None
        if e["lat"]:
            d = distance_km(statistics.median(e["lat"]), statistics.median(e["lon"]))
        lignes.append((rendement, e["nom"], prix_m2, loyer_m2, len(ventes), obs_loyer, d))

    if mode == "--rue":
        cible = (sys.argv[2] if len(sys.argv) > 2 else "GROSLAY").upper()
        e = next((v for k, v in communes.items() if v["nom"].upper() == cible), None)
        if not e:
            print("commune inconnue :", cible); return
        par_rue = defaultdict(list)
        for v in e["ventes"]:
            if v[2]:
                par_rue[v[2]].append(v[0])
        print(f"=== {cible} — prix au m2 par rue (appartements {SURF_MIN:.0f}-{SURF_MAX:.0f} m2, ventes 2025) ===")
        for rue, vals in sorted(par_rue.items(), key=lambda x: statistics.median(x[1])):
            if len(vals) >= 1:
                print(f"  {statistics.median(vals):7.0f} EUR/m2  {rue[:38]:38s} {len(vals)} vente(s)")
        return

    if mode == "--autour":
        lignes = [l for l in lignes if l[6] is not None and l[6] <= RAYON_KM]
        lignes.sort(reverse=True)
        print(f"=== COMMUNES A MOINS DE {RAYON_KM:.0f} KM D'ECOUEN — appartements {SURF_MIN:.0f}-{SURF_MAX:.0f} m2 ===")
        print("  rend.  commune                        ventes  obs.  prix/m2  loyer/m2  25 m2")
        for r, nom, prix, loy, n, obs, d in lignes:
            print(f"  {r:5.2f}% {nom[:30]:30s} {n:6d} {obs:5d} {prix:8.0f} {loy:8.2f} {prix*25*1.08:8.0f} EUR")
        return

    lignes.sort(reverse=True)
    print("=== RENDEMENT BRUT — APPARTEMENTS 15-45 m2, VAL-D'OISE (ventes 2025, loyers 2025) ===")
    print("  rend.  commune                        ventes  obs.  prix/m2  loyer/m2")
    for r, nom, prix, loy, n, obs, d in lignes[:20]:
        print(f"  {r:5.2f}% {nom[:30]:30s} {n:6d} {obs:5d} {prix:8.0f} {loy:8.2f}")
    print(f"\n  mediane departementale : {statistics.median(l[0] for l in lignes):.2f} %")
    print(f"  communes retenues : {len(lignes)}")

if __name__ == "__main__":
    main()
