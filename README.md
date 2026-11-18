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

## Installation

```bash
python -m venv .venv
# Windows : .venv\Scripts\activate   |   Linux/Mac : source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # puis remplir les valeurs
```

Identifiants Google (compte de test de l'atelier uniquement) : placer
`credentials.json` à la racine — **jamais commité** (voir `.gitignore`).

## Lancement

> À compléter par chaque partie au fil des exercices.

```bash
python mcp_server/catalogue.py                         # crée data/catalogue.db (auto au 1er appel sinon)
python mcp_server/mcp_server.py                        # serveur MCP en stdio
python mcp_server/mcp_server.py --transport http       # serveur MCP en HTTP : http://127.0.0.1:8000/mcp
python -m agent.main                 # lance l'agent
python evaluation/run_eval.py        # rejoue le jeu de test
```

## Serveur MCP — documentation

> Partie 1 : outils, arguments, exemples d'appel (exigé par l'exercice 2).
