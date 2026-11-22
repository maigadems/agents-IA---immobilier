# Traces livrées

Ce dossier contient les traces de trois traitements complets, dont un échec analysé dans
[../analyse_echecs.md](../analyse_echecs.md). Les traces de travail restent dans `traces/`,
qui n'est pas versionné.

Pour y ajouter une trace :

```bash
python -m agent.main conversations                  # repérer la conversation
python -m agent.main trace traces/<fichier>.jsonl   # la relire
cp traces/<fichier>.jsonl evaluation/traces/
```

Une trace est un fichier JSON Lines, avec une ligne par événement : `demande`,
`appel_outil`, `resultat_outil`, `erreur_outil`, `interpretation`, `validation`, `reponse`,
`usage`. Elle ne doit contenir que des emails du compte de test et aucun identifiant.
