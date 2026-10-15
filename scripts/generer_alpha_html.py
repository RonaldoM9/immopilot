#!/usr/bin/env python3
"""Diagramme de l'alpha personnelle ImmoPilot (HTML autonome + SVG inline -> PNG)."""
import html, pathlib

W, H = 1700, 1010
CYAN, EMER, AMBER, VIOLET, ROSE, SLATE, ORANGE = ("#22d3ee", "#34d399", "#fbbf24",
                                                  "#a78bfa", "#fb7185", "#94a3b8", "#fb923c")
out = []
add = out.append


def esc(t):
    return html.escape(str(t), quote=True)


def rect(x, y, w, h, stroke, fill, rx=6, sw=1.5, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="#0f172a"/>')
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}"'
        f' stroke-width="{sw}"{d}/>')


def text(x, y, t, size=12, color="#e2e8f0", weight="400", anchor="start"):
    add(f'<text x="{x}" y="{y}" font-family="\'JetBrains Mono\',\'DejaVu Sans Mono\',monospace"'
        f' font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}">{esc(t)}</text>')


def box(x, y, w, h, title, subs, stroke, fill="rgba(30,41,59,0.5)", tsize=11.5, ssize=9,
        accent=False, tag=None):
    rect(x, y, w, h, stroke, fill, sw=2.2 if accent else 1.5)
    text(x + 12, y + 20, title, tsize, "#f1f5f9", "700")
    for i, s in enumerate(subs):
        text(x + 12, y + 35 + i * 12, s, ssize, SLATE)
    if tag:
        text(x + w - 12, y + 20, tag, 8.5, stroke, "700", anchor="end")


def band(x, y, w, h, label, stroke):
    rect(x, y, w, h, stroke, "#0b1220", rx=12, sw=1.2, dash="8,4")
    text(x + 14, y + 19, label, 10.5, stroke, "700")


def arrow(x1, y1, x2, y2, stroke, dash=None, w=1.8):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{w}"'
        f'{d} marker-end="url(#arw-{stroke.strip("#")})"/>')


add('<defs><pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">'
    '<path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1e293b" stroke-width="0.5"/></pattern>')
for c in (CYAN, EMER, AMBER, VIOLET, ROSE, SLATE, ORANGE):
    add(f'<marker id="arw-{c.strip("#")}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6"'
        f' markerHeight="6" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="{c}"/></marker>')
add('</defs>')
add(f'<rect width="{W}" height="{H}" fill="#020617"/><rect width="{W}" height="{H}" fill="url(#grid)"/>')

X, IW = 36, W - 72

# 1 · portes d'entree
band(X, 40, IW, 108, "1 · TES TROIS PORTES D'ENTREE", CYAN)
w3 = (IW - 28 - 2 * 18) / 3
for i, (t, s, tag) in enumerate([
        ("Discord — ce fil", ["« ce bien a Sannois a 118 000 EUR,", "je le prends ? »  ->  dossier complet"], "deja la"),
        ("Webapp cockpit", ["l'app existante, mais alimentee", "par un fichier généré (make webapp)"], "deja la"),
        ("CLI et cron", ["veille mensuelle, alertes", "de seuil, réévaluation"], "deja la")]):
    box(X + 14 + i * (w3 + 18), 68, w3, 62, t, s, CYAN, "rgba(8,51,68,0.4)", tag=tag)

arrow(X + IW / 2, 148, X + IW / 2, 168, SLATE, w=2.2)

# 2 · moteur
band(X, 168, IW, 200, "2 · LE MOTEUR — PAQUET PYTHON `moteur/`  (le modèle ne calcule jamais)", AMBER)
w6 = (IW - 28 - 5 * 12) / 6
mods = [("comparables_rue", ["DVF signe, mediane,", "dispersion, >= 5 ventes"], "existe"),
        ("valeur", ["effet taille et terrain", "+ intervalle de confiance"], "existe"),
        ("locatif", ["nu / meublé / par lots", "loyer + nb observations"], "à écrire"),
        ("fiscalite", ["3 régimes, deficit", "foncier, apres impot"], "à écrire"),
        ("financement", ["capacité, effort, ET", "contrôle de trésorerie"], "à écrire"),
        ("verdict", ["ACHETER / NEGOCIER", "/ NON + confiance"], "à écrire")]
for i, (t, s, tag) in enumerate(mods):
    col = EMER if tag == "existe" else AMBER
    box(X + 14 + i * (w6 + 12), 196, w6, 66, t, s, col, "rgba(6,78,59,0.35)" if tag == "existe" else "rgba(120,53,15,0.3)",
        tsize=10.5, ssize=8.5, tag=tag)
box(X + 14, 274, IW - 28, 78, "BANC D'ESSAI — 20 dossiers de référence, dont 5 pièges a refuser",
    ["un test échoue si le moteur valide un piège  ·  cas de depart : la maison d'Ecouen, les communes du dossier du 14/10,",
     "la rue Clemenceau 2021 (2 916 et 4 866 EUR/m2), un achat hors capacité apres contrôle de trésorerie, un prix 12 % au-dessus du marche"],
    ROSE, "rgba(136,19,55,0.35)", ssize=8.5, accent=True)

arrow(X + IW / 2, 372, X + IW / 2, 392, SLATE, w=2.2)

# 3 · données
band(X, 392, IW, 196, "3 · TES DONNEES — UNE SOURCE DE VERITE PAR DONNEE", VIOLET)
w4 = (IW - 28 - 3 * 18) / 4
dons = [("DuckDB + Parquet", ["dvf95_2021..2025 · loyers_2025", "versionnes par millesime"], "existe"),
        ("cache/", ["cadastre, PLU, DPE :", "reponses mises en cache"], "à écrire"),
        ("mon_patrimoine.yaml", ["la maison, les crédits,", "les charges réelles"], "à écrire"),
        ("dossiers/ + Foyer", ["un fichier par bien étudié", "· budget reel importe"], "partiel")]
for i, (t, s, tag) in enumerate(dons):
    col = EMER if tag == "existe" else (ORANGE if tag == "partiel" else AMBER)
    box(X + 14 + i * (w4 + 18), 420, w4, 66, t, s, col, "rgba(76,29,149,0.4)", tsize=10.5, ssize=8.5, tag=tag)
box(X + 14, 496, IW - 28, 78, "FICHIERS DE SORTIE",
    ["dossiers/2026-10-15-sannois-t3.md — verdict, comparables, fiscalite, cash-flow : la mémoire de la decision",
     "une page web regénérée pour le cockpit  ·  un CSV de suivi des biens étudiés"],
    VIOLET, "rgba(76,29,149,0.3)", ssize=8.5)

arrow(X + IW / 2, 592, X + IW / 2, 612, SLATE, w=2.2)

# 4 · veille
band(X, 612, IW, 130, "4 · VEILLE ET ALERTES — CRON (ce qui travaille sans que tu demandes)", ORANGE)
for i, (t, s) in enumerate([("Mensuelle — nouveaux DVF", ["la rue et la commune sont réextraites,", "réévaluation + alerte si écart > 5 %"]),
                            ("Hebdomadaire — enchères du 95", ["le seul canal d'annonces legal :", "publication obligatoire, open data"]),
                            ("Trimestrielle — échéances", ["taxe fonciere, AG de copropriete,", "PNO, travaux votes"])]):
    box(X + 14 + i * (w3 + 18), 640, w3, 62, t, s, ORANGE, "rgba(251,146,60,0.25)", tsize=10.5, ssize=8.5)

arrow(X + IW / 2, 742, X + IW / 2, 762, SLATE, w=2.2)

# 5 · garde-fous
band(X, 762, IW, 118, "5 · GARDE-FOUS ET CADRE", ROSE)
for i, (t, s) in enumerate([("Aucun scraping", ["les annonces entrent collées", "a la main, ou par les enchères"]),
                            ("Aucun identifiant bancaire", ["la connexion bancaire reste", "hors périmètre"]),
                            ("Tout sur le VPS, tailnet", ["aucune exposition publique,", "sauvegarde chiffrée"]),
                            ("Pas un conseil", ["chiffrage sur des prix", "d'actes publics"])]):
    box(X + 14 + i * (w4 + 18), 790, w4, 62, t, s, ROSE, "rgba(136,19,55,0.4)", tsize=10.5, ssize=8.5)

# legende
ly = 918
for i, (lab, col) in enumerate([("existe deja", EMER), ("à écrire pour l'alpha", AMBER),
                                ("partiel", ORANGE), ("données", VIOLET), ("garde-fous", ROSE)]):
    x = X + i * 230
    add(f'<rect x="{x}" y="{ly - 9}" width="12" height="12" rx="3" fill="{col}" opacity="0.9"/>')
    text(x + 18, ly, lab, 9.5, SLATE)
text(X, ly + 22, "Le modèle de langage orchestre et redige ; il ne calcule jamais. Le moteur rend un verdict structuré, l'agent le met en mots.",
     9, "#64748b")
text(X, ly + 40, "Alpha personnelle : un seul utilisateur, donc pas de Postgres, pas de Docker, pas de workflow durable, pas de base vectorielle.",
     9, "#64748b")

svg = "\n".join(out)
PAGE = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<title>ImmoPilot Alpha — architecture personnelle</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#020617;color:#e2e8f0;font-family:'JetBrains Mono','DejaVu Sans Mono',monospace;padding:24px 30px 28px}}
header{{display:flex;align-items:center;gap:14px;margin-bottom:16px}}
.dot{{width:11px;height:11px;border-radius:50%;background:#5de3c5;animation:p 2.4s infinite}}
@keyframes p{{70%{{box-shadow:0 0 0 12px rgba(93,227,197,0)}}100%{{box-shadow:0 0 0 0 rgba(93,227,197,0)}}}}
h1{{font-size:20px;letter-spacing:-.4px}}.sub{{font-size:11.5px;color:#94a3b8;margin-top:3px}}
.frame{{border:1px solid #1e293b;border-radius:14px;overflow:hidden}}
footer{{margin-top:14px;font-size:10px;color:#64748b}}</style></head><body>
<header><div class="dot"></div><div><h1>ImmoPilot Alpha — architecture personnelle</h1>
<div class="sub">Gerer le bien d'Ecouen et preparer les futurs investissements · un seul utilisateur · 15 octobre 2026</div></div></header>
<div class="frame"><svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">{svg}</svg></div>
<footer>Sources : DVF 2025 et Carte des loyers 2025 (data.gouv) · dossier de travail du 14/10/2026 · revue de la maquette et architecture du 15/10/2026.</footer>
</body></html>"""
p = pathlib.Path('/root/projects/immopilot/livrables/alpha_immopilot.html')
p.write_text(PAGE, encoding='utf-8')
print("HTML ecrit :", p, len(PAGE), "caracteres")
