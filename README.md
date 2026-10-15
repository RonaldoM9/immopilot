# ImmoPilot — alpha personnelle

Un outil d'aide à la décision en investissement immobilier, pour un seul utilisateur :
Ronald, sa maison d'Écouen et ses futurs investissements dans le Val-d'Oise.

**Le principe qui tient tout : le modèle de langage ne calcule rien.** Tous les chiffres —
médianes, quartiles, rendements, cash-flows, mensualités, impôts — sortent de ce paquet Python,
déterministe et testé. Une conversation peut mettre les chiffres en mots ; elle ne les produit pas.

---

## 1. Démarrage

```bash
# les données (elles ne sont pas dans le dépôt) : 95 seul, ou l'Île-de-France complète
cd /root/projects/immopilot
python3 scripts/telecharge_donnees.py
python3 scripts/telecharge_donnees.py --departements 75,77,78,91,92,93,94,95

# le moteur, en ligne de commande
python3 -m moteur.bench                                   # banc d'essai : 26/26 attendu
python3 -m moteur.dossier --commune Groslay --surface 30 --prix 110000 --loyer 637
python3 -m moteur.dossier --commune "Paris 11e" --surface 35 --prix 350000 --loyer 1400
python3 -m moteur.dossier --commune Écouen --type Maison --surface 100 --terrain 300 \
        --prix 330000 --loyer 1400 --md                   # le dossier en texte, prêt à coller

# le cockpit (service systemd utilisateur, déjà actif)
systemctl --user status immopilot.service
systemctl --user restart immopilot.service                # après toute modification du moteur
# → http://100.125.91.40:8770   (réseau tailnet uniquement, aucune exposition publique)

# régénérer les données de marché servies à la webapp et au site publié
python3 scripts/exporte_marche.py                         # tous les départements chargés
python3 scripts/generer_site_statique.py                  # docs/index.html (GitHub Pages)
```

Réglages par variables d'environnement : `IMMOPILOT_HOST`, `IMMOPILOT_PORT`, `IMMOPILOT_PREFIXE`.

---

## 2. Le moteur — six modules

| Module | Rôle |
|---|---|
| `moteur/donnees.py` | lecture des actes DVF, filtres, indice annuel, cache |
| `moteur/analyse.py` | comparables de rue et de commune, valeur, loyer, rendement |
| `moteur/fiscalite.py` | quatre régimes comparés, projection sur dix ans |
| `moteur/financement.py` | mensualité, capacité d'emprunt, **contrôle de trésorerie** |
| `moteur/verdict.py` | les règles de décision, la confiance, les motifs de refus |
| `moteur/dossier.py` | assemblage du dossier, CLI, rendu texte |

Un dossier complet prend **150 ms**, interface comprise — hors premier chargement des données.

## 2 bis. Le périmètre de données

Un fichier DVF par département et par millésime : le moteur ne suppose plus le 95 en dur. Il
travaille sur tous les départements présents dans `donnees/`, et chaque prix est actualisé avec
**l'indice de son propre département** — le Val-d'Oise a perdu 13 % de son prix au m² depuis 2022,
l'Île-de-France dans son ensemble moins. Chargés à ce jour : **75, 77, 78, 91, 92, 93, 94, 95**.

Un nom de commune peut exister dans deux départements. `analyse.resout_commune` retient celle qui
compte le plus de ventes et **signale l'homonymie** ; un code INSEE lève toute ambiguïté. Deux
marchés ne sont jamais mélangés dans une même médiane.

Pour étendre : `python3 scripts/telecharge_donnees.py --departements 27,60,76`, puis relancer
l'export et la génération du site. Comptez 1,4 Mo compressé et 6 à 10 Mo décompressé par
département et par millésime.

## 3. Méthode — ce qui a été appris le 15/10/2026

Ces quatre points ne sont pas des détails : chacun a été mesuré, chiffré, puis corrigé.

1. **Actualiser les prix anciens.** Le 95 a perdu 13 % de son prix au m² entre 2022 et 2025.
   Mélanger cinq ans gonfle la médiane (Groslay passait de 3 526 à 4 029 €/m²). Les comparables
   sont donc ramenés au niveau 2025 par un indice départemental, et la fenêtre de référence
   est de trois ans.
2. **Une bande de surface stricte, jamais élargie.** À Écouen, élargir autour d'une maison de
   100 m² fait entrer des maisons de 40 m² dont le prix au m² vaut le double : la médiane
   annonçait 4 320 €/m² au lieu de 3 285. Quand le périmètre est trop mince, on élargit le
   **temps**, puis on passe au **modèle taille + terrain** — jamais la surface.
3. **L'écart interquartile, pas l'écart-type.** Sur des prix d'actes, l'écart-type est dominé
   par quelques ventes atypiques (bien dégradé, vente en bloc) et fait passer un marché normal
   pour chaotique. La dispersion affichée est (Q3 − Q1) / médiane.
4. **Le contrôle de trésorerie.** La maquette du 15/10 validait un achat à 350 000 € pour un
   foyer à +1 500 €/mois, alors que le solde réel tombait à −600 €/mois : la mensualité
   n'entrait dans aucun calcul. Toute décision passe désormais par le solde mensuel **après**
   la nouvelle mensualité.

Vérification croisée : l'export de marché donne Écouen à **3 814 €/m² et 6,61 % de rendement
brut** — exactement les chiffres calibrés à la main le 14/10/2026, par un autre chemin de code.

## 4. Les règles de refus

Le moteur refuse de trancher (`INDÉTERMINÉ`) ou refuse l'opération (`NON`). Refuser est une
réponse, pas un échec.

- moins de **5 ventes** comparables → refus de trancher ;
- écart interquartile **> 45 %** ou confiance **< 0,45** → refus de trancher ;
- prix demandé **> 15 %** au-dessus du marché du périmètre, à surface comparable → NON ;
- cash-flow après impôt **négatif en moyenne sur dix ans** → NON ;
- solde mensuel du foyer **négatif après la mensualité** → NON ;
- entre +5 % et +15 % au-dessus du marché → NÉGOCIER, avec un prix cible chiffré.

## 5. Le banc d'essai — `python3 -m moteur.bench`

20 dossiers et 6 contrôles de données. Les cinq pièges doivent être refusés :

| Piège | Ce qu'il teste |
|---|---|
| budget de vie supérieur aux revenus | trésorerie |
| achat financé à 100 % | cash-flow |
| prix 30 % au-dessus du marché | prix du périmètre |
| commune à une seule vente (Le Heaulme) | refus de trancher |
| échantillon hétérogène (Bruyères-sur-Oise) | confiance |

Les prix des cas « dans le marché » sont **calculés par le moteur lui-même**, pas codés en dur :
le banc reste valide quand les données DVF sont mises à jour.

## 6. Le cockpit — quatre onglets

- **Décider** — un bien, un prix demandé → verdict, comparables ouverts, fiscalité sur dix ans,
  mensualité, solde du foyer, et un bouton *Copier le dossier (markdown)*.
- **Mon marché** — 182 communes, 2 927 voies, rendement brut, tri et filtre. Chaque médiane dit
  sur combien de ventes elle repose.
- **Mon foyer** — biens, crédits, dépenses, revenus, épargne. Le disponible mensuel réel, taux
  d'endettement, patrimoine net. **À compléter par Ronald : c'est la seule entrée que le moteur
  ne peut pas deviner.**
- **Méthode & limites** — les règles, les sources, et ce que l'outil n'est pas.

## 7. API (stdlib, aucune dépendance externe)

```
GET  /                  cockpit
GET  /api/sante         version du moteur, état du banc d'essai
GET  /api/marche        communes + voies (données précalculées)
GET  /api/patrimoine    biens, crédits, dépenses
GET  /api/foyer         synthèse du foyer + capacité d'emprunt
POST /api/patrimoine    enregistre le patrimoine
POST /api/dossier       construit un dossier et rend le verdict
POST /api/dossier.md    le même dossier, en texte
```

## 8. Limites — à lire avant de décider

- **Pas un conseil fiscal.** Mécanique indicative 2026 ; la réforme LMNP de 2025 réintroduit les
  amortissements dans la plus-value à la revente. À valider par un expert-comptable.
- **Pas un avis d'expert.** DVF = prix d'acte, hors état réel du bien.
- Ni DPE, ni état de copropriété, ni travaux votés, ni servitudes, ni bruit : à vérifier sur place.
- Le montant des travaux et le loyer retenu sont **des hypothèses saisies**, pas des mesures.
- Pas d'annonces : le scraping d'annonces est illégal (Jinka, 200 000 € en 2026). Le seul flux
  d'annonces légal — les ventes aux enchères judiciaires — n'est pas encore exploité.

## 9. Sources

- **DVF Etalab** — demandes de valeurs foncières, fichiers 2021 à 2025, Val-d'Oise.
- **Carte des loyers** — ministère chargé du Logement, loyers d'annonce par commune.
- Aucune donnée personnelle bancaire : le patrimoine est saisi à la main.

## 10. Arborescence

```
immopilot/
├── moteur/                  le moteur (6 modules) + banc d'essai
├── scripts/                 export du marché, générateurs de diagrammes
├── webapp/
│   ├── server.py            serveur stdlib + API
│   ├── cockpit.html         l'interface (aucun calcul dans la page)
│   └── data/
│       ├── marche.json      communes et voies (généré)
│       └── mon_patrimoine.json  biens, crédits, dépenses (édité)
├── donnees/                 fichiers sources DVF et loyers
└── livrables/               notes, diagrammes, dossiers exportés
```

---

*Alpha du 15 octobre 2026. Ce qui est construit ici — le moteur, le banc d'essai, le format de
dossier, les données — est exactement ce que le produit vendra aux professionnels sous licence.
L'alpha, c'est le moteur du produit avec un seul utilisateur.*
