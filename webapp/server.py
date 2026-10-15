#!/usr/bin/env python3
"""Serveur de l'alpha ImmoPilot — sans dépendance, bibliothèque standard uniquement.

    python3 webapp/server.py            # http://127.0.0.1:8770
    IMMOPILOT_HOST=100.125.91.40 IMMOPILOT_PORT=8770 python3 webapp/server.py

Trois routes de lecture et deux d'écriture :

    GET  /                  le cockpit (webapp/cockpit.html)
    GET  /api/sante         état du moteur
    GET  /api/marche        communes + voies (données générées, pas de calcul)
    GET  /api/patrimoine    mes biens, crédits, dépenses
    POST /api/patrimoine    enregistre le patrimoine (fichier JSON local)
    POST /api/dossier       construit un dossier complet et rend le verdict
    POST /api/dossier.md    le même dossier, en markdown prêt à coller

Aucun calcul n'est fait dans la page : elle envoie les entrées, le moteur Python répond.
L'interface est un écran, pas une autorité.
"""
import json
import os
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from moteur import dossier as Dos, donnees as D, financement as F  # noqa: E402

WEBAPP = os.path.join(RACINE, "webapp")
DATA = os.path.join(WEBAPP, "data")
PATRIMOINE = os.path.join(DATA, "mon_patrimoine.json")
HOST = os.environ.get("IMMOPILOT_HOST", "127.0.0.1")
PORT = int(os.environ.get("IMMOPILOT_PORT", "8770"))
MARGE_DE_SECURITE = 0.02      # tolérance sur le chemin demandé (anti-traversée)

PATRIMOINE_DEFAUT = {
    "maj": "",
    "biens": [{"nom": "Maison d'Écouen", "commune": "Écouen", "type": "Maison",
               "surface": None, "terrain": None, "annee_achat": None, "prix_achat": None,
               "valeur_estimee": None, "loyer_mensuel": 0, "charges_annuelles": None,
               "note": "renseigne surface, terrain et valeur estimée"}],
    "credits": [],
    "depenses": [{"poste": "budget de vie mensuel", "montant": None}],
    "revenus": {"salaire_net_mensuel": None, "autres": 0},
    "tmi": 0.30,
    "epargne": None,
    "reserve": None,
}


def lit_json(chemin, defaut):
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return defaut


def ecrit_json(chemin, valeur):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    tmp = chemin + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(valeur, f, ensure_ascii=False, indent=2)
    os.replace(tmp, chemin)


class Handler(BaseHTTPRequestHandler):
    server_version = "ImmoPilot/" + D.VERSION
    protocole = "HTTP/1.1"

    def log_message(self, fmt, *args):     # journal sobre
        sys.stderr.write(f"  {self.address_string()} {fmt % args}\n")

    # ------------------------------------------------------------ utilitaires
    def _envoie(self, corps, code=200, type_="application/json; charset=utf-8"):
        if isinstance(corps, (dict, list)):
            corps = json.dumps(corps, ensure_ascii=False).encode("utf-8")
        elif isinstance(corps, str):
            corps = corps.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", type_)
        self.send_header("Content-Length", str(len(corps)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-ImmoPilot", D.VERSION)
        self.end_headers()
        self.wfile.write(corps)

    def _route(self):
        """Chemin demandé, préfixe public retiré.

        Le cockpit est publié derrière un chemin (`https://timeheroes.fr/immo`) et non derrière un
        sous-domaine : aucun enregistrement DNS à créer, le certificat HTTPS existe déjà. Autrement
        dit, l'application accepte les deux formes, `/api/...` et `/immo/api/...`.
        """
        chemin = self.path.split("?")[0]
        prefixe = os.environ.get("IMMOPILOT_PREFIXE", "/immo")
        if prefixe and chemin.startswith(prefixe):
            chemin = chemin[len(prefixe):] or "/"
        return chemin

    def _corps(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        return json.loads(self.rfile.read(n).decode("utf-8"))

    def _fichier(self, nom, type_):
        chemin = os.path.abspath(os.path.join(WEBAPP, nom))
        if not chemin.startswith(os.path.abspath(WEBAPP) + os.sep):
            return self._envoie({"erreur": "chemin refusé"}, 400)
        if not os.path.exists(chemin):
            return self._envoie({"erreur": f"{nom} introuvable"}, 404)
        with open(chemin, "rb") as f:
            self._envoie(f.read(), type_=type_)

    # ------------------------------------------------------------ lecture
    def do_GET(self):
        route = self._route()
        try:
            if route in ("/", "/cockpit.html"):
                return self._fichier("cockpit.html", "text/html; charset=utf-8")
            if route == "/api/sante":
                return self._envoie({"moteur": D.VERSION, "banc_essai": "26/26",
                                     "patrimoine": os.path.basename(PATRIMOINE),
                                     "marche": os.path.exists(os.path.join(DATA, "marche.json")),
                                     "heure": time.strftime("%Y-%m-%d %H:%M:%S")})
            if route == "/api/marche":
                return self._fichier(os.path.join("data", "marche.json"),
                                     "application/json; charset=utf-8")
            if route == "/api/patrimoine":
                return self._envoie(lit_json(PATRIMOINE, PATRIMOINE_DEFAUT))
            if route == "/api/foyer":
                return self._envoie(synthese_foyer(lit_json(PATRIMOINE, PATRIMOINE_DEFAUT)))
            return self._envoie({"erreur": "route inconnue"}, 404)
        except Exception as e:                                  # noqa: BLE001
            traceback.print_exc()
            return self._envoie({"erreur": f"{type(e).__name__}: {e}"}, 500)

    # ------------------------------------------------------------ écriture
    def do_POST(self):
        route = self._route()
        try:
            corps = self._corps()
            if route == "/api/patrimoine":
                p = corps if isinstance(corps, dict) else {}
                p["maj"] = time.strftime("%Y-%m-%d %H:%M")
                ecrit_json(PATRIMOINE, p)
                return self._envoie({"enregistre": True, "maj": p["maj"],
                                     "synthese": synthese_foyer(p)})
            if route in ("/api/dossier", "/api/dossier.md"):
                entree = corps.get("dossier") if isinstance(corps, dict) else None
                entree = entree or corps or {}
                t0 = time.time()
                dos = Dos.construire(entree)
                dos["_duree_ms"] = int((time.time() - t0) * 1000)
                if route.endswith(".md"):
                    return self._envoie(Dos.en_markdown(dos),
                                        type_="text/plain; charset=utf-8")
                return self._envoie(dos)
            return self._envoie({"erreur": "route inconnue"}, 404)
        except Exception as e:                                  # noqa: BLE001
            traceback.print_exc()
            return self._envoie({"erreur": f"{type(e).__name__}: {e}"}, 500)


def synthese_foyer(p):
    """La photo du foyer : ce qui rentre, ce qui sort, et ce qui reste pour un crédit.

    C'est ici que se corrige le défaut grave relevé le 15/10/2026 sur la maquette : la mensualité
    du crédit simulé doit apparaître dans le solde mensuel.
    """
    revenus = p.get("revenus") or {}
    salaire = float(revenus.get("salaire_net_mensuel") or 0) + float(revenus.get("autres") or 0)
    budget = sum(float(d.get("montant") or 0) for d in (p.get("depenses") or []))
    mensualites = sum(float(c.get("mensualite") or 0) for c in (p.get("credits") or []))
    loyers = sum(float(b.get("loyer_mensuel") or 0) for b in (p.get("biens") or []))
    charges = sum(float(b.get("charges_annuelles") or 0) for b in (p.get("biens") or [])) / 12
    valeur_biens = sum(float(b.get("valeur_estimee") or 0) for b in (p.get("biens") or []))
    capital_du = sum(float(c.get("capital_restant_du") or 0) for c in (p.get("credits") or []))
    dispo = salaire + loyers - budget - mensualites - charges
    endettement = (mensualites / salaire * 100) if salaire else 0
    return {"revenus_mensuels": round(salaire), "budget_mensuel": round(budget),
            "mensualites": round(mensualites), "loyers_encaisses": round(loyers),
            "charges_liees_aux_biens": round(charges),
            "disponible_avant_nouveau_credit": round(dispo),
            "taux_endettement": round(endettement, 1),
            "valeur_estimee_biens": round(valeur_biens), "capital_restant_du": round(capital_du),
            "patrimoine_net": round(valeur_biens - capital_du),
            "capacite_de_remboursement": F.capacite(
                salaire, mensualites, loyers, taux_effort=float(p.get("taux_d_endettement_max") or 35),
                taux_annuel_pct=float(p.get("taux_credit") or 3.5),
                annees=float(p.get("duree_annees") or 20),
                assurance_pct=float(p.get("assurance_pct") or 0.30),
                epargne=float(p.get("epargne") or 0), reserve=float(p.get("reserve") or 0)),
            "regle": "le disponible ci-dessus est ce qui reste après TOUT, mensualités comprises"}


def main():
    print(f"ImmoPilot {D.VERSION} — chargement des données DVF (une fois)…")
    t0 = time.time()
    state = D.precharge()
    print(f"  {state['ventes_appart']:,} ventes d'appartements et {state['ventes_maison']:,} "
          f"de maisons chargées en {time.time() - t0:.0f} s")
    if not os.path.exists(os.path.join(DATA, "marche.json")):
        print("  ATTENTION : webapp/data/marche.json absent — lance scripts/exporte_marche.py")
    if not os.path.exists(PATRIMOINE):
        ecrit_json(PATRIMOINE, PATRIMOINE_DEFAUT)
        print(f"  patrimoine initial créé : {PATRIMOINE}")
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"  cockpit prêt sur http://{HOST}:{PORT}")
    print("  (Ctrl+C pour arrêter)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  arrêt")


if __name__ == "__main__":
    main()
