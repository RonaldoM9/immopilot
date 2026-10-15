# Immopilot — architecture de l'agent d'investissement immobilier

Note de conception, **15 octobre 2026**. Elle prolonge le dossier du 14/10 (analyse DVF,
loi Hoguet, forme produit) et l'atelier du même soir (scripts de rendement et d'estimation,
qui tournent déjà dans `/root/projects/immopilot/`).

---

## 0. Les trois contraintes qui déterminent l'architecture

Toute la conception découle de trois faits établis la veille. Les ignorer, c'est construire
quelque chose d'illégal, d'inutile ou de dangereux.

1. **Loi Hoguet (art. 14, loi du 02/01/1970)** — « prêter son concours, même à titre
   accessoire » à une opération immobilière sans carte professionnelle est puni de six mois
   et 7 500 €. Donc : **le client agit, le logiciel assiste.** Jamais de recherche *pour*
   lui, jamais de démarche *à sa place*.
2. **Les annonces ne se récupèrent pas.** Portails fermés (DataDome), jurisprudence Jinka
   (CA Versailles, 14/04/2026, 200 000 €), droit sui generis L341-1 CPI. Donc :
   **l'annonce entre par le client** — il colle le lien ou le texte. Les seuls flux
   d'annonces légitimes sont les enchères (annonce légale, publication obligatoire) et les
   notaires.
3. **L'outil doit pouvoir dire non.** Un outil incapable de rejeter une opération valide
   mécaniquement les décisions déjà prises. Le verdict doit être **structuré**, avec un
   seuil de refus explicite et un indice de confiance.

---

## 1. Vue d'ensemble — six briques

```
   ┌──────────────────────────────────────────────────────────────────┐
   │  1. SOURCES            données ouvertes + documents du client    │
   ├──────────────────────────────────────────────────────────────────┤
   │  2. MOTEUR             calcul déterministe, en code, jamais par   │
   │                        le modèle de langage                       │
   ├──────────────────────────────────────────────────────────────────┤
   │  3. LECTURE            PV d'AG, cahiers des conditions de vente,  │
   │     DE DOCUMENTS       règlement de copropriété  ->  Jev          │
   ├──────────────────────────────────────────────────────────────────┤
   │  4. ORCHESTRATION      compétence + scripts dans le harnais       │
   ├──────────────────────────────────────────────────────────────────┤
   │  5. LIVRAISON          dossier PDF, tableur de suivi, alertes,    │
   │                        puis app privée multi-clients              │
   ├──────────────────────────────────────────────────────────────────┤
   │  6. TRANSVERSE         conformité, versionnage, journal d'audit   │
   └──────────────────────────────────────────────────────────────────┘
```

**Décision fondatrice : deux architectures en une.** Le **moteur (brique 2)** est commun.
Au-dessus de lui, deux enveloppes : la version personnelle (compétence + scripts dans le
harnais Hermes existant, décision du 14/10) et la version produit (application privée
auto-hébergée multi-clients, vendue sous licence). On ne développe pas deux fois le même
calcul.

---

## 2. Brique 1 — Sources : état réel, testé les 14 et 15 octobre 2026

### 2.1 Données ouvertes, vérifiées en direct

- **DVF** — `files.data.gouv.fr/geo-dvf/latest/csv/<année>/departements/<dep>.csv.gz`
  Réponse 302 puis 200, 39 955 lignes pour le Val-d'Oise en 2025, 54 159 en 2021.
  Colonnes utiles : `id_mutation`, `valeur_fonciere`, `type_local`,
  `surface_reelle_bati`, `surface_terrain`, `adresse_nom_voie`, `latitude`, `longitude`.
  **C'est la source de prix, et elle donne des prix signés, pas des prix demandés.**
- **Carte des loyers (ministère)** — 183 communes du 95 renseignées en loyers 1-2 pièces,
  avec intervalle de confiance et **nombre d'observations par commune**. Millésime 2025.
  Attention à l'encodage du fichier : latin-1, séparateur `;`, décimale à la virgule.
- **Cadastre IGN / API Carto** — `apicarto.ign.fr/api/cadastre/parcelle?code_insee=...`
  **Testé : HTTP 200**, parcelles et contenances.
- **Base Adresse Nationale** — `api-adresse.data.gouv.fr/search/?q=...`
  **Testé : HTTP 200**, géocodage et code INSEE.
- **Géoportail de l'urbanisme (GPU)** — `apicarto.ign.fr/api/gpu/zone-urba`
  **Testé : HTTP 400 avec `?insee=`** — l'API exige un paramètre **`geom`** (géométrie) ou
  **`partition`** (ex. `DU_95205`). À corriger dans les scripts : c'est l'erreur classique
  qui fait croire que la source est fermée alors qu'elle attend un autre paramètre.
- **DPE / ADEME** — l'API data-fair existe, mais mon premier identifiant de jeu de données
  a renvoyé 404 : **le bon slug reste à confirmer** avant de l'intégrer.
- **Open data des ventes aux enchères judiciaires** (data.gouv) — 3 762 ventes pour 2022,
  colonnes `Vente_Mise_a_prix` et `Resultat_Prix`. 73 % adjugées, écart médian entre mise
  à prix et adjudication **×2,04**. C'est un flux d'annonces **légal**, et personne ne
  l'exploite.
- **immobilier.notaires.fr** — HTTP 200, sitemap publié, annonces notariales et ventes aux
  enchères des notaires.

### 2.2 Sources fermées, à ne pas retenter

Portails d'annonces (SeLoger, Leboncoin, Bien'ici) : aucune API, protection anti-robot,
CGU explicites. `encheres-publiques.com` et `interencheres.com` : défis Cloudflare (403),
donc bloqués à un client HTTP simple — un vrai navigateur passe, mais cela reste du
contournement. `licitor.com` : listes vendues par abonnement.

### 2.3 Documents fournis par le client

C'est la couche qui fait la valeur, et elle est **juridiquement propre** : le client
fournit ce qu'il possède déjà — annonce, PV des trois dernières assemblées générales,
cahier des conditions de vente (enchères), règlement de copropriété, état des charges,
carnet d'entretien, DPE du bien. Aucune extraction, aucun scraping.

---

## 3. Brique 2 — Le moteur : du calcul, jamais des probabilités

**Règle absolue : le modèle de langage ne calcule rien.** Les rendements, médianes,
quartiles et cash-flows sont calculés en code, exactement, puis relus par le modèle.

Fonctions du moteur, chacune avec sa sortie structurée :

- **Comparables de rue** — médiane €/m², dispersion, nombre de ventes, filtre d'artefacts
  (une mutation où le logement ne représente qu'une fraction de la surface déclarée fausse
  le prix au m² d'un facteur deux : c'est l'erreur qui a produit « Eaubonne à 1 022 €/m² »
  le 14/10, attrapée par un contrôle de vraisemblance départemental — **ce contrôle est une
  fonction permanente du moteur, pas un rattrapage ponctuel**).
- **Effet taille et terrain** — modèle log-log, avec **intervalle de confiance**. Sur les
  36 ventes 2025 d'Écouen : écart-type résiduel de 21 %. Le moteur doit rendre cet écart,
  pas seulement un chiffre.
- **Simulation locative** — nu, meublé, par lots ; loyer de référence de la commune et son
  nombre d'observations ; zone tendue ou encadrée.
- **Fiscalité** — les trois régimes côte à côte, déficit foncier, amortissement,
  prélèvements sociaux, puis **cash-flow après impôt : la seule ligne qui décide**.
- **Constructibilité** — ce que le PLU autorise : extension, division, dépendance.
  Sur Écouen, exemple réel : la commune abrite un château (Musée national de la
  Renaissance) — les **périmètres de protection des monuments historiques** s'appliquent,
  donc avis de l'ABF et contraintes réelles. Aucun modèle ne le devine : il faut l'aller
  chercher dans le GPU et les servitudes d'utilité publique.
- **Décision** — un verdict énuméré : `ACHETER` / `NÉGOCIER À <prix>` / `NON`, avec la
  raison chiffrée et l'indice de confiance. Règle de refus : moins de 5 comparables, ou
  dispersion supérieure à 30 %, ou cash-flow négatif après impôt, ou prix demandé au-dessus
  du marché de la rue → **NON**.

---

## 4. Brique 3 — Jev : la lecture des documents que personne ne lit

Jev (TypeSafe System One) traite des **questions bornées** sur un texte : réponses
énumérables d'avance, aucun calcul, volume qui justifie l'appel. C'est exactement le profil
des documents que l'on ne lit pas — et son comportement mesuré le 14/10 est le bon :

- « Quelle commune est la plus adaptée ? » → il a répondu `montmorency`, **pas** le meilleur
  rendement (Garges, 10,21 %, écarté), parce que le texte signalait que la santé des
  copropriétés était inconnue.
- « Les données suffisent-elles pour décider ? » → **0,06**. Réponse nette : non.
- Coût : 251 ms, 0,000037 $. Négligeable.

Usage prévu, document par document :

- **PV des trois dernières AG** : des travaux ont-ils été votés et non réalisés ? existe-t-il
  un impayé de copropriétaire ? un DTG a-t-il été voté ? la copropriété est-elle en
  procédure ? → **c'est l'angle mort absolu des données ouvertes.**
- **Cahier des conditions de vente** (enchères, 50 à 100 pages) : conditions suspensives,
  occupation, charges impayées.
- **Arbitrage final** entre plusieurs biens : les mêmes critères, un seul appel.

**Deux précautions** : 24 % de faux positifs ont été mesurés sur un usage de type
portillon ; la primitive `score` a renvoyé un nombre là où quatre niveaux textuels étaient
fournis. Donc Jev n'est jamais un juge unique — ses réponses alimentent le verdict, elles
ne le remplacent pas.

---

## 5. Brique 4 — Orchestration : une compétence et des scripts, pas un second agent

Décision du 14/10, maintenue : **un agent séparé serait de la cérémonie.** Deuxième mémoire
à nourrir, deuxième surface à maintenir, aucun gain.

- **Compétence `immobilier-achat`** — la méthode : les étapes, les trois régimes fiscaux, la
  liste des sources ouvertes et de leurs limites, les règles de refus.
- **Scripts, un par question** — `recherche_bien.py` (adresse + prix → verdict),
  `rendement_95.py`, `estimation_commune.py`, `documents.py` (appel Jev), `encheres.py`
  (surveillance du canal légal).
- **Le modèle orchestre** : il choisit l'outil, interprète, rédige le dossier, et refuse de
  conclure quand le moteur dit que la donnée est insuffisante.

---

## 6. Brique 5 — Livraison, en trois étages

1. **Aujourd'hui** — conversation (Discord/Telegram) + dossier PDF par bien + note de
   valeur. C'est ce qui existe déjà, et c'est ce qui sert.
2. **Version produit** — application privée auto-hébergée, sur le patron déjà éprouvé de
   Foyer : écoute sur la boucle locale ou le tailnet, aucun port public, SQLite, un seul
   compte, sortie réseau confinée. Le professionnel y colle son annonce et reçoit son
   dossier. **Multi-clients : un espace par client, cloisonné, jamais de mélange.**
3. **Dernier étage, pas le premier** — une API ou un serveur MCP exposé aux outils que le
   professionnel utilise déjà (CRM, tableur). À construire quand trois clients l'auront
   demandé, pas avant.

---

## 7. Brique 6 — Transverse : conformité, versionnage, audit

- **Versionner les données et les modèles** : millésime DVF, millésime des loyers, version
  du modèle d'estimation. Sans cela, deux analyses du même bien donnent deux chiffres sans
  qu'on sache pourquoi — c'est exactement ce qui s'est produit le 14/10 entre mes chiffres
  de l'après-midi et ceux du soir.
- **Journaliser chaque verdict** : bien, comparables utilisés, filtres appliqués, seuils,
  version du moteur. Un dossier doit être rejouable ligne à ligne.
- **Séparer l'aide à la décision du conseil** : mentions explicites que la sortie n'est pas
  un conseil en investissement personnalisé.
- **Ne rien conserver de tiers** : pas d'annonces de portails en base, documents du client
  chiffrés, purge à la demande.

---

## 8. Ce qui est déjà construit et se réutilise

- `/root/projects/immopilot/` — cinq années de DVF (2021-2025), carte des loyers 2025,
  open data des enchères, et **quatre scripts qui tournent et reproduisent les chiffres**.
- **Jev** — serveur MCP local, compétence, et un portillon déjà éprouvé sur les appels
  d'outils.
- **Foyer** — le patron complet d'une application privée auto-hébergée, déjà sécurisée.
- **Le harnais** — Discord/Telegram, cron pour les alertes, PDF, markdown.

Rien de tout cela n'est à refaire. C'est la différence entre concevoir et démarrer de zéro.

---

## 9. Découpage réaliste

- **J1 — une semaine.** Compétence `immobilier-achat` + trois scripts consolidés + sortie
  PDF. Utilisable par Ronald sur un vrai dossier, sans interface.
- **J2 — deux à quatre semaines.** Lecture des documents par Jev (PV d'AG, cahier des
  conditions de vente), tableur de suivi, **alerte cron sur les enchères du secteur**
  (le seul canal d'annonces ouvert), et le parseur DPE/ADEME une fois le bon identifiant
  confirmé.
- **J3 — le produit.** App privée multi-clients, dossier client, et **trois chasseurs
  immobiliers en test** — le test qui vaut 200 € par mois se fait en trois coups de fil,
  pas en trois mois de développement.

---

## 10. Ce qui fera échouer ce projet, si on ne le dit pas maintenant

1. **Le loyer est la donnée la plus faible.** Les prix de vente sont exacts et ouverts ;
   les loyers du parc privé ne le sont pas. Toute la fiscalité repose dessus : le moteur
   doit afficher le loyer comme une hypothèse, jamais comme un fait.
2. **L'état du bâti est invisible.** Aucune donnée ouverte ne dit un toit mort, une
   infiltration, une structure fatiguée. Cela reste une visite.
3. **La santé d'une copropriété est invisible** — et c'est précisément là que Jev sert,
   parce qu'il lit les documents qui, eux, en parlent.
4. **La dispersion locale est énorme.** Dans la même rue, deux maisons comparables peuvent
   s'échanger avec un facteur 1,7 (Écouen, 2021 : deux maisons de la même rue). Un outil qui rend
   un chiffre unique sans intervalle ment, même quand son calcul est juste.
