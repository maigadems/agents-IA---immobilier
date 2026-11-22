# Analyse des échecs (Ex 6)

> **À compléter après le premier rejeu avec le vrai modèle.** Les tableaux sont produits par
> `python evaluation/evaluer_ex6.py`. Les traces citées sont copiées dans `evaluation/traces/`.

## Méthode

1. Lancer `python evaluation/evaluer_ex6.py --seul avant`, puis ouvrir `evaluation/resultats/ex6_avant.md`.
2. Pour chaque email en échec, relire sa trace (colonne `traces` du fichier JSON) :

   ```bash
   python -m agent.main trace traces/<fichier>.jsonl
   ```

3. Classer la cause :
   - **compréhension** : critères mal extraits, comme le quartier, les pièces ou le budget ;
   - **outil** : mauvais arguments, erreur non corrigée ;
   - **rédaction** : horaire ou bien absent des retours d'outils ;
   - **décision** : répondu au lieu de transmettre, ou l'inverse.
4. Corriger **un** échec. Enregistrer la correction dans [agent/correctifs.py](../agent/correctifs.py),
   sous un nom, et la conditionner à `est_actif("<nom>")`.
5. Rejouer le jeu complet, avant et après :

   ```bash
   python evaluation/evaluer_ex6.py
   ```

## Échec 1

- **Email** :
- **Attendu / obtenu** :
- **Ce que montre la trace** (étape, outil, arguments, retour) :
- **Cause** :
- **Correction** (si c'est l'échec corrigé) :

## Échec 2

- **Email** :
- **Attendu / obtenu** :
- **Ce que montre la trace** :
- **Cause** :
- **Piste de correction** :

## Échec 3

- **Email** :
- **Attendu / obtenu** :
- **Ce que montre la trace** :
- **Cause** :
- **Piste de correction** :

## Résultat avant / après

Recopier ici le tableau de `evaluation/resultats/ex6_avant_apres.md`.
