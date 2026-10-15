#!/usr/bin/env python3
"""Banc d'essai du moteur ImmoPilot — les pièges d'abord, puis les cas réels.

    python3 -m moteur.bench

Principe : chaque cas vise UNE règle de décision du moteur. Les prix des cas « dans le
marché » ou « au-dessus du marché » sont calculés **à partir de la référence du moteur
lui-même** (médiane du périmètre, à surface comparable) et non codés en dur : ainsi le test
reste valide quand les données DVF sont mises à jour.

Un moteur d'aide à la décision qui valide un piège ne sert à rien : c'est le test central.
"""
import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from moteur import analyse, dossier as Dos, fiscalite as Fis, verdict as V
else:
    from . import analyse, dossier as Dos, fiscalite as Fis, verdict as V

# ---------------------------------------------------------------- profils de foyer
P_AISE = {"revenus_mensuels": 7594, "budget_de_vie": 4500, "charges_recurrentes": 0,
          "mensualites_existantes": 0, "epargne": 100000, "reserve": 20000, "tmi": 0.30}
P_APPORT_TOTAL = {"revenus_mensuels": 7594, "budget_de_vie": 4500, "charges_recurrentes": 0,
                  "mensualites_existantes": 0, "epargne": 250000, "reserve": 50000, "tmi": 0.30}
P_TRES_FORT = {"revenus_mensuels": 7594, "budget_de_vie": 4500, "charges_recurrentes": 0,
               "mensualites_existantes": 0, "epargne": 450000, "reserve": 50000, "tmi": 0.30}
P_TENDU = {"revenus_mensuels": 7594, "budget_de_vie": 10625, "charges_recurrentes": 0,
           "mensualites_existantes": 0, "epargne": 100000, "reserve": 20000, "tmi": 0.30}
P_SANS_APPORT = {"revenus_mensuels": 6000, "budget_de_vie": 2000, "charges_recurrentes": 0,
                 "mensualites_existantes": 0, "epargne": 0, "reserve": 0, "tmi": 0.30}
P_ENDUETTE = {"revenus_mensuels": 7594, "budget_de_vie": 4500, "charges_recurrentes": 0,
              "mensualites_existantes": 3600, "epargne": 100000, "reserve": 20000, "tmi": 0.30}

EXPL = {"charges_annuelles": 900, "taxe_fonciere": 750, "entretien_annuel": 400,
        "vacance_pct": 5, "impaye_pct": 2, "travaux": 0, "mobilier": 0}


def cas(**kw):
    d = {"exploitation": dict(EXPL)}
    d.update(kw)
    return d


def reference(commune, surface, type_local="Appartement"):
    """La même référence que celle utilisée par le moteur : la cascade de comparables."""
    ventes, _ = analyse.comparables_avec_repli(commune=commune, type_local=type_local,
                                               surface=surface)
    return analyse.synthese(ventes)


def prix(commune, surface, ecart_pct, type_local="Appartement"):
    """Prix total du bien à X % au-dessus (ou en dessous) de la médiane du périmètre."""
    r = reference(commune, surface, type_local)
    return round(r["median_eur_m2"] * surface * (1 + ecart_pct / 100))


CAS = [
    # ============ 1. LES PIEGES — le moteur doit refuser, ou refuser de trancher =========
    ("PIEGE 1 — le foyer ne peut pas payer la mensualite (budget de vie 10 625 EUR)",
     cas(commune="Groslay", prix_demande=95000, surface=30, loyer_mensuel_ht=424, profil=P_TENDU),
     V.NON, ("Trésorerie",)),
    ("PIEGE 2 — achat 100 % finance : consomme de la trésorerie chaque mois",
     cas(commune="Groslay", prix_demande=95000, surface=30, loyer_mensuel_ht=424, profil=P_SANS_APPORT),
     V.NON, ("Cash-flow",)),
    ("PIEGE 3 — prix 30 % au-dessus du marche du perimetre",
     cas(commune="Groslay", surface=30, prix_demande=prix("Groslay", 30, 30),
         loyer_mensuel_ht=424, profil=P_APPORT_TOTAL),
     V.NON, ("Prix demandé",)),
    ("PIEGE 4 — une seule vente connue dans la commune : refuser de trancher",
     cas(commune="Le Heaulme", prix_demande=90000, surface=30, loyer_mensuel_ht=400,
         profil=P_APPORT_TOTAL),
     V.INDETERMINE, ("Comparables insuffisants", "Confiance")),
    ("PIEGE 5 — donnee trop heterogene pour trancher (Bruyeres-sur-Oise)",
     cas(commune="Bruyères-sur-Oise", prix_demande=100000, surface=30, loyer_mensuel_ht=450,
         profil=P_APPORT_TOTAL),
     V.INDETERMINE, ("Comparables insuffisants", "Confiance")),

    # ============ 2. CAS DE REFERENCE — les chiffres du dossier du 14/10 ================
    ("Groslay, T2 de 30 m² au prix du marche (le cas du 14/10)",
     cas(commune="Groslay", surface=30, prix_demande=prix("Groslay", 30, -5),
         loyer_mensuel_ht=637, profil=P_AISE), V.ACHETER, None),
    ("Garges-les-Gonesse, 25 m² au prix du marche (10 % brut)",
     cas(commune="Garges-lès-Gonesse", surface=25, prix_demande=prix("Garges-lès-Gonesse", 25, -5),
         loyer_mensuel_ht=546, profil=P_AISE), V.ACHETER, None),
    ("Villiers-le-Bel, 30 m² au prix du marche (9,4 % brut)",
     cas(commune="Villiers-le-Bel", surface=30, prix_demande=prix("Villiers-le-Bel", 30, -5),
         loyer_mensuel_ht=643, profil=P_AISE), V.ACHETER, None),
    ("Ecouen, 30 m² — la commune de Ronald",
     cas(commune="Écouen", surface=30, prix_demande=prix("Écouen", 30, -6),
         loyer_mensuel_ht=630, profil=P_AISE), V.ACHETER, None),
    ("Ecouen, 25 m²",
     cas(commune="Écouen", surface=25, prix_demande=prix("Écouen", 25, -6),
         loyer_mensuel_ht=525, profil=P_AISE), V.ACHETER, None),
    ("Goussainville, 40 m²",
     cas(commune="Goussainville", surface=40, prix_demande=prix("Goussainville", 40, -6),
         loyer_mensuel_ht=860, profil=P_AISE), V.ACHETER, None),
    ("Sannois, 30 m² a +8 % : negocier, pas refuser",
     cas(commune="Sannois", surface=30, prix_demande=prix("Sannois", 30, 8),
         loyer_mensuel_ht=690, profil=P_APPORT_TOTAL), V.NEGOCIER, ("au-dessus du marché",)),
    ("Montmorency, 30 m² a +8 %",
     cas(commune="Montmorency", surface=30, prix_demande=prix("Montmorency", 30, 8),
         loyer_mensuel_ht=704, profil=P_APPORT_TOTAL), V.NEGOCIER, ("au-dessus du marché",)),
    ("Groslay, 30 m² a +12 %",
     cas(commune="Groslay", surface=30, prix_demande=prix("Groslay", 30, 12),
         loyer_mensuel_ht=424, profil=P_APPORT_TOTAL), V.NEGOCIER, ("au-dessus du marché",)),

    # ============ 3. FINANCEMENT =======================================================
    ("Le meme bien, avec 3 600 EUR de credits deja en cours",
     cas(commune="Groslay", prix_demande=95000, surface=30, loyer_mensuel_ht=424, profil=P_ENDUETTE),
     V.NON, ("Trésorerie",)),
    ("Le meme bien paye par un apport total : le cash-flow doit devenir positif",
     cas(commune="Groslay", prix_demande=95000, surface=30, loyer_mensuel_ht=424,
         profil=P_APPORT_TOTAL), V.ACHETER, None),

    # ============ 4. FISCALITE =========================================================
    ("Meuble a Sannois : l'amortissement LMNP doit l'emporter",
     cas(commune="Sannois", surface=30, prix_demande=prix("Sannois", 30, -10),
         loyer_mensuel_ht=690, profil=P_APPORT_TOTAL,
         exploitation={**EXPL, "mobilier": 6000}), V.ACHETER, None),
    ("Gros travaux a Goussainville : le deficit foncier doit reduire l'impot",
     cas(commune="Goussainville", surface=40, prix_demande=prix("Goussainville", 40, -10),
         loyer_mensuel_ht=900, profil=P_APPORT_TOTAL,
         exploitation={**EXPL, "travaux": 40000, "entretien_annuel": 3000}), V.ACHETER, None),

    # ============ 5. VALEUR — le bien de Ronald ========================================
    ("La maison d'Ecouen (100 m², 300 m² de terrain) louee 1 400 EUR et financee",
     cas(commune="Écouen", type="Maison", surface=100, terrain=300, prix_demande=330000,
         loyer_mensuel_ht=1400, profil=P_APPORT_TOTAL,
         exploitation={**EXPL, "charges_annuelles": 0, "taxe_fonciere": 1800}), V.NON, ("Cash-flow",)),
    ("La meme maison, payee sans credit : le verdict doit changer",
     cas(commune="Écouen", type="Maison", surface=100, terrain=300, prix_demande=330000,
         loyer_mensuel_ht=1400, profil=P_TRES_FORT,
         exploitation={**EXPL, "charges_annuelles": 0, "taxe_fonciere": 1800}), V.ACHETER, None),
]

VERIFS = [
    ("Controle de vraisemblance departemental (appartements 2025)",
     lambda: analyse.controle_vraisemblance(), "plausible"),
    ("Ecouen : le modele maison doit avoir un R2 exploitable",
     lambda: analyse.modele_valeur(commune="Écouen", type_local="Maison"), "r2>0.2"),
    ("Groslay : mediane des appartements au-dessus de 3 000 EUR/m²",
     lambda: analyse.synthese(analyse.comparables(commune="Groslay", surface=30)), "median>3000"),
    ("Villiers-le-Bel : dispersion elevee, donc echantillon a surveiller",
     lambda: analyse.synthese(analyse.comparables(commune="Villiers-le-Bel", surface=30)),
     "dispersion>15"),
    ("Garges : rendement brut au-dessus de 9 % (le meilleur du departement)",
     lambda: analyse.rendement_brut(analyse.loyer_mensuel(
         analyse.loyer_reference(commune="Garges-lès-Gonesse")["loyer_m2"], 30), 64100), "rendement>9"),
    ("Meuble sans travaux : le LMNP au reel doit sortir meilleur sur 10 ans",
     lambda: Fis.projection(Fis.Bien(prix_achat=110000, mobilier=6000, loyer_mensuel_ht=690,
                                     charges_annuelles=900, taxe_fonciere=750,
                                     entretien_annuel=400), 0.30, capital=0, taux_pct=3.5),
     "lmnp_meilleur"),
]


def verifie(regle, valeur):
    if regle == "plausible":
        return bool(valeur and valeur.get("plausible"))
    if regle.startswith("r2"):
        return bool(valeur and valeur.get("r2", 0) > 0.2)
    if regle.startswith("median"):
        return bool(valeur and valeur.get("median_eur_m2", 0) > 3000)
    if regle.startswith("dispersion"):
        return bool(valeur and valeur.get("dispersion", 0) > 15)
    if regle.startswith("rendement"):
        return bool(valeur and valeur > 9)
    if regle == "lmnp_meilleur":
        par = valeur["par_regime"]
        meilleur = max(par, key=lambda n: par[n]["cumul"])
        return "LMNP" in meilleur
    return False


def diagnostic():
    print("REFERENCE DES PERIMETRES UTILISES PAR LE BANC D'ESSAI")
    print("  commune                surface   n   mediane   dispersion")
    for commune, surface, type_local in (("Groslay", 30, "Appartement"), ("Garges-lès-Gonesse", 25, "Appartement"),
                                         ("Villiers-le-Bel", 30, "Appartement"), ("Écouen", 30, "Appartement"),
                                         ("Écouen", 100, "Maison"), ("Sannois", 30, "Appartement"),
                                         ("Montmorency", 30, "Appartement"), ("Goussainville", 40, "Appartement"),
                                         ("Le Heaulme", 30, "Appartement"), ("Bruyères-sur-Oise", 30, "Appartement")):
        s = reference(commune, surface, type_local)
        print(f"  {commune:22s} {surface:5.0f} m2 {s['n']:3d} {s['median_eur_m2']:9,.0f} {s['dispersion']:9.1f} %"
              f"   {'' if s['solide'] else '-> ' + s['raison']}")


def main():
    print("=" * 84)
    print(f"BANC D'ESSAI IMMOPILOT v{Dos.VERSION} — {len(CAS)} dossiers, {len(VERIFS)} verifications")
    print("=" * 84)
    diagnostic()
    echecs, details = 0, []
    print("\n" + "=" * 84)
    for nom, d, attendu, motifs in CAS:
        dos = Dos.construire(d)
        v = dos["verdict"]
        raisons = " | ".join(v["raisons"])
        ok = v["verdict"] == attendu and (not motifs or any(m.lower() in raisons.lower() for m in motifs))
        echecs += 0 if ok else 1
        print(f"\n[{'OK  ' if ok else 'ECHEC'}] {nom}")
        cf = v.get("cash_flow_apres_impot")
        print(f"        {v['verdict']} (attendu {attendu}) · confiance {v['confiance']:.2f} · "
              f"marche {(v['prix_marche_m2'] or 0):,.0f} EUR/m2 · prix bien "
              f"{(v['prix_marche_bien'] or 0):,.0f} EUR"
              + (f" · cash-flow {cf:,.0f} EUR/an" if cf is not None else ""))
        print(f"        {raisons[:175]}")
        if not ok:
            details.append(nom)

    print("\n" + "=" * 84)
    print("VERIFICATIONS DES DONNEES ET DES REGIMES")
    print("=" * 84)
    for nom, fn, regle in VERIFS:
        val = fn()
        ok = verifie(regle, val)
        echecs += 0 if ok else 1
        print(f"  [{'OK  ' if ok else 'ECHEC'}] {nom}")
        if not ok:
            print(f"        valeur : {str(val)[:300]}")
            details.append(nom)

    total = len(CAS) + len(VERIFS)
    print("\n" + "=" * 84)
    print(f"RESULTAT : {total - echecs}/{total} — "
          f"{'TOUT PASSE' if not echecs else 'ECHECS : ' + ' | '.join(details)}")
    print("=" * 84)
    return 1 if echecs else 0


if __name__ == "__main__":
    raise SystemExit(main())
