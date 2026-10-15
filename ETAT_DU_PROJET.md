# Immopilot — état du projet

**Récupéré du fil Telegram du mercredi 14 octobre 2026** (session `20260730_043914_ca1e1c36`,
échanges de 10 h 28 à 17 h 02 UTC) vers ce dépôt de travail, à la demande de Ronald.
Tout ce qui suit est la reprise fidèle du travail fait ce jour-là, plus la vérification
faite le soir même (le 14/10 à 21 h) : le script `scripts/rendement_95.py` rejoue les
chiffres et signale les écarts.

---

## 1. De quoi on parle

Un **outil d'aide à la décision en achat immobilier**, conçu à partir de données
ouvertes, dans deux formes successivement envisagées :

- **v-outil (personnelle)** : pour Ronald, sur sa commune et ses communes voisines.
  Il transforme une adresse et un prix demandé en verdict chiffré en cinq minutes.
- **v-produit (licence)** : le même moteur vendu **aux professionnels** — chasseurs
  immobiliers, agences, CGP, courtiers. Ils ont déjà la carte professionnelle et les
  annonces ; le produit apporte le travail, pas l'information.

Nom de travail du fil Discord : **immopilot**.

---

## 2. Ce qui a été fait le 14 octobre 2026

Cinq questions de Ronald, cinq réponses construites sur des données réelles, pas sur
des hypothèses.

1. **« Peux-tu te brancher à SeLoger, Leboncoin, les cadastres ? »** → cadastre, DVF,
   BAN : oui. Portails d'annonces : non, et ce n'est pas une limite technique.
2. **« Mon camarade de MBA divise des maisons en 4 lots : la culbute est dans le
   terrain exploitable ? »** → testé sur les ventes réelles d'Écouen. Sa règle est
   fausse et son propre montage la contredit.
3. **« Créer un agent spécialiste de l'achat immobilier, t'en penses quoi ? »** →
   oui pour l'outil, non pour un agent séparé, non pour l'achat maintenant.
4. **« Créer de l'IA sous licence pour de la vente immobilière »** → là c'est un
   produit : deux murs (annonces, loi Hoguet) et une seule forme qui tient debout.
5. **« Quel investissement à 100 000 € dans le 95 ? Quel bien, quel quartier ? »** →
   rendements réels par commune et par rue (DVF 2025 × carte des loyers 2025),
   test de Jev sur le cas réel, recommandation argumentée.

Livrables produits ce jour-là :

- `livrables/dossier_immobilier_jev.docx` — dossier Word complet, 13 sections,
  17 tableaux, remis à 17 h 02 pour mise en forme dans ChatGPT.
- `livrables/immo_slide.png` (+ `immo_slide.html`) — slide unique
  architecture + cash flow, 1920×1080, corrigée après contrôle visuel.
- `transcription_telegram_14oct2026.txt` — la conversation intégrale, pour qu'aucun
  chiffre ne dépende d'un souvenir.

---

## 3. Les chiffres établis

### 3.1 Écouen, ventes 2025 (DVF) — le montage du camarade, testé

- Ventes de maisons : 38, médiane **3 437 €/m²**
- Ventes d'appartements : 51, médiane **2 687 €/m²** (moins cher que la maison)
- Effet taille : **< 45 m² = 3 828 €/m²**, 45-70 m² = 3 030, 70-100 m² = 2 716, > 100 m² = 2 720
- Achat d'une maison de 104 m² à 3 302 €/m² : **343 408 €**
- Revente en 4 lots de 26 m² à 3 828 €/m² : **398 112 €** → gain brut **+54 704 €**
- Travaux de division (4 cuisines, 4 salles d'eau, réseaux, portes, architecte, notaire,
  règlement de copropriété) : **100 000 à 200 000 €**
- **Résultat : fortement négatif à Écouen.** Le montage marche à Paris intra-muros
  (maison ~9 000 €/m², 25 m² > 13 000 €/m²), pas en banlieue pavillonnaire où l'écart
  entre le m² maison et le m² appartement est de l'ordre de 500 €/m².

### 3.2 Le vrai levier

- **Nombre d'unités locatives par euro investi** (diviser, combles, garage, dépendance —
  avec ou sans terrain).
- **Écart à l'entrée** : acheter au m² bas, relouer/revendre au m² haut.
- **Régime fiscal**, déterminant et généralement ignoré : nu (revenus fonciers, 17,2 %,
  aucun amortissement) / meublé LMNP (amortissement du bien, revenu imposable souvent
  quasi nul) / déficit foncier (travaux imputables sur le **revenu global**, jusqu'à
  **10 700 €/an**). À faire valider par un expert-comptable, pas par un agent.

### 3.3 Le produit sous licence

- Honoraires d'un chasseur immobilier : **2 à 4 % du prix, moyenne 3 % HT**, plancher
  6 000 à 10 000 € en zone tendue. Un bien à 300 000 € = 9 000 € pour le chasseur.
  Un outil à 500-1 000 € est **95 % sous le marché** → place pour un prix intermédiaire.
- Taille du marché : **200 à 300 chasseurs en France** (~100 en IDF, le plus gros réseau
  en revendique 160, deux fédérations de quelques dizaines d'adhérents).
  **100 % de ce marché ≈ 1 M€/an** : ce n'est pas un candidat au capital-risque, c'est
  un revenu complémentaire ou un business à taille humaine.
- Prix SaaS immobilier relevés 2026 : mandataire seul 49-150 €/mois, agence 5 personnes
  99-139 €/mois, multi-sites 800 €+. **Hypothèse de 290 €/mois écartée** ; fourchette
  retenue **120-180 €/mois**.
- Trois scénarios : **A** chasseurs seuls, 20 cabinets × 150 € = 36 k€/an ;
  **B** chasseurs + CGP, 130 clients = 198 k€/an ; **C** marque blanche à un éditeur de
  CRM, 1 intégration × 5 000 € = 60 k€/an. Taux de conversion **non validés**.

### 3.4 Les deux murs

- **Les annonces.** SeLoger / Leboncoin / Bien'ici : pas d'API publique, DataDome
  (détection < 2 ms par requête). Le risque est chiffré : **14 avril 2026, cour d'appel
  de Versailles, l'éditeur de Jinka condamné à 200 000 € au profit de Leboncoin** pour
  extraction et republication d'annonces. L'arme n'est pas les CGU mais le **droit sui
  generis du producteur de base de données (art. L341-1 CPI)** : extractions
  quantitativement ou qualitativement substantielles interdites. 363 000 annonces, ce
  n'est ni l'un ni l'autre de négligeable.
- **La loi Hoguet.** Article 14 de la loi n° 70-9 du 2 janvier 1970 : six mois
  d'emprisonnement et 7 500 € d'amende pour s'être livré ou avoir **« prêté son
  concours »**, **« même à titre accessoire »**, à une opération immobilière sans carte
  professionnelle. Conséquence de conception : jamais « chercher pour le client » —
  **un logiciel que le client utilise lui-même**.

### 3.5 Sources de données — état vérifié

Ouvert et exploité : **DVF** (ventes signées, 39 955 lignes pour le 95 en 2025),
**carte des loyers 2025** (loyers d'annonce 1-2 pièces), **cadastre IGN / API Carto**,
**BAN**, Géoportail de l'urbanisme, **immobilier.notaires.fr** (HTTP 200 + sitemap),
**open data des ventes aux enchères judiciaires** (data.gouv.fr, 3 762 ventes pour 2022 :
73 % adjugées, écart médian entre mise à prix et adjudication **×2,04**).

Bloqué : `encheres-publiques.com` et `interencheres.com` (défis Cloudflare, pas des
refus d'exploration), `licitor.com` (listes vendues par abonnement), les portails
d'annonces. Aucune donnée ouverte ne dit l'état du bâti ni la santé d'une copropriété.

### 3.6 Rendements réels, Val-d'Oise 2025 (appartements 15-45 m²)

*(chiffres tels qu'établis et communiqués le 14/10 ; voir § 6 pour l'écart de
reproduction sur quatre communes)*

- 10,21 % **Garges-lès-Gonesse** — 2 564 €/m², 15 ventes, 406 obs. de loyer
- 9,43 % **Villiers-le-Bel** — 2 727 €/m², 28 ventes, 871 obs.
- 8,34 % Goussainville · 8,03 % Arnouville · 7,46 % Magny-en-Vexin
- 7,38 % **Sannois** — 3 741 €/m², 32 ventes, **1 495 obs.** (donnée la plus solide)
- 7,23 % **Groslay** — 3 526 €/m², 8 ventes, 278 obs. (échantillon mince)
- 7,19 % Sarcelles · 7,17 % Montmorency · médiane départementale **6,58 %**

Lecture : les rendements élevés sont des **prix du risque** (impayés, copropriétés
dégradées, revente lente), pas des cadeaux. Écarts de prix au m² **entre les rues d'une
même commune** : Villiers-le-Bel 1 000 → 4 406 €/m² (×4,4), Sarcelles ×2,3, Groslay ×1,8.
Un 25 m² coûte plus de 100 000 € dans douze des seize communes autour d'Écouen.

### 3.7 Recommandation du 14/10

- Commune : **Groslay**, ou **Sannois** en second (marché homogène, pas de rue à éviter).
- Le bien : appartement **30-45 m², 2 pièces**, immeuble **≥ 20 lots**, **DPE D ou mieux**
  (F interdit à la location en 2028, E en 2034), **plafond 95 000 € frais compris**.
- À éviter malgré le rendement : Villiers-le-Bel bd Carnot et rue Bourdelle, Sarcelles
  route de Garges.
- Contexte assumé : revenus du foyer ~7 594 €/mois contre ~10 625 € de charges
  (**−3 000 €/mois**). L'outil, oui, tout de suite. **L'achat, après la sortie de MBA.**
- TimeHeroes a un jalon en décembre 2026 (produit + une association en bêta) :
  recommander de ne pas lancer un second produit sous licence avant.

### 3.8 Jev (TypeSafe System One) sur le cas réel

Test du 14/10 à 16 h 37, sur le contexte réel de l'investisseur :

- « Quelle commune est la plus adaptée pour toi ? » → **montmorency** (il n'a pas pris
  les meilleurs rendements — Garges 10,21 % et Villiers-le-Bel 9,43 % écartés)
- « Les données suffisent-elles pour décider ? » → **0,06** (non, et il le dit fort)
- « Fiabilité de l'analyse ? » → 0,95 (la primitive `score` renvoie un nombre là où
  quatre niveaux textuels étaient fournis : comportement non conforme au contrat)
- 251 ms, 0,000037 $, modèle jev-1.13.0

Usage réel identifié : **lire les PV des trois dernières assemblées générales de
copropriété**, le cahier des conditions de vente d'une enchère, et trancher l'arbitrage
final entre plusieurs biens. Jev ne calcule pas, ne cherche pas, ne remplace pas la
visite — il n'a pas accès à la santé d'une copropriété, et c'est justement l'angle mort
de toutes les données ouvertes.

---

## 4. Décisions prises / non prises

Prise le 14/10 :
- Le dossier Word a été remis pour mise en forme dans ChatGPT.
- La slide a été remise telle quelle (correction du bandeau coupé + du prix hors marché).
- Le scraping est écarté comme base d'un produit commercial.
- La forme « licence aux particuliers » est écartée ; seule la licence aux professionnels
  tient debout.
- L'achat immobilier est reporté après la sortie de MBA.

Proposé, **pas encore tranché par Ronald** :
- Construire **v0 pour soi** : un script `dvf_lookup.py` (une adresse → les ventes réelles
  de la rue, la médiane au m², les comparables, le verdict sur le prix demandé) et une
  compétence `immobilier-achat` (les 6 étapes, les 3 régimes fiscaux, les limites des
  données). Estimé à une heure, sans risque.
- Sortir la slide en **PPTX éditable**, et/ou en **anglais** pour le camarade de MBA.
- **Surveiller les ventes aux enchères du 95** (canal légal : publication obligatoire) —
  la question n'a pas été tranchée ce jour-là.
- Le test décisif pour le produit : **trois coups de fil à trois chasseurs immobiliers**,
  avec un dossier d'achat complet produit en cinq minutes.

---

## 5. Arborescence

```
projects/immopilot/
├── ETAT_DU_PROJET.md                  ce document
├── transcription_telegram_14oct2026.txt   la conversation source, intégrale
├── livrables/
│   ├── dossier_immobilier_jev.docx     dossier 13 sections / 17 tableaux
│   ├── immo_slide.png                  slide architecture + cash flow
│   └── immo_slide.html                 source de la slide (régénérable)
├── donnees/
│   ├── dvf95_2025.csv                  DVF 2025, Val-d'Oise (39 955 lignes)
│   ├── dvf_ecouen_2025.csv             DVF 2025, Écouen seul
│   ├── loyers_12p_2025.csv             carte des loyers 2025, appartements 1-2 pièces
│   ├── loyers_appartements_2025.csv    idem, tous appartements
│   ├── encheres_judiciaires_2022.xlsx  ventes aux enchères 2022, mise à prix + résultat
│   └── encheres_liste_2006_2024.csv    liste des ventes 2006-2024 (sans prix)
└── scripts/
    └── rendement_95.py                 rejoue les rendements et les prix par rue
```

## 6. Ajout du 14/10 au soir — estimation de la maison d'Écouen

Ronald a demandé la valeur de sa maison, **13 rue Georges Clemenceau, 95440 Écouen**.
Trois scripts et une note de valeur ont été ajoutés :

- `livrables/estimation_maison_ecouen_14oct2026.md` — la note complète (rue, marché
  communal 2021-2025, grille par surface, comparaison des communes voisines).
- `scripts/estimation_ecouen.py` — Écouen par année, par tranche de surface, communes
  voisines.
- `scripts/estimation_clemenceau.py` — la rue elle-même, puis modèle log-log
  surface + terrain sur 211 ventes.
- `scripts/grille_valeur_ecouen.py` — grille de valeur calée sur les seules ventes 2025.
- `donnees/dvf95_2021.csv` … `dvf95_2024.csv` — quatre années de plus, téléchargées
  pour mesurer la tendance.

Résultat central : marché d'Écouen en **baisse de 13 % depuis le pic de 2022**
(3 956 → 3 445 €/m²). Pour 95-105 m² avec 300-400 m² de terrain et un DPE correct :
**320 000 à 335 000 €**, fourchette défendable 260 000 à 395 000 €. La rue n'a que
deux ventes depuis 2021 (2 916 et 4 866 €/m²) — c'est la mesure de l'incertitude
restante tant que surface, terrain, DPE et dépendances ne sont pas connus.

## 7. Reproductibilité — vérifiée le 14/10/2026 à 21 h

`python3 scripts/rendement_95.py` (rendements du 95), `--autour` (communes autour
d'Écouen), `--rue "GROSLAY"` (prix au m² par rue).

Le script reproduit **exactement** Garges-lès-Gonesse (10,21 % / 2 564 €/m² / 15 ventes),
Villiers-le-Bel (9,43 % / 2 727 €/m² / 28), Sarcelles (7,19 % / 3 571 €), Arnouville
(8,03 %), Magny-en-Vexin (7,46 %). Il s'écarte de **1 à 3 % sur quatre communes**
(Sannois, Groslay, Montmorency, Goussainville) : le filtre d'artefacts exact du 14/10
n'a pas été journalisé, celui du script est le suivant — mutation « Vente » d'un
appartement de 15 à 45 m², où le logement représente **au moins 80 %** de la surface
bâtie déclarée, et prix au m² borné entre 500 et 25 000 €. **Les chiffres à citer sont
ceux du script**, pas ceux recopiés de mémoire.

---

## ALPHA CONSTRUITE — 15 octobre 2026

Le moteur et le cockpit personnels sont en service. Ce qui existe, ce qui est vérifié, ce qui reste.

### Ce qui tourne

- `moteur/` — six modules : `donnees`, `analyse`, `fiscalite`, `financement`, `verdict`, `dossier`.
  Aucun calcul n'est délégué à un modèle de langage.
- `python3 -m moteur.bench` — 26/26 : 20 dossiers dont 5 pièges à refuser, 6 contrôles de données.
- `webapp/` — serveur bibliothèque standard (aucune dépendance) et cockpit `cockpit.html`,
  quatre onglets : Décider, Mon marché, Mon foyer, Méthode et limites.
- Service systemd utilisateur `immopilot.service`, actif sur http://100.125.91.40:8770
  (tailnet uniquement), relance automatique. Journaux : `webapp/data/serveur.log`.
- Données de marché générées : `webapp/data/marche.json` — 182 communes, 2 927 voies, 340 Ko.
- Dossier exporté : `livrables/dossier_maison_ecouen_15oct2026.md`.
- Capture du cockpit : `livrables/cockpit_alpha.png`.
- Documentation d'entrée : `README.md`.

### Les quatre corrections de méthode du 15/10

1. Actualisation des comparables par un indice départemental, base 1,0 en 2025.
   Appartements : 2021 x0,980 - 2022 x0,947 - 2023 x0,964 - 2024 x0,997.
   Maisons : x0,949 - x0,900 - x0,926 - x0,993.
   Sans cela, élargir la fenêtre gonfle la médiane : Groslay passait de 3 526 à 4 029 euros/m².
2. Bande de surface stricte (plus ou moins 35 %), jamais élargie : à Écouen, une maison de 100 m²
   attirait des comparables de 40 m² et annonçait 4 320 euros/m² au lieu de 3 285.
3. Dispersion mesurée par l'écart interquartile (Q3 moins Q1) sur la médiane, et non par l'écart-type :
   sur des prix d'actes, l'écart-type est dominé par les ventes atypiques.
4. Contrôle de trésorerie intégré au verdict, et non seulement affiché : le solde mensuel après la
   nouvelle mensualité est un motif de refus au même titre que le prix.

Deux défauts de code découverts par le banc d'essai : la comparaison du prix demandé au prix du bien
(médiane multipliée par la surface) et non à la médiane au m² ; l'amortissement des travaux conservé
chaque année en LMNP alors qu'ils ne sont déduits qu'une fois en location nue.

### Vérification croisée

`scripts/exporte_marche.py` donne Écouen à 3 814 euros/m² et 6,61 % de rendement brut : exactement
les chiffres calibrés à la main le 14/10/2026, par un chemin de code indépendant. La maison d'Écouen
(100 m², 300 m² de terrain) ressort à 328 450 euros par le modèle taille et terrain, quand la note
du 14/10 annonçait 320 000 à 335 000 euros.

### Ce qui reste

- `webapp/data/mon_patrimoine.json` : surface et terrain exacts de la maison, taxe foncière, épargne
  mobilisable, budget de vie détaillé. Sans ces entrées, tout verdict de trésorerie est faux.
- DPE (identifiant du jeu de données ADEME à confirmer), Géoportail urbanisme (partition DU_95205),
  état de copropriété, ventes aux enchères judiciaires : non exploités à ce jour.
- Webapp de suivi de portefeuille (multi-biens, historique daté) : postérieure à l'alpha.
- Fiscalité : mécanique indicative 2026, à faire valider par un expert-comptable
  (réforme LMNP 2025 sur les amortissements et la plus-value).
