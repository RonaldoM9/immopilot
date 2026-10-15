#!/usr/bin/env python3
"""Grille de valeur 2025 pour une maison a Ecouen — calibrage sur les seules ventes 2025."""
import csv, statistics, math, os
from collections import defaultdict
DOSSIER = "/root/projects/immopilot/donnees"

def ols(X, y):
    n, k = len(X), len(X[0])
    XtX = [[sum(X[i][a]*X[i][b] for i in range(n)) for b in range(k)] for a in range(k)]
    Xty = [sum(X[i][a]*y[i] for i in range(n)) for a in range(k)]
    A = [r[:] + [Xty[a]] for a, r in enumerate(XtX)]
    for c in range(k):
        p = max(range(c, k), key=lambda r: abs(A[r][c])); A[c], A[p] = A[p], A[c]
        piv = A[c][c]; A[c] = [v/piv for v in A[c]]
        for r in range(k):
            if r != c and A[r][c]:
                f = A[r][c]; A[r] = [A[r][j]-f*A[c][j] for j in range(k+1)]
    beta = [A[i][k] for i in range(k)]
    res = [y[i]-sum(beta[a]*X[i][a] for a in range(k)) for i in range(n)]
    sse = sum(r*r for r in res); sst = sum((v-statistics.mean(y))**2 for v in y)
    return beta, res, 1-sse/sst

def maisons(annee, cp):
    par = defaultdict(list)
    with open(f"{DOSSIER}/dvf95_{annee}.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("nature_mutation") == "Vente" and r.get("valeur_fonciere") and r.get("id_mutation"):
                par[r["id_mutation"]].append(r)
    out = []
    for lignes in par.values():
        c = [l for l in lignes if l.get("type_local") == "Maison"]
        if not c:
            continue
        s = sum(float(l["surface_reelle_bati"] or 0) for l in c)
        st = sum(float(l["surface_reelle_bati"] or 0) for l in lignes)
        if s <= 0 or st <= 0 or s/st < 0.6:
            continue
        val = max(float(l["valeur_fonciere"] or 0) for l in lignes)
        if not (50000 <= val <= 2000000) or not (30 <= s <= 300):
            continue
        t = sum(float(l.get("surface_terrain") or 0) for l in c)
        if (c[0].get("code_postal") or "") == cp:
            out.append((s, t, val))
    return out

for an in (2025, 2024, 2023):
    E = maisons(an, "95440")
    X = [[1.0, math.log(s)] for s, t, v in E]
    y = [math.log(v) for s, t, v in E]
    beta, res, r2 = ols(X, y)
    ecart = statistics.stdev(res)
    print(f"\n=== ECOUEN {an} : {len(E)} ventes de maisons | R2={r2:.3f} | residu {ecart*100:.0f} %")
    print(f"    prix = exp({beta[0]:.4f}) * surface^{beta[1]:.4f}")
    print(f"    {'surf':>6} | {'EUR/m2':>8} | {'prix central':>13} | {'-1 sigma':>10} | {'+1 sigma':>10}")
    for s in (75, 80, 85, 90, 95, 100, 105, 110, 120, 130):
        p = math.exp(beta[0] + beta[1]*math.log(s))
        print(f"    {s:4d} m2 | {p/s:8.0f} | {p:13.0f} | {p*math.exp(-ecart):10.0f} | {p*math.exp(ecart):10.0f}")
