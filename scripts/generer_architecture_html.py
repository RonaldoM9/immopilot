#!/usr/bin/env python3
"""Genere le diagramme d'architecture logicielle d'ImmoPilot (HTML autonome + SVG inline)."""
import html, pathlib

W, H = 1800, 1010
SLATE = "#94a3b8"
CYAN = "#22d3ee"      # interfaces
EMER = "#34d399"      # agent / orchestration
AMBER = "#fbbf24"     # moteur deterministe
ORANGE = "#fb923c"    # outils
VIOLET = "#a78bfa"    # donnees
ROSE = "#fb7185"      # conformite / garde-fous
BORDER = "#1e293b"

out = []
add = out.append


def esc(t):
    return html.escape(str(t), quote=True)


def rect(x, y, w, h, stroke, fill, rx=6, sw=1.5, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="#0f172a"/>')
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}"'
        f' stroke-width="{sw}"{d}/>')


def text(x, y, t, size=12, color="#e2e8f0", weight="400", anchor="start", mono=True):
    fam = "'JetBrains Mono','DejaVu Sans Mono',monospace" if mono else \
          "Inter,system-ui,sans-serif"
    add(f'<text x="{x}" y="{y}" font-family="{fam}" font-size="{size}" fill="{color}"'
        f' font-weight="{weight}" text-anchor="{anchor}">{esc(t)}</text>')


def box(x, y, w, h, title, subs, stroke, fill, tsize=11.5, ssize=9, accent=False):
    rect(x, y, w, h, stroke, fill, sw=2.2 if accent else 1.5)
    text(x + 12, y + 20, title, tsize, "#f1f5f9", "700")
    for i, s in enumerate(subs):
        text(x + 12, y + 35 + i * 12, s, ssize, SLATE)


def band(x, y, w, h, label, stroke):
    rect(x, y, w, h, stroke, "#0b1220", rx=12, sw=1.2, dash="8,4")
    text(x + 14, y + 19, label, 10.5, stroke, "700")


def arrow(x1, y1, x2, y2, stroke, dash=None, label=None, lx=None, ly=None):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="1.6"'
        f'{d} marker-end="url(#arw-{stroke.strip("#")})"/>')
    if label:
        text(lx if lx else (x1 + x2) / 2, ly if ly else (y1 + y2) / 2 - 5, label, 8.5, stroke)


# ---- defs : grille + marqueurs de fleches ----
add(f'<defs><pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">'
    f'<path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1e293b" stroke-width="0.5"/></pattern>')
for c in (SLATE, CYAN, EMER, AMBER, ORANGE, VIOLET, ROSE):
    add(f'<marker id="arw-{c.strip("#")}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6"'
        f' markerHeight="6" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="{c}"/></marker>')
add('</defs>')
add(f'<rect width="{W}" height="{H}" fill="#020617"/>')
add(f'<rect width="{W}" height="{H}" fill="url(#grid)"/>')

# ================= PANNEAU GAUCHE : AUJOURD'HUI =================
LX, LW = 36, 470
band(LX, 96, LW, 834, "AUJOURD'HUI — MAQUETTE V0.1 (ce qui tourne vraiment)", SLATE)
bx, bw = LX + 20, LW - 40
box(bx, 140, bw, 84, "immopilot.html", ["fichier unique · HTML + CSS + JS · 6 modules",
                                        "aucune dependance, aucun serveur"], SLATE, "rgba(30,41,59,0.5)")
box(bx, 236, bw, 76, "MARKET — 17 communes figees", ["extrait du dossier du 14/10, code en dur",
                                                     "perimetres melanges : Ecouen en toutes surfaces"], SLATE, "rgba(30,41,59,0.5)")
box(bx, 324, bw, 76, "localStorage", ["donnees du foyer, non chiffrees",
                                      "un seul navigateur, aucun multi-appareil"], SLATE, "rgba(30,41,59,0.5)")
box(bx, 412, bw, 76, "Import CSV / Export JSON", ["depenses et sauvegarde : manuel",
                                                  "pas de connexion bancaire"], SLATE, "rgba(30,41,59,0.5)")
box(bx, 500, bw, 76, "Calculs du credit", ["exacts : coefficient 0,0060496 verifie",
                                           "previsionnel 12 mois juste au centime"], EMER, "rgba(6,78,59,0.35)")
box(bx, 588, bw, 138, "MOTEUR ABSENT", ["pas d'analyse rue par rue",
                                        "pas de fiscalite, donc pas de cash-flow apres impot",
                                        "aucun verdict, aucune regle de refus",
                                        "defaut teste : valide un achat non finançable",
                                        "(-600 EUR/mois, sans alerte)"], ROSE, "rgba(136,19,55,0.35)", accent=True)
box(bx, 738, bw, 168, "Ce qui reste a brancher", ["1. MARKET regenere : 57 communes, meme perimetre",
                                                  "   -> livrables/marche_95_2025.js (pret)",
                                                  "2. controle de tresorerie apres credit",
                                                  "3. verdict a 3 etats + regles de refus",
                                                  "4. moteur : rue, taille, terrain, fiscalite"], AMBER, "rgba(120,53,15,0.3)")

# ================= PANNEAU DROIT : CIBLE =================
RX, RW = 592, 1172
band(RX, 96, RW, 834, "CIBLE — ARCHITECTURE LOGICIELLE EN COUCHES", CYAN)
ix, iw = RX + 20, RW - 40

# --- L1 interfaces ---
band(ix, 128, iw, 96, "1 · INTERFACES — QUI PARLE A L'AGENT", CYAN)
w3 = (iw - 2 * 14 - 36) / 3
for i, (t, s) in enumerate([("Webapp cockpit privee", ["tailnet / 127.0.0.1", "multi-clients cloisonnes"]),
                            ("Agent Discord / Telegram", ["porte d'entree", "'colle ton annonce'"]),
                            ("API / serveur MCP", ["vers le CRM du pro", "dernier etage a construire"])]):
    box(ix + 14 + i * (w3 + 18), 156, w3, 56, t, s, CYAN, "rgba(8,51,68,0.4)")

# --- L2 agent ---
band(ix, 236, iw, 96, "2 · AGENT — ORCHESTRATION ET MODELE", EMER)
for i, (t, s) in enumerate([("Workflow durable", ["etats, reprise, checkpoint", "validation humaine"]),
                            ("Routage de modeles", ["petit modele + Ollama local", "pour extraire et classer"]),
                            ("Evaluation et traces", ["4 scores : completion, outil,", "ancrage, justesse du refus"])]):
    box(ix + 14 + i * (w3 + 18), 264, w3, 56, t, s, EMER, "rgba(6,78,59,0.4)")

# --- L3 moteur ---
band(ix, 344, iw, 172, "3 · MOTEUR DETERMINISTE — LE CŒUR (aucun calcul par le modele)", AMBER)
w4 = (iw - 28 - 3 * 18) / 4
for i, (t, s) in enumerate([("Comparables de rue", ["DVF signe, mediane,", "dispersion, n ventes"]),
                            ("Effet taille et terrain", ["modele log-log", "+ intervalle de confiance"]),
                            ("Constructibilite", ["PLU, servitudes,", "perimetres ABF"]),
                            ("Simulation locative", ["nu / meuble / par lots", "zone tendue"])]):
    box(ix + 14 + i * (w4 + 18), 372, w4, 56, t, s, AMBER, "rgba(120,53,15,0.3)")
for i, (t, s) in enumerate([("Fiscalite — 3 regimes", ["foncier, LMNP,", "deficit foncier"]),
                            ("Cash-flow apres impot", ["la seule ligne", "qui compte"]),
                            ("VERDICT + REFUS", ["ACHETER / NEGOCIER / NON", "avec indice de confiance"])]):
    box(ix + 14 + i * (w3 + 18), 440, w3, 62, t, s, AMBER,
        "rgba(120,53,15,0.45)" if i == 2 else "rgba(120,53,15,0.3)", accent=(i == 2))

# --- L4 outils ---
band(ix, 528, iw, 96, "4 · OUTILS — UN SERVEUR MCP PAR FAMILLE DE SOURCE (lecture seule)", ORANGE)
names = [("mcp-dvf", "prix signes"), ("mcp-loyers", "loyers + obs."), ("mcp-geo", "BAN + cadastre"),
         ("mcp-urbanisme", "GPU / zonage"), ("mcp-dpe", "etiquettes"), ("mcp-encheres", "canal legal"),
         ("mcp-documents", "PV d'AG -> Jev")]
w7 = (iw - 28 - 6 * 12) / 7
for i, (t, s) in enumerate(names):
    box(ix + 14 + i * (w7 + 12), 556, w7, 56, t, [s], ORANGE, "rgba(251,146,60,0.25)", tsize=10.5, ssize=8.5)

# --- L5 donnees ---
band(ix, 636, iw, 96, "5 · DONNEES ET MEMOIRE — TROIS MEMOIRES SEPAREES", VIOLET)
for i, (t, s) in enumerate([("Parquet + DuckDB", ["reference, millesimes", "DVF 2021-2025"]),
                            ("Postgres", ["etat des dossiers,", "verdicts, audit"]),
                            ("Documents clients", ["chiffres,", "purge sur demande"]),
                            ("Cache par hash", ["les memes fichiers", "relus mille fois"])]):
    box(ix + 14 + i * (w4 + 18), 664, w4, 56, t, s, VIOLET, "rgba(76,29,149,0.4)")

# --- transverse ---
band(ix, 744, iw, 96, "TRANSVERSE — CONFORMITE, VERSIONNAGE, AUDIT", ROSE)
for i, (t, s) in enumerate([("Loi Hoguet", ["le logiciel assiste,", "le client agit"]),
                            ("Aucun scraping", ["pas d'annonce extraite,", "aucune valeur par defaut"]),
                            ("Versionnage", ["millesimes + version", "du moteur"]),
                            ("Journal d'audit", ["chaque verdict", "rejouable ligne a ligne"])]):
    box(ix + 14 + i * (w4 + 18), 772, w4, 56, t, s, ROSE, "rgba(136,19,55,0.4)")

# --- hote ---
box(ix, 854, iw, 56, "HOTE — VPS : 8 vCPU, 15 Gio, Docker",
    ["systemd : gateway, profil immopilot, postgres, redis, caddy, ollama",
     "isolation : niveau 1 (profil) -> niveau 2 (conteneur, donnees client)"], SLATE, "rgba(30,41,59,0.5)")

# --- flux verticaux ---
cx = ix + iw - 30
for y1, y2, col, lab in ((224, 236, CYAN, None), (332, 344, EMER, None), (516, 528, AMBER, None),
                         (624, 636, ORANGE, None), (732, 744, VIOLET, None)):
    arrow(y1=y1 + 0, y2=y2, x1=cx, x2=cx, stroke=col)
# fleche de gauche a droite : le moteur manquant
add('<line x1="512" y1="664" x2="578" y2="436" stroke="#fb7185" stroke-width="2.6" stroke-dasharray="7,4" marker-end="url(#arw-fb7185)"/>')
text(506, 560, "a construire", 9, ROSE, "700", anchor="start")

# --- legende ---
ly = 962
items = [("Interfaces", CYAN), ("Agent / orchestration", EMER), ("Moteur deterministe", AMBER),
         ("Outils MCP", ORANGE), ("Donnees", VIOLET), ("Conformite / garde-fous", ROSE)]
x = LX
for lab, col in items:
    add(f'<rect x="{x}" y="{ly - 9}" width="12" height="12" rx="3" fill="{col}" opacity="0.85"/>')
    text(x + 18, ly, lab, 9.5, SLATE)
    x += 24 + len(lab) * 6.2
text(LX, ly + 20, "Fleches pleines : appel synchrone entre couches · pointille rose : garde-fou et flux differe (a construire)",
     9, "#64748b")

svg = "\n".join(out)

PAGE = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<title>ImmoPilot — architecture logicielle</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:#020617; color:#e2e8f0; font-family:'JetBrains Mono','DejaVu Sans Mono',monospace;
          padding:26px 30px 34px; }}
  header {{ display:flex; align-items:center; gap:14px; margin-bottom:18px; }}
  .dot {{ width:11px; height:11px; border-radius:50%; background:#5de3c5;
          box-shadow:0 0 0 0 rgba(93,227,197,.7); animation:pulse 2.4s infinite; }}
  @keyframes pulse {{ 70% {{ box-shadow:0 0 0 12px rgba(93,227,197,0); }} 100% {{ box-shadow:0 0 0 0 rgba(93,227,197,0); }} }}
  h1 {{ font-size:21px; letter-spacing:-0.4px; }}
  .sub {{ font-size:12px; color:#94a3b8; margin-top:3px; }}
  .frame {{ border:1px solid #1e293b; border-radius:14px; overflow:hidden; background:#020617; }}
  .cards {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin-top:18px; }}
  .card {{ border:1px solid #1e293b; border-radius:12px; background:#0b1220; padding:14px 16px; }}
  .card h3 {{ font-size:12.5px; margin-bottom:8px; }}
  .card ul {{ list-style:none; }} .card li {{ font-size:10.5px; color:#94a3b8; line-height:1.65; }}
  .cy {{ color:#22d3ee; }} .em {{ color:#34d399; }} .am {{ color:#fbbf24; }}
  footer {{ margin-top:16px; font-size:10px; color:#64748b; }}
</style></head><body>
<header><div class="dot"></div><div>
  <h1>ImmoPilot — architecture logicielle</h1>
  <div class="sub">Maquette actuelle (a gauche) et architecture cible (a droite) · 15 octobre 2026 · projet /root/projects/immopilot</div>
</div></header>
<div class="frame"><svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">{svg}</svg></div>
<div class="cards">
  <div class="card"><h3 class="cy">Decision fondatrice</h3><ul>
    <li>• Un seul moteur, deux enveloppes : profil personnel, puis service autonome.</li>
    <li>• Le modele ne calcule jamais : le calcul est en code, le modele orchestre et redige.</li>
    <li>• L'outil doit pouvoir dire non, sinon il valide les decisions deja prises.</li>
  </ul></div>
  <div class="card"><h3 class="em">Ce que la couche 2 apporte</h3><ul>
    <li>• Reprise apres panne : un dossier long ne repart pas de zero.</li>
    <li>• Chaque transition d'etat devient une entree d'audit : verdict rejouable.</li>
    <li>• Routage par noeud : petit modele pour extraire, modele fort pour decider.</li>
  </ul></div>
  <div class="card"><h3 class="am">Ordre de construction</h3><ul>
    <li>• Livre : moteur + banc d'essai (20 dossiers dont 5 pieges).</li>
    <li>• Puis les serveurs MCP, la boucle durable, les traces.</li>
    <li>• L'interface en dernier : la webapp est une facade, pas un projet.</li>
    <li>• Puis 3 chasseurs en test — le test qui vaut 200 EUR par mois se fait en 3 coups de fil.</li>
  </ul></div>
</div>
<footer>Sources : DVF 2025 et Carte des loyers 2025 (data.gouv) · dossier de travail du 14/10/2026 · revue de la maquette du 15/10/2026.</footer>
</body></html>
"""

path = pathlib.Path('/root/projects/immopilot/livrables/architecture_immopilot.html')
path.write_text(PAGE, encoding='utf-8')
print("HTML ecrit :", path, len(PAGE), "caracteres")
