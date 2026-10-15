# Construire l'agent — architecture d'ingénierie

Note du **15 octobre 2026**. Elle répond à une question différente de `ARCHITECTURE.md` :
celle-ci décrit *le métier* (quelles sources, quel moteur d'estimation, quelle conformité) ;
celle-ci décrit **comment on construit l'agent lui-même** — couches, choix techniques,
mémoire, évaluation, coût, ordre de construction.

---

## 0. La recommandation, en une phrase

**Ne construis pas un agent : construis un moteur, et emballe-le dans un agent qui existe
déjà.** Puis, quand un client paie, extrais-le en service autonome. Le moteur est le même
dans les deux cas ; seul l'emballage change, et il y a un ordre pour ne pas payer deux fois.

C'est vrai en 2026 : le goulot d'étranglement n'est plus le modèle. Ce sont les **outils,
la mémoire, l'évaluation et la boucle d'orchestration** qui séparent une démonstration d'un
système qui survit à du trafic réel.

---

## 1. Palier 1 — L'agent dans le harnais existant (une à deux semaines)

Le plus court chemin entre « une idée d'agent » et « un agent qui rend un verdict sur un
vrai bien ». **Un profil dédié**, isolé de ton agent principal :

```bash
hermes profile create immopilot --description "Agent d'investissement immobilier"
hermes profile use immopilot            # devient le profil par défaut
hermes profile list                     # le profil apparaît, avec sa gateway et son alias
```

Ce que le profil isole, gratuitement : ses `skills/`, ses `plugins/`, ses `cron/`, ses
`memories/`, son `config.yaml` (donc son modèle, ses serveurs MCP, ses hooks, ses
routages de plateforme) et sa base de sessions. **L'agent immobilier ne partage rien avec
l'agent du quotidien — et ne peut pas le polluer.**

Contenu du profil :

- `skills/immobilier-achat/` — la méthode : les étapes, les trois régimes fiscaux, les
  limites des sources, les règles de refus.
- `mcp/` — un serveur MCP local par famille de source (voir §3).
- `scripts/` — le moteur (les quatre scripts qui tournent déjà, consolidés).
- `cron/` — la veille des enchères du secteur et les alertes de seuil.
- `agent-hooks/` — les garde-fous : refus de scraper, journalisation des verdicts.

**Et la pièce qui change tout :**

```bash
hermes profile export immopilot -o immopilot-profile.tar.gz
hermes profile install <dépôt git ou archive>
```

Un profil s'exporte et s'installe. **L'agent devient donc un livrable versionné**,
distribuable à un client, sans que tu réécrives quoi que ce soit. C'est l'argument
décisif pour commencer ici plutôt que par un service à part.

## 2. Palier 2 — L'agent en service autonome (quand un client paie)

Cinq couches. Ce sont celles de l'état de l'art 2026 ; en oublier une donne un agent qui
marche en démo et pas en production.

### Couche 1 — Le raisonnement (les modèles)

- **Routage par nœud, pas un modèle unique.** Un petit modèle pour l'extraction et la
  classification, un modèle fort pour la décomposition, la décision et la rédaction du
  dossier. Le coût par tâche baisse d'un facteur 5 à 10.
- **Jev (TypeSafe) pour les questions bornées sur documents** : PV d'AG, cahier des
  conditions de vente. Mesuré : 251 ms, 0,000037 $ l'appel.
- **Règle non négociable : le modèle ne calcule pas.** Rendements, médianes, quartiles,
  cash-flows : en code, exactement. Le modèle rédige et choisit les outils.

### Couche 2 — L'orchestration (la boucle, l'état, la reprise)

Un dossier d'analyse est un **workflow long, à étapes, qui doit survivre à un
redémarrage**. Deux choix défendables :

- **LangGraph** — machine à états explicite en graphe, points de reprise (checkpoints
  Postgres), interruption pour validation humaine, débogage « time travel ». **Le meilleur
  argument pour ce projet : chaque transition d'état devient une entrée de journal
  d'audit** — donc le verdict rejouable, ce que la loi et le client exigent.
- **Pydantic AI** — un agent unique, sorties typées et validées, dans un service Python.
  Moins de cérémonie, adapté si l'agent reste petit et linéaire.

Recommandation : **Pydantic AI au palier 1, LangGraph dès que le dossier devient
multi-étapes avec reprise et validation humaine.** Ne pas adopter les deux.

### Couche 3 — Les outils (MCP, un serveur par famille de source)

**Un serveur MCP par famille, en lecture seule, avec schéma typé :**

```
mcp-dvf          prix signés par mutation, par rue, par commune, par année
mcp-loyers       loyers d'annonce + nombre d'observations + zone tendue
mcp-geo          BAN (géocodage) + cadastre IGN (parcelles, contenances)
mcp-urbanisme    GPU : zonage PLU, servitudes, périmètres de protection
mcp-dpe          étiquettes DPE (identifiant de jeu de données à confirmer, §7)
mcp-encheres     ventes aux enchères judiciaires + notaires (canal légal)
mcp-documents    lecture bornée des documents client, via Jev
```

Pourquoi MCP et pas des fonctions internes : **c'est un contrat standard**. Les mêmes
outils servent dans ton harnais aujourd'hui, dans ton service demain, et dans le CRM du
client après-demain. Et chaque serveur se teste seul, sans agent.

Trois règles sur les outils : lecture seule partout · **cache par hash de contenu** (les
mêmes fichiers DVF seront relus mille fois) · un outil qui échoue le dit, il ne renvoie
jamais une valeur plausible par défaut.

### Couche 4 — La mémoire (trois mémoires séparées, pas une)

- **Données de référence** — DVF, loyers, cadastre : immuables, versionnées par millésime,
  stockées en Parquet et interrogées avec **DuckDB**. Analytique local, pas de serveur,
  des jointures sur des dizaines de millions de lignes sans effort.
- **État des dossiers** — **Postgres** : un dossier, ses étapes, ses résultats, ses
  versions de données, son coût. C'est ce qui rend un verdict rejouable.
- **Documents du client** — stockage chiffré + les réponses extraites, structurées.

**Et pas de base vectorielle au départ.** C'est l'erreur la plus fréquente : ici la
recherche utile est **structurée et géographique** (« les ventes de cette rue, sur ces
trois ans, pour ce type de bien »), pas sémantique. Le RAG sémantique n'ajoute rien tant
qu'on n'indexe pas de la doctrine juridique.

### Couche 5 — Observabilité et évaluation (la couche qui décide du succès)

Une trace par dossier : outils appelés, versions de données, nombre de jetons, coût,
latence, verdict. Puis **quatre scores** mesurés en continu :

1. **Complétion** — le dossier atteint-il un état final valide ?
2. **Choix d'outil** — à chaque étape, le bon outil a-t-il été appelé ?
3. **Ancrage** — chaque affirmation chiffrée remonte-t-elle à une donnée réelle ?
4. **Justesse du refus** — quand l'agent refuse, le refus était-il approprié ?

Le quatrième est celui du métier : un outil d'aide à la décision qui n'a pas le droit de
dire non ne sert à rien. Il doit donc y avoir un jeu de dossiers de référence contenant
**de vraies mauvaises affaires**, et un test qui échoue si l'agent les valide.

**Le harnais d'évaluation se construit avant d'ajouter des outils.** Sans lui, l'agent
grandit à l'intuition et les régressions deviennent invisibles.

## 3. Transverse — Conformité, coût, sécurité

- **Hoguet** : le service ne contacte jamais un tiers, ne négocie pas, ne représente
  personne. Le client agit. C'est une contrainte de code, pas une mention en bas de page.
- **Pas de scraping** : aucune valeur par défaut qui irait chercher une annonce.
- **Documents** : chiffrés, durée de conservation déclarée, purge sur demande.
- **Coût cible : moins de 0,10 € de modèle par dossier complet.** À 150 €/mois pour un
  chasseur, même à 20 dossiers par jour, la marge est intacte. **Ce calcul se fait avant
  d'écrire du code** ; après, c'est une mauvaise nouvelle qu'on découvre en production.
- **Budget et alertes** : budget de coût par dossier et par jour, alerte sur les
  trajectoires anormalement longues (boucles de reprise = argent jeté).

## 4. L'ordre de construction, et il est impératif

1. **Semaine 1 — le moteur et son banc d'essai.** Les scripts de calcul, et **20 dossiers
   de référence dont 5 mauvaises affaires**. Aucune interface, aucun agent.
2. **Semaine 2 — les outils.** Les serveurs MCP, en lecture seule, testés isolément.
3. **Semaine 3 — la boucle.** Workflow durable, traces, scores, journal d'audit.
4. **Semaine 4 — l'interface.** Conversation d'abord, app privée ensuite. **L'interface
   en dernier — c'est ce qui donne l'illusion d'avancer le plus vite.**
5. **Ensuite — trois clients en test.** Le test qui vaut 200 € par mois se fait avec trois
   chasseurs immobiliers, pas avec six mois de développement.

## 5. Les quatre erreurs qui tuent un projet d'agent

1. **Le multi-agents décoratif.** Plusieurs agents qui se parlent, c'est trois à cinq fois
   le coût, des défaillances en cascade, et aucune tâche du domaine n'en a besoin. **Un
   agent, des outils.** Le découpage se fait dans les outils et le workflow, pas dans des
   personnalités.
2. **Le modèle qui calcule, ou qui estime.** La dispersion locale mesurée atteint 21 % sur
   une commune et un facteur 1,7 dans une même rue. Un modèle qui « estime » produit un
   chiffre plausible, et donc faux — de la pire façon qui soit.
3. **Pas de banc d'essai.** Sans dossiers de référence, aucune régression n'est visible, et
   la revue d'incident devient de l'archéologie.
4. **La base vectorielle par réflexe.** La donnée de ce domaine est structurée et
   géographique. On ajoute du sémantique le jour où l'on indexe de la doctrine, pas avant.

## 6. Résumé des choix

```
Palier 1  profil Hermes dédié          skills + MCP + scripts + cron + hooks
          export/install                -> l'agent devient un livrable versionné

Palier 2  service Python autonome
          modèles         routage par nœud + Jev pour le borné
          orchestration   LangGraph (durable, audit) ou Pydantic AI (minimal)
          outils          un serveur MCP par famille de source, lecture seule
          données         DuckDB/Parquet (référence) + Postgres (dossiers)
          interface       conversation -> app privée -> API/MCP vers le CRM
          évaluation      4 scores, 20 dossiers de référence, blocage si régression
          coût cible      < 0,10 EUR par dossier
```

## 8. Déploiement sur le VPS — état vérifié le 15/10/2026

**Oui, l'agent peut tourner en autonome sur le VPS**, à trois niveaux d'isolation croissante.
Le VPS est déjà une machine d'application : 8 vCPU, 15 Gio de RAM (12 disponibles), 4 Gio
de swap, Docker 29.1.3, Postgres, Redis, Caddy, Syncthing, Ollama, Foyer et TimeHeroes en
service. **La contrainte réelle n'est pas la mémoire : c'est le disque — 20 Go libres sur
75, à 73 % d'occupation.**

### Niveau 1 — Un profil Hermes avec sa propre gateway (recommandé pour commencer)

La gateway tourne aujourd'hui comme **service systemd utilisateur** (`hermes-gateway.service`,
sous le gestionnaire de l'utilisateur root), et `hermes gateway list` sait afficher l'état
de la gateway **par profil**. Chaque profil peut donc avoir la sienne :

```bash
hermes profile create immopilot --description "Agent d'investissement immobilier"
hermes profile use immopilot
# ... installation des skills, serveurs MCP, scripts et cron DANS le profil ...
hermes gateway install --system --run-as-user root --start-now
hermes gateway list          # les deux gateways, et leur état
hermes profile export immopilot -o immopilot-profile.tar.gz
```

Ce que cela donne : base de sessions, mémoire, skills, MCP, cron et configuration de modèle
**propres à l'agent immobilier**. Il survit indépendamment, se met à jour séparément, et
s'exporte comme livrable.

**Ce que cela ne donne pas** : une isolation de sécurité. Les deux profils tournent sous le
même compte et le même binaire — l'agent principal peut lire les fichiers de l'agent
immobilier. L'isolation est logique, pas étanche.

### Niveau 2 — Un conteneur Docker (isolation réelle)

Docker est déjà installé et en service. L'agent vit alors dans sa propre image, avec son
propre système de fichiers, ses limites de ressources (`--memory`, `--cpus`), un compte
dédié, et des montages en lecture seule. C'est le niveau à franchir **le jour où l'agent
manipule les données d'un client**, ou des identifiants qu'un autre agent ne doit pas
pouvoir lire.

### Niveau 3 — Le service autonome du palier 2

Le workflow durable, les serveurs MCP, les traces et l'évaluation, dans un service à lui,
sans harnais de conversation autour. À construire quand un client paie.

### Deux points de blocage, à régler avant d'installer

1. **Un agent autonome a besoin de son propre bot.** Deux profils branchés sur le même
   jeton Telegram se disputeraient les mêmes messages. Il faut donc un second bot
   (BotFather pour Telegram, ou une seconde application Discord), ou bien faire tourner
   l'agent **sans plateforme de messagerie** — piloté par cron, ligne de commande et API.
2. **Le disque.** 20 Go libres, dont une base d'état de près d'1 Go, des conteneurs, et les
   données DVF. À surveiller avant d'empiler une troisième pile applicative.

### Une opportunité déjà en place

**Ollama tourne déjà** sur le VPS. L'extraction et la classification — les nœuds les moins
exigeants du workflow — peuvent donc tourner en local, gratuitement et sans qu'aucune
donnée ne sorte de la machine, en réservant le modèle fort à la décision et à la rédaction.

---

## 9. Webapp ou agent ? — la décision, et elle n'est pas symétrique

**Réponse courte : l'agent est le moteur, la webapp est le cockpit. On construit le moteur
d'abord, la webapp dès le premier client — jamais l'inverse.**

Le raisonnement tient en trois points.

1. **Ce que le client achète, c'est un dossier, pas une conversation.** Un chasseur
   immobilier veut, par bien : un verdict chiffré, les comparables de la rue, la simulation
   fiscale, un PDF présentable. Ni un chat, ni un tableau de bord ne produisent cela tout
   seuls — c'est le moteur qui le produit, et les deux autres ne sont que des façades.
2. **Le travail difficile est dans la donnée hétérogène, pas dans l'écran.** Comparables
   DVF, carte des loyers, PLU, DPE, PV d'assemblée générale, cahier des conditions de vente :
   c'est exactement ce qu'un agent sait absorber et qu'un formulaire web ne sait pas.
3. **Ce que la webapp apporte et que l'agent n'apporte pas : la mémoire du client.**
   Une conversation ne laisse rien derrière elle. Une application accumule : l'archive des
   dossiers, la comparaison entre biens, le suivi des mandats, les alertes, l'audit. C'est
   ce qui crée l'abonnement — un professionnel ne paie pas 150 € par mois pour un chat, il
   paie pour un dossier qui s'accumule et une archive qu'il peut rouvrir.

Répartition des rôles, à tenir strictement :

- **Dans le moteur / l'agent** : les comparables, le verdict, les règles de refus, la
  lecture des documents, la rédaction du dossier. **Les règles de décision ne vivent jamais
  dans l'interface** : elles changent vite et doivent être versionnées.
- **Dans la webapp** : les comptes clients, le dépôt des annonces et des documents, la file
  d'attente, l'archive, le suivi des mandats, les alertes, l'export PDF, la facturation, le
  journal d'audit consultable.
- **L'agent conversationnel** : le meilleur canal d'entrée (« colle ton annonce ») et le
  pire système d'enregistrement. On le garde comme porte d'entrée, jamais comme archive.

**Et la bonne nouvelle technique : le choix n'est pas définitif.** Si le moteur est exposé
en serveurs MCP — ce que recommande la section 3 — alors l'agent et la webapp **appellent les
mêmes outils**. La webapp est une façade de plus, pas un deuxième projet. C'est précisément
pour cela que le moteur passe en premier.

### L'ordre, avec les durées

```
1. Moteur + banc d'essai          1 semaine    aucune interface
2. Agent (CLI, cron, MCP)         1 semaine    utilisable par Ronald tout de suite
3. Webapp privée                  2 à 3 semaines   dépôt, file d'attente, archive, PDF
4. Ouverture à un client test      1 semaine    compte, licence, journal d'audit
```

### La règle de décision, en une phrase

**Si la valeur se joue sur un écran, fais une webapp. Si elle se joue sur un dossier produit
en cinq minutes à partir de documents hétérogènes, fais l'agent — puis mets une webapp
devant quand un client paie.** Dans ce métier, la valeur se joue sur le dossier.

---

## 7. Ce qui reste à vérifier techniquement

- **Identifiant du jeu de données DPE de l'ADEME** — mon premier essai a renvoyé 404.
- **API du Géoportail de l'urbanisme** — elle exige `geom` ou `partition`, pas `code_insee` :
  l'appel correct est `?partition=DU_<INSEE>`, à valider sur une commune réelle.
- **Comportement de Woob sur la caisse régionale de Ronald** — le module `cragr` existe,
  la connexion n'a pas été testée (elle demande son identifiant et sa validation forte).
- **Coût réel par dossier**, mesuré et non estimé, dès les 20 dossiers de référence.
