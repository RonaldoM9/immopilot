"""Financement : mensualité, capacité d'emprunt, et le contrôle que la maquette oubliait.

Le contrôle de trésorerie est la correction la plus importante identifiée le 15/10/2026 :
un foyer peut passer le taux d'effort de 35 % et ne pas pouvoir payer la mensualité.
"""

TAUX_EFFORT = 0.35          # référence HCSF, avec marge de flexibilité bancaire
FRAIS_NOTAIRE_ANCIEN = 0.075
FRAIS_NOTAIRE_NEUF = 0.025


def coefficient_annuite(taux_annuel_pct, mois, assurance_pct=0.0):
    """Mensualité par euro emprunté, assurance comprise (assurance assise sur le capital)."""
    if mois <= 0:
        return 0.0
    r = taux_annuel_pct / 1200
    principal = 1 / mois if r == 0 else r / (1 - (1 + r) ** (-mois))
    return principal + assurance_pct / 1200


def mensualite(capital, taux_annuel_pct, mois, assurance_pct=0.0):
    return capital * coefficient_annuite(taux_annuel_pct, mois, assurance_pct)


def capital_empruntable(mensualite_max, taux_annuel_pct, mois, assurance_pct=0.0):
    c = coefficient_annuite(taux_annuel_pct, mois, assurance_pct)
    return mensualite_max / c if c else 0.0


def _fr(x, dec=0):
    """Format français : espace fine comme séparateur de milliers, virgule décimale."""
    return f"{x:,.{dec}f}".replace(",", "\u202f").replace(".", ",")


def frais_acquisition(prix, neuf=False):
    return prix * (FRAIS_NOTAIRE_NEUF if neuf else FRAIS_NOTAIRE_ANCIEN)


def capacite(revenus_menuels_nets, mensualites_existantes, loyers_attendus=0.0,
             poids_loyers=0.70, taux_effort=TAUX_EFFORT, taux_annuel_pct=3.5, annees=20,
             assurance_pct=0.30, epargne=0.0, reserve=0.0, frais_pct=7.5):
    """Marge de mensualité, capital empruntable, apport mobilisable et budget total."""
    if taux_effort > 1:            # 35 veut dire 35 % : on l'accepte, mais on le normalise
        taux_effort = taux_effort / 100
    revenus_retenus = revenus_menuels_nets + loyers_attendus * poids_loyers
    marge = max(0.0, revenus_retenus * taux_effort - mensualites_existantes)
    mois = int(annees * 12)
    capital = capital_empruntable(marge, taux_annuel_pct, mois, assurance_pct)
    apport = max(0.0, epargne - reserve)
    budget_avec_frais = capital + apport
    prix_max = budget_avec_frais / (1 + frais_pct / 100)
    return {"revenus_retenus": revenus_retenus, "marge_mensualite": marge,
            "capital_empruntable": capital, "apport_mobilisable": apport,
            "budget_total": budget_avec_frais, "prix_max_bien": prix_max,
            "taux_effort_actuel": (mensualites_existantes / revenus_retenus * 100)
                                  if revenus_retenus else 0.0}


def controle_tresorerie(revenus_menuels_nets, budget_de_vie, charges_recurrentes,
                        mensualites_existantes, nouvelle_mensualite, loyers_encaisse=0.0):
    """LE contrôle qui manquait : le solde mensuel APRÈS le nouveau crédit.

    Tant que ce solde n'est pas calculé, un outil peut valider un achat que le foyer ne peut
    pas payer. Mesuré sur la maquette du 15/10 : foyer à +1 500 EUR/mois, achat à 350 000 EUR
    -> -600 EUR/mois, sans aucune alerte.
    """
    disponible_avant = revenus_menuels_nets + loyers_encaisse - budget_de_vie \
        - charges_recurrentes - mensualites_existantes
    solde_apres = disponible_avant - nouvelle_mensualite
    return {"disponible_avant_credit": disponible_avant,
            "solde_apres_credit": solde_apres,
            "faisable": solde_apres >= 0,
            "marge_de_securite_pct": (solde_apres / revenus_menuels_nets * 100)
                                     if revenus_menuels_nets else 0.0,
            "raison": f"solde de {_fr(solde_apres)} €/mois après crédit : "
                      + ("le foyer peut payer" if solde_apres >= 0 else
                         "le foyer ne peut pas payer")}


def plan_financement(prix, apport, taux_annuel_pct=3.5, annees=20, assurance_pct=0.30,
                     neuf=False):
    frais = frais_acquisition(prix, neuf)
    besoin = prix + frais
    capital = max(0.0, besoin - apport)
    mois = int(annees * 12)
    mens = mensualite(capital, taux_annuel_pct, mois, assurance_pct)
    return {"prix": prix, "frais_acquisition": frais, "besoin_total": besoin,
            "apport": apport, "capital_emprunte": capital, "mensualite": mens,
            "cout_total_credit": mens * mois, "interets_et_assurance": mens * mois - capital}
