#!/usr/bin/env python3
"""Estimation de la valeur d'une maison a Ecouen :
   - la rue Georges Clemenceau elle-meme (historique complet)
   - micro-marche : Ecouen + communes limitrophes, effet taille et effet terrain
   - modele log-log : prix = a * surface^b * (1 + c * terrain), calibre sur 2021-2025
"""
import csv, statistics, math, os
from collections import defaultdict

DOSSIER = "/root/projects/immopilot/donnees"
ECOUEN = "95440"
VOISINES = {"95460", "95350", "95160", "95330", "95270", "95580", "95400", "95230"}

def ventes(annees, cps):
    out = []
    for an in annees:
        p = f"{DOSSIER}/dvf95_{an}.csv"
        if not os.path.exists(p):
            continue
        par_mut = defaultdict(list)
        with open(p, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("nature_mutation") == "Vente" and r.get("valeur_fonciere") and r.get("id_mutation"):
                    par_mut[r["id_mutation"]].append(r)
        for lignes in par_mut.values():
            cible = [l for l in lignes if l.get("type_local") == "Maison"]
            if not cible:
                continue
            s = sum(float(l["surface_reelle_bati"] or 0) for l in cible)
            st = sum(float(l["surface_reelle_bati"] or 0) for l in lignes)
            if s <= 0 or st <= 0 or s / st < 0.6:
                continue
            val = max(float(l["valeur_fonciere"] or 0) for l in lignes)
            if not (50000 <= val <= 2000000) or not (30 <= s <= 300):
                continue
            d = cible[0]
            cp = d.get("code_postal") or ""
            if cp not in cps:
                continue
            out.append({"annee": an, "commune": d["nom_commune"], "cp": cp,
                        "rue": (d.get("adresse_nom_voie") or "").upper(),
                        "num": d.get("adresse_numero") or "",
                        "date": d["date_mutation"], "surf": s, "val": val,
                        "terrain": min(sum(float(l.get("surface_terrain") or 0) for l in cible), s * 8),
                        "lat": float(d["latitude"]) if d.get("latitude") else None,
                        "lon": float(d["longitude"]) if d.get("longitude") else None})
    return out

def ols(X, y):
    """Moindres carres ordinaires, X = liste de listes (avec constante)."""
    n, k = len(X), len(X[0])
    XtX = [[sum(X[i][a] * X[i][b] for i in range(n)) for b in range(k)] for a in range(k)]
    Xty = [sum(X[i][a] * y[i] for i in range(n)) for a in range(k)]
    # inversion Gauss-Jordan
    A = [row[:] + [Xty[a]] for a, row in enumerate(XtX)]
    for c in range(k):
        p = max(range(c, k), key=lambda r: abs(A[r][c]))
        A[c], A[p] = A[p], A[c]
        piv = A[c][c]
        A[c] = [v / piv for v in A[c]]
        for r in range(k):
            if r != c and A[r][c]:
                f = A[r][c]
                A[r] = [A[r][j] - f * A[c][j] for j in range(k + 1)]
    beta = [A[i][k] for i in range(k)]
    pred = [sum(beta[a] * X[i][a] for a in range(k)) for i in range(n)]
    resid = [y[i] - pred[i] for i in range(n)]
    sse = sum(r * r for r in resid)
    sst = sum((v - statistics.mean(y)) ** 2 for v in y)
    return beta, resid, 1 - sse / sst

print("=" * 78)
print("A. LA RUE — ECOUEN, rue Georges Clemenceau : tout l'historique DVF 2021-2025")
print("=" * 78)
tout = ventes(range(2021, 2026), {ECOUEN})
for v in sorted([x for x in tout if "CLEMENCEAU" in x["rue"]], key=lambda x: x["date"]):
    print(f"  {v['date']}  {v['num']:>4} {v['rue'][:32]:32s} {v['surf']:5.0f} m2  {v['val']:9.0f} EUR  "
          f"{v['val']/v['surf']:7.0f} EUR/m2  terrain {v['terrain']:5.0f} m2  ({v['lat']:.5f}, {v['lon']:.5f})")

print()
print("=" * 78)
print("B. ECOUEN — effet taille et terrain (2021-2025, maisons)")
print("=" * 78)
E = tout
ech = [(x["surf"], x["terrain"], x["val"]) for x in E]
# log-log : log(prix) = a + b log(surface) + c log(1+terrain)
X = [[1.0, math.log(s), math.log(1 + t)] for s, t, _ in ech]
y = [math.log(v) for _, _, v in ech]
beta, resid, r2 = ols(X, y)
print(f"  n = {len(ech)} ventes | modele log-log | R2 = {r2:.3f}")
print(f"  prix = exp({beta[0]:.3f}) * surface^{beta[1]:.3f} * (1+terrain)^{beta[2]:.3f}")
print(f"  ecart-type residuel : {statistics.stdev(resid)*100:.1f} %  "
      f"(=> intervalle de confiance a 1 sigma : +/- {statistics.stdev(resid)*100:.0f} %)")

def predit(surf, terrain):
    return math.exp(beta[0] + beta[1] * math.log(surf) + beta[2] * math.log(1 + terrain))

print()
print("  surface | terrain 200 m2 | terrain 400 m2 | terrain 600 m2 | EUR/m2 (terrain 400)")
for s in (80, 90, 100, 110, 120, 130, 150):
    a, b, c = predit(s, 200), predit(s, 400), predit(s, 600)
    print(f"  {s:5d} m2 | {a:14.0f} | {b:14.0f} | {c:14.0f} | {b/s:8.0f}")

print()
print("=" * 78)
print("C. ECOUEN 2025 — le marche reel a un an (ce que paye un acheteur aujourd'hui)")
print("=" * 78)
v25 = [x for x in E if x["annee"] == 2025]
for lo, hi in ((0, 71), (71, 91), (91, 106), (106, 200)):
    sel = [x for x in v25 if lo <= x["surf"] < hi]
    if sel:
        s = sorted(x["val"] / x["surf"] for x in sel)
        pr = sorted(x["val"] for x in sel)
        print(f"  {lo:3d}-{hi:3d} m2 : {len(sel):2d} ventes | EUR/m2 median {statistics.median(s):6.0f} "
              f"| prix median {statistics.median(pr):9.0f} EUR | Q1 prix {pr[len(pr)//4]:9.0f} | Q3 prix {pr[3*len(pr)//4]:9.0f}")

print()
print("=" * 78)
print("D. TENDANCE ECOUEN — maisons, prix median en EUR (pas de mise en avant)")
print("=" * 78)
for an in range(2021, 2026):
    sel = [x["val"] for x in E if x["annee"] == an]
    sm = [x["val"] / x["surf"] for x in E if x["annee"] == an]
    print(f"  {an} : {len(sel):3d} ventes | prix median {statistics.median(sel):9.0f} EUR | "
          f"EUR/m2 median {statistics.median(sm):6.0f}")
