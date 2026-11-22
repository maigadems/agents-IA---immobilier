# Agent IA · Sama Kër Immobilier

Agent qui traite de bout en bout les demandes de visite reçues par email :
lecture Gmail → recherche dans le catalogue (serveur MCP) → créneaux libres
Google Calendar → brouillon de réponse → **validation humaine** → envoi →
inscription de la visite.

Atelier *Agents IA* · Programme Data & IA – Orange Digital Center.

## Équipe

| Partie | Exercices | Responsable | Branche |
|---|---|---|---|
| 1 · Catalogue & serveur MCP | Ex 1, Ex 2 | @dinho325 | `partie-1/catalogue-mcp` |
| 2 · Google Calendar & Gmail | Ex 3, Ex 4 | @maigadems (tech lead) | `partie-2/calendar-gmail` |
| 3 · Pipeline complet & évaluation | Ex 5, Ex 6 | @yohanfredyh | `partie-3/pipeline-eval` |

Organisation et règles Git : voir [CONTRIBUTING.md](CONTRIBUTING.md).

## Architecture

```
Email client ──► Agent (modèle + boucle + état) ──► Serveur MCP catalogue (SQLite)
                     │                          ──► Google Calendar (créneaux, visites)
                     │                          ──► Gmail (lecture, brouillons, envoi)
                     ├──► Validation conseiller (obligatoire avant envoi / écriture agenda)
                     └──► Traces et journal
```

## Structure du dépôt

```
mcp_server/   Serveur MCP + script du catalogue (30 biens)   — Partie 1
data/         Base SQLite générée (non versionnée)           — Partie 1
agent/        Boucle de l'agent, prompt système              — Parties 1 puis 3
agent/tools/  calendar.py, gmail.py, validation humaine      — Partie 2
evaluation/   15 emails de test, résultats attendus, script  — Partie 3
traces/       Traces de 3 traitements complets               — Partie 3
docs/         Schémas, décisions techniques
```

## Choix techniques

| Brique | Choix | Pourquoi |
|---|---|---|
| Modèle | Ollama (`qwen2.5:7b`) ou API gratuite compatible OpenAI (Groq…) | appel d'outils natif, gratuit |
| Framework | [Pydantic AI](https://ai.pydantic.dev) | open source, outils typés, client MCP intégré, historique complet des messages pour les traces |
| Catalogue | SQLite + serveur MCP [FastMCP](https://gofastmcp.com) | imposé ; FastMCP = SDK MCP Python de référence |
| Traces | fichiers JSON Lines dans `traces/` | lisibles sans outil externe, rejouables |

## Prérequis

- Python 3.11+ (testé en 3.13)
- Un modèle avec appel d'outils :
  - **local** : [Ollama](https://ollama.com) puis `ollama pull qwen2.5:7b`
  - **ou API gratuite** compatible OpenAI (ex. Groq) : clé dans `.env`
- Node.js 18+ uniquement pour l'inspecteur MCP

## Installation

```bash
python -m venv .venv
# Windows : .venv\Scripts\activate   |   Linux/Mac : source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # puis choisir le modèle (voir commentaires du fichier)
python mcp_server/catalogue.py   # crée data/catalogue.db (sinon créé au 1er appel)
```

Identifiants Google (compte de test de l'atelier uniquement) : placer
`credentials.json` à la racine — **jamais commité** (voir `.gitignore`).

## Lancement

```bash
# Ex 1-2 : interroger l'agent (il lance lui-même le serveur MCP en stdio)
python -m agent.main demande "Je cherche un F3 à Mermoz à moins de 400 000 F" -v

# Serveur MCP seul, en HTTP (puis MCP_SERVER_URL=http://127.0.0.1:8000/mcp dans .env)
python mcp_server/mcp_server.py --transport http

# Relire une trace
python -m agent.main trace traces/<fichier>.jsonl
```

## Boucle de l'agent et traces (Ex 1)

- **Prompt système** : [agent/prompts.py](agent/prompts.py), avec la date du jour ; l'agent ne
  cite que des biens renvoyés par les outils et le dit clairement quand rien ne correspond.
- **Étapes limitées** : `AGENT_MAX_ETAPES` requêtes au modèle et `AGENT_MAX_APPELS_OUTILS`
  appels d'outils par demande ; au-delà, l'agent s'arrête et transmet à un conseiller.
- **Erreur d'outil** : le message d'erreur est renvoyé au modèle, qui corrige ses arguments
  (`AGENT_RETRIES_OUTILS` tentatives au maximum).
- **Traces** : un fichier `traces/<date>-<libellé>-<id>.jsonl` par demande, avec chaque
  `appel_outil` (arguments), `resultat_outil`, `erreur_outil`, la `reponse` et l'`usage`
  (étapes, appels, tokens, durée). Exemple :

```
[demande] un F3 a Mermoz a moins de 400 000 F
  -> rechercher_biens({"quartier": "Mermoz", "pieces_min": 3, "pieces_max": 3, "loyer_max_fcfa": 400000})
  <- rechercher_biens : {"nombre": 1, "biens": [{"id": "SK-001", "quartier": "Mermoz", ...}]}
[reponse] Je vous propose l'appartement SK-001 à Mermoz : 3 pièces, 380 000 F CFA/mois...
```

## Critères d'acceptation Ex 1-2

```bash
python evaluation/verifier_ex1.py --json evaluation/resultats_ex1.json
```

Rejoue les 10 demandes de [evaluation/demandes_ex1.json](evaluation/demandes_ex1.json)
(dont 3 sans aucun bien correspondant) et vérifie qu'aucun identifiant inventé n'est cité,
que les biens attendus le sont, et que l'absence de résultat est annoncée. Comme l'agent passe
par le serveur MCP, la même commande valide l'exercice 2 (« mêmes résultats via MCP »).

## Tests

```bash
pytest -q
```

Catalogue, serveur MCP (via un vrai client MCP), boucle de l'agent avec un modèle simulé
(traces, erreur d'outil, limite d'étapes) et cohérence des 10 demandes avec la base.

## Serveur MCP du catalogue — documentation

Serveur `catalogue-sama-ker` ([mcp_server/mcp_server.py](mcp_server/mcp_server.py)),
écrit avec FastMCP, qui expose la base SQLite des 30 biens (identifiants `SK-001` à `SK-030`).
La base est créée automatiquement au premier appel si elle n'existe pas.

### Démarrer le serveur

| Transport | Commande | Point d'accès |
|---|---|---|
| local (stdio) | `python mcp_server/mcp_server.py` | sous-processus du client |
| HTTP | `python mcp_server/mcp_server.py --transport http --host 0.0.0.0 --port 8000` | `http://<ip>:8000/mcp` |

Variable optionnelle : `CATALOGUE_DB_PATH` (défaut `data/catalogue.db`).

### Outil `rechercher_biens`

Recherche des biens **à louer**. Tous les filtres sont optionnels et se cumulent.

| Argument | Type | Défaut | Description |
|---|---|---|---|
| `quartier` | string | — | quartier de Dakar, accents/majuscules ignorés (`"Sacre-Coeur"`, `"mermoz"`) |
| `type_bien` | `appartement` \| `studio` \| `villa` \| `duplex` | — | type de bien |
| `pieces_min` / `pieces_max` | int | — | nombre de pièces (un F3 = 3) |
| `loyer_min_fcfa` / `loyer_max_fcfa` | int | — | loyer mensuel hors charges, en F CFA |
| `meuble` | bool | — | `true` meublé, `false` non meublé |
| `disponible_seulement` | bool | `true` | exclut les biens loués ou réservés |
| `limite` | int (1-10) | `5` | nombre maximum de résultats |

Réponse :

```json
{"nombre": 1, "message": "Resultats tries par loyer croissant.",
 "biens": [{"id": "SK-001", "type_bien": "appartement", "quartier": "Mermoz", "pieces": 3,
            "surface_m2": 78, "loyer_fcfa": 380000, "charges_fcfa": 25000, "meuble": false,
            "disponibilite": "disponible", "conseiller": "Awa Diop"}]}
```

Sans résultat : `"nombre": 0`, `"biens": []`, un message « Aucun bien ne correspond… » et la
liste `quartiers_avec_biens_disponibles` pour proposer une alternative.

### Outil `detail_bien`

| Argument | Type | Description |
|---|---|---|
| `bien_id` | string | identifiant du bien, ex. `"SK-007"` (casse ignorée) |

Renvoie la fiche complète : champs ci-dessus + `adresse`, `equipements` (liste),
`caution_fcfa` (2 mois de loyer), `total_mensuel_fcfa` (loyer + charges).

### Outil `infos_agence` et ressource `agence://infos`

Horaires de visite, zones couvertes, conditions de location, conseillers, demandes hors périmètre.
L'outil et la ressource renvoient le même JSON (la ressource pour les clients qui lisent les
ressources MCP, l'outil pour les modèles qui ne savent appeler que des outils).

### Erreurs

Un argument invalide (`limite` hors 1-10, `pieces_min > pieces_max`, identifiant inconnu…)
renvoie une erreur d'outil MCP (`isError: true`) avec un message explicite que le modèle
peut lire pour corriger son appel, par exemple :
`Aucun bien avec l'identifiant SK-999. Les identifiants vont de SK-001 a SK-030.`

### Exemples d'appel

Avec le client Python FastMCP :

```python
import asyncio
from fastmcp import Client

async def main():
    async with Client("http://127.0.0.1:8000/mcp") as c:   # ou "mcp_server/mcp_server.py"
        r = await c.call_tool("rechercher_biens",
                              {"quartier": "Mermoz", "pieces_min": 3, "pieces_max": 3,
                               "loyer_max_fcfa": 400000})
        print(r.data)                      # {'nombre': 1, 'biens': [{'id': 'SK-001', ...}]}
        print((await c.read_resource("agence://infos"))[0].text)

asyncio.run(main())
```

Avec pydantic-ai (c'est ce que fait notre agent, [agent/catalogue_mcp.py](agent/catalogue_mcp.py)) :

```python
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset

agent = Agent("openai:gpt-4o-mini", toolsets=[MCPToolset("http://127.0.0.1:8000/mcp")])
```
