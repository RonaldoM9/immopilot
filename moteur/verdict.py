"""Le verdict — la pièce sans laquelle tout le reste ne sert à rien.

Un outil d'aide à la décision qui ne sait pas dire non devient une machine à confirmer les
décisions déjà prises. Les règles ci-dessous sont volontairement explicites, ordonnées, et
chacune produit une raison chiffrée. Elles sont testées par le banc d'essai : si le moteur
valide un piège, le test échoue.
"""

ACHETER, NEGOCIER, NON, INDETERMINE = "ACHETER", "NEGOCIER", "NON", "INDETERMINE"

# Ce que l'on affiche. Les constantes restent sans accent (comparaisons, tests, tri),
# l'affichage porte l'accent.
AFFICHAGE = {ACHETER: "ACHETER", NEGOCIER: "NÉGOCIER", NON: "NON", INDETERMINE: "INDÉTERMINÉ"}

# Seuils, tous paramétrables et tous affichés dans le dossier
ECART_NEGOCIATION = 0.05      # jusqu'à +5 % au-dessus du marche : acceptable
ECART_REFUS = 0.15            # au-delà de +15 % : non
CASH_FLOW_MIN = 0.0           # le cash-flow apres impot doit etre positif
CONFIANCE_MIN = 0.45          # en-dessous : le verdict n'est pas publiable



def _fr(x, dec=0):
    """Format français : espace fine comme séparateur de milliers, virgule décimale."""
    t = f"{x:,.{dec}f}".replace(",", "\u202f").replace(".", ",")
    return t


def _eur(x, dec=0):
    return _fr(x, dec) + " €"


def _euro_m2(x):
    return _fr(x) + " €/m²"


def _confiance(comparables, loyer, sigma_pct=None):
    """Confiance 0-1 : nombre de ventes, dispersion, observations de loyer, erreur du modèle."""
    c = 0.0
    n = comparables["n"]
    c += 0.40 * min(n / 15, 1.0)                                  # echantillon
    c += 0.25 * (1 - min(comparables["dispersion"] / 60, 1.0))     # homogeneite
    if loyer:
        c += 0.20 * {"solide": 1.0, "moyenne": 0.6, "faible": 0.3}[loyer["fiabilite"]]
    if sigma_pct is not None:
        c += 0.15 * (1 - min(sigma_pct / 40, 1.0))                 # erreur du modele
    return max(0.0, min(1.0, c))


def decider(comparables, prix_demande, fiscalite, tresorerie, surface, loyer=None,
            sigma_pct=None, annees_ventes=None):
    """Rend le verdict, ses raisons et sa confiance.

    Le prix demandé est comparé au marché du périmètre **pour la même surface** : comparer
    un prix total à une médiane au m² est l'erreur qui produit des « +2 000 % ».
    """
    raisons, blocages, reserves = [], [], []
    ref = comparables["median_eur_m2"]
    prix_marche_bien = ref * surface if ref and surface else 0.0
    c = _confiance(comparables, loyer, sigma_pct)

    # 1. la donnée est-elle suffisante pour se prononcer ?
    if comparables["n"] < 5:
        raisons.append(f"Comparables insuffisants : {comparables['n']} vente(s) retenue(s), "
                       f"5 exigées ({comparables['raison']}).")
        return {"verdict": INDETERMINE, "confiance": round(c, 2), "raisons": raisons,
                "blocages": [], "reserves": [],
                "prix_marche_m2": ref or None,
                "prix_marche_bien": prix_marche_bien or None,
                "prix_cible": None, "ecart_prix_pct": None,
                "cash_flow_apres_impot": None,
                "detail": {"comparables": comparables, "tresorerie": tresorerie}}

    # 2. le foyer peut-il payer ?
    if not tresorerie["faisable"]:
        blocages.append(f"Trésorerie : {tresorerie['raison']} "
                        f"(solde de {_eur(tresorerie['solde_apres_credit'])}/mois).")

    # 3. l'opération s'autofinance-t-elle après impôt, en moyenne sur dix ans ?
    cf = fiscalite["meilleur_cash_flow"]
    cf_retenu = cf.get("cash_flow_moyen_10_ans", cf["cash_flow_apres_impot"]) if cf else None
    if cf_retenu is not None and cf_retenu < CASH_FLOW_MIN:
        blocages.append(f"Cash-flow après impôt négatif avec le meilleur régime "
                        f"({cf['regime']}) : {_eur(cf_retenu)}/an en moyenne sur 10 ans. "
                        f"L'opération consomme de la trésorerie chaque mois.")

    # 4. le prix demandé tient-il devant le marché du périmètre, à surface égale ?
    ecart = (prix_demande / prix_marche_bien - 1) * 100 if prix_marche_bien else 0.0
    prix_cible = prix_marche_bien * (1 + ECART_NEGOCIATION)
    if ecart > ECART_REFUS * 100:
        blocages.append(f"Prix demandé {ecart:+.1f} % au-dessus du marché du périmètre "
                        f"({_euro_m2(ref)}, soit {_eur(prix_marche_bien)} pour "
                        f"{_fr(surface)} m²). Cible défendable : {_eur(prix_cible)}.")
    elif ecart > ECART_NEGOCIATION * 100:
        reserves.append(f"Prix demandé {ecart:+.1f} % au-dessus du marché : "
                        f"négocier vers {_eur(prix_cible)} (médiane {_euro_m2(ref)}, "
                        f"{_eur(prix_marche_bien)} pour {_fr(surface)} m²).")
    else:
        raisons.append(f"Prix demandé dans le marché : {ecart:+.1f} % par rapport à la médiane "
                       f"de {_euro_m2(ref)} ({_eur(prix_marche_bien)} pour {_fr(surface)} m²).")

    # 5. le rendement brut mérite-t-il l'effort ?
    if loyer and loyer.get("rendement_brut") is not None:
        rb = loyer["rendement_brut"]
        if rb < 4.0:
            reserves.append(f"Rendement brut faible ({rb:.2f} %) : à ce niveau, l'opération ne "
                            f"tient que par la fiscalité ou la revalorisation.")
        else:
            raisons.append(f"Rendement brut {rb:.2f} % (loyer de référence communal, "
                           f"{loyer['observations']} observations).")

    # 6. la confiance est-elle suffisante pour publier un verdict ?
    if comparables["dispersion"] > 45:
        reserves.append(f"Écart interquartile de {comparables['dispersion']:.0f} % dans le "
                        f"périmètre : deux biens comparables peuvent s'échanger très différemment.")
    if c < CONFIANCE_MIN:
        raisons.extend(reserves)
        raisons.append(f"Confiance {c:.2f} sous le seuil de {CONFIANCE_MIN} : "
                       f"le dossier ne permet pas de trancher.")
        return {"verdict": INDETERMINE, "confiance": round(c, 2), "raisons": raisons,
                "blocages": blocages, "reserves": reserves,
                "prix_marche_m2": ref, "prix_marche_bien": prix_marche_bien,
                "prix_cible": prix_cible, "ecart_prix_pct": ecart,
                "cash_flow_apres_impot": cf_retenu,
                "detail": {"comparables": comparables, "tresorerie": tresorerie,
                           "fiscalite": fiscalite}}

    # 7. conclusion
    if blocages:
        verdict = NON
        raisons.extend(blocages)
    elif reserves:
        verdict = NEGOCIER
        raisons.extend(reserves)
    else:
        verdict = ACHETER
        raisons.append("Aucun motif de refus : prix dans le marché, trésorerie positive, "
                       "cash-flow après impôt positif.")

    return {"verdict": verdict, "libelle": AFFICHAGE.get(verdict, verdict),
            "confiance": round(c, 2), "raisons": raisons,
            "blocages": blocages, "reserves": reserves,
            "prix_marche_m2": ref, "prix_marche_bien": prix_marche_bien,
            "prix_cible": prix_cible if verdict != ACHETER else None,
            "ecart_prix_pct": ecart,
            "cash_flow_apres_impot": cf_retenu,
            "detail": {"comparables": comparables, "tresorerie": tresorerie,
                       "fiscalite": fiscalite}}
