#!/usr/bin/env python3
"""Génère le site statique d'ImmoPilot pour GitHub Pages — `docs/index.html`.

    python3 scripts/generer_site_statique.py

Le site publié est une **fenêtre** : les données de marché et trois dossiers d'exemple y sont
calculés ici, une fois, par le moteur Python, puis figés dans la page. Aucun calcul d'impôt, de
rendement ou de verdict n'est refait en JavaScript dans la page — seul un calcul de mensualité,
explicitement étiqueté comme tel, est proposé au visiteur.

Le site publié ne contient **aucune donnée personnelle** : ni patrimoine, ni adresse, ni montant
réel. Les dossiers d'exemple portent sur des communes où Ronald n'habite pas.
"""
import html
import json
import os
import sys
from datetime import datetime, timezone

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
from moteur import analyse, donnees as D, dossier as Dos  # noqa: E402

C = D.fr       # format français, défini une seule fois dans le moteur


def euro(x, dec=0):
    return D.eur(x, dec)


def pct(x, dec=1):
    return C(x, dec) + " %"


# ---------------------------------------------------------------- dossiers d'exemple
# Profils génériques et cohérents : le site publié ne contient aucun chiffre personnel.
P_MENAGE = {"revenus_mensuels": 5000, "budget_de_vie": 3000, "charges_recurrentes": 0,
            "mensualites_existantes": 0, "epargne": 250000, "reserve": 30000, "tmi": 0.30}


def prix_marche(commune, surface, type_local="Appartement", ecart_pct=0.0):
    """Prix à X % du marché du périmètre — calculé par le moteur, pas écrit à la main."""
    ventes, _ = analyse.comparables_avec_repli(commune=commune, type_local=type_local,
                                               surface=surface)
    s = analyse.synthese(ventes)
    return round(s["median_eur_m2"] * surface * (1 + ecart_pct / 100))


EXEMPLES = [
    ("Appartement 30 m² à Groslay, au prix du marché",
     "Un rendement correct, payé sans crédit : les trois feux sont verts.",
     {"commune": "Groslay", "surface": 30, "loyer_mensuel_ht": 637, "profil": P_MENAGE,
      "prix_demande": prix_marche("Groslay", 30),
      "exploitation": {"charges_annuelles": 900, "taxe_fonciere": 750, "entretien_annuel": 400,
                       "vacance_pct": 5, "impaye_pct": 2, "travaux": 0, "mobilier": 0}}),
    ("Appartement 30 m² à Sannois, affiché 8 % au-dessus du marché",
     "Ni refus, ni blanc-seing : le moteur chiffre le prix auquel il faudrait négocier.",
     {"commune": "Sannois", "surface": 30, "loyer_mensuel_ht": 690, "profil": P_MENAGE,
      "prix_demande": prix_marche("Sannois", 30, ecart_pct=8),
      "exploitation": {"charges_annuelles": 900, "taxe_fonciere": 750, "entretien_annuel": 400,
                       "vacance_pct": 5, "impaye_pct": 2, "travaux": 0, "mobilier": 0}}),
    ("Appartement 30 m² à Montmorency, affiché 30 % au-dessus du marché",
     "Le piège du prix : c'est exactement pour ce cas qu'un outil doit savoir dire non.",
     {"commune": "Montmorency", "surface": 30, "loyer_mensuel_ht": 704, "profil": P_MENAGE,
      "prix_demande": prix_marche("Montmorency", 30, ecart_pct=30),
      "exploitation": {"charges_annuelles": 900, "taxe_fonciere": 750, "entretien_annuel": 400,
                       "vacance_pct": 5, "impaye_pct": 2, "travaux": 0, "mobilier": 0}}),
]


def dossier_html(entree, titre, sous_titre):
    try:
        dos = Dos.construire(entree)
        texte = Dos.en_markdown(dos)
        verdict = dos["verdict"]["verdict"]
        libelle = dos["verdict"].get("libelle", verdict)
        confiance = dos["verdict"]["confiance"]
        classe = {"ACHETER": "acheter", "NEGOCIER": "negocier",
                  "NON": "non"}.get(verdict, "indetermine")
    except Exception as e:                                       # noqa: BLE001
        return (f'<div class="carte"><h3>{html.escape(titre)}</h3>'
                f'<p class="note">Dossier indisponible : {html.escape(str(e))}</p></div>')
    return f'''<div class="carte">
      <div class="verdict v-{classe}"><span>{html.escape(libelle)}</span>
        <small>confiance {pct(confiance * 100, 0)}</small></div>
      <h3>{html.escape(titre)}</h3>
      <p class="sous">{html.escape(sous_titre)}</p>
      <details><summary>Voir le dossier complet produit par le moteur</summary>
        <pre>{html.escape(texte)}</pre></details>
    </div>'''


def main():
    chemin_index = os.path.join(RACINE, "docs", "data", "index.json")
    with open(chemin_index, encoding="utf-8") as f:
        index = json.load(f)
    total = sum(d["communes"] for d in index["departements"])
    print(f"marché : {len(index['departements'])} départements, {total} communes — "
          + ", ".join(d["code"] for d in index["departements"]))

    print("dossiers d'exemple…")
    exemples = []
    for titre, sous_titre, entree in EXEMPLES:
        blocs = dossier_html(entree, titre, sous_titre)
        exemples.append(blocs)
        print("  ", titre, "->", "ok" if "verdict v-" in blocs else "ECHEC")
    dossiers = "\n".join(exemples)

    adresse = "https://ronaldom9.github.io/immopilot/"
    page = PAGE.replace("__DOSSIERS__", dossiers)
    page = page.replace("__NB_DEP__", str(len(index["departements"])))
    page = page.replace("__NB_COMMUNES__", str(total))
    page = page.replace("__DEPARTEMENTS__", ", ".join(d["code"] for d in index["departements"]))
    page = page.replace("__GENERE__", datetime.now(timezone.utc).strftime("%d/%m/%Y"))
    page = page.replace("__ADRESSE__", adresse)

    dossier_sortie = os.path.join(RACINE, "docs")
    os.makedirs(dossier_sortie, exist_ok=True)
    chemin = os.path.join(dossier_sortie, "index.html")
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"écrit : {chemin} ({os.path.getsize(chemin) / 1024:.0f} Ko)")


PAGE = r"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark">
<title>ImmoPilot — marché d'Île-de-France et décision d'investissement</title>
<style>
:root{--bg:#08131f;--panel:#112335;--panel2:#172c40;--border:#294255;--text:#f3f7fa;--muted:#98afc0;
--accent:#5de3c5;--warn:#ffcc7b;--red:#ff928e;--radius:16px;
font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif}
*{box-sizing:border-box}body{margin:0;background:linear-gradient(130deg,#07111a,#0e1e31 54%,#08131e);color:var(--text)}
.shell{max-width:1200px;margin:0 auto;padding:26px 22px 80px}
header{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;margin-bottom:26px}
.brand{display:flex;gap:13px;align-items:center}
.logo{width:44px;height:44px;background:var(--accent);color:#07231f;display:grid;place-items:center;border-radius:13px;font-size:23px;font-weight:900}
h1{margin:0;font-size:23px;letter-spacing:-.8px}h1 small{color:var(--muted);font-weight:400;font-size:13px}
.brand p{margin:3px 0 0;color:var(--muted);font-size:12px}
.pill{border:1px solid #407367;color:var(--accent);background:#153c36;padding:7px 12px;border-radius:99px;font-size:12px}
h2{font-size:24px;letter-spacing:-.6px;margin:38px 0 6px}
p.lead{color:var(--muted);font-size:14px;line-height:1.6;margin:0 0 16px;max-width:920px}
.carte{background:var(--panel);border:1px solid var(--border);border-radius:var(--radius);padding:18px;margin-bottom:14px}
.grid{display:grid;gap:13px}.g2{grid-template-columns:repeat(2,minmax(0,1fr))}
.g3{grid-template-columns:repeat(3,minmax(0,1fr))}
input,select{background:#0c1d2b;border:1px solid #385265;border-radius:10px;padding:10px;color:var(--text);width:100%;font:inherit}
label{display:block;color:var(--muted);font-size:12px;margin-bottom:5px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid #22384a}
th{color:var(--muted);font-weight:600;font-size:12px}td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.scroll{max-height:460px;overflow:auto}
.verdict{display:flex;justify-content:space-between;align-items:baseline;border-radius:12px;padding:12px 16px;margin-bottom:12px;border:1px solid var(--border)}
.verdict span{font-size:26px;font-weight:800;letter-spacing:-.5px}
.verdict small{color:var(--muted);font-size:12px}
.v-acheter{border-color:#2f7d68;background:#12312c}.v-acheter span{color:var(--accent)}
.v-negocier{border-color:#8a7434;background:#2c2614}.v-negocier span{color:var(--warn)}
.v-non{border-color:#8a4643;background:#2c1618}.v-non span{color:var(--red)}
.v-indetermine{border-color:#3c5667;background:#1a2634}.v-indetermine span{color:var(--muted)}
.carte h3{margin:0 0 4px;font-size:16px}
p.sous{color:var(--muted);font-size:13px;margin:0 0 10px;line-height:1.5}
details summary{cursor:pointer;color:var(--accent);font-size:13px}
pre{background:#0c1d2b;border:1px solid #2b4256;border-radius:10px;padding:14px;overflow:auto;font-size:12px;line-height:1.5;white-space:pre-wrap;max-height:420px}
.note{background:#12283a;border-left:3px solid var(--accent);padding:12px 14px;border-radius:8px;font-size:13px;line-height:1.6}
.note.avert{border-left-color:var(--warn)}
.muted{color:var(--muted)}.sm{font-size:12px;line-height:1.6}
ul.rules{padding-left:20px;font-size:14px;line-height:1.7;margin:8px 0}
.kv{display:flex;justify-content:space-between;gap:12px;padding:7px 0;border-bottom:1px solid #22384a;font-size:13px}
.kv span:first-child{color:var(--muted)}.kv span:last-child{font-variant-numeric:tabular-nums}
footer{margin-top:46px;border-top:1px solid var(--border);padding-top:18px;color:var(--muted);font-size:12px;line-height:1.7}
a{color:var(--accent)}
@media(max-width:900px){.g3,.g2{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="shell">
<header>
  <div class="brand">
    <div class="logo">◆</div>
    <div>
      <h1>ImmoPilot <small>— marché d'Île-de-France</small></h1>
      <p>Moteur déterministe · les chiffres viennent des actes notariés, pas d'un modèle de langage</p>
    </div>
  </div>
  <span class="pill">données DVF 2021-2025 · publié le __GENERE__</span>
</header>

<h2>Ce que fait le moteur</h2>
<p class="lead">Il lit les <b>actes notariés réels</b> (base DVF, 39 955 ventes pour le Val-d'Oise en 2025),
calcule la médiane de la rue puis de la commune <b>à surface comparable</b>, estime la valeur par un
modèle taille et terrain, compare <b>quatre régimes fiscaux sur dix ans</b>, vérifie la mensualité et la
trésorerie du foyer — puis rend un verdict qui peut être <b>NON</b>. Il refuse même de trancher
quand la donnée ne suffit pas.</p>
<div class="carte">
  <ul class="rules">
    <li>Moins de <b>5 ventes comparables</b> : refus de trancher.</li>
    <li>Écart interquartile au-delà de <b>45 %</b> ou confiance sous <b>0,45</b> : pas de verdict.</li>
    <li>Prix demandé <b>&gt; 15 % au-dessus</b> du marché du périmètre : NON.</li>
    <li>Cash-flow après impôt <b>négatif en moyenne sur dix ans</b> : NON.</li>
    <li>Solde mensuel du foyer <b>négatif après la mensualité</b> : NON.</li>
    <li>Sinon ACHETER ; entre +5 % et +15 %, NÉGOCIER à un prix cible chiffré.</li>
  </ul>
</div>

<h2>Trois dossiers produits par le moteur</h2>
<p class="lead">Chaque carte contient le dossier complet, tel que le moteur l'écrit : comparables
ouverts, valeur, loyer, financement, fiscalité, trésorerie, verdict et motifs.</p>
<div class="g3" id="dossiers">
__DOSSIERS__
</div>

<h2>Le marché, commune par commune</h2>
<p class="lead">__NB_DEP__ départements d'Île-de-France (__DEPARTEMENTS__), __NB_COMMUNES__ communes.
Prix <b>actualisés au niveau 2025</b>, département par département. Sur les appartements de 15 à
45 m², la médiane départementale a monté de 4 à 10 % entre 2022 et 2025 (95 : +5,3 %, 92 : +9,8 %).
Médiane sur trois ans,
ou sur cinq ans quand la commune est trop petite. Chaque ligne dit sur combien de ventes elle
repose : une médiane sur deux ventes n'est pas un prix.</p>
<div class="carte">
  <div class="grid g4">
    <div><label>Département</label><select id="dep"></select></div>
    <div><label>Rechercher une commune</label><input id="q" placeholder="écouen, montreuil, paris…"></div>
    <div><label>Trier par</label><select id="tri">
      <option value="rendement">rendement brut</option>
      <option value="median_m2">prix au m² (croissant)</option>
      <option value="n">nombre de ventes</option>
      <option value="nom">nom</option></select></div>
    <div><label>Filtre</label><select id="filtre">
      <option value="solides">échantillons solides</option>
      <option value="tous">toutes les communes</option></select></div>
  </div>
</div>
<div class="carte">
  <h3 id="titre">Communes</h3>
  <div class="scroll"><table id="t"></table></div>
  <p class="sm muted" id="pied"></p>
</div>
<div class="carte" id="voies" style="display:none">
  <h3 id="titre-voies">Voies</h3>
  <div class="scroll"><table id="tv"></table></div>
  <p class="sm muted">Le prix se joue rue par rue : dans une même commune, l'écart entre deux voies
  dépasse souvent 40 %.</p>
</div>

<h2>Chercher la meilleure opération</h2>
<p class="lead">Les mêmes données que ci-dessus, filtrées par ce que tu peux et ce que tu veux :
budget, rendement exigé, surface. <b>Aucun modèle de langage n'intervient ici</b> — que de
l'arithmétique sur les actes notariés. La version complète (fiscalité sur dix ans, contrôle de
trésorerie, verdict et arbitrage Jev) tourne dans le cockpit privé, sur exactement les mêmes
chiffres.</p>
<div class="carte">
  <div class="grid g4">
    <div><label>Budget d'achat max (€)</label><input id="s-budget" type="number" value="160000" step="5000"></div>
    <div><label>Apport (€)</label><input id="s-apport" type="number" value="40000" step="5000"></div>
    <div><label>Rendement brut mini (%)</label><input id="s-rendement" type="number" value="6" step="0.5"></div>
    <div><label>Surface de — à (m²)</label><div style="display:flex;gap:8px">
      <input id="s-smin" type="number" value="20" step="1">
      <input id="s-smax" type="number" value="45" step="1"></div></div>
    <div><label>Type</label><select id="s-type"><option value="appart">appartement</option>
      <option value="maison">maison</option></select></div>
    <div><label>Intention</label><select id="s-intention">
      <option value="rendement">rendement</option><option value="securite">sécurité</option>
      <option value="revente">revente</option></select></div>
    <div><label>Taux du crédit (%)</label><input id="s-taux" type="number" value="3.5" step="0.05"></div>
    <div><label>Durée (années)</label><input id="s-duree" type="number" value="20" step="1"></div>
  </div>
</div>
<div id="s-resultat"></div>

<h2>Calcul rapide</h2>
<p class="lead">Arithmétique de crédit et de rendement, faite dans la page. C'est une calculatrice,
<b>pas un verdict</b> : le verdict demande les comparables, la fiscalité et la trésorerie.</p>
<div class="carte grid g3">
  <div><label>Prix d'achat (€)</label><input id="c-prix" type="number" value="110000" step="1000"></div>
  <div><label>Frais de notaire (%)</label><input id="c-frais" type="number" value="7.5" step="0.5"></div>
  <div><label>Apport (€)</label><input id="c-apport" type="number" value="20000" step="1000"></div>
  <div><label>Taux (%)</label><input id="c-taux" type="number" value="3.5" step="0.05"></div>
  <div><label>Durée (années)</label><input id="c-duree" type="number" value="20" step="1"></div>
  <div><label>Loyer mensuel HC (€)</label><input id="c-loyer" type="number" value="637" step="10"></div>
  <div><label>Charges annuelles (€)</label><input id="c-charges" type="number" value="2050" step="50"></div>
  <div><label>Statut</label><select id="c-statut">
    <option value="nu">Location nue</option><option value="meuble">Location meublée</option></select></div>
  <div><label>Tranche marginale</label><select id="c-tmi">
    <option value="0.11">11 %</option><option value="0.30" selected>30 %</option>
    <option value="0.41">41 %</option></select></div>
</div>
<div class="carte" id="c-resultat"></div>

<h2>Limites, à lire avant de décider</h2>
<div class="grid g2">
  <div class="carte">
    <h3>Ce que ce n'est pas</h3>
    <ul class="rules">
      <li><b>Pas un conseil fiscal.</b> Mécanique indicative 2026 ; la réforme LMNP de 2025
      réintroduit les amortissements dans le calcul de la plus-value. À valider par un expert-comptable.</li>
      <li><b>Pas un avis d'expert.</b> DVF = prix d'acte, hors état réel du bien.</li>
      <li>Ni DPE, ni état de copropriété, ni travaux votés, ni servitudes, ni bruit.</li>
      <li>Le montant des travaux et le loyer retenu sont des hypothèses saisies, pas des mesures.</li>
      <li>Pas d'annonces immobilières : leur extraction automatisée est illégale
      (Jinka, 200 000 € en 2026). Les ventes aux enchères judiciaires, seul flux légal, ne sont pas exploitées ici.</li>
    </ul>
  </div>
  <div class="carte">
    <h3>Méthode et sources</h3>
    <div class="kv"><span>Prix</span><span>DVF Etalab, 2021-2025, Île-de-France</span></div>
    <div class="kv"><span>Loyers</span><span>carte des loyers, ministère du Logement</span></div>
    <div class="kv"><span>Actualisation</span><span>indice départemental, base 2025</span></div>
    <div class="kv"><span>Comparables</span><span>bande de surface à ± 35 %</span></div>
    <div class="kv"><span>Dispersion</span><span>écart interquartile</span></div>
    <div class="kv"><span>Verdict</span><span>moteur Python, testé sur 20 dossiers dont 5 pièges</span></div>
    <p class="sm muted" style="margin-top:10px">Le code du moteur et le banc d'essai sont dans le
    dépôt. La version interactive complète (analyser n'importe quel bien, éditer son patrimoine)
    tourne sur un serveur privé : elle a besoin de Python, GitHub Pages ne sert que du statique.</p>
  </div>
</div>

<footer>
  ImmoPilot — moteur déterministe d'aide à la décision immobilière. Le modèle de langage ne calcule
  rien : médianes, quartiles, cash-flows, mensualités et impôts sont produits par le code Python du
  dépôt, puis mis en mots.<br>
  Adresse de cette page : <a href="__ADRESSE__">__ADRESSE__</a> · données publiées le __GENERE__.
</footer>
</div>

<script>
let M = null;
const n = x => (x===null||x===undefined||isNaN(x)) ? '—' : Math.round(x).toLocaleString('fr-FR');
const e = x => n(x) + ' €';
const p = (x,d=2) => (x===null||x===undefined||isNaN(x)) ? '—' : (+x).toFixed(d).replace('.',',') + ' %';
const esc = s => String(s??'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

async function charge(dep){
  const r = await fetch('data/marche_' + dep + '.json');
  if(!r.ok) throw new Error(dep);
  M = await r.json();
  document.getElementById('titre').textContent = 'Chargement…';
  document.getElementById('q').value = '';
  liste();
  cherche();
}

function liste(){
  const q = document.getElementById('q').value.toLowerCase();
  const tri = document.getElementById('tri').value;
  const filtre = document.getElementById('filtre').value;
  let l = M.communes.filter(c => c.appart)
        .filter(c => !q || c.nom.toLowerCase().includes(q))
        .filter(c => filtre === 'tous' || (c.appart.n >= 5 && c.appart.dispersion <= 45));
  l.sort((a,b) => tri === 'nom' ? a.nom.localeCompare(b.nom)
    : tri === 'n' ? b.appart.n - a.appart.n
    : tri === 'median_m2' ? a.appart.median_m2 - b.appart.median_m2
    : (b.appart.rendement_brut||0) - (a.appart.rendement_brut||0));
  document.getElementById('titre').textContent = l.length + ' communes sur ' + M.communes.length;
  document.getElementById('t').innerHTML = '<thead><tr><th>Commune</th><th class="num">Ventes</th>'
    + '<th class="num">Médiane €/m²</th><th class="num">Q1 – Q3</th><th class="num">Dispersion</th>'
    + '<th class="num">Loyer €/m²</th><th class="num">Rendement brut</th><th></th></tr></thead><tbody>'
    + l.map(c => { const a = c.appart; const deg = a.rendement_brut >= 9 ? 'mint' : '';
      return '<tr><td>'+esc(c.nom)+'</td><td class="num">'+a.n+'</td><td class="num">'+n(a.median_m2)+'</td>'
      + '<td class="num">'+n(a.q1)+' – '+n(a.q3)+'</td><td class="num">'+p(a.dispersion,0)+'</td>'
      + '<td class="num">'+(c.loyer ? p(c.loyer.loyer_m2,2) : '—')+'</td>'
      + '<td class="num" style="color:'+(deg?'var(--accent)':'inherit')+'">'+(a.rendement_brut ? p(a.rendement_brut,2) : '—')+'</td>'
      + '<td><button data-c="'+esc(c.nom)+'" style="background:#223a4b;color:var(--text);border:1px solid #3c5667;border-radius:8px;padding:5px 9px;font-size:12px;cursor:pointer">voies</button></td></tr>';
    }).join('') + '</tbody>';
  document.getElementById('pied').innerHTML = 'Prix actualisés au niveau 2025. Indice départemental '
    + Object.entries(M.indice_appartements).map(([a,v]) => a + ' × ' + String(v).replace('.',',')).join(' · ')
    + ' — médianes sur ' + M.annees_reference.join('-') + ', ou ' + M.annees_modele.join('-')
    + ' pour les petites communes. Généré le ' + esc(M.genere_le) + '.';
  document.querySelectorAll('[data-c]').forEach(b => b.onclick = () => voies(b.dataset.c));
}
function voies(nom){
  const c = M.communes.find(x => x.nom === nom); if(!c || !c.appart) return;
  document.getElementById('voies').style.display = 'block';
  document.getElementById('titre-voies').textContent = nom + ' — ' + c.appart.voies.length + ' voies';
  document.getElementById('tv').innerHTML = '<thead><tr><th>Voie</th><th class="num">Ventes</th>'
    + '<th class="num">Médiane €/m²</th><th class="num">Prix médian</th><th>Années</th></tr></thead><tbody>'
    + c.appart.voies.map(v => '<tr><td>'+esc(v.nom)+'</td><td class="num">'+v.n+'</td><td class="num">'
      + n(v.median_m2)+'</td><td class="num">'+e(v.median_prix)+'</td><td>'+esc(v.annees)+'</td></tr>').join('')
    + '</tbody>';
  document.getElementById('voies').scrollIntoView({behavior:'smooth', block:'nearest'});
}
['q','tri','filtre'].forEach(id => document.getElementById(id).addEventListener('input', liste));
document.getElementById('dep').addEventListener('change', e => charge(e.target.value).catch(err => {
  document.getElementById('titre').textContent = 'Département ' + err.message + ' indisponible';
}));
(async function(){
  try{
    const idx = await (await fetch('data/index.json')).json();
    document.getElementById('dep').innerHTML = idx.departements.map(d =>
      '<option value="'+d.code+'">département '+d.code+' — '+d.communes+' communes</option>').join('');
    const prefere = idx.departements.some(d => d.code === '95') ? '95' : idx.departements[0].code;
    document.getElementById('dep').value = prefere;
    await charge(prefere);
  }catch(e){
    document.getElementById('titre').textContent = 'Données de marché indisponibles (réseau ?)';
  }
})();

/* ---- recherche locale : filtre et tri sur les données déjà dans la page.
       Aucun appel réseau, aucun modèle de langage : de l'arithmétique, et rien d'autre. ---- */
function cherche(){
  if(!M) return;
  const type = document.getElementById('s-type').value === 'maison' ? 'maison' : 'appart';
  const budget = +document.getElementById('s-budget').value || 0;
  const apport = +document.getElementById('s-apport').value || 0;
  const rmin = +document.getElementById('s-rendement').value || 0;
  const smin = +document.getElementById('s-smin').value || 0;
  const smax = +document.getElementById('s-smax').value || 999;
  const taux = (+document.getElementById('s-taux').value || 0) / 100;
  const annees = +document.getElementById('s-duree').value || 20;
  const intention = document.getElementById('s-intention').value;

  const out = [];
  for (const c of M.communes){
    const a = c[type];
    if (!a || !a.median_m2 || !c.loyer || !c.loyer.loyer_m2) continue;
    if ((a.n || 0) < 5) continue;
    let surface = Math.min(Math.max(a.median_surface || smin, smin), smax);
    if (surface * a.median_m2 > budget) surface = smin;
    if (surface * a.median_m2 > budget) continue;
    const prix = surface * a.median_m2;
    const loyerM = c.loyer.loyer_m2 * surface * 0.95;
    const rendement = loyerM * 12 / prix * 100;
    if (rendement < rmin) continue;
    const capital = Math.max(0, prix * 1.075 - apport);
    const i = taux / 12, mois = annees * 12;
    const mensualite = capital ? capital * (i ? i / (1 - Math.pow(1 + i, -mois)) : 1 / mois) : 0;
    const charges = 14 * surface + prix * 0.0075 + prix * 0.004;
    const loyersAn = loyerM * 12 * 0.95 * 0.98;
    const cash = loyersAn - charges - mensualite * 12
               - loyersAn * (type === 'appart' ? 0.5 : 0.7) * 0.472;
    out.push({nom:c.nom, surface:surface, prix:prix, rendement:rendement, cash:cash,
              n:a.n, dispersion:a.dispersion, median_m2:a.median_m2, loyer:c.loyer.loyer_m2});
  }
  out.sort((x,y) => intention === 'securite' ? (y.n - x.n) || (x.dispersion - y.dispersion)
                  : intention === 'revente'   ? (y.n - x.n) || (y.rendement - x.rendement)
                  : (y.cash - x.cash) || (y.rendement - x.rendement));
  const l = out.slice(0, 12);
  const t = document.getElementById('s-resultat');
  if (!l.length){
    t.innerHTML = '<div class="carte"><p class="muted" style="margin:0">Aucune commune du '
      + 'département ' + esc(M.departement) + ' ne passe ces critères. Desserre le rendement exigé, '
      + 'élargis la surface ou augmente le budget — ou change de département ci-dessus.</p></div>';
    return;
  }
  t.innerHTML = '<div class="carte"><h3>' + out.length + ' opération(s) passent ces critères'
    + ' — les 12 premières</h3><div class="scroll"><table><thead><tr><th>Commune</th>'
    + '<th class="num">Lot</th><th class="num">Prix</th><th class="num">Médiane €/m²</th>'
    + '<th class="num">Loyer €/m²</th><th class="num">Rendement brut</th>'
    + '<th class="num">Trésorerie an 1 (approx.)</th><th class="num">Ventes</th>'
    + '<th class="num">Dispersion</th></tr></thead><tbody>'
    + l.map(x => '<tr><td>' + esc(x.nom) + '</td>'
        + '<td class="num">' + n(x.surface) + ' m²</td>'
        + '<td class="num">' + e(x.prix) + '</td>'
        + '<td class="num">' + n(x.median_m2) + '</td>'
        + '<td class="num">' + p(x.loyer, 2) + '</td>'
        + '<td class="num" style="color:' + (x.rendement >= 9 ? 'var(--accent)' : 'inherit') + '">'
          + p(x.rendement, 2) + '</td>'
        + '<td class="num" style="color:' + (x.cash < 0 ? 'var(--red)' : 'var(--accent)') + '">'
          + e(x.cash) + '</td>'
        + '<td class="num">' + x.n + '</td>'
        + '<td class="num">' + p(x.dispersion, 0) + '</td></tr>').join('')
    + '</tbody></table></div>'
    + '<p class="muted" style="margin:14px 0 0">La dernière colonne est une <b>approximation de '
    + 'trésorerie</b> : abattement forfaitaire (50 % meublé, 30 % nu), prélèvements 17,2 % et '
    + 'tranche marginale 30 %, sur l\'an 1. Le moteur complet classe les régimes sur dix ans, '
    + 'vérifie la trésorerie du foyer, rend un verdict — et sait refuser. Cet arbitrage-là ne se '
    + 'fait pas dans un navigateur.</p></div>';
}
document.querySelectorAll('#s-budget,#s-apport,#s-rendement,#s-smin,#s-smax,#s-type,#s-intention,#s-taux,#s-duree')
  .forEach(x => x.addEventListener('input', cherche));

function rapide(){
  const prix = +document.getElementById('c-prix').value || 0;
  const frais = (+document.getElementById('c-frais').value || 0) / 100;
  const apport = +document.getElementById('c-apport').value || 0;
  const taux = (+document.getElementById('c-taux').value || 0) / 100;
  const annees = +document.getElementById('c-duree').value || 20;
  const loyer = +document.getElementById('c-loyer').value || 0;
  const charges = +document.getElementById('c-charges').value || 0;
  const meuble = document.getElementById('c-statut').value === 'meuble';
  const tmi = +document.getElementById('c-tmi').value;
  const besoin = prix * (1 + frais);
  const capital = Math.max(0, besoin - apport);
  const i = taux / 12, mois = annees * 12;
  const mensualite = capital ? capital * (i ? i / (1 - Math.pow(1 + i, -mois)) : 1 / mois) : 0;
  const annuite = mensualite * 12;
  const loyers = loyer * 12 * 0.95 * 0.98;
  const interetsAn1 = capital * taux * 0.983;
  const base = meuble ? Math.max(0, loyers * 0.5) : Math.max(0, loyers * 0.7);
  const impot = base * (tmi + 0.172);
  const cash = loyers - charges - interetsAn1 - annuite - impot;
  const rendement = prix ? loyer * 12 / prix * 100 : 0;
  document.getElementById('c-resultat').innerHTML = '<div class="grid g3">'
    + '<div class="kv"><span>Besoin total</span><span>'+e(besoin)+'</span></div>'
    + '<div class="kv"><span>Capital emprunté</span><span>'+e(capital)+'</span></div>'
    + '<div class="kv"><span>Mensualité hors assurance</span><span>'+e(mensualite)+'</span></div>'
    + '<div class="kv"><span>Rendement brut</span><span>'+p(rendement,2)+'</span></div>'
    + '<div class="kv"><span>Impôt estimé an 1</span><span>'+e(impot)+'</span></div>'
    + '<div class="kv"><span>Cash-flow après impôt an 1</span><span style="color:'+(cash<0?'var(--red)':'var(--accent)')+'">'+e(cash)+'</span></div>'
    + '</div><div class="note avert" style="margin-top:12px">Cette calculatrice applique un abattement '
    + 'forfaitaire ('+(meuble?'50 % micro-BIC':'30 % micro-foncier')+') et n\'applique ni amortissement '
    + 'LMNP, ni régime réel, ni déficit foncier : le vrai classement des régimes se fait sur dix ans dans '
    + 'le moteur. Utiliser la version interactive complète pour un verdict.</div>';
}
document.querySelectorAll('#c-prix,#c-frais,#c-apport,#c-taux,#c-duree,#c-loyer,#c-charges,#c-statut,#c-tmi')
  .forEach(x => x.addEventListener('input', rapide));
rapide();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
