"""Comparables de rue et de commune, valeur d'un bien, loyer de référence."""
import math
import statistics
from collections import defaultdict

from . import donnees as D


# ---------------------------------------------------------------- comparables
def comparables(commune=None, insee=None, voie=None, type_local="Appartement",
                annees=None, surf_min=None, surf_max=None, type_surface="Appartement",
                surface=None, tolerance=None):
    """Ventes retenues, filtrées par commune, voie, et **bande de surface comparable**.

    Deux leçons apprises le 15/10/2026 en construisant le moteur :
    1. comparer un prix demandé à une médiane calculée sur toutes les surfaces produit des
       écarts absurdes (une maison de 100 m² n'a pas le prix au m² d'un 40 m²) : la bande
       autour de la surface cible est obligatoire ;
    2. mélanger cinq ans gonfle la médiane, le marché ayant perdu 13 % depuis 2022 : la
       fenêtre de référence par défaut est donc (2024, 2025).
    """
    annees = annees or D.ANNEES_REFERENCE
    lo, hi = (surf_min, surf_max) if surf_min and surf_max else (
        D.SURF_APPART if type_surface == "Appartement" else D.SURF_MAISON)
    if surface:
        tol = D.TOLERANCE_SURFACE if tolerance is None else tolerance
        lo = max(lo, surface * (1 - tol))
        hi = min(hi, surface * (1 + tol))
    cible = (commune or "").strip().upper()
    voie_upper = (voie or "").strip().upper()

    # Un même nom de commune peut exister dans deux départements : on ne mélange jamais deux
    # marchés dans une même médiane. La commune retenue est celle qui compte le plus de ventes.
    if not insee and cible:
        r = resout_commune(cible)
        if r and r.get("insee"):
            insee = r["insee"]

    sel = []
    for v in D.ventes_actualisees(annees, type_local):
        if insee and v["insee"] != insee:
            continue
        if not insee and cible and v["commune"].upper() != cible:
            continue
        if not (lo <= v["surface"] <= hi):
            continue
        if voie_upper and voie_upper not in v["voie"]:
            continue
        sel.append(v)
    return sel


def synthese(ventes):
    """Médiane, quartiles, dispersion, comptage — et le verdict sur la solidité.

    La dispersion retenue est l'écart interquartile rapporté à la médiane, et non l'écart-type :
    sur des prix d'actes, l'écart-type est dominé par quelques ventes atypiques (bien dégradé,
    vente en bloc) et fait passer un marché normal pour chaotique. L'écart-type reste affiché
    à côté, pour information.
    """
    if not ventes:
        return {"n": 0, "median_eur_m2": 0, "q1": 0, "q3": 0, "dispersion": 0,
                "ecart_type_pct": 0, "median_prix": 0, "median_surface": 0, "solide": False,
                "raison": "aucune vente comparable"}
    m2 = sorted(v["eur_m2"] for v in ventes)
    prix = sorted(v["valeur"] for v in ventes)
    med = statistics.median(m2)
    q1, q3 = m2[len(m2) // 4], m2[3 * len(m2) // 4]
    dispersion = (q3 - q1) / med * 100 if med else 0
    ecart_type_pct = (D.ecart_type(m2) / med * 100) if med else 0
    n = len(ventes)
    raison, solide = "échantillon suffisant", True
    if n < D.MIN_VENTES:
        solide, raison = False, f"seulement {n} vente(s) : moins de {D.MIN_VENTES} exigées"
    elif dispersion > 45:
        solide, raison = False, f"écart interquartile {dispersion:.0f} % : marché hétérogène"
    return {"n": n, "median_eur_m2": med, "q1": q1, "q3": q3,
            "dispersion": dispersion, "ecart_type_pct": ecart_type_pct,
            "median_prix": statistics.median(prix),
            "median_surface": statistics.median(v["surface"] for v in ventes),
            "solide": solide, "raison": raison}


def comparables_avec_repli(commune=None, insee=None, voie=None, type_local="Appartement",
                           surface=None, tolerance=0.35):
    """Comparables en cascade — la bande de surface reste stricte, la fenêtre s'élargit.

    Un comparable doit avoir une **taille proche** : à Écouen, élargir la bande autour d'une
    maison de 100 m² fait entrer des maisons de 40 m² dont le prix au m² vaut le double. Quand
    la bande stricte ne donne pas cinq ventes, on élargit le temps, puis on passe au modèle
    taille + terrain (voir `dossier.construire`) — jamais la surface.
    """
    essais = [
        (D.ANNEES_REFERENCE, f"surface à ± {tolerance*100:.0f} %, "
                             f"ventes {'-'.join(str(a) for a in D.ANNEES_REFERENCE)}"),
        (D.ANNEES, f"surface à ± {tolerance*100:.0f} %, "
                   f"ventes {'-'.join(str(a) for a in D.ANNEES)}"),
    ]
    meilleur, description = None, ""
    for annees, desc in essais:
        v = comparables(commune=commune, insee=insee, voie=voie, type_local=type_local,
                        surface=surface, tolerance=tolerance, annees=annees)
        if meilleur is None or len(v) > len(meilleur):
            meilleur, description = v, desc
        if len(v) >= D.MIN_VENTES:
            return v, desc
    return meilleur or [], description


def prix_par_voie(commune=None, insee=None, type_local="Appartement",
                  annees=None, min_ventes=3, surface=None):
    """Prix médian au m² par voie — c'est là que se joue la décision, pas dans la commune."""
    par_voie = {}
    for v in comparables(commune=commune, insee=insee, type_local=type_local, annees=annees,
                         surface=surface):
        if v["voie"]:
            par_voie.setdefault(v["voie"], []).append(v)
    out = []
    for voie, ventes in par_voie.items():
        if len(ventes) < min_ventes:
            continue
        s = synthese(ventes)
        out.append({"voie": voie, "n": s["n"], "median_eur_m2": s["median_eur_m2"],
                    "dispersion": s["dispersion"], "median_surface": s["median_surface"]})
    out.sort(key=lambda x: x["median_eur_m2"])
    return out


_index_communes = None
_commune_cache = {}


def index_communes():
    """Index {NOM EN MAJUSCULES: {insee: nombre de ventes}} construit une seule fois.

    Résoudre un nom de commune en parcourant toutes les ventes à chaque appel coûtait des
    secondes par dossier dès que huit départements étaient chargés ; l'index le fait une fois.
    """
    global _index_communes
    if _index_communes is not None:
        return _index_communes
    agg, infos = defaultdict(lambda: defaultdict(int)), {}
    for t in ("Appartement", "Maison"):
        for v in D.ventes_multi(D.ANNEES, t):
            nom = v["commune"].upper()
            if not nom:
                continue
            agg[nom][v["insee"]] += 1
            infos[v["insee"]] = (v["commune"], v["departement"])
    _index_communes = (agg, infos)
    return _index_communes


def resout_commune(reference):
    """Retrouve la commune visée à partir d'un nom ou d'un code INSEE.

    Avec plusieurs départements chargés, un nom peut exister deux fois (« Sainte-Colombe »,
    « Villiers »…). On retient alors la commune qui compte le plus de ventes, et on le dit :
    une homonymie silencieuse fausserait tout le dossier. Un code INSEE, lui, ne prête à
    aucune confusion.
    """
    ref = (reference or "").strip()
    if not ref:
        return None
    if ref in _commune_cache:
        return _commune_cache[ref]
    agg, infos = index_communes()
    if ref.isdigit() and len(ref) >= 5:
        commune, dep = infos.get(ref, (ref, None))
        res = {"insee": ref, "commune": commune, "departement": dep, "homonymes": 0,
               "source": "code INSEE"}
        _commune_cache[ref] = res
        return res
    par_insee = agg.get(ref.upper())
    if not par_insee:
        # Le nom saisi n'est pas exactement celui de l'état civil (« Paris 11e » pour
        # « Paris 11e Arrondissement ») : on cherche par préfixe, puis par inclusion, et on
        # retient la commune la mieux servie. Le nom retenu est renvoyé, donc vérifiable.
        cible = ref.upper()
        for test in (lambda k: k.startswith(cible), lambda k: cible in k):
            candidats = {k: v for k, v in agg.items() if test(k)}
            if candidats:
                meilleur = max(candidats.items(),
                               key=lambda kv: sum(kv[1].values()))
                par_insee = meilleur[1]
                break
    if not par_insee:
        return None
    classement = sorted(par_insee.items(), key=lambda kv: -kv[1])
    insee, n = classement[0]
    commune, dep = infos.get(insee, (ref, None))
    res = {"insee": insee, "commune": commune, "departement": dep, "ventes": n,
           "homonymes": len(classement) - 1, "source": "nom de commune",
           "autres": [{"insee": i, "commune": infos.get(i, ("", None))[0],
                       "departement": infos.get(i, ("", None))[1], "ventes": c}
                      for i, c in classement[1:4]]}
    _commune_cache[ref] = res
    return res


def controle_vraisemblance(departement="95", annee=2025, type_local="Appartement",
                           bornes=(800, 12_000)):
    """Garde-fou permanent : la médiane départementale doit rester plausible.
    C'est ce contrôle qui a attrapé « Eaubonne à 1 022 EUR/m² » le 14/10/2026."""
    v = D.ventes(annee, type_local)
    med = D.mediane([x["eur_m2"] for x in v])
    ok = bornes[0] <= med <= bornes[1]
    return {"median_departementale": med, "n": len(v), "plausible": ok,
            "raison": f"mediane {med:.0f} EUR/m2 dans les bornes {bornes}" if ok
                      else f"mediane {med:.0f} EUR/m2 HORS bornes {bornes} : filtre a verifier"}


# ---------------------------------------------------------------- valeur
def modele_valeur(commune=None, insee=None, type_local="Maison", annees=D.ANNEES,
                  avec_terrain=None):
    """Modèle log-log prix ~ surface (+ terrain). Renvoie les coefficients et l'incertitude.

    Le terme de terrain est écarté si le terrain ne varie pas (appartements, ou toutes les
    parcelles identiques) : une variable constante rend le système singulier.
    """
    ventes = comparables(commune=commune, insee=insee, type_local=type_local, annees=annees,
                         type_surface=type_local)
    ventes = [v for v in ventes if v["surface"] > 0 and v["valeur"] > 0]
    if len(ventes) < 8:
        return None
    if avec_terrain is None:
        terrains = {round(v["terrain"]) for v in ventes}
        avec_terrain = type_local != "Appartement" and len(terrains) > 1
    if avec_terrain:
        X = [[1.0, math.log(v["surface"]), math.log(1 + v["terrain"])] for v in ventes]
    else:
        X = [[1.0, math.log(v["surface"])] for v in ventes]
    y = [math.log(v["valeur"]) for v in ventes]
    beta, res, r2 = D.ols(X, y)
    return {"beta": beta, "r2": r2, "n": len(ventes),
            "sigma": statistics.pstdev(res) if len(res) > 1 else 0.0,
            "avec_terrain": avec_terrain, "type": type_local, "annees": list(annees)}


def valeur_estimee(modele, surface, terrain=0.0):
    """Valeur centrale et fourchette ± 1 écart-type résiduel."""
    if not modele:
        return None
    b = modele["beta"]
    if modele["avec_terrain"]:
        log_p = b[0] + b[1] * math.log(surface) + b[2] * math.log(1 + terrain)
    else:
        log_p = b[0] + b[1] * math.log(surface)
    centre = math.exp(log_p)
    s = modele["sigma"]
    return {"valeur": centre, "bas": centre * math.exp(-s), "haut": centre * math.exp(s),
            "eur_m2": centre / surface if surface else 0, "sigma_pct": s * 100}


# ---------------------------------------------------------------- loyer
def loyer_reference(insee=None, commune=None, type_local="Appartement"):
    """Loyer d'annonce au m² de la carte des loyers du ministère, avec ses observations."""
    loy = D.loyers()
    ref = loy.get(insee) if insee else None
    if not ref and commune:
        for v in D.ventes(2025, type_local):
            if v["commune"].upper() == commune.strip().upper() and v["insee"] in loy:
                ref = loy[v["insee"]]
                insee = v["insee"]
                break
    if not ref:
        return None
    return {"loyer_m2": ref[0], "observations": ref[1], "insee": insee,
            "fiabilite": "solide" if ref[1] >= 1000 else ("moyenne" if ref[1] >= 300 else "faible")}


def loyer_mensuel(loyer_m2, surface, decote_annonce=0.0):
    """Un loyer d'annonce n'est pas un loyer signé : la décote est un paramètre, pas un fait."""
    return loyer_m2 * (1 - decote_annonce) * surface


def rendement_brut(loyer_mensuel_ht, prix_achat):
    if not prix_achat:
        return 0.0
    return loyer_mensuel_ht * 12 / prix_achat * 100
