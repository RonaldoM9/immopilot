"""Arbitrage Jev : la seule question que le code ne peut pas trancher.

Jev (TypeSafe System One) ne calcule pas, n'écrit pas, ne vérifie pas un fait : il tranche des
questions **bornées** sur un texte fourni et rend des valeurs typées. Il ne connaît rien d'autre
que ce texte.

Trois règles, en dur dans ce module :

1. **L'état envoyé ne contient que des chiffres produits par le moteur.** Aucune estimation
   écrite par un modèle n'entre ici : sinon on blanchirait un chiffre inventé en le faisant
   valider par une seconde machine.
2. **Aucun chiffre de la réponse n'est recopié dans un résultat.** On ne garde que la *clé* de
   son choix et sa probabilité ; les chiffres affichés à côté restent ceux du moteur, et la clé
   sert à savoir quelle opération il désigne — donc c'est vérifiable ligne à ligne.
3. **La panne est un état normal.** Sans clé, sans réseau ou sur erreur, on renvoie
   `{"ok": False}` : la page affiche le classement du moteur, en disant que l'arbitrage est absent.

Coût mesuré : quelques milliers de jetons d'entrée, soit ~0,0001 $ par recherche (modèle
jev-1.13.0, ~200 ms).
"""
from __future__ import annotations

import json
import pathlib
import re
import time
import urllib.error
import urllib.request

URL = "https://api.typesafe.ai/v1/systemone"
ENV_PATH = pathlib.Path("/root/.hermes/.env")
MODELE = "jev-latest"
DELAI_S = 40

INTENTIONS = {
    "rendement": "tirer le meilleur revenu net de son argent",
    "securite": "privilégier la solidité du marché et la régularité du loyer",
    "revente": "pouvoir revendre facilement dans cinq à dix ans",
}


ECHELLE_ROBUSTESSE = ["fragile", "passable", "solide", "très solide"]


def niveau_de(score):
    """Traduit la note de Jev en mot de l'échelle.

    `score` revient en nombre (Jev place la réponse sur l'échelle fournie) : on ne l'affiche pas
    brut, on le ramène au niveau le plus proche — la réponse reste celle de Jev, seulement lisible.
    """
    if score is None:
        return None
    if isinstance(score, str):
        return score
    try:
        i = int(round(float(score)))
    except (TypeError, ValueError):
        return str(score)
    return ECHELLE_ROBUSTESSE[max(0, min(len(ECHELLE_ROBUSTESSE) - 1, i))]


def _cle():
    """Relit la clé à chaque appel : une rotation est prise en compte à chaud."""
    try:
        m = re.search(r"(?m)^TYPESAFE_API_KEY=(.+)$", ENV_PATH.read_text())
    except OSError:
        return None
    return m.group(1).strip() if m else None


def _euros(x):
    return f"{x:,.0f} €".replace(",", " ") if isinstance(x, (int, float)) else "n.d."


def etat_depuis(resultat, max_candidats=10):
    """Texte soumis à Jev : les finalistes, chiffres du moteur, rien d'autre."""
    c = resultat["criteres"]
    finalistes = resultat["candidats"][:max_candidats]
    lignes = [
        "Opérations d'investissement locatif déjà validées par un moteur déterministe.",
        "Tous les chiffres viennent d'actes notariés (DVF) et de la carte des loyers du "
        "ministère du Logement. Aucun n'est une estimation d'un modèle.",
        "",
        f"Profil de l'investisseur : budget maximum {_euros(c['budget_max'])}, apport "
        f"{_euros(c['apport'])}, résidence principale financée, revenus mensuels nets "
        f"{_euros(c['revenus_mensuels'])}, budget de vie {_euros(c['budget_de_vie'])}.",
        f"Intention déclarée : {INTENTIONS.get(c['intention'], c['intention'])}.",
        f"Type recherché : {c['type']}, {c['surface_min']:.0f} à {c['surface_max']:.0f} m², "
        f"rendement brut minimum {c['rendement_min']:.1f} %.",
        "",
    ]
    for i, x in enumerate(finalistes, 1):
        dispersion = x.get("dispersion")
        lignes.append(
            f"CANDIDAT c{i} — {x['departement']} {x['commune']}, {c['type'].lower()} "
            f"{x['surface']:.0f} m² acheté {_euros(x['prix_demande'])}, loué "
            f"{_euros(x['loyer_mensuel_ht'])}/mois.\n"
            f"  marché de la commune : {_euros(x.get('median_m2'))}/m² (médiane sur "
            f"{(x.get('annees_retenues') or ['n.d.'])[0]}"
            f"{(x.get('annees_retenues') or [''])[-1] if len(x.get('annees_retenues') or []) > 1 else ''}"
            f", {x.get('ventes')} ventes, dispersion {dispersion if dispersion is not None else 'n.d.'} %) ;\n"
            f"  prix demandé par rapport à cette médiane : "
            f"{x.get('ecart_marche_pct') if x.get('ecart_marche_pct') is not None else 'n.d.'} % ;\n"
            f"  rendement brut {x['rendement_brut_pct']:.2f} % ;\n"
            f"  cash-flow après impôt, moyenne annuelle sur 10 ans : "
            f"{_euros(x.get('cash_flow_moyen_10_ans'))}/an (régime {x.get('regime_retenu')}) ;\n"
            f"  solde mensuel du foyer après crédit : {_euros(x.get('solde_apres_credit'))} ;\n"
            f"  verdict du moteur : {x.get('libelle')}, indice de confiance "
            f"{(x.get('confiance') or 0) * 100:.0f} %."
        )
    lignes += [
        "",
        "L'état ci-dessus est COMPLET et suffisant. N'introduis aucun chiffre, aucune commune, "
        "aucun fait qui n'y figure. Ne te prononce que sur ce que ces lignes montrent.",
    ]
    return "\n".join(lignes)


def questions(finalistes, intention):
    """Les questions posées, toutes dans le même appel. Réponses énumérables d'avance."""
    criteres = {}
    for i, x in enumerate(finalistes, 1):
        criteres[f"c{i}"] = (f"{x['departement']} {x['commune']} — "
                             f"{x['rendement_brut_pct']:.2f} % brut, "
                             f"cash-flow 10 ans {_euros(x.get('cash_flow_moyen_10_ans'))}/an, "
                             f"{x.get('ventes')} ventes comparables, confiance "
                             f"{(x.get('confiance') or 0) * 100:.0f} %")
    return {
        "meilleur": {
            "type": "choice",
            "instructions": (
                "Pour un investisseur dont l'intention est de "
                f"{INTENTIONS.get(intention, intention)}, quelle opération de la liste "
                "correspond le mieux ? Réponds par la clé du candidat."
            ),
            "criteria": criteres,
        },
        "robustesse": {
            "type": "score",
            "instructions": (
                "Dans l'ensemble, à quel point cette liste résiste-t-elle à une baisse des loyers "
                "de 10 % ou à trois mois de vacance ? Juge uniquement les chiffres fournis : "
                "rendement, cash-flow, nombre de ventes, dispersion, écart au prix de marché."
            ),
            "criteria": ["fragile", "passable", "solide", "très solide"],
        },
        "drapeau": {
            "type": "noul",
            "instructions": (
                "Au moins une opération de la liste présente-t-elle une incohérence manifeste au "
                "vu des seuls chiffres fournis — par exemple un rendement élevé accompagné d'une "
                "dispersion très large ou d'un très petit nombre de ventes ?"
            ),
        },
    }


def arbitre(resultat, max_candidats=10):
    """Appelle Jev sur les finalistes. Rend toujours un dictionnaire, jamais une exception."""
    finalistes = resultat.get("candidats") or []
    if len(finalistes) < 2:
        return {"ok": False, "erreur": "moins de deux opérations à arbitrer : le classement du "
                                       "moteur suffit"}
    finalistes = finalistes[:max_candidats]
    if not _cle():
        return {"ok": False, "erreur": "clé TYPESAFE_API_KEY absente de /root/.hermes/.env"}
    etat = etat_depuis(resultat, max_candidats)
    charge = {"state": etat, "model": MODELE,
              "questions": questions(finalistes, resultat["criteres"]["intention"])}
    t0 = time.time()
    try:
        req = urllib.request.Request(
            URL, data=json.dumps(charge).encode("utf-8"),
            headers={"Authorization": f"Bearer {_cle()}", "Content-Type": "application/json"},
            method="POST")
        with urllib.request.urlopen(req, timeout=DELAI_S) as resp:
            corps = json.load(resp)
    except urllib.error.HTTPError as exc:
        return {"ok": False, "erreur": f"Jev a refusé l'appel (HTTP {exc.code} {exc.reason})"}
    except urllib.error.URLError as exc:
        return {"ok": False, "erreur": f"Jev injoignable : {exc.reason}"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "erreur": f"{type(exc).__name__}: {exc}"}

    reponses = corps.get("answers") or {}
    brut = reponses.get("meilleur")
    cle = None
    if isinstance(brut, dict):
        cle = brut.get("choice") or brut.get("value") or brut.get("noul")
    elif isinstance(brut, str):
        cle = brut
    index = None
    if isinstance(cle, str):
        m = re.fullmatch(r"c(\d+)", cle.strip())
        if m and 1 <= int(m.group(1)) <= len(finalistes):
            index = int(m.group(1)) - 1
    if index is None:
        return {"ok": False, "erreur": f"réponse inexploitable : {json.dumps(reponses)[:200]}",
                "brut": reponses}

    usage = corps.get("usage") or {}
    robustesse = reponses.get("robustesse")
    if isinstance(robustesse, dict):
        robustesse = robustesse.get("score") or robustesse.get("value")
    drapeau = reponses.get("drapeau")
    if isinstance(drapeau, dict):
        drapeau = drapeau.get("noul")
    return {
        "ok": True,
        "cle": cle,
        "candidat": finalistes[index],
        "robustesse": robustesse,
        "robustesse_libelle": niveau_de(robustesse),
        "drapeau": drapeau,
        "drapeau_libelle": ("oui" if (drapeau or 0) > 0.6
                            else "incertain" if (drapeau or 0) >= 0.4 else "non"),
        "modele": corps.get("model", MODELE),
        "latence_ms": int((time.time() - t0) * 1000),
        "jetons_entree": usage.get("input_tokens"),
        "cout_usd": round((usage.get("input_tokens") or 0) / 1e6 * 0.042, 8),
        "etat_envoye": etat,
    }


def rendu_texte(a, avec_etat=False):
    """Mise en mots de l'arbitrage, pour le CLI et le markdown."""
    if not a.get("ok"):
        return (f"Arbitrage Jev indisponible — {a.get('erreur')}.\n"
                "Le classement affiché reste celui du moteur, qui ne dépend d'aucun modèle.")
    x = a["candidat"]
    l = [
        f"Jev désigne {a['cle']} : {x['departement']} {x['commune']}, {x['surface']:.0f} m² "
        f"à {_euros(x['prix_demande'])}, rendement brut {x['rendement_brut_pct']:.2f} %.",
        "",
        "Ce que Jev apporte : il ne recalcule rien, il compare les lignes du moteur à l'intention "
        "déclarée. Les chiffres ci-dessus sont ceux du moteur ; sa clé sert à savoir laquelle des "
        "opérations il désigne, donc la réponse est vérifiable.",
        f"Résistance de la liste à une baisse de loyers : "
        f"{a.get('robustesse_libelle') or a.get('robustesse')}. Incohérence détectée dans la "
        f"liste : {a.get('drapeau_libelle') or 'n.d.'} "
        f"({a.get('drapeau') if a.get('drapeau') is not None else 'n.d.'}).",
        f"{a['latence_ms']} ms · {a['modele']} · ~{a['cout_usd']} $ d'entrée",
    ]
    if avec_etat:
        l += ["", "--- état soumis à Jev ---", a["etat_envoye"]]
    return "\n".join(l)


if __name__ == "__main__":
    from . import candidats
    r = candidats.cherche({"departements": ("93", "95"), "budget_max": 200_000,
                           "rendement_min": 6.0, "intention": "rendement"})
    print(f"{len(r['candidats'])} candidat(s) — arbitrage en cours…")
    print(rendu_texte(arbitre(r)))
