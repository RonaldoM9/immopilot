# Revue de l'MVP webapp ImmoPilot (V0.1) — 15 octobre 2026

Revue technique et produit de `immopilot.html` (fichier unique, localStorage, six modules).
Méthode : extraction de la partie calcul du fichier et exécution sous Node 24 avec un banc
d'essai, puis comparaison des données de marché avec les sources recalculées.

Scripts de la revue : `scripts/export_marche_webapp.py`, `/root/_test_immo.js` (banc d'essai JS).

---

## 1. Ce qui est solide — vérifié, pas supposé

- **Les mathématiques de crédit sont justes.** `annuityFactor(3,5 %, 240 mois, 0,30 %/an)`
  renvoie 0,0060496, identique à mon recalcul indépendant : 1 209,92 € par mois pour
  200 000 €. L'amortissement simplifié sur 12 mois donne 7 032 € de capital remboursé,
  conforme au calcul bancaire classique. **Aucune erreur à signaler sur ce poste.**
- **Le prévisionnel 12 mois tombe juste.** Test à 6 000 € de revenus, 4 500 € de budget de
  vie, 120 € de charges mensuelles, 1 400 € de taxe foncière annuelle et 3 200 € de travaux
  ponctuels : cumul 11 960 €, identique au calcul indépendant. L'imputation des dépenses
  annuelles à leur mois d'échéance fonctionne.
- **Les garde-fous de saisie sont là** : assurance supérieure à la mensualité refusée,
  échappement HTML systématique des saisies (pas d'injection), validation de la structure
  d'une sauvegarde importée.
- **L'honnêteté des libellés est remarquable** et doit être conservée : « médiane du dossier,
  non recalculée sur la liste », « le loyer est parfois déduit mathématiquement du rendement
  publié », « les zones non couvertes n'affichent pas de chiffres inventés », la mention
  HCSF, l'avertissement sur le rendement élevé qui peut traduire un risque. C'est exactement
  la posture d'un outil d'aide à la décision.
- **Les données de marché sont fidèles au dossier** : sur 17 communes, **10 reproduisent le
  chiffre au euro près**.

## 2. Le défaut grave — l'outil peut dire « ça passe » à un foyer qui ne peut pas payer

`monthlyBalance()` additionne revenus, loyers, puis retire le budget de vie, les dépenses
récurrentes et les crédits existants. **Elle n'inclut jamais la mensualité du crédit simulé.**
L'alerte « solde négatif » de l'écran Capacité teste donc le solde *actuel*, pas le solde
*après* l'opération.

Démonstration chiffrée (banc d'essai exécuté) :

```
foyer    revenus 6 000 EUR/mois · budget de vie 4 500 EUR · epargne 60 000 EUR · reserve 10 000 EUR
app dit  solde mensuel +1 500 EUR · capital empruntable 347 131 EUR · budget 367 713 EUR
achat teste    bien a 350 000 EUR -> cout 378 000 EUR -> mensualite 2 100 EUR
realite        solde mensuel APRES credit = -600 EUR/mois
app            aucune alerte · le module marche repond "entre dans ton enveloppe"
```

C'est précisément le mode de défaillance identifié le 14/10 : **un outil qui valide la
décision déjà prise.** Correction : trois lignes. Soustraire la mensualité simulée dans le
contrôle de solde, et refuser (ou avertir sans ambiguïté) dès que le solde devient négatif.

## 3. Écouen casse la comparaison

L'application affiche Écouen à **2 687 €/m²** (appartements, toutes surfaces, 51 ventes) à
côté de Sannois 3 741, Groslay 3 526 ou Sarcelles 3 570 — qui sont, eux, sur le périmètre
15-45 m². Conclusion naturelle du lecteur : Écouen est bien moins cher.

**Sur le même périmètre, Écouen est à 3 814 €/m² (6,61 %)** — plus cher que Sannois.
L'écart de périmètre est de 1 127 €/m², soit 29 % de sous-estimation. La note de bas d'écran
l'explique, mais une ligne non comparable au milieu d'un classement de rendements reste un
piège. Correction : remplacer par le chiffre de même périmètre, ou exclure la ligne du
classement.

## 4. Six communes dérivent de 1 à 132 €/m²

| commune | app | recalculé | écart prix | écart rendement |
|---|---|---|---|---|
| Garges-lès-Gonesse | 2 564 / 10,21 % | 2 564 / 10,21 % | 0 | 0 |
| Villiers-le-Bel | 2 727 / 9,43 % | 2 727 / 9,43 % | 0 | 0 |
| Goussainville | 3 101 / 8,34 % | 3 095 / 8,36 % | −6 € | +0,02 pt |
| Arnouville | 3 178 / 8,03 % | 3 179 / 8,03 % | +1 € | 0 |
| Magny-en-Vexin | 2 666 / 7,46 % | 2 667 / 7,46 % | +1 € | 0 |
| Gonesse | 3 436 / 7,30 % | 3 438 / 7,30 % | +2 € | 0 |
| **Sannois** | 3 741 / 7,38 % | 3 824 / 7,22 % | **+83 €** | −0,16 pt |
| Sarcelles | 3 570 / 7,19 % | 3 571 / 7,19 % | +1 € | 0 |
| **Groslay** | 3 526 / 7,23 % | 3 571 / 7,14 % | **+45 €** | −0,09 pt |
| **Montmorency** | 3 929 / 7,17 % | 4 027 / 7,00 % | **+98 €** | −0,17 pt |
| **Montmagny** | 3 866 / 7,05 % | 3 998 / 6,82 % | **+132 €** | −0,23 pt |
| **Argenteuil** | 3 896 / 6,84 % | 3 913 / 6,81 % | +17 € | −0,03 pt |
| Saint-Gratien | 4 272 / 6,79 % | 4 273 / 6,79 % | +1 € | 0 |
| **Soisy-sous-Montmorency** | 3 906 / 6,80 % | 3 953 / 6,72 % | +47 € | −0,08 pt |
| Franconville | 3 934 / 6,54 % | 3 935 / 6,54 % | +1 € | 0 |
| Enghien-les-Bains | 5 258 / 5,42 % | 5 258 / 5,42 % | 0 | 0 |

Cause : le filtre d'artefacts du 14/10 (part des surfaces déclarées, bornes de prix) n'avait
pas été journalisé. Le filtre retenu, désormais écrit dans le script, est : mutation de type
Vente, appartement, surface 15-45 m² représentant au moins 80 % de la surface bâtie
déclarée, prix au m² entre 500 et 25 000 €, au moins 5 ventes par commune.

## 5. Un correctif livré avec cette revue

`livrables/marche_95_2025.js` — le bloc `MARKET` régénéré depuis les données :

- **57 communes au lieu de 17**, toutes sur le même périmètre 15-45 m².
- Rendement brut médian départemental : **6,54 %**.
- Champs identiques à l'existant (`n, p, r, y, s, o`) : remplacement direct, aucune
  modification de code nécessaire.
- Objet `MARKET_META` ajouté : source, date de génération, périmètre, médiane du
  département, nombre de communes — pour que l'écran puisse afficher ses propres
  conditions de validité.
- Version JSON équivalente : `livrables/marche_95_2025.json`.
- 46 communes écartées, avec le motif en clair dans le script (moins de 5 ventes, ou
  loyer non publié par le ministère) : c'est ce qui évite d'afficher un chiffre inventé.

## 6. Ce qui manque, par ordre d'importance

1. **Le verdict et le refus.** L'application affiche des rendements et une simulation, mais
   elle ne dit jamais non et n'a aucune règle de refus. Un outil d'aide à la décision sans
   capacité de refus devient une machine à confirmer.
2. **La rue.** Le module s'arrête à la commune, alors que toute l'analyse du 14/10 montrait
   que la décision se joue **dans la rue** : à Écouen, un facteur 1,7 entre deux maisons de
   la même rue en 2021. C'est l'écart le plus important avec le moteur.
3. **La fiscalité.** Sans les trois régimes, il n'y a pas de cash-flow après impôt — « la
   seule ligne qui compte ». Le déficit foncier est le levier qui peut changer le signe d'une
   opération.
4. **Le DPE et la santé de la copropriété.** Angles morts assumés des données ouvertes, à
   couvrir par la lecture des documents (PV d'AG, cahier des conditions de vente).

Détails à corriger au passage :

- L'« indice d'endettement indicatif » affiche le taux **actuel**, pas celui d'après le
  nouvel emprunt : le libellé est trompeur, la valeur est juste.
- Le README demande d'exclure les dépenses déjà saisies du budget de vie : une erreur de
  saisie ici fausse tout le diagnostic sans aucun signal.
- Une sauvegarde JSON sort en clair et contient tout le patrimoine : à mentionner, ou à
  chiffrer.

## 7. Verdict

**Comme cockpit, c'est du bon travail** : lisible, honnête, sans chiffre inventé, et le
calcul de crédit est exact. **Comme outil de décision, il lui manque la seule chose qui
compte : le refus.** Et comme produit, il lui manque le moteur — le module marché est un
extrait figé, pas une source qui se met à jour.

Trois corrections, dans cet ordre :

1. Coller le `MARKET` régénéré (57 communes, même périmètre) : cinq minutes, zéro code.
2. Ajouter le contrôle de trésorerie après crédit et le verdict à trois états
   (`ACHETER` / `NÉGOCIER À …` / `NON`) avec les règles de refus.
3. Brancher l'application sur le moteur (rue, effet taille et terrain, fiscalité) au lieu
   d'une liste figée : c'est la marche qui transforme une maquette en outil.
