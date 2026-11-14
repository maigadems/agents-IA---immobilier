# Organisation de l'équipe

## Branches

```
main                      ← toujours fonctionnelle, on n'y pousse jamais directement
 ├── partie-1/catalogue-mcp   @dinho325     Ex 1-2
 ├── partie-2/calendar-gmail  @maigadems    Ex 3-4
 └── partie-3/pipeline-eval   @yohanfredyh  Ex 5-6
```

Chacun ne travaille **que dans sa branche** et que dans **ses dossiers** :

| Partie | Dossiers dont on est propriétaire |
|---|---|
| 1 | `data/`, `mcp_server/`, `agent/` (version initiale ex 1) |
| 2 | `agent/tools/calendar.py`, `agent/tools/gmail.py`, `agent/tools/validation.py` |
| 3 | `agent/` (pipeline ex 5), `evaluation/`, `traces/` |

Toucher au dossier d'un autre ? On le prévient d'abord.

## Workflow quotidien

```bash
git checkout partie-X/...          # sa branche
git pull origin main               # récupérer le travail déjà fusionné
# ... coder ...
git add <fichiers>
git commit -m "ex1: ajoute l'outil rechercher_biens"
git push origin partie-X/...
```

Quand un exercice est terminé (critère d'acceptation démontré) :
ouvrir une **Pull Request** vers `main` sur GitHub → le tech lead relit et fusionne.

## Règles

- Messages de commit : `exN: ce qui a été fait` (ex : `ex3: liste les créneaux libres`).
- Commits petits et fréquents, push au moins une fois par séance.
- **Aucun secret dans Git** : `.env`, `credentials.json`, `token.json` sont ignorés.
  Une nouvelle variable ? On l'ajoute dans `.env.example` avec une valeur factice.
- Nouvelle dépendance ? On l'ajoute à `requirements.txt` dans le même commit.
- Avant de demander une PR : `git pull origin main` puis vérifier que ça tourne.

## Contrats entre les parties

Pour travailler en parallèle sans s'attendre, on fixe les interfaces dès maintenant :

- **Catalogue (P1)** — outils MCP `rechercher_biens(type, quartier, loyer_max, pieces)`
  et `detail_bien(bien_id)`, retour en dict JSON, erreurs `{"erreur": "..."}`.
- **Calendar (P2)** — `lister_creneaux_libres(debut, fin)`, `creer_visite(...)`,
  `deplacer_visite(...)`, `annuler_visite(event_id)`.
- **Gmail (P2)** — `lire_demandes()`, `creer_brouillon(thread_id, texte)`,
  `envoyer_brouillon(draft_id)`.
- **Validation (P2)** — `demander_validation(action, details) -> bool`, appelée avant
  toute écriture (envoi, création/déplacement/annulation de visite).

La Partie 3 assemble ces fonctions : elle peut démarrer avec des fonctions factices
(mêmes signatures) et les remplacer quand les PR des parties 1 et 2 sont fusionnées.

## Calendrier

| Date | Objectif |
|---|---|
| 14 nov | Ex 1 et 2 fusionnés dans `main` |
| 16 nov | Ex 3 et 4 fusionnés |
| 17 nov | Ex 5 fusionné |
| 18 nov 23h59 | Ex 6 terminé, dépôt figé |
| 19 nov | Démo devant le jury (chacun doit pouvoir expliquer sa partie) |
