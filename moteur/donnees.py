"""ImmoPilot — moteur d'aide à la décision en investissement immobilier.

Règle fondatrice : **le modèle de langage ne calcule jamais.** Tout le chiffrage est ici,
déterministe, testable, reproductible.

Filtre d'artefacts documenté (leçon du 14/10/2026) :
  mutation de type Vente · local de type Maison ou Appartement · surface du logement
  comprise entre SURF_MIN et SURF_MAX · le logement représente au moins PART_SURFACE de la
  surface bâtie déclarée dans la mutation · prix au m² borné entre PRIX_MIN_M2 et PRIX_MAX_M2.
Sans ces garde-fous, une mutation d'immeuble entier fausse le prix au m² d'un facteur deux.
"""
import csv
import io
import math
import os
import re
import statistics
from collections import defaultdict

VERSION = "0.1.0"
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DONNEES = os.path.join(BASE, "donnees")

ANNEES = (2021, 2022, 2023, 2024, 2025)
ANNEES_REFERENCE = (2023, 2024, 2025)  # fenêtre de référence : le marché a perdu 13 % depuis
                                       # 2022, mélanger cinq ans gonfle la médiane de ~15 %
PART_SURFACE = 0.40               # au-delà, on répartit le prix au prorata des surfaces
TOLERANCE_SURFACE = 0.35          # bande de comparables autour de la surface cible
PRIX_MIN_M2, PRIX_MAX_M2 = 500, 25_000
SURF_APPART = (15.0, 45.0)
SURF_MAISON = (30.0, 300.0)
MIN_VENTES = 5

# Périmètre de données : un fichier DVF par département et par millésime. Le moteur ne suppose
# pas le 95 en dur — il travaille sur les départements réellement présents dans donnees/.
DEPARTEMENTS_DEFAUT = ("95",)
_cible_perimetre = None


def departements_disponibles():
    """Départements réellement téléchargés (détectés sur les fichiers présents)."""
    if not os.path.isdir(DONNEES):
        return DEPARTEMENTS_DEFAUT
    trouves = {m.group(1) for m in
               (re.match(r"dvf(\d{2,3})_\d{4}\.csv$", n) for n in os.listdir(DONNEES)) if m}
    return tuple(sorted(trouves)) or DEPARTEMENTS_DEFAUT


def perimetre(departements=None):
    """Départements sur lesquels porte le chargement courant."""
    if departements:
        return tuple(departements)
    return _cible_perimetre or departements_disponibles()


def fixe_perimetre(departements=None):
    """Force le périmètre du moteur (export dédié, démonstration, test). None = tous."""
    global _cible_perimetre
    _cible_perimetre = tuple(departements) if departements else None
    return perimetre()

_cache_dvf = {}


def _ouvre(path):
    """DVF est en utf-8 ; la carte des loyers est en latin-1 avec des points-virgules."""
    brut = open(path, "rb").read()
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return io.StringIO(brut.decode(enc))
        except UnicodeDecodeError:
            continue
    return io.StringIO(brut.decode("utf-8", errors="replace"))


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def ventes(annee, type_local="Appartement", departement="95"):
    """Ventes retenues pour une année : liste de dicts légers (une ligne par logement)."""
    cle = (annee, type_local, departement)
    if cle in _cache_dvf:
        return _cache_dvf[cle]

    chemin = os.path.join(DONNEES, f"dvf{departement}_{annee}.csv")
    if not os.path.exists(chemin):
        # Pas de repli silencieux sur un autre département : mélanger deux marchés serait pire
        # que ne rien avoir. Un département absent rend simplement une liste vide.
        _cache_dvf[cle] = []
        return []

    par_mutation = defaultdict(list)
    with open(chemin, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("nature_mutation") != "Vente" or r.get("type_local") != type_local:
                continue
            if not r.get("valeur_fonciere") or not r.get("surface_reelle_bati"):
                continue
            if not r.get("id_mutation"):
                continue
            par_mutation[r["id_mutation"]].append(r)

    lo, hi = SURF_APPART if type_local == "Appartement" else SURF_MAISON
    out = []
    for lignes in par_mutation.values():
        surf_totale = sum(_f(l["surface_reelle_bati"]) for l in lignes)
        for l in lignes:
            s = _f(l["surface_reelle_bati"])
            if not (lo <= s <= hi):
                continue
            if surf_totale and s / surf_totale < PART_SURFACE:
                continue
            # Prix attribué au logement : quand la mutation porte aussi d'autres lots
            # (garage, cave, second logement), le prix est réparti au prorata des surfaces.
            # Sans cette répartition, le prix au m² d'un logement vendu avec un garage
            # est surestimé — c'est l'artefact qui faussait les analyses du 14/10.
            part = (s / surf_totale) if surf_totale > s else 1.0
            prix = _f(l["valeur_fonciere"]) * part
            if s <= 0:
                continue
            eur_m2 = prix / s
            if not (PRIX_MIN_M2 <= eur_m2 <= PRIX_MAX_M2):
                continue
            out.append({
                "annee": annee, "date": l.get("date_mutation", ""),
                "departement": departement,
                "commune": (l.get("nom_commune") or "").strip(),
                "cp": (l.get("code_postal") or "").strip(),
                "insee": (l.get("code_commune") or "").strip(),
                "voie": (l.get("adresse_nom_voie") or "").strip().upper(),
                "numero": (l.get("adresse_numero") or "").strip(),
                "type": l.get("type_local"), "surface": s, "valeur": prix,
                "eur_m2": eur_m2,
                "terrain": sum(_f(x.get("surface_terrain")) for x in lignes),
                "pieces": l.get("nombre_pieces_principales") or "",
                "lat": _f(l.get("latitude")), "lon": _f(l.get("longitude")),
            })
    _cache_dvf[cle] = out
    return out


def ventes_multi(annees=ANNEES, type_local="Appartement", departements=None):
    out = []
    for dep in perimetre(departements):
        for a in annees:
            out.extend(ventes(a, type_local, dep))
    return out


_indice_cache = {}


def indice_annuel(type_local="Appartement", annees=ANNEES, departements=None):
    """Indice départemental des prix au m², base 1.0 = la dernière année connue.

    Sert à **actualiser les comparables anciens** : le marché du Val-d'Oise a perdu 13 % de son
    prix au m² entre 2022 et 2025. Sans cette actualisation, élargir la fenêtre pour avoir plus
    de ventes gonfle la médiane — c'est l'erreur qui a été mesurée le 15/10/2026 (Groslay
    passait de 3 526 à 4 029 EUR/m² en passant d'un an à trois ans de données).
    """
    deps = perimetre(departements)
    cle = (type_local, tuple(annees), deps)
    if cle in _indice_cache:
        return _indice_cache[cle]
    derniere = max(annees)
    par_dep, medianes = {}, {}
    for dep in deps:
        med = {}
        for a in annees:
            med[a] = mediane([x["eur_m2"] for x in ventes(a, type_local, dep)])
        ref = med.get(derniere) or 0
        par_dep[dep] = {a: (ref / m if m else 1.0) for a, m in med.items()}
        medianes[dep] = med
    # Indice « régional » publié : la médiane des indices départementaux, pour l'affichage.
    median_regional = {a: mediane([par_dep[d][a] for d in deps if d in par_dep]) for a in annees}
    _indice_cache[cle] = {"indice": par_dep, "mediane_par_annee": medianes,
                          "indice_regional": median_regional, "annee_reference": derniere,
                          "departements": list(deps)}
    return _indice_cache[cle]


_actu_cache = {}


def ventes_actualisees(annees=ANNEES, type_local="Appartement", departements=None):
    """Ventes dont le prix au m² est ramené au niveau de la dernière année connue.

    Résultat mis en cache : la webapp appelle cette fonction à chaque dossier, et recopier
    deux cent mille ventes à chaque clic se sentirait.
    """
    deps = perimetre(departements)
    cle = (tuple(annees), type_local, deps)
    if cle in _actu_cache:
        return _actu_cache[cle]
    idx = indice_annuel(type_local, annees, deps)["indice"]
    out = []
    for v in ventes_multi(annees, type_local, deps):
        w = dict(v)
        # chacun est ramené au niveau de sa propre année de référence, département par département :
        # l'Île-de-France et le Val-d'Oise n'ont pas connu la même baisse depuis 2022
        w["eur_m2_brut"] = v["eur_m2"]
        facteur = (idx.get(v.get("departement")) or {}).get(v["annee"], 1.0)
        w["eur_m2"] = v["eur_m2"] * facteur
        w["valeur_actualisee"] = w["eur_m2"] * v["surface"]
        out.append(w)
    _actu_cache[cle] = out
    return out


def precharge(departements=None):
    """Charge tout ce dont un dossier a besoin, une fois. Appelé au démarrage du serveur."""
    deps = perimetre(departements)
    for type_local in ("Appartement", "Maison"):
        indice_annuel(type_local, ANNEES, deps)
        for annees in (ANNEES_REFERENCE, ANNEES):
            ventes_actualisees(annees, type_local, deps)
    loyers_cache = loyers(deps)
    return {"departements": list(deps),
            "ventes_appart": len(_actu_cache[(tuple(ANNEES_REFERENCE), "Appartement", deps)]),
            "ventes_maison": len(_actu_cache[(tuple(ANNEES_REFERENCE), "Maison", deps)]),
            "communes_loyers": len(loyers_cache)}


_loyers_cache = {}


def loyers(departements=None):
    """Carte des loyers d'annonce du ministère : {insee: (loyer_m2, nb_observations)}.

    Le fichier couvre la France entière (34 900 communes) : on filtre sur le périmètre chargé.
    Millésime 2025, appartements 1-2 pièces.
    """
    deps = perimetre(departements)
    if deps in _loyers_cache:
        return _loyers_cache[deps]
    chemin = os.path.join(DONNEES, "loyers_12p_2025.csv")
    if not os.path.exists(chemin):
        return {}
    out = {}
    for r in csv.DictReader(_ouvre(chemin), delimiter=";"):
        if r.get("DEP") not in deps:
            continue
        try:
            loy = float(r["loypredm2"].replace(",", "."))
        except ValueError:
            continue
        out[r["INSEE_C"]] = (loy, int(r["nbobs_com"] or 0))
    _loyers_cache[deps] = out
    return out


def fr(x, dec=0):
    """Format français : espace fine comme séparateur de milliers, virgule décimale."""
    return f"{x:,.{dec}f}".replace(",", "\u202f").replace(".", ",")


def eur(x, dec=0):
    return fr(x, dec) + " €"


def euro_m2(x):
    return fr(x) + " €/m²"


def mediane(valeurs):
    return statistics.median(valeurs) if valeurs else 0.0


def ecart_type(valeurs):
    return statistics.pstdev(valeurs) if len(valeurs) > 1 else 0.0


def ols(X, y):
    """Moindres carrés ordinaires, avec constante dans X. Renvoie (beta, residus, r2)."""
    n, k = len(X), len(X[0])
    XtX = [[sum(X[i][a] * X[i][b] for i in range(n)) for b in range(k)] for a in range(k)]
    Xty = [sum(X[i][a] * y[i] for i in range(n)) for a in range(k)]
    A = [row[:] + [Xty[a]] for a, row in enumerate(XtX)]
    for c in range(k):
        p = max(range(c, k), key=lambda r: abs(A[r][c]))
        A[c], A[p] = A[p], A[c]
        piv = A[c][c]
        if abs(piv) < 1e-12:
            raise ValueError("matrice singuliere : une variable est constante")
        A[c] = [v / piv for v in A[c]]
        for r in range(k):
            if r != c and A[r][c]:
                f = A[r][c]
                A[r] = [A[r][j] - f * A[c][j] for j in range(k + 1)]
    beta = [A[i][k] for i in range(k)]
    res = [y[i] - sum(beta[a] * X[i][a] for a in range(k)) for i in range(n)]
    sse = sum(r * r for r in res)
    sst = sum((v - statistics.mean(y)) ** 2 for v in y)
    return beta, res, (1 - sse / sst if sst else 0.0)
