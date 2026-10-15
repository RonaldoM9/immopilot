# ImmoPilot Alpha — architecture personnelle

Note du **15 octobre 2026**. Elle répond à une question précise : **qu'est-ce qu'une alpha
pour Ronald seul**, pour gérer son bien d'Écouen et préparer ses futurs investissements —
sans construire le produit, et sans refaire ce qui existe déjà.

À lire avec `ARCHITECTURE.md` (le métier) et `ARCHITECTURE_AGENT.md` (l'ingénierie).

---

## 0. Le principe : la plus petite architecture qui rend la bonne réponse

Une alpha personnelle n'a pas les contraintes d'un produit. Pas de multi-clients, pas
d'authentification, pas de facturation, pas de haute disponibilité. **Ce qu'elle doit avoir,
et rien d'autre :**

- le moteur juste (comparables, fiscalité, financement, verdict) ;
- une source de vérité par donnée, sans recopie manuelle ;
- trois portes d'entrée qu'on utilise déjà : Discord, une page web, le cron ;
- un banc d'essai, sinon les erreurs de calcul reviennent sans prévenir.

**Ce que l'alpha n'inclut pas volontairement** : Postgres, Redis, Docker, workflow durable,
base vectorielle, comptes utilisateurs. Toute cette mécanique n'existe que pour servir un
second utilisateur, ou pour survivre à une charge. Il n'y en a pas.

---

## 1. Vue d'ensemble

```
PORTES D'ENTREE          Discord (ce fil) · Webapp cockpit · CLI et cron
                                  |
                                  v
MOTEUR (Python)          comparables · valeur · locatif · fiscalite · financement · VERDICT
                                  |
                                  v
DONNEES                  DuckDB/Parquet (DVF, loyers, caches) + mon_patrimoine.yaml
                         + dossiers/ (un fichier par bien etudie) + Foyer (budget reel)
                                  |
                                  v
VEILLE (cron)            nouveaux DVF -> reevaluation · encheres du 95 · echeances
```

Une seule flèche dans les deux sens : **l'agent ne calcule pas, il appelle le moteur ; le
moteur ne rédige pas, il rend un verdict structuré que l'agent met en mots.**

## 2. Portes d'entrée — les trois qu'utilise déjà Ronald

1. **Discord (ce fil).** Poser la question en langage naturel : « ce bien à Sannois à
   118 000 €, je le prends ? ». L'agent appelle le moteur et rend le dossier.
2. **La webapp cockpit.** Celle qui existe déjà, mais **alimentée par un fichier généré**
   (`make webapp` remplace le bloc `MARKET` et les fiches de biens). Elle ne détient plus de
   données figées, et gagne la rue, la fiscalité et le verdict.
3. **CLI et cron.** Pour tout ce qui ne doit pas dépendre d'une conversation : la veille
   mensuelle, les alertes de seuil, la réévaluation annuelle.

## 3. Le moteur — un paquet Python, six modules

`projects/immopilot/moteur/` — aucune dépendance réseau, testable seul.

1. **`comparables_rue.py`** — ventes signées de la rue, médiane au m², dispersion, nombre de
   ventes, contrôle de vraisemblance départemental. *Déjà écrit, à consolider* (le filtre
   d'artefacts est désormais documenté : 15-45 m², ≥ 80 % de la surface déclarée, bornes de
   prix, ≥ 5 ventes).
2. **`valeur.py`** — effet taille et terrain (modèle log-log), intervalle de confiance,
   grille par surface. *Déjà écrit pour Écouen et le 95.*
3. **`locatif.py`** — loyer de référence, nombre d'observations, nu / meublé / par lots.
   *À écrire : deux heures.*
4. **`fiscalite.py`** — les trois régimes côte à côte, déficit foncier, amortissement,
   prélèvements sociaux, **cash-flow après impôt**. *À écrire : c'est le module qui manque
   le plus, et celui qui change le signe d'une opération.*
5. **`financement.py`** — capacité à 35 %, capital empruntable, apport, et surtout **le
   contrôle de trésorerie après nouveau crédit** (le défaut trouvé dans la maquette).
   *La formule de crédit est déjà validée : 0,0060496 de coefficient, vérifié.*
6. **`verdict.py`** — les règles de refus, le verdict à trois états
   (`ACHETER` / `NÉGOCIER À …` / `NON`), l'indice de confiance. *À écrire : une soirée, et
   c'est la pièce sans laquelle le reste ne sert à rien.*

## 4. Les données — une source de vérité par donnée

```
donnees/dvf95_2021..2025.parquet      prix signes, versionnes par millesime
donnees/loyers_2025.parquet           loyers d'annonce + nombre d'observations
donnees/cache/                        cadastre, PLU, DPE : reponses mises en cache
mon_patrimoine.yaml                   mes biens, credits, charges, objectifs
dossiers/2026-10-15-sannois-t3.md     un dossier par bien etudie : verdict + donnees
```

- **DuckDB** interroge les Parquet : analytique local, aucun serveur, et les mêmes fichiers
  serviront au produit.
- **`mon_patrimoine.yaml`** est le fichier qu'on édite à la main : la maison, les crédits,
  les charges réelles. Il alimente le module de financement et la webapp.
- **`dossiers/`** est la mémoire de la décision : ce qui a été étudié, avec quel verdict et
  quelles données. C'est ce qu'une conversation ne laisse pas derrière elle.
- **Foyer** reste la source du budget réel (relevés importés). Le moteur lit ses agrégats,
  il ne les recalcule pas.

## 5. La veille — cron, trois tâches utiles

1. **Mensuelle : nouveaux DVF.** Les ventes de la rue et de la commune sont réextraites, la
   valeur du bien est réévaluée, et une alerte tombe si l'écart dépasse 5 %.
2. **Hebdomadaire : enchères du secteur.** Le seul canal d'annonces légal — publication
   obligatoire, mise à prix et résultat en open data. Personne ne le surveille.
3. **Trimestrielle : échéances.** Taxe foncière, assemblée générale de copropriété, PNO,
   travaux votés.

## 6. Le banc d'essai — la pièce qui évite de se mentir

Vingt dossiers de référence, dont **cinq pièges** (une opération qui doit être refusée), et
un test qui échoue si le moteur valide un piège. Point de départ, déjà à disposition :

- la maison d'Écouen : cohérence de la valeur ;
- les communes du dossier du 14/10 : Garges, Villiers-le-Bel, Sannois, Groslay ;
- Écouen, rue des comparables 2021 : 2 916 et 4 866 €/m² — le cas de dispersion forte ;
- un bien dont le coût dépasse la capacité après contrôle de trésorerie → **NON** ;
- un bien correct dont le prix demandé est 12 % au-dessus du marché de la rue → **NÉGOCIER**.

## 7. Sécurité et cadre — simples, parce qu'il n'y a qu'un utilisateur

- Tout sur le VPS, accessible par le tailnet ; aucune exposition publique.
- Aucun identifiant bancaire stocké : la connexion bancaire reste hors périmètre (voir
  `../foyer/CONNEXION_BANCAIRE.md`).
- Aucun scraping : les annonces entrent collées à la main, ou par le canal des enchères.
- Sauvegarde chiffrée du dossier `donnees/` et de `mon_patrimoine.yaml`.
- La sortie n'est pas un conseil en investissement : c'est un chiffrage sur des prix
  d'actes publics.

## 8. Ce qui existe déjà, et ce qu'il reste à écrire

**Existe et fonctionne** : DVF 2021-2025 (cinq ans, 95), carte des loyers 2025, open data des
enchères, quatre scripts qui reproduisent les chiffres, le banc d'essai JS de la maquette,
la webapp, Foyer, le profil Hermes, Ollama.

**À écrire pour l'alpha** : `fiscalite.py` et `verdict.py` (le cœur manquant), `locatif.py`,
le contrôle de trésorerie, le générateur de données de la webapp, les trois cron, et le banc
d'essai de 20 dossiers.

**Estimation honnête : trois soirées, ou une semaine de travail répartie.** La première
soirée produit le premier verdict chiffré sur un vrai bien.

## 9. Ce que cette alpha prépare pour le produit

Rien ne sera perdu : le moteur, le banc d'essai, les serveurs de données et le format de
dossier sont exactement ce que le produit vendra. **L'alpha est le moteur du produit, avec
une seule différence : un seul utilisateur.** C'est la raison pour laquelle elle passe
d'abord — elle produit de la valeur immédiatement, et elle construit la pièce la plus dure.
