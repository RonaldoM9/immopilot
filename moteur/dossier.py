"""Assemblage d'un dossier complet : c'est le livrable que l'agent met en mots.

Usage :
  python3 -m moteur.dossier --commune Groslay --prix 95000 --surface 30 --loyer 424
  python3 -m moteur.dossier --fichier dossiers/exemple.json --md

Un dossier = comparables de rue + valeur estimée + loyer + fiscalité comparée +
financement + contrôle de trésorerie + verdict + confiance.
"""
import argparse
import json
import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from moteur import analyse, donnees as D, financement as F, fiscalite as Fis, verdict as V
else:
    from . import analyse, donnees as D, financement as F, fiscalite as Fis, verdict as V
# un seul format de nombre dans tout le moteur : celui du verdict
_fr, _eur, _euro_m2 = V._fr, V._eur, V._euro_m2

VERSION = D.VERSION


def dossier_par_defaut():
    return {
        "commune": "Groslay", "voie": None, "type": "Appartement",
        "surface": 30.0, "terrain": 0.0, "prix_demande": 95000.0,
        "loyer_mensuel_ht": 424.0,
        "profil": {"revenus_mensuels": 7594.0, "budget_de_vie": 8500.0,
                   "charges_recurrentes": 0.0, "mensualites_existantes": 0.0,
                   "epargne": 100000.0, "reserve": 20000.0, "tmi": 0.30,
                   "poids_loyers": 0.70, "taux": 3.5, "annees": 20, "assurance_pct": 0.30},
        "exploitation": {"charges_annuelles": 900.0, "taxe_fonciere": 750.0,
                         "entretien_annuel": 400.0, "vacance_pct": 5.0, "impaye_pct": 2.0,
                         "travaux": 0.0, "mobilier": 0.0},
    }


def _ventes_pour_affichage(ventes, limite=25):
    """Les ventes comparables, les plus récentes d'abord, réduites aux champs lisibles.

    Un chiffre qui ne peut pas être ouvert n'est pas vérifiable : chaque dossier embarque donc
    la liste des actes sur lesquels il s'appuie.
    """
    garde = ("date", "numero", "voie", "surface", "terrain", "valeur", "valeur_actualisee",
             "eur_m2", "eur_m2_brut", "annee", "pieces")
    out = []
    for v in sorted(ventes, key=lambda x: x["date"], reverse=True)[:limite]:
        out.append({k: (round(v[k]) if isinstance(v.get(k), float) and k != "eur_m2" else v.get(k))
                    for k in garde if k in v})
    return out


def construire(d):
    """Rend le dossier complet, prêt à être lu par l'agent ou affiché."""
    p = {**dossier_par_defaut()["profil"], **(d.get("profil") or {})}
    e = {**dossier_par_defaut()["exploitation"], **(d.get("exploitation") or {})}
    type_local = d.get("type", "Appartement")
    commune, voie = d.get("commune"), d.get("voie")
    surface, prix = float(d["surface"]), float(d["prix_demande"])

    # --- comparables : la rue d'abord, la commune ensuite, à surface comparable, en cascade
    if voie:
        par_rue, desc_rue = analyse.comparables_avec_repli(commune=commune, voie=voie,
                                                           type_local=type_local, surface=surface)
    else:
        par_rue, desc_rue = [], ""
    s_rue = analyse.synthese(par_rue)
    par_commune, desc_commune = analyse.comparables_avec_repli(
        commune=commune, type_local=type_local, surface=surface)
    s_commune = analyse.synthese(par_commune)
    reference = s_rue if s_rue["n"] >= 5 else s_commune
    description_reference = desc_rue if s_rue["n"] >= 5 else desc_commune

    # --- valeur de marché du bien, par le modèle taille + terrain (calibré sur cinq ans)
    modele = analyse.modele_valeur(commune=commune, type_local=type_local)
    valeur = analyse.valeur_estimee(modele, surface, float(d.get("terrain") or 0)) if modele else None

    # Quand le périmètre comparable est trop mince, la référence par médiane n'a pas de sens
    # (à Écouen, les maisons de 100 m² n'ont que des comparables de 40 m², dont le prix au m²
    # est le double). On passe alors au modèle, qui explicite l'effet taille.
    if reference["n"] < 5 and valeur:
        reference = {"n": modele["n"], "median_eur_m2": valeur["valeur"] / surface,
                     "q1": valeur["bas"] / surface, "q3": valeur["haut"] / surface,
                     "dispersion": valeur["sigma_pct"], "ecart_type_pct": valeur["sigma_pct"],
                     "median_prix": valeur["valeur"], "median_surface": surface,
                     "solide": valeur["sigma_pct"] < 45, "source": "modele",
                     "raison": f"modele taille + terrain (R2 {modele['r2']:.2f}, "
                               f"{modele['n']} ventes)"}
        description_reference += " · référence par le modèle taille + terrain (périmètre trop mince)"
    elif "source" not in reference:
        reference["source"] = "comparables"

    # élision : « commune d'Écouen », pas « commune de Écouen »
    de_commune = ("d'" if commune[:1].upper() in "AEIOUYÂÉÈÊÎÏÔÛÜ" else "de ") + commune
    ou = (f"voie « {voie} »" if s_rue["n"] >= 5 else f"commune {de_commune}") if voie \
        else f"commune {de_commune}"
    perimetre = f"{ou} — {description_reference}"

    # --- loyer et rendement
    loyer_ref = analyse.loyer_reference(commune=commune, type_local=type_local)
    loyer = None
    if loyer_ref:
        mensuel = float(d["loyer_mensuel_ht"]) if d.get("loyer_mensuel_ht") else \
            analyse.loyer_mensuel(loyer_ref["loyer_m2"], surface)
        loyer = {"loyer_m2": loyer_ref["loyer_m2"], "observations": loyer_ref["observations"],
                 "fiabilite": loyer_ref["fiabilite"], "loyer_mensuel_ht": mensuel,
                 "rendement_brut": analyse.rendement_brut(mensuel, prix)}

    # --- financement et contrôle de trésorerie
    plan = F.plan_financement(prix, p.get("apport", 0) or max(0.0, p["epargne"] - p["reserve"]),
                              p["taux"], p["annees"], p["assurance_pct"])
    cap = F.capacite(p["revenus_mensuels"], p["mensualites_existantes"],
                     loyer["loyer_mensuel_ht"] if loyer else 0.0, p["poids_loyers"],
                     taux_annuel_pct=p["taux"], annees=p["annees"], assurance_pct=p["assurance_pct"],
                     epargne=p["epargne"], reserve=p["reserve"])
    tresorerie = F.controle_tresorerie(p["revenus_mensuels"], p["budget_de_vie"],
                                       p["charges_recurrentes"], p["mensualites_existantes"],
                                       plan["mensualite"],
                                       (loyer["loyer_mensuel_ht"] if loyer else 0.0))

    # --- fiscalité comparée
    bien = Fis.Bien(prix_achat=prix, travaux=e["travaux"], mobilier=e["mobilier"],
                    loyer_mensuel_ht=loyer["loyer_mensuel_ht"] if loyer else 0.0,
                    charges_annuelles=e["charges_annuelles"], taxe_fonciere=e["taxe_fonciere"],
                    entretien_annuel=e["entretien_annuel"],
                    # Intérêts de la 1re année : le capital reste dû à ~98 % sur les douze
                    # premiers mois d'un prêt amortissable. Approximation documentée.
                    interets_annuels=plan["capital_emprunte"] * p["taux"] / 100 * 0.983,
                    vacance_pct=e["vacance_pct"], impaye_pct=e["impaye_pct"],
                    credit_annuel=plan["mensualite"] * 12)
    fiscalite = Fis.comparer_regimes(bien, p["tmi"])
    # classement sur dix ans, parce qu'un classement sur la seule première année se trompe
    # (les travaux sont déduits d'un coup au réel, amortis sur quinze ans en LMNP)
    proj = Fis.projection(bien, p["tmi"], plan["capital_emprunte"], p["taux"], annees=10,
                          duree_annees=int(p["annees"]), assurance_pct=p["assurance_pct"])
    fiscalite["projection_10_ans"] = proj
    for r in fiscalite["regimes"]:
        pr = proj["par_regime"].get(r["regime"])
        if pr:
            r["cumul_10_ans"] = pr["cumul"]
            r["cash_flow_moyen_10_ans"] = pr["moyenne_annuelle"]
    valides = [r for r in fiscalite["regimes"] if r.get("impot") is not None]
    meilleur = max(valides, key=lambda r: r.get("cash_flow_moyen_10_ans",
                                                r["cash_flow_apres_impot"]), default=None)
    fiscalite["meilleur_cash_flow"] = meilleur
    fiscalite["meilleur_regime_sur_10_ans"] = meilleur["regime"] if meilleur else None

    # --- verdict
    verdict = V.decider(reference, prix, fiscalite, tresorerie, surface, loyer=loyer,
                        sigma_pct=valeur["sigma_pct"] if valeur else None)

    return {
        "version": VERSION, "horodatage": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "bien": {"commune": commune, "voie": voie, "type": type_local, "surface": surface,
                 "terrain": float(d.get("terrain") or 0), "prix_demande": prix,
                 "prix_au_m2": prix / surface if surface else 0},
        "comparables": {"perimetre": perimetre, "rue": s_rue if voie else None,
                        "commune": s_commune, "reference": reference,
                        "ventes_rue": _ventes_pour_affichage(par_rue),
                        "ventes_commune": _ventes_pour_affichage(par_commune, limite=20)},
        "prix_par_voie": analyse.prix_par_voie(commune=commune, type_local=type_local)[:12]
                         if not voie else None,
        "valeur_estimee": valeur, "modele": {k: v for k, v in (modele or {}).items() if k != "beta"}
                  if modele else None,
        "loyer": loyer, "financement": plan, "capacite": cap, "tresorerie": tresorerie,
        "fiscalite": fiscalite, "verdict": verdict,
        "controle_vraisemblance": analyse.controle_vraisemblance(type_local=type_local),
    }


def en_markdown(dos):
    """Le dossier en texte, prêt à coller dans une conversation.

    Pas de tableau : des lignes étiquetées et des puces — parce qu'un tableau markdown illisible
    ne se colle nulle part. Le chiffre et la source du chiffre sont toujours sur la même ligne.
    """
    v, b, c = dos["verdict"], dos["bien"], dos["comparables"]
    ref = c["reference"]
    f, fin, t = dos["fiscalite"], dos["financement"], dos["tresorerie"]
    L = [f"DOSSIER — {b['commune']}" + (f", {b['voie']}" if b.get("voie") else ""),
         f"{dos['horodatage'][:16]} · moteur {dos['version']} · {b['type']} de "
         f"{_fr(b['surface'])} m² à {_eur(b['prix_demande'])} ({_euro_m2(b['prix_au_m2'])})", "",
         f"VERDICT : {v.get('libelle', v['verdict'])}   (confiance {_fr(v['confiance']*100)} %)", ""]
    L += [f"· {r}" for r in v["raisons"]]
    if v.get("prix_cible"):
        L.append(f"· Prix cible de négociation : {_eur(v['prix_cible'])} "
                 f"({_euro_m2(v['prix_cible'] / b['surface'])})")
    if v.get("cash_flow_apres_impot") is not None:
        L.append(f"· Cash-flow après impôt, meilleur régime : "
                 f"{_eur(v['cash_flow_apres_impot'])}/an")

    L += ["", f"MARCHÉ — {c['perimetre']}"]
    if ref.get("source") == "modele":
        L.append(f"· référence par modèle taille + terrain : {_euro_m2(ref['median_eur_m2'])} "
                 f"→ {_eur(ref['median_prix'])} pour {_fr(b['surface'])} m² "
                 f"(écart-type du modèle {_fr(ref['dispersion'])} %)")
    else:
        L.append(f"· {ref['n']} vente(s) retenue(s) · médiane {_euro_m2(ref['median_eur_m2'])} "
                 f"· Q1 {_euro_m2(ref['q1'])} · Q3 {_euro_m2(ref['q3'])} "
                 f"· écart interquartile {_fr(ref['dispersion'])} %")
    if dos.get("prix_par_voie"):
        L += ["", "  Prix par voie :"]
        L += [f"  · {x['voie'].title()} : {_euro_m2(x['median_eur_m2'])} ({x['n']} ventes)"
              for x in dos["prix_par_voie"][:8]]
    if dos.get("comparables", {}).get("ventes_rue") or dos.get("comparables", {}).get("ventes_commune"):
        ventes = c.get("ventes_rue") or c.get("ventes_commune") or []
        if ventes:
            L += ["", "  Actes sur lesquels le dossier s'appuie :"]
            L += [f"  · {x['date'][:10]} — {(str(x.get('numero') or '') + ' ' + (x.get('voie') or '')).strip().title()}"
                  f" : {_fr(x['surface'])} m², {_eur(x['valeur'])}"
                  f" ({_euro_m2(x['eur_m2'])})" for x in ventes[:10]]

    if dos.get("valeur_estimee"):
        ve = dos["valeur_estimee"]
        L += ["", "VALEUR ESTIMÉE (modèle taille + terrain)",
              f"· {_eur(ve['valeur'])} — fourchette {_eur(ve['bas'])} à {_eur(ve['haut'])} "
              f"(± {_fr(ve['sigma_pct'])} %)"]
    if dos.get("loyer"):
        lo = dos["loyer"]
        L += ["", "LOYER ET RENDEMENT",
              f"· référence communale : {_fr(lo['loyer_m2'], 2)} €/m²/mois "
              f"({lo['observations']} observations, fiabilité {lo['fiabilite']})",
              f"· loyer retenu : {_eur(lo['loyer_mensuel_ht'])}/mois · rendement brut "
              f"{_fr(lo['rendement_brut'], 2)} %"]

    L += ["", "FINANCEMENT",
          f"· besoin total : {_eur(fin['besoin_total'])} "
          f"(prix {_eur(fin['prix'])} + frais {_eur(fin['frais_acquisition'])})",
          f"· apport mobilisé : {_eur(fin['apport'])} · capital emprunté : "
          f"{_eur(fin['capital_emprunte'])}",
          f"· mensualité assurance comprise : {_eur(fin['mensualite'])} · "
          f"intérêts + assurance sur la durée : {_eur(fin['interets_et_assurance'])}",
          "", "TRÉSORERIE DU FOYER (le contrôle qui manquait)",
          f"· disponible avant crédit : {_eur(t['disponible_avant_credit'])}/mois",
          f"· solde après nouveau crédit : {_eur(t['solde_apres_credit'])}/mois → "
          f"{'faisable' if t['faisable'] else 'NON FAISABLE'}"]

    L += ["", "FISCALITÉ — trois régimes, dix ans"]
    for r in f["regimes"]:
        if r.get("impot") is None:
            L.append(f"· {r['regime']} : {r.get('raison', 'non applicable')}")
            continue
        marque = "  ← retenu" if r["regime"] == f.get("meilleur_regime_sur_10_ans") else ""
        ligne10 = (f" · cumul 10 ans {_eur(r['cumul_10_ans'])}"
                   if r.get("cumul_10_ans") is not None else "")
        deficit = (f" · déficit imputé {_eur(r['deficit_impute_revenu_global'])}"
                   if r.get("deficit_impute_revenu_global") else "")
        L.append(f"· {r['regime']}{marque} : impôt an 1 {_eur(r['impot'])} · cash-flow an 1 "
                 f"{_eur(r['cash_flow_apres_impot'])}{ligne10}{deficit}")
    L += ["", f"({f['avertissement']})"]

    cv = dos["controle_vraisemblance"]
    L += ["", "---",
          f"Contrôle de vraisemblance départemental : {_euro_m2(cv['median_departementale'])} "
          f"sur {_fr(cv['n'])} ventes — "
          f"{'plausible' if cv['plausible'] else cv['raison']}.",
          "Chiffres produits par le moteur déterministe ; aucun calcul n'est fait par un modèle de langage."]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Construit un dossier d'investissement immobilier.")
    ap.add_argument("--fichier", help="dossier d'entrée en JSON")
    ap.add_argument("--commune")
    ap.add_argument("--voie")
    ap.add_argument("--type", default="Appartement")
    ap.add_argument("--surface", type=float)
    ap.add_argument("--terrain", type=float, default=0.0)
    ap.add_argument("--prix", type=float)
    ap.add_argument("--loyer", type=float)
    ap.add_argument("--tmi", type=float, default=0.30)
    ap.add_argument("--revenus", type=float)
    ap.add_argument("--budget-vie", type=float)
    ap.add_argument("--credits", type=float, default=0.0)
    ap.add_argument("--epargne", type=float, default=0.0)
    ap.add_argument("--reserve", type=float, default=0.0)
    ap.add_argument("--taux", type=float, default=3.5)
    ap.add_argument("--annees", type=float, default=20)
    ap.add_argument("--md", action="store_true", help="sortie lisible")
    ap.add_argument("--sortie", help="écrit le résultat dans ce fichier")
    a = ap.parse_args(argv)

    d = dossier_par_defaut()
    if a.fichier:
        d = {**d, **json.load(open(a.fichier, encoding="utf-8"))}
    for champ, val in (("commune", a.commune), ("voie", a.voie), ("type", a.type),
                       ("surface", a.surface), ("terrain", a.terrain), ("prix_demande", a.prix),
                       ("loyer_mensuel_ht", a.loyer)):
        if val is not None:
            d[champ] = val
    prof = d.setdefault("profil", {})
    for cle, val in (("tmi", a.tmi), ("revenus_mensuels", a.revenus),
                     ("budget_de_vie", a.budget_vie), ("mensualites_existantes", a.credits),
                     ("epargne", a.epargne), ("reserve", a.reserve), ("taux", a.taux),
                     ("annees", a.annees)):
        if val is not None:
            prof[cle] = val

    dos = construire(d)
    texte = en_markdown(dos) if a.md else json.dumps(dos, ensure_ascii=False, indent=1)
    if a.sortie:
        open(a.sortie, "w", encoding="utf-8").write(texte)
        print("ecrit :", a.sortie)
    else:
        print(texte)
    return dos


if __name__ == "__main__":
    main()
