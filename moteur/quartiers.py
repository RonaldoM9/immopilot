"""Quartiers officiels (IRIS) — la bonne maille pour dire où acheter.

DVF nomme une **rue**, jamais un quartier. Or « quel quartier est le meilleur » est la vraie
question, et les prix y sont hétérogènes : à Villiers-le-Bel, trois rues concentrent la moitié des
ventes d'appartements, et l'écart entre la moins chère et la plus chère des rues correctement
échantillonnées dépasse 55 %.

Chaque acte notarié porte sa **longitude et sa latitude**. L'IGN publie les contours **IRIS**
(découpage officiel de l'INSEE, avec un nom d'usage : « Puits la Marlière », « Centre Ville »…).
On replace donc chaque vente dans son quartier par un test géométrique — point dans polygone — et
on agrège. Le rattachement est **vérifiable** : ni déclaratif, ni deviné.

Rien de tout cela n'appelle un modèle de langage : ce sont des coordonnées, des polygones et des
médianes.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import urllib.parse
import urllib.request

from . import analyse as A
from . import donnees as D

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(RACINE, "donnees", "iris")
WFS = "https://data.geopf.fr/wfs/ows"
COUCHE = "STATISTICALUNITS.IRIS:contours_iris"
MIN_VENTES_QUARTIER = 5


# ------------------------------------------------------------------ géométrie
def _dans_anneau(anneau, x, y):
    """Lancer de rayon : le point est-il dans l'anneau ? (aucune bibliothèque externe)"""
    dedans = False
    n = len(anneau)
    for i in range(n):
        xi, yi = anneau[i][0], anneau[i][1]
        xj, yj = anneau[i - 1][0], anneau[i - 1][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            dedans = not dedans
    return dedans


def _dans_polygone(polygone, x, y):
    """Un polygone = un anneau extérieur moins ses trous (MultiPolygon = plusieurs polygones)."""
    if not polygone:
        return False
    if not _dans_anneau(polygone[0], x, y):
        return False
    return not any(_dans_anneau(trou, x, y) for trou in polygone[1:])


def contient(geometrie, x, y):
    t = (geometrie or {}).get("type")
    c = (geometrie or {}).get("coordinates") or []
    if t == "Polygon":
        return _dans_polygone(c, x, y)
    if t == "MultiPolygon":
        return any(_dans_polygone(p, x, y) for p in c)
    return False


# ------------------------------------------------------------------ contours IGN
def _telecharge(bbox):
    """Contours IRIS intersectant une emprise (lon_min, lat_min, lon_max, lat_max).

    Attention : malgré `SRSNAME=EPSG:4326`, le service attend ici l'emprise en **longitude
    d'abord**. Vérifié le 15/10/2026 : `2.36,49.00,2.44,49.04` rend 44 IRIS, l'ordre inverse en
    rend 0. Un résultat vide ne prouve donc rien — d'où le contrôle explicite plus bas.
    """
    params = {
        "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
        "TYPENAMES": COUCHE, "SRSNAME": "EPSG:4326",
        "BBOX": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},EPSG:4326",
        "OUTPUTFORMAT": "application/json",
    }
    url = WFS + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=90) as r:
        corps = json.load(r)
    return corps.get("features") or []


def iris_de_commune(insee, ventes):
    """IRIS d'une commune, avec cache disque. L'emprise vient des ventes elles-mêmes."""
    os.makedirs(CACHE, exist_ok=True)
    chemin = os.path.join(CACHE, f"iris_{insee}.json")
    if os.path.exists(chemin):
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    pts = [(v["lat"], v["lon"]) for v in ventes if v.get("lat") and v.get("lon")]
    if not pts:
        return []
    marge = 0.01  # ~1 km : couvre les IRIS qui débordent de l'emprise stricte des ventes
    bbox = (min(p[1] for p in pts) - marge, min(p[0] for p in pts) - marge,
            max(p[1] for p in pts) + marge, max(p[0] for p in pts) + marge)  # lon, lat, lon, lat
    try:
        features = _telecharge(bbox)
    except Exception as e:  # noqa: BLE001 — un service injoignable n'est pas une réponse fausse
        print(f"  contours IGN injoignables ({type(e).__name__}) : "
              f"pas de découpage par quartier pour cette commune")
        return []
    gardees = [f for f in features
               if str((f.get("properties") or {}).get("code_insee") or "") == str(insee)]
    if not gardees:
        # ne jamais mettre en cache un vide : un service qui répond zéro une fois ne doit pas
        # condamner la commune définitivement
        print(f"  aucun contour IRIS pour l'INSEE {insee} dans l'emprise "
              f"({len(features)} IRIS voisins reçus)")
        return []
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(gardees, f, ensure_ascii=False)
    return gardees


def quartier_de(iris, lon, lat):
    for f in iris:
        if contient(f.get("geometry"), lon, lat):
            p = f.get("properties") or {}
            return p.get("code_iris"), p.get("nom_iris")
    return None, None


# ------------------------------------------------------------------ agrégation
def _stats(vs, loyer_m2):
    m2 = [x["eur_m2"] for x in vs if x.get("eur_m2")]
    if not m2:
        return None
    m2s = sorted(m2)
    med = statistics.median(m2s)
    n = len(m2s)
    if n == 1:
        q1 = q3 = med
    else:
        # moitiés non vides par construction : sur un échantillon d'une ou deux ventes, les
        # quartiles n'ont aucun sens — on retombe sur la médiane plutôt que de planter
        bas = m2s[:n // 2] or m2s[:1]
        haut = m2s[(n + 1) // 2:] or m2s[-1:]
        q1, q3 = statistics.median(bas), statistics.median(haut)
    prix = statistics.median([x["valeur_actualisee"] for x in vs if x.get("valeur_actualisee")])
    surf = statistics.median([x["surface"] for x in vs if x.get("surface")])
    return {
        "n": len(vs), "median_m2": med, "q1": q1, "q3": q3,
        "dispersion": (q3 - q1) / ((q1 + q3) / 2) * 100 if (q1 + q3) else 0.0,
        "median_prix": prix, "median_surface": surf,
        "rendement_brut": (loyer_m2 * 0.95 * 12 / med * 100) if (loyer_m2 and med) else None,
        "annees": sorted({x["annee"] for x in vs}),
    }


def quartiers(commune=None, insee=None, type_local="Appartement", annees=None):
    """Agrège les ventes par IRIS, et regarde quelles rues portent chaque quartier."""
    r = A.resout_commune(commune or insee)
    if not r:
        return {"erreur": f"commune introuvable : {commune or insee}"}
    annees = annees or D.ANNEES_REFERENCE
    ventes = A.comparables(commune=r["commune"], insee=r["insee"], type_local=type_local,
                           type_surface=type_local, annees=annees)
    toutes = A.comparables(commune=r["commune"], insee=r["insee"], type_local=type_local,
                           type_surface=type_local, annees=D.ANNEES)  # toutes surfaces : emprise
    iris = iris_de_commune(r["insee"], toutes or ventes)
    loyer = A.loyer_reference(insee=r["insee"])
    loyer_m2 = (loyer or {}).get("loyer_m2")

    par_iris = {}
    for v in ventes:
        if not (v.get("lat") and v.get("lon")):
            continue
        code, nom = quartier_de(iris, v["lon"], v["lat"])
        cle = code or "hors_iris"
        par_iris.setdefault(cle, {"code_iris": code, "nom_iris": nom or "hors contours", "ventes": []})
        par_iris[cle]["ventes"].append(v)

    resultats = []
    for cle, bloc in par_iris.items():
        st = _stats(bloc["ventes"], loyer_m2)
        if not st:
            continue
        rues = {}
        for v in bloc["ventes"]:
            nom_rue = (v.get("voie") or "").strip().upper() or "(sans voie)"
            rues.setdefault(nom_rue, []).append(v)
        top = sorted(rues.items(), key=lambda kv: -len(kv[1]))[:4]
        st.update({
            "code_iris": bloc["code_iris"], "nom_iris": bloc["nom_iris"],
            "solide": st["n"] >= MIN_VENTES_QUARTIER,
            "rues": [{"voie": k, "n": len(v), "median_m2": statistics.median([x["eur_m2"] for x in v])}
                     for k, v in top],
        })
        resultats.append(st)
    resultats.sort(key=lambda x: -x["n"])
    return {
        "commune": r["commune"], "insee": r["insee"], "departement": r["departement"],
        "type": type_local, "annees_reference": list(annees),
        "nb_ventes": len(ventes), "loyer_m2": loyer_m2,
        "nb_iris": len(iris), "quartiers": resultats,
        "n_cartographiees": sum(x["n"] for x in resultats if x["code_iris"]),
    }


# ------------------------------------------------------------------ CLI
def main():
    ap = argparse.ArgumentParser(description="Prix par quartier officiel (IRIS).")
    ap.add_argument("--commune", required=True)
    ap.add_argument("--type", default="Appartement", choices=("Appartement", "Maison"))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    res = quartiers(commune=a.commune, type_local=a.type)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
        return
    if res.get("erreur"):
        print(res["erreur"])
        return
    print(f"\n{res['commune']} ({res['departement']}) — {res['type']}, "
          f"{res['annees_reference'][0]}-{res['annees_reference'][-1]} · {res['nb_ventes']} ventes "
          f"comparables · loyer {res['loyer_m2']:.2f} €/m²" if res.get("loyer_m2") else "")
    print(f"{res['nb_iris']} quartiers IRIS connus, {res['n_cartographiees']} ventes localisées\n")
    for q in res["quartiers"]:
        marque = "" if q["solide"] else "  (échantillon trop mince pour conclure)"
        print(f"— {q['nom_iris']} [{q['code_iris']}] — {q['n']} ventes{marque}")
        print(f"    médiane {q['median_m2']:,.0f} €/m²  [{q['q1']:,.0f}-{q['q3']:,.0f}]  "
              f"dispersion {q['dispersion']:.0f} %  lot {q['median_surface']:.0f} m² à "
              f"{q['median_prix']:,.0f} €".replace(",", " "))
        if q.get("rendement_brut"):
            print(f"    rendement brut indicatif {q['rendement_brut']:.2f} % (loyer communal)")
        print("    rues : " + ", ".join(f"{r['voie']} ({r['n']} ventes, {r['median_m2']:,.0f} €/m²)"
                                        .replace(",", " ") for r in q["rues"]))
        print()


if __name__ == "__main__":
    main()
