#!/usr/bin/env python3
"""Estimation d'une maison a Ecouen (13 rue Georges Clemenceau) a partir de DVF 2021-2025."""
import csv, statistics, glob, os, re
from collections import defaultdict

DOSSIER = "/root/projects/immopilot/donnees"
CIBLE_RUE = "CLEMENCEAU"
CIBLE_CP = "95440"


def mutations(path):
    """Regroupe les lignes DVF par mutation (une mutation = une vente)."""
    par_mut = defaultdict(list)
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("nature_mutation") != "Vente":
                continue
            if not r.get("valeur_fonciere") or not r.get("id_mutation"):
                continue
            par_mut[r["id_mutation"]].append(r)
    return par_mut


def logements(par_mut, types=("Maison",)):
    """Ventes ou un logement represente l'essentiel de la surface declaree."""
    out = []
    for lignes in par_mut.values():
        cible = [l for l in lignes if l.get("type_local") in types]
        if not cible:
            continue
        s_cible = sum(float(l["surface_reelle_bati"] or 0) for l in cible)
        s_tot = sum(float(l["surface_reelle_bati"] or 0) for l in lignes)
        if s_cible <= 0 or s_tot <= 0 or s_cible / s_tot < 0.6:
            continue
        val = max(float(l["valeur_fonciere"] or 0) for l in lignes)
        if not (50000 <= val <= 2000000) or not (30 <= s_cible <= 300):
            continue
        d = cible[0]
        out.append({
            "date": d["date_mutation"], "annee": d["date_mutation"][:4],
            "commune": d["nom_commune"], "cp": d.get("code_postal") or "",
            "rue": (d.get("adresse_nom_voie") or "").upper(),
            "num": d.get("adresse_numero") or "",
            "surf": s_cible, "val": val, "eur_m2": val / s_cible,
            "terrain": sum(float(l.get("surface_terrain") or 0) for l in cible),
            "pieces": d.get("nombre_pieces_principales") or "",
            "type": d.get("type_local"),
        })
    return out


def stat(vals):
    if not vals:
        return None
    return (len(vals), statistics.median(vals), min(vals), max(vals))


print("=" * 78)
print("1. LA RUE GEORGES CLEMENCEAU — toutes les ventes de logement, 2021-2025, tout le 95")
print("=" * 78)
for an in range(2021, 2026):
    p = f"{DOSSIER}/dvf95_{an}.csv"
    if not os.path.exists(p):
        continue
    for v in logements(mutations(p), ("Maison", "Appartement")):
        if CIBLE_RUE in v["rue"]:
            print(f"  {v['date']}  {v['commune'][:20]:20s} {v['cp']} {v['num']:>4} {v['rue'][:30]:30s} "
                  f"{v['type'][:11]:11s} {v['surf']:5.0f} m2  {v['val']:9.0f} EUR  {v['eur_m2']:7.0f} EUR/m2  terrain {v['terrain']:6.0f}")

print()
print("=" * 78)
print("2. ECOUEN (95440) — maisons : prix au m2 par annee")
print("=" * 78)
for an in range(2021, 2026):
    p = f"{DOSSIER}/dvf95_{an}.csv"
    if not os.path.exists(p):
        continue
    v = [x for x in logements(mutations(p)) if x["cp"] == CIBLE_CP]
    s = stat([x["eur_m2"] for x in v])
    sv = stat([x["surf"] for x in v])
    if s:
        print(f"  {an} : {s[0]:3d} ventes | mediane {s[1]:6.0f} EUR/m2  (min {s[2]:.0f} / max {s[3]:.0f}) "
              f"| surface mediane {sv[1]:.0f} m2 | prix median {stat([x['val'] for x in v])[1]:9.0f} EUR")

print()
print("=" * 78)
print("3. ECOUEN 2025 — maisons par tranche de surface")
print("=" * 78)
v = [x for x in logements(mutations(f"{DOSSIER}/dvf95_2025.csv")) if x["cp"] == CIBLE_CP]
tranches = [(0, 60), (60, 80), (80, 100), (100, 120), (120, 160), (160, 400)]
for lo, hi in tranches:
    sel = [x for x in v if lo <= x["surf"] < hi]
    if not sel:
        continue
    s = stat([x["eur_m2"] for x in sel])
    sv = stat([x["val"] for x in sel])
    print(f"  {lo:3d}-{hi:3d} m2 : {s[0]:2d} ventes | mediane {s[1]:6.0f} EUR/m2 "
          f"| prix median {sv[1]:9.0f} EUR | fourchette prix {sv[2]:.0f}-{sv[3]:.0f}")
    for x in sorted(sel, key=lambda y: y["eur_m2"]):
        print(f"        {x['date']} {x['num']:>4} {x['rue'][:28]:28s} {x['surf']:5.0f} m2 {x['val']:9.0f} EUR {x['eur_m2']:7.0f} EUR/m2 (terrain {x['terrain']:5.0f})")

print()
print("=" * 78)
print("4. COMMUNES VOISINES 2025 — maisons de 80 a 120 m2 (le segment de la 13 rue Clemenceau)")
print("=" * 78)
VOISINES = {"95440": "Ecouen", "95460": "Ezanville", "95230": "Montmorency", "95170": "Deuil-la-Barre",
            "95350": "Saint-Brice-sous-Foret", "95580": "Sarcelles", "95400": "Villiers-le-Bel",
            "95330": "Domont", "95270": "Bouffemont"}
v = [x for x in logements(mutations(f"{DOSSIER}/dvf95_2025.csv")) if 80 <= x["surf"] <= 120]
par_cp = defaultdict(list)
for x in v:
    par_cp[x["cp"]].append(x)
for cp, nom in VOISINES.items():
    sel = par_cp.get(cp, [])
    if not sel:
        continue
    s = stat([x["eur_m2"] for x in sel])
    print(f"  {nom:24s} {s[0]:3d} ventes | mediane {s[1]:6.0f} EUR/m2 | prix median {stat([x['val'] for x in sel])[1]:9.0f} EUR")

print()
print("=" * 78)
print("5. SIMULATION — valeur de la maison selon sa surface, au prix median d'Ecouen 2025")
print("=" * 78)
villes = [x["eur_m2"] for x in logements(mutations(f"{DOSSIER}/dvf95_2025.csv")) if x["cp"] == CIBLE_CP]
med, lic, cap = statistics.median(villes), min(villes), max(villes)
print(f"  base : mediane Ecouen 2025 = {med:.0f} EUR/m2 | ecart observe {lic:.0f} a {cap:.0f} EUR/m2")
print()
print(f"  {'surface':>8} | {'bas (-10%)':>12} | {'median':>12} | {'haut (+10%)':>12}")
for s in (85, 90, 95, 100, 105, 110, 115, 120, 130):
    print(f"  {s:6d} m2 | {s*med*0.9:12.0f} | {s*med:12.0f} | {s*med*1.1:12.0f}")
print()
print("  loyers Ecouen (carte des loyers 2025, appartements 1-2 p.) : 21,00 EUR/m2/mois")
