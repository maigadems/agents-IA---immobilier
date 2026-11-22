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

- **Catalogue (P1)** — serveur MCP `catalogue-sama-ker` ([mcp_server/mcp_server.py](mcp_server/mcp_server.py)) :
  - `rechercher_biens(quartier, type_bien, pieces_min, pieces_max, loyer_min_fcfa,
    loyer_max_fcfa, meuble, disponible_seulement=True, limite=5)` — tous optionnels,
    renvoie `{"nombre", "biens", "message"}` ; `biens` vide = ne proposer aucun bien ;
  - `detail_bien(bien_id)` — identifiant `SK-001` à `SK-030`, renvoie la fiche avec l'adresse ;
  - `infos_agence()` et la ressource `agence://infos` — horaires, zones, conditions ;
  - erreurs : l'outil lève une erreur MCP avec un message explicite.
- **Calendar (P2)** — outils du modèle dans [agent/tools/outils_agenda.py](agent/tools/outils_agenda.py) :
  - `lister_creneaux_libres(bien_id, date_debut, date_fin, heure_min, heure_max)` renvoie
    `{"conseiller", "creneaux": [{"debut", "fin", "libelle"}]}` ;
  - `creer_visite(bien_id, debut, client_nom, client_email)`, `deplacer_visite(bien_id, event_id, nouveau_debut)`
    et `annuler_visite(bien_id, event_id)` renvoient `{"statut": "cree" | "deplace" | "annule" | "creneau_pris"
    | "doublon" | "refuse_par_conseiller" | "regle_non_respectee", ...}`.
- **Gmail (P2)** — outils du modèle dans [agent/tools/outils_gmail.py](agent/tools/outils_gmail.py) :
  - `lire_demandes(maximum)` renvoie une liste `{message_id, thread_id, client_nom, client_email, objet,
    contenu, statut, suspect_injection, hors_perimetre_probable}` ;
  - `creer_brouillon(message_id, texte)` renvoie `{"statut": "brouillon_cree", "draft_id", "thread_id"}` ;
  - `envoyer_brouillon(draft_id)` renvoie `{"statut": "envoye" | "refuse_par_conseiller"}` ;
  - `transmettre_conseiller(message_id, motif)`.
- **Validation (P2)** — `Validation.demander(action, details) -> bool`
  ([agent/tools/validation.py](agent/tools/validation.py)), appelée **par le code** avant toute
  écriture ; chaque décision est inscrite dans la trace.

La Partie 3 (pipeline) réutilise `agent.boite.traiter_boite` et les mêmes outils. Elle ajoute la
gestion de la confirmation du client et l'état de chaque conversation, en s'appuyant sur le fil Gmail.

## Calendrier

| Date | Objectif |
|---|---|
| 14 nov | Ex 1 et 2 fusionnés dans `main` |
| 16 nov | Ex 3 et 4 fusionnés |
| 17 nov | Ex 5 fusionné |
| 18 nov 23h59 | Ex 6 terminé, dépôt figé |
| 19 nov | Démo devant le jury (chacun doit pouvoir expliquer sa partie) |
