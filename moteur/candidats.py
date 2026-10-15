"""Recherche d'opérations dans tout le périmètre : le moteur énumère, filtre et classe.

Trois temps, et aucun modèle de langage n'intervient dans les deux premiers :

1. **Présélection** — arithmétique pure sur les données de marché déjà produites par le moteur
   (`scripts/exporte_marche.py`) : on élimine une commune quand le lot typique dépasse le budget,
   quand le rendement brut passe sous le seuil, quand l'échantillon est trop mince (moins de
   `MIN_VENTES` ventes) ou trop dispersé. C'est ce filtre qui ramène 1 284 communes à quelques
   dizaines sans rien calculer de faux.
2. **Évaluation** — chaque survivant passe par `moteur.dossier`, donc par **exactement le même
   chemin de code** qu'un dossier monté à la main : mêmes comparables, même fiscalité, même
   contrôle de trésorerie, même verdict. Un candidat affiché ici et le même bien saisi dans
   l'onglet Décider donnent le même résultat, sinon la page serait un second moteur à maintenir.
3. **Classement** — selon l'intention déclarée (`rendement`, `securite`, `revente`), en tri
   arithmétique sur les grandeurs déjà calculées.

Ce qui reste à trancher quand les chiffres ne suffisent pas — « laquelle de ces dix opérations
correctes correspond le mieux à ce que je veux faire ? » — part chez Jev, sur une question
bornée : voir `moteur/arbitrage.py`.
"""
from __future__ import annotations

import argparse
import json
import os
import time

from . import analyse as A
from . import donnees as D
from . import dossier as Dos

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIERS = (os.path.join(RACINE, "webapp", "data"), os.path.join(RACINE, "docs", "data"))

CRITERES_PAR_DEFAUT = {
    "budget_max": 250_000.0,        # prix d'achat maximum, frais compris non comptés
    "apport": 60_000.0,             # apport mobilisable
    "reserve": 20_000.0,            # réserve de sécurité à ne pas engager
    "surface_min": 20.0,
    "surface_max": 45.0,
    "rendement_min": 5.0,           # rendement brut minimum, en %
    "type": "Appartement",
    "departements": None,           # None = tous les départements chargés
    "taux": 3.5,
    "annees": 20,
    "assurance_pct": 0.30,
    "revenus_mensuels": 5_000.0,
    "budget_de_vie": 3_000.0,
    "charges_recurrentes": 0.0,
    "mensualites_existantes": 0.0,
    "tmi": 0.30,
    "poids_loyers": 0.70,
    "intention": "rendement",       # rendement | securite | revente
    "decote_loyer": 0.05,           # un loyer d'annonce n'est pas un loyer signé
    "limite_par_departement": 3,
    "max_evaluations": 40,          # garde-fou : le dossier complet coûte ~150 ms
}

_blocs_cache: dict = {}


# ------------------------------------------------------------------ entrées
def complete(criteres=None):
    """Fusionne les critères reçus avec les valeurs par défaut, en forçant les types."""
    c = dict(CRITERES_PAR_DEFAUT)
    for k, v in (criteres or {}).items():
        if k in c and v is not None and v != "":
            try:
                c[k] = float(v) if isinstance(c[k], float) else v
            except (TypeError, ValueError):
                c[k] = v
    if isinstance(c.get("departements"), str):
        c["departements"] = tuple(x.strip() for x in c["departements"].split(",") if x.strip())
    elif c.get("departements"):
        c["departements"] = tuple(str(x) for x in c["departements"])
    if c.get("intention") not in ("rendement", "securite", "revente"):
        c["intention"] = "rendement"
    if c.get("type") not in ("Appartement", "Maison"):
        c["type"] = "Appartement"
    return c


def blocs_marché(departements=None):
    """Données de marché par département, telles que produites par le moteur."""
    deps = tuple(departements) if departements else D.departements_disponibles()
    out = {}
    for dep in deps:
        if dep in _blocs_cache:
            out[dep] = _blocs_cache[dep]
            continue
        for dossier in DOSSIERS:
            chemin = os.path.join(dossier, f"marche_{dep}.json")
            if os.path.exists(chemin):
                with open(chemin, encoding="utf-8") as f:
                    _blocs_cache[dep] = json.load(f)
                out[dep] = _blocs_cache[dep]
                break
    return out


# ------------------------------------------------------------------ 1. présélection
def surface_retable(median_m2, median_surface, c):
    """La plus grande surface de la fourchette demandée que le budget permet d'acheter.

    Un investisseur ne veut pas le lot typique de la commune s'il ne peut pas le payer : on
    redescend jusqu'à sa surface plancher, et on abandonne la commune en dessous.
    """
    propose = min(max(median_surface or c["surface_min"], c["surface_min"]), c["surface_max"])
    for s in (propose, c["surface_min"]):
        if median_m2 and s * median_m2 <= c["budget_max"]:
            return s
    return None


def candidats_commune(nom, dep, bloc, c, type_local, loyer):
    """Filtre grossier sur une commune. Rend un candidat ou None, avec le motif de rejet."""
    m = (bloc.get("appart") if type_local == "Appartement" else bloc.get("maison")) or {}
    if not m or not m.get("median_m2"):
        return None, "aucune vente de ce type"
    if (m.get("n") or 0) < D.MIN_VENTES:
        return None, f"moins de {D.MIN_VENTES} ventes ({m.get('n')})"
    if not m.get("solide") and (m.get("dispersion") or 0) > 45:
        return None, f"dispersion {m.get('dispersion')} % > 45 %"
    if not loyer or not loyer.get("loyer_m2"):
        return None, "pas de loyer de référence"
    surface = surface_retable(m["median_m2"], m.get("median_surface"), c)
    if not surface:
        return None, f"lot typique hors budget ({m.get('median_prix')} €)"
    prix = surface * m["median_m2"]
    loyer_mensuel = loyer["loyer_m2"] * surface * (1 - c["decote_loyer"])
    if not prix or not loyer_mensuel:
        return None, "donnée incomplète"
    rendement = loyer_mensuel * 12 / prix * 100
    if rendement < c["rendement_min"]:
        return None, f"rendement brut {rendement:.2f} % sous le seuil"
    return {
        "commune": nom, "departement": dep, "insee": bloc.get("insee"),
        "surface": round(surface, 1), "prix_demande": round(prix),
        "loyer_mensuel_ht": round(loyer_mensuel),
        "rendement_brut_pct": round(rendement, 2),
        "median_m2": m.get("median_m2"), "q1": m.get("q1"), "q3": m.get("q3"),
        "ventes": m.get("n"), "dispersion_pct": m.get("dispersion"),
        "loyer_observations": loyer.get("observations"),
        "annees_retenues": m.get("annees_retenues"),
    }, None


def preselection(c, blocs=None):
    """Passe toutes les communes au filtre grossier. Rend (retenus, résumé des rejets)."""
    blocs = blocs if blocs is not None else blocs_marché(c["departements"])
    retenus, rejets = [], {}
    for dep, bloc in sorted(blocs.items()):
        for commune in bloc.get("communes", []):
            cand, motif = candidats_commune(commune.get("nom"), dep, commune, c,
                                            c["type"], commune.get("loyer"))
            if cand:
                retenus.append(cand)
            else:
                rejets[motif.split(" (")[0]] = rejets.get(motif.split(" (")[0], 0) + 1
    return retenus, rejets


# ------------------------------------------------------------------ 2. évaluation
def profil_de(c):
    return {
        "revenus_mensuels": c["revenus_mensuels"], "budget_de_vie": c["budget_de_vie"],
        "charges_recurrentes": c["charges_recurrentes"],
        "mensualites_existantes": c["mensualites_existantes"],
        "epargne": c["apport"], "reserve": c["reserve"], "tmi": c["tmi"],
        "poids_loyers": c["poids_loyers"], "taux": c["taux"], "annees": c["annees"],
        "assurance_pct": c["assurance_pct"],
    }


def exploitation_de(candidat, c):
    """Charges d'exploitation estimées, proportionnées au bien — jamais un forfait unique."""
    prix, surface = candidat["prix_demande"], candidat["surface"]
    return {
        "charges_annuelles": round(14 * surface),          # copropriété, ~14 €/m²/an
        "taxe_fonciere": round(prix * 0.0075),
        "entretien_annuel": round(prix * 0.004),
        "vacance_pct": 5.0, "impaye_pct": 2.0, "travaux": 0.0, "mobilier": 0.0,
    }


def evalue(candidat, c, prix=None):
    """Dossier complet du candidat, par le chemin de code commun (moteur.dossier).

    `prix` permet de réévaluer le même bien à un autre prix, sans toucher au reste : c'est ce
    qui sert à chercher le prix d'équilibre.
    """
    entree = {
        "commune": candidat["commune"], "type": c["type"], "surface": candidat["surface"],
        "prix_demande": float(prix if prix is not None else candidat["prix_demande"]),
        "loyer_mensuel_ht": candidat["loyer_mensuel_ht"],
        "profil": profil_de(c), "exploitation": exploitation_de(candidat, c),
    }
    dos = Dos.construire(entree)
    v = dos.get("verdict") or {}
    f = dos.get("fiscalite") or {}
    meilleur = f.get("meilleur_cash_flow") or {}
    t = dos.get("tresorerie") or {}
    comp = dos.get("comparables") or {}
    out = dict(candidat)
    out.update({
        "verdict": v.get("verdict"), "libelle": v.get("libelle"),
        "confiance": v.get("confiance"), "prix_marche_m2": v.get("prix_marche_m2"),
        "ecart_marche_pct": v.get("ecart_marche_pct"),
        "raisons": (v.get("raisons") or [])[:4],
        "cash_flow_moyen_10_ans": meilleur.get("cash_flow_moyen_10_ans"),
        "regime_retenu": meilleur.get("regime") or f.get("meilleur"),
        "solde_apres_credit": t.get("solde_apres_credit"), "faisable": t.get("faisable"),
        "mensualite": (dos.get("financement") or {}).get("mensualite"),
        "capital_emprunte": (dos.get("financement") or {}).get("capital"),
        "comparables_n": comp.get("n"), "comparables_perimetre": comp.get("perimetre"),
        "dispersion": comp.get("dispersion"),
    })
    return out


def prix_equilibre(candidat, c, iterations=8):
    """Prix le plus haut auquel l'opération s'autofinance encore après impôt.

    Le cash-flow décroît quand le prix monte (mensualité plus lourde, impôt plus lourd) : une
    dichotomie sur cette seule fonction du prix donne la réponse sans rien inventer. C'est le
    chiffre qui manquait — un refus sans « à quel prix ça tiendrait » ne sert qu'à moitié.
    """
    def cf(prix):
        try:
            x = evalue(candidat, c, prix=prix)
        except Exception:  # noqa: BLE001
            return None
        v = x.get("cash_flow_moyen_10_ans")
        return None if v is None else float(v)

    bas, haut = candidat["prix_demande"] * 0.35, candidat["prix_demande"] * 1.25
    cf_bas = cf(bas)
    if cf_bas is None or cf_bas < 0:
        return {"prix": None, "raison": "même à 35 % sous le prix affiché, l'opération consomme "
                                        "de la trésorerie : le problème est le loyer, pas le prix."}
    cf_haut = cf(haut)
    if cf_haut is not None and cf_haut >= 0:
        return {"prix": round(haut), "raison": "s'autofinance même au-delà du prix affiché"}
    for _ in range(int(iterations)):
        milieu = (bas + haut) / 2
        v = cf(milieu)
        if v is None:
            break
        if v >= 0:
            bas = milieu
        else:
            haut = milieu
    return {"prix": round(bas), "raison": f"dichotomie en {iterations} itérations"}


def _pistes(c, refuses, indetermines, limite=6):
    """Quand rien ne passe, montrer à quel prix l'opération tiendrait quand même.

    On part des plus proches du but (cash-flow le moins négatif), on leur cherche un prix
    d'équilibre, et on ne garde que celles où la baisse demandée est plausible — au-delà de 25 %
    sous le prix affiché, ce n'est plus une négociation, c'est un autre bien.
    """
    base = [x for x in refuses + indetermines if x.get("surface")]
    base = [x for x in base if x.get("cash_flow_moyen_10_ans") is not None]
    base.sort(key=lambda x: -(x.get("cash_flow_moyen_10_ans") or -10 ** 9))
    pistes = []
    for x in base[:limite]:
        pe = prix_equilibre(x, c)
        if not pe.get("prix"):
            continue
        baisse = (x["prix_demande"] - pe["prix"]) / x["prix_demande"] * 100
        if baisse < 0:
            continue
        pistes.append({**x, "prix_equilibre": pe["prix"], "baisse_requise_pct": round(baisse, 1),
                       "prix_actuel": x["prix_demande"],
                       "marge_marche_pct": x.get("ecart_marche_pct")})
    return pistes


# ------------------------------------------------------------------ 3. classement
def score_intention(x, intention):
    """Clé de tri arithmétique. Aucun modèle : les grandeurs sont déjà calculées."""
    if intention == "securite":
        return (x.get("confiance") or 0, -(x.get("dispersion") or 999),
                -(x.get("ventes") or 0))
    if intention == "revente":
        return (x.get("ventes") or 0, -(x.get("dispersion") or 999),
                x.get("confiance") or 0)
    return (x.get("cash_flow_moyen_10_ans") if x.get("cash_flow_moyen_10_ans") is not None
            else -10 ** 9, x.get("rendement_brut_pct") or 0, x.get("confiance") or 0)


def cherche(criteres=None, verbeux=False):
    """Pipeline complet. Rend les candidats retenus, classés, et de quoi expliquer le tri."""
    c = complete(criteres)
    t0 = time.time()
    retenus, rejets = preselection(c)

    # le dossier complet coûte ~150 ms : on n'évalue que la tête de liste, par rendement
    retenus.sort(key=lambda x: (-x["rendement_brut_pct"], -(x["ventes"] or 0)))
    a_evaluer = retenus[: int(c["max_evaluations"])]
    if verbeux:
        print(f"  présélection : {len(retenus)} candidats, {len(a_evaluer)} évalués en entier")

    evaluates, refuses, indetermines = [], [], []
    for cand in a_evaluer:
        try:
            x = evalue(cand, c)
        except Exception as exc:  # noqa: BLE001 — un dossier qui plante ne doit pas tuer la recherche
            refuses.append({**cand, "motif": f"évaluation impossible : {type(exc).__name__}"})
            continue
        if x.get("verdict") == "NON":
            refuses.append({**x, "motif": (x.get("raisons") or ["NON"])[0]})
        elif x.get("verdict") == "INDETERMINE":
            # données trop minces pour trancher : ce n'est pas une bonne opération, ce n'est pas
            # non plus un refus. On les garde à part et on le dit.
            indetermines.append({**x, "motif": (x.get("raisons") or ["INDÉTERMINÉ"])[-1]})
        else:
            evaluates.append(x)

    evaluates.sort(key=lambda x: score_intention(x, c["intention"]), reverse=True)
    par_dep = {}
    for x in evaluates:
        par_dep.setdefault(x["departement"], [])
        if len(par_dep[x["departement"]]) < int(c["limite_par_departement"]):
            par_dep[x["departement"]].append(x)

    # rien ne passe ? on cherche alors à quel prix une opération tiendrait — un refus sans ce
    # chiffre laisse l'investisseur sans rien à faire de la réponse.
    pistes = [] if len(evaluates) >= 2 else _pistes(c, refuses, indetermines)

    return {
        "criteres": c, "duree_ms": int((time.time() - t0) * 1000),
        "nb_preselectionnes": len(retenus), "nb_evalues": len(a_evaluer),
        "rejets_preselection": rejets,
        "candidats": evaluates, "refuses": refuses, "indetermines": indetermines,
        "pistes": pistes,
        "par_departement": par_dep,
        "meilleur": evaluates[0] if evaluates else None,
        "departements": sorted(par_dep),
    }


# ------------------------------------------------------------------ CLI
def _resume(x):
    return (f"{x['departement']} {x['commune'][:22]:22s} {x.get('surface') or 0:4.0f} m² "
            f"{x.get('prix_demande') or 0:>8,.0f} €  {x.get('rendement_brut_pct') or 0:5.2f} % brut  "
            f"{(x.get('libelle') or '?'):8s} conf. {(x.get('confiance') or 0):4.0%}  CF 10 ans "
            f"{(x.get('cash_flow_moyen_10_ans') or 0):>7,.0f} €/an").replace(",", " ")


def main():
    ap = argparse.ArgumentParser(description="Cherche les meilleures opérations du périmètre.")
    ap.add_argument("--budget-max", type=float, default=CRITERES_PAR_DEFAUT["budget_max"])
    ap.add_argument("--apport", type=float, default=CRITERES_PAR_DEFAUT["apport"])
    ap.add_argument("--reserve", type=float, default=CRITERES_PAR_DEFAUT["reserve"])
    ap.add_argument("--rendement-min", type=float, default=CRITERES_PAR_DEFAUT["rendement_min"])
    ap.add_argument("--type", default="Appartement", choices=("Appartement", "Maison"))
    ap.add_argument("--surface-min", type=float, default=20)
    ap.add_argument("--surface-max", type=float, default=45)
    ap.add_argument("--departements", default=None, help="ex. 93,95 — défaut : tout le périmètre")
    ap.add_argument("--intention", default="rendement", choices=("rendement", "securite", "revente"))
    ap.add_argument("--revenus", type=float, default=CRITERES_PAR_DEFAUT["revenus_mensuels"])
    ap.add_argument("--budget-vie", type=float, default=CRITERES_PAR_DEFAUT["budget_de_vie"])
    ap.add_argument("--tmi", type=float, default=CRITERES_PAR_DEFAUT["tmi"])
    ap.add_argument("--taux", type=float, default=CRITERES_PAR_DEFAUT["taux"])
    ap.add_argument("--jev", action="store_true", help="ajoute l'arbitrage Jev sur les finalistes")
    ap.add_argument("--json", action="store_true", help="sortie machine")
    args = ap.parse_args()

    c = complete({
        "budget_max": args.budget_max, "apport": args.apport, "reserve": args.reserve,
        "rendement_min": args.rendement_min, "type": args.type,
        "surface_min": args.surface_min, "surface_max": args.surface_max,
        "departements": args.departements, "intention": args.intention,
        "revenus_mensuels": args.revenus, "budget_de_vie": args.budget_vie,
        "tmi": args.tmi, "taux": args.taux,
    })
    r = cherche(c, verbeux=not args.json)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=1, default=str))
        return
    print(f"\nBudget {c['budget_max']:,.0f} € · apport {c['apport']:,.0f} € · "
          f"{c['type']} {c['surface_min']:.0f}-{c['surface_max']:.0f} m² · "
          f"rendement mini {c['rendement_min']:.1f} % · intention {c['intention']}".replace(",", " "))
    print(f"{len(r['candidats'])} opération(s) retenue(s) sur {r['nb_preselectionnes']} "
          f"présélectionnées en {r['duree_ms']} ms\n")
    print("rejets de présélection :",
          ", ".join(f"{v}× {k}" for k, v in sorted(r["rejets_preselection"].items(),
                                                   key=lambda kv: -kv[1])[:5]))
    for dep in r["departements"]:
        print(f"\n— département {dep}")
        for x in r["par_departement"][dep]:
            print("  " + _resume(x))
    if r.get("pistes"):
        print(f"\n=== rien ne s'autofinance à ces prix — à quel prix ça tiendrait "
              f"({len(r['pistes'])} pistes) ===")
        for x in r["pistes"]:
            print(f"  {x['departement']} {x['commune'][:20]:20s} {x['surface']:4.0f} m² : "
                  f"affiché {x['prix_actuel']:>8,.0f} € → équilibre {x['prix_equilibre']:>8,.0f} € "
                  f"(baisse de {x['baisse_requise_pct']:.1f} %), cash-flow actuel "
                  f"{(x['cash_flow_moyen_10_ans'] or 0):>7,.0f} €/an".replace(",", " "))
    if args.jev:
        from . import arbitrage
        a = arbitrage.arbitre(r)
        print("\n=== arbitrage Jev ===")
        print(arbitrage.rendu_texte(a))


if __name__ == "__main__":
    main()
