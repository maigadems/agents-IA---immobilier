# Vérifier le serveur avec l'inspecteur MCP

Prérequis : Node.js 18+ (pour `npx`) et l'environnement Python du projet activé.

## 1. Transport local (stdio)

```bash
npx @modelcontextprotocol/inspector python mcp_server/mcp_server.py
```

L'inspecteur s'ouvre dans le navigateur (http://localhost:6274) et lance lui-même le serveur.
Cliquer sur **Connect**.

## 2. Transport HTTP

Terminal 1 :

```bash
python mcp_server/mcp_server.py --transport http --port 8000
```

Terminal 2 :

```bash
npx @modelcontextprotocol/inspector
```

Dans l'inspecteur : *Transport Type* = **Streamable HTTP**, *URL* = `http://127.0.0.1:8000/mcp`,
puis **Connect**.

## 3. Ce qu'il faut vérifier (à capturer pour le jury)

| Onglet | Action | Résultat attendu |
|---|---|---|
| Tools | *List Tools* | `rechercher_biens`, `detail_bien`, `infos_agence` avec leurs descriptions |
| Tools | `rechercher_biens` avec `quartier=Mermoz`, `pieces_min=3`, `pieces_max=3`, `loyer_max_fcfa=400000` | un seul bien, `SK-001` |
| Tools | `rechercher_biens` avec `quartier=Hann` | `nombre: 0` et le message « Aucun bien… » |
| Tools | `detail_bien` avec `bien_id=SK-999` | erreur lisible (`isError: true`) |
| Resources | `agence://infos` | horaires, zones, conditions de location |

Les mêmes vérifications sont automatisées dans [tests/test_serveur_mcp.py](../tests/test_serveur_mcp.py)
(`pytest tests/test_serveur_mcp.py`).
