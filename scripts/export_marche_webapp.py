#!/usr/bin/env python3
"""Genere le bloc MARKET de la webapp ImmoPilot depuis les donnees verifiees.

Sortie : livrables/marche_95_2025.js et .json
Filtre documente (celui du 15/10, cale sur les chiffres du dossier) :
  - mutation de type Vente, local Appartement
  - surface du logement entre 15 et 45 m2 et >= 80 % de la surface batie declaree
  - prix au m2 entre 500 et 25 000 EUR
  - au moins 5 ventes dans la commune
  - loyer d'annonce 1-2 pieces 2025 du ministere + nombre d'observations
Rendement brut = loyer/m2 x 12 / prix/m2.
"""
import csv, io, json, statistics, datetime
from collections import defaultdict

D = "/root/projects/immopilot/donnees"
APP = {'Garges-lès-Gonesse', 'Villiers-le-Bel', 'Goussainville', 'Arnouville', 'Magny-en-Vexin', 'Sannois',
       'Gonesse', 'Montmorency', 'Argenteuil', 'Groslay', 'Sarcelles', 'Montmagny', 'Soisy-sous-Montmorency',
       'Saint-Gratien', 'Franconville', 'Enghien-les-Bains', 'Écouen'}


def loyers():
    brut = open(f"{D}/loyers_12p_2025.csv", "rb").read()
    txt = brut.decode("utf-8-sig") if _ok(brut, "utf-8-sig") else brut.decode("latin-1")
    out = {}
    for r in csv.DictReader(io.StringIO(txt), delimiter=";"):
        if r["DEP"] != "95":
            continue
        try:
            out[r["INSEE_C"]] = (float(r["loypredm2"].replace(",", ".")), int(r["nbobs_com"] or 0))
        except ValueError:
            pass
    return out


def _ok(b, enc):
    try:
        b.decode(enc); return True
    except UnicodeDecodeError:
        return False


par_mut = defaultdict(list)
for r in csv.DictReader(open(f"{D}/dvf95_2025.csv", encoding="utf-8")):
    if r.get("nature_mutation") == "Vente" and r.get("type_local") == "Appartement" \
       and r.get("valeur_fonciere") and r.get("surface_reelle_bati") and r.get("id_mutation"):
        par_mut[r["id_mutation"]].append(r)

communes, noms = defaultdict(list), {}
for lignes in par_mut.values():
    st = sum(float(l["surface_reelle_bati"]) for l in lignes)
    for l in lignes:
        s = float(l["surface_reelle_bati"])
        if not (15 <= s <= 45) or (st and s / st < 0.8):
            continue
        p = float(l["valeur_fonciere"]) / s
        if not (500 <= p <= 25000):
            continue
        communes[l["code_commune"]].append(p)
        noms[l["code_commune"]] = l["nom_commune"]

L = loyers()
rows, ecartes = [], []
for code, vals in communes.items():
    nom = noms[code]
    if len(vals) < 5:
        ecartes.append((nom, len(vals), "moins de 5 ventes"))
        continue
    loy = L.get(code)
    if not loy or loy[0] <= 0:
        ecartes.append((nom, len(vals), "pas de loyer publie"))
        continue
    prix_m2 = statistics.median(vals)
    loyer_m2, obs = loy
    rows.append({"n": nom, "p": round(prix_m2), "r": round(loyer_m2, 2),
                 "y": round(loyer_m2 * 12 / prix_m2 * 100, 2), "s": len(vals), "o": obs})

rows.sort(key=lambda x: -x["y"])
med = statistics.median([x["y"] for x in rows])
stamp = datetime.datetime.utcnow().strftime("%Y-%m-%d")

js = ["/* ImmoPilot — marche appartements 15-45 m2, Val-d'Oise, ventes et loyers d'annonce 2025.",
      f"   Genere le {stamp} depuis DVF 2025 (data.gouv) et la Carte des loyers 2025 (ministere).",
      f"   {len(rows)} communes, rendement brut median {med:.2f} %. Filtre : voir scripts/export_marche_webapp.py. */",
      "const MARKET=[", ",".join(json.dumps(x, ensure_ascii=False) for x in rows), "];",
      f"const MARKET_META={{source:'DVF 2025 + Carte des loyers 2025',genere:'{stamp}',"
      f"perimetre:'appartements 15-45 m2',medianDepartementale:{med:.2f},communes:{len(rows)}}};"]
open("/root/projects/immopilot/livrables/marche_95_2025.js", "w", encoding="utf-8").write("\n".join(js) + "\n")
json.dump({"meta": {"source": "DVF 2025 + Carte des loyers 2025", "genere": stamp,
                    "perimetre": "appartements 15-45 m2", "median_departementale": round(med, 2)},
           "communes": rows}, open("/root/projects/immopilot/livrables/marche_95_2025.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

print(f"communes retenues : {len(rows)} | mediane departementale : {med:.2f} % | ecartees : {len(ecartes)}")
print(f"COUVERTURE : {sum(1 for x in rows if x['n'] in APP)} des 17 communes de la webapp")
print("\n=== COMMUNES DE LA WEBAPP : ecart avec les donnees recalculees ===")
print("  commune                  app(p/y)      recalcule(p/y)     ecart")
for x in rows:
    if x["n"] not in APP:
        continue
    app = {"Garges-lès-Gonesse": (2564, 10.21), "Villiers-le-Bel": (2727, 9.43), "Goussainville": (3101, 8.34),
           "Arnouville": (3178, 8.03), "Magny-en-Vexin": (2666, 7.46), "Sannois": (3741, 7.38),
           "Gonesse": (3436, 7.30), "Montmorency": (3929, 7.17), "Argenteuil": (3896, 6.84),
           "Groslay": (3526, 7.23), "Sarcelles": (3570, 7.19), "Montmagny": (3866, 7.05),
           "Soisy-sous-Montmorency": (3906, 6.80), "Saint-Gratien": (4272, 6.79),
           "Franconville": (3934, 6.54), "Enghien-les-Bains": (5258, 5.42), "Écouen": (2687, None)}.get(x["n"])
    if not app:
        continue
    ep = x["p"] - app[0]
    ey = (x["y"] - app[1]) if app[1] else None
    flag = "" if abs(ep) <= 6 and (ey is None or abs(ey) < 0.05) else "   <-- ECART"
    print(f"  {x['n']:24s} {app[0]:>6}/{str(app[1]):>5}   {x['p']:>6}/{x['y']:<5}   {ep:+5d} EUR  "
          f"{('%+.2f pt' % ey) if ey is not None else '     -':>9}{flag}")
print("\n=== 10 MEILLEURS RENDEMENTS RECALCULES ===")
for x in rows[:10]:
    print(f"  {x['y']:5.2f} %  {x['n']:26s} {x['p']:5d} EUR/m2  loyer {x['r']:5.2f}  {x['s']:3d} ventes  {x['o']:5d} obs")
print("\n=== COMMUNES ECARTEES (et pourquoi) ===")
for nom, n, motif in ecartes[:12]:
    print(f"  {nom:26s} {n:3d} ventes  -> {motif}")
