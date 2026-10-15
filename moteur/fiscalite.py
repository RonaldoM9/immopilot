"""Fiscalité de l'investissement locatif — trois régimes mis côte à côte.

Mécanique standard, constantes 2026. Ce n'est PAS un conseil fiscal : les plafonds, les
conditions et les réformes récentes (rabot du LMNP, réintégration des amortissements dans la
plus-value) exigent la validation d'un expert-comptable. Le moteur rend un ordre de grandeur
et rend le mécanisme visible, ce que personne ne fait à la main.
"""
from dataclasses import dataclass, field

PS = 0.172                 # prélèvements sociaux sur les revenus du patrimoine
MICRO_FONCIER_PLAFOND = 15_000
MICRO_FONCIER_ABATTEMENT = 0.30
MICRO_BIC_PLAFOND = 77_700
MICRO_BIC_ABATTEMENT = 0.50
DEFICIT_FONCIER_PLAFOND = 10_700     # imputable sur le revenu global, hors intérêts
PART_TERRAIN_DEFAUT = 0.15           # non amortissable
DUREE_AMORT_BATI = 30                # années, usage courant
DUREE_AMORT_TRAVAUX = 15


@dataclass
class Bien:
    prix_achat: float
    travaux: float = 0.0
    mobilier: float = 0.0
    part_terrain: float = PART_TERRAIN_DEFAUT
    loyer_mensuel_ht: float = 0.0
    charges_annuelles: float = 0.0        # copro non récupérables, assurance PNO, gestion
    taxe_fonciere: float = 0.0
    entretien_annuel: float = 0.0
    interets_annuels: float = 0.0         # 1re année
    vacance_pct: float = 5.0
    impaye_pct: float = 2.0
    credit_annuel: float = 0.0            # annuité totale, assurance comprise
    frais_acquisition_pct: float = 8.0
    travaux_deduction_immediate: bool = True   # au réel (nu) : déduits l'année des travaux,
                                               # en LMNP : amortis sur 15 ans


def charges_exploitation(b: Bien) -> float:
    return b.charges_annuelles + b.taxe_fonciere + b.entretien_annuel


def loyers_encaisses(b: Bien) -> float:
    """Loyers réellement encaissés : vacance et impayés sont des hypothèses, pas des oublis."""
    brut = b.loyer_mensuel_ht * 12
    return brut * (1 - b.vacance_pct / 100) * (1 - b.impaye_pct / 100)


def _impot_nu_reel(b: Bien, loyers: float, tmi: float):
    """Location nue au réel — et le mécanisme du déficit foncier, qui change le signe.

    Les travaux déductibles (entretien, réparation, amélioration) et les charges viennent en
    déduction des loyers. Le déficit hors intérêts s'impute sur le revenu global dans la
    limite de 10 700 EUR par an ; le reste est reportable sur les revenus fonciers (10 ans).
    """
    charges = charges_exploitation(b) + (b.travaux if b.travaux_deduction_immediate else 0.0)
    resultat = loyers - charges - b.interets_annuels
    hors_interets = loyers - charges
    deficit_global = min(max(-hors_interets, 0.0), DEFICIT_FONCIER_PLAFOND)
    import_fiscal = max(resultat, 0.0) * (tmi + PS)
    economie = deficit_global * tmi          # réduction de l'impôt sur le revenu global
    return {"regime": "Foncier au réel (travaux déductibles)", "base_imposable": max(resultat, 0.0),
            "deficit_impute_revenu_global": deficit_global,
            "deficit_reportable": max(-hors_interets, 0.0) - deficit_global + max(-b.interets_annuels - max(hors_interets, 0), 0),
            "economie_impot_revenu_global": economie,
            "impot": import_fiscal - economie, "taux_effectif": ((import_fiscal - economie) / loyers * 100) if loyers else 0}


def _impot_micro_foncier(b: Bien, loyers: float, tmi: float):
    base = loyers * (1 - MICRO_FONCIER_ABATTEMENT)
    impot = base * (tmi + PS)
    return {"regime": "Micro-foncier (abattement 30 %)", "base_imposable": base,
            "deficit_impute_revenu_global": 0.0, "deficit_reportable": 0.0,
            "impot": impot, "taux_effectif": (impot / loyers * 100) if loyers else 0}


def _impot_micro_bic(b: Bien, loyers: float, tmi: float):
    base = loyers * (1 - MICRO_BIC_ABATTEMENT)
    impot = base * (tmi + PS)
    return {"regime": "Micro-BIC (abattement 50 %)", "base_imposable": base,
            "deficit_impute_revenu_global": 0.0, "deficit_reportable": 0.0,
            "impot": impot, "taux_effectif": (impot / loyers * 100) if loyers else 0}


def _impot_lmnp_reel(b: Bien, loyers: float, tmi: float):
    charges = charges_exploitation(b)
    base_bati = b.prix_achat * (1 - b.part_terrain)
    amort_bati = base_bati / DUREE_AMORT_BATI
    amort_travaux = b.travaux / DUREE_AMORT_TRAVAUX
    amort_mobilier = b.mobilier / 7
    amortissements = amort_bati + amort_travaux + amort_mobilier
    amort_impute = min(amortissements, max(loyers - charges - b.interets_annuels, 0.0))
    resultat = loyers - charges - b.interets_annuels - amort_impute
    impot = max(resultat, 0.0) * (tmi + PS)
    return {"regime": "LMNP au réel (amortissement)",
            "base_imposable": max(resultat, 0.0),
            "amortissements": amortissements, "amortissements_imputes": amort_impute,
            "amortissements_reportes": amortissements - amort_impute,
            "deficit_impute_revenu_global": 0.0, "deficit_reportable": max(-resultat, 0.0),
            "impot": impot, "taux_effectif": (impot / loyers * 100) if loyers else 0}


def projection(b: Bien, tmi: float, capital: float, taux_pct: float, annees: int = 10,
               duree_annees: int = 20, assurance_pct: float = 0.30):
    """Cumul de trésorerie après impôt sur N années, régime par régime.

    Nécessaire parce qu'un classement sur la seule première année se trompe : au régime réel
    (nu), les travaux sont déduits immédiatement — et peuvent produire un déficit foncier
    spectaculaire la première année — alors qu'en LMNP ils sont amortis sur quinze ans.
    Un classement honnête se fait sur la durée, pas sur l'année de démarrage.
    """
    from dataclasses import replace

    mois_total = int(duree_annees * 12)
    r = taux_pct / 1200
    coef = (1 / mois_total if r == 0 else r / (1 - (1 + r) ** (-mois_total))) + assurance_pct / 1200
    mensualite = capital * coef if capital else 0.0

    # échéancier : intérêts et capital restant dû par année
    echeancier, solde = [], capital
    for annee in range(annees):
        interets = 0.0
        for _ in range(12):
            if solde <= 0:
                break
            i = solde * r
            interets += i
            solde = max(0.0, solde - (mensualite - i))
        echeancier.append({"annee": annee + 1, "interets": interets, "solde": solde})

    cumuls = {nom: 0.0 for nom in REGIMES}
    detail = {nom: [] for nom in REGIMES}
    for e in echeancier:
        credit_annuel = mensualite * 12 if e["interets"] > 0 or capital else 0.0
        for nom, fn in REGIMES.items():
            # les travaux restent amortissables en LMNP chaque année, mais ne sont déduits
            # qu'une fois en location nue
            bb = replace(b, interets_annuels=e["interets"],
                         travaux_deduction_immediate=(e["annee"] == 1),
                         credit_annuel=credit_annuel)
            res = fn(bb, loyers_encaisses(bb), tmi)
            cash = (loyers_encaisses(bb) - charges_exploitation(bb) - e["interets"]
                    - credit_annuel - res["impot"])
            cumuls[nom] += cash
            detail[nom].append(round(cash))
    return {"annees": annees, "capital": capital, "mensualite": mensualite,
            "echeancier": echeancier,
            "par_regime": {nom: {"cumul": cumuls[nom], "moyenne_annuelle": cumuls[nom] / annees,
                                 "detail_annuel": detail[nom]} for nom in REGIMES}}


REGIMES = {
    "Micro-foncier (abattement 30 %)": _impot_micro_foncier,
    "Foncier au réel (travaux déductibles)": _impot_nu_reel,
    "Micro-BIC (abattement 50 %)": _impot_micro_bic,
    "LMNP au réel (amortissement)": _impot_lmnp_reel,
}


def comparer_regimes(b: Bien, tmi: float = 0.30):
    """Les quatre mécanismes côte à côte, plus le cash-flow après impôt de chacun."""
    loyers = loyers_encaisses(b)
    charges = charges_exploitation(b)
    resultats = [
        _impot_micro_foncier(b, loyers, tmi) if loyers <= MICRO_FONCIER_PLAFOND else
        {"regime": "Micro-foncier", "impot": None, "raison": f"loyers > {MICRO_FONCIER_PLAFOND} EUR"},
        _impot_nu_reel(b, loyers, tmi),
        _impot_micro_bic(b, loyers, tmi) if loyers <= MICRO_BIC_PLAFOND else
        {"regime": "Micro-BIC", "impot": None, "raison": f"loyers > {MICRO_BIC_PLAFOND} EUR"},
        _impot_lmnp_reel(b, loyers, tmi),
    ]
    for r in resultats:
        if r.get("impot") is None:
            continue
        cash_avant = loyers - charges - b.interets_annuels - b.credit_annuel
        r["cash_flow_avant_impot"] = cash_avant
        r["cash_flow_apres_impot"] = cash_avant - r["impot"]
        r["rendement_net_pct"] = (r["cash_flow_apres_impot"] + b.credit_annuel * 0
                                  - 0) / (b.prix_achat * (1 + b.frais_acquisition_pct / 100)) * 100
    valides = [r for r in resultats if r.get("impot") is not None]
    meilleur = max(valides, key=lambda r: r["cash_flow_apres_impot"]) if valides else None
    return {"loyers_encaisses": loyers, "charges_exploitation": charges,
            "tmi": tmi, "regimes": resultats, "meilleur": meilleur["regime"] if meilleur else None,
            "avertissement": ("Mecanique indicative 2026. Plafonds et conditions a valider par un "
                              "expert-comptable. La reforme 2025 du LMNP reintroduit les "
                              "amortissements dans le calcul de la plus-value a la revente.")}
