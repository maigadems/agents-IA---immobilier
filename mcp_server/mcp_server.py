import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Literal
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

sys.path.insert(0, str(Path(__file__).parent))
from catalogue import DB_DEFAUT, RACINE, creer, norme


# chemin de la base : variable CATALOGUE_DB_PATH (voir .env.example), relatif a la racine du depot
DB_PATH = Path(os.getenv("CATALOGUE_DB_PATH", DB_DEFAUT))
if not DB_PATH.is_absolute():
    DB_PATH = RACINE / DB_PATH
LIMITE_MAX = 10

# connection avec le catalogue
def _connection() -> sqlite3.Connection:
    if not DB_PATH.exists():
        creer(DB_PATH)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection

def _bien_resume(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"],
        "type_bien": r["type_bien"],
        "quartier": r["quartier"],
        "pieces": r["pieces"],
        "surface_m2": r["surface_m2"],
        "loyer_fcfa": r["loyer_fcfa"],
        "charges_fcfa": r["charges_fcfa"],
        "meuble": bool(r["meuble"]),
        "disponibilite": r["disponibilite"],
        "conseiller": r["conseiller"],
    }
    
def creer_serveur() -> FastMCP:
    mcp = FastMCP(
        "catalogue-sama-ker",
        instructions="Catalogue des biens a louer de l'agence Sama Ker Immobilier (Dakar).",
    )

    # outils rechercher_biens 
    @mcp.tool()
    def rechercher_biens(
        quartier: str | None = None,
        type_bien: Literal["appartement", "studio", "villa", "duplex"] | None = None,
        pieces_min: int | None = None,
        pieces_max: int | None = None,
        loyer_max_fcfa: int | None = None,
        loyer_min_fcfa: int | None = None,
        meuble: bool | None = None,
        disponible_seulement: bool = True,
        limite: int = 5,
    ) -> dict:
        """Recherche des biens a LOUER dans le catalogue de l'agence.

        Tous les filtres sont optionnels et se cumulent.
        - quartier : nom du quartier de Dakar (accents et majuscules ignores), ex. "Mermoz", "Sacre-Coeur".
        - type_bien : appartement, studio, villa ou duplex.
        - pieces_min / pieces_max : nombre de pieces (un "F3" = 3 pieces).
        - loyer_max_fcfa / loyer_min_fcfa : loyer mensuel HORS charges, en F CFA.
        - meuble : true pour meuble, false pour non meuble.
        - disponible_seulement : true (defaut) ne renvoie que les biens libres a la location.
        - limite : nombre maximum de resultats (1 a 10, defaut 5).

        Renvoie {"nombre": n, "biens": [...], "message": "..."}. Si aucun bien ne correspond,
        "biens" est vide : il ne faut alors proposer aucun bien au client.
        """
        if not 1 <= limite <= LIMITE_MAX:
            raise ToolError(f"limite doit etre comprise entre 1 et {LIMITE_MAX} (recu : {limite}).")
        if pieces_min is not None and pieces_max is not None and pieces_min > pieces_max:
            raise ToolError("pieces_min est superieur a pieces_max.")
        if loyer_min_fcfa is not None and loyer_max_fcfa is not None and loyer_min_fcfa > loyer_max_fcfa:
            raise ToolError("loyer_min_fcfa est superieur a loyer_max_fcfa.")
        sql, params = "SELECT * FROM biens WHERE 1=1", []
        if quartier:
            sql += " AND quartier_norm LIKE ?"
            params.append(f"%{norme(quartier)}%")
        if type_bien:
            sql += " AND type_bien = ?"
            params.append(type_bien)
        if pieces_min is not None:
            sql += " AND pieces >= ?"
            params.append(pieces_min)
        if pieces_max is not None:
            sql += " AND pieces <= ?"
            params.append(pieces_max)
        if loyer_max_fcfa is not None:
            sql += " AND loyer_fcfa <= ?"
            params.append(loyer_max_fcfa)
        if loyer_min_fcfa is not None:
            sql += " AND loyer_fcfa >= ?"
            params.append(loyer_min_fcfa)
        if meuble is not None:
            sql += " AND meuble = ?"
            params.append(1 if meuble else 0)
        if disponible_seulement:
            sql += " AND disponibilite = 'disponible'"
        sql += " ORDER BY loyer_fcfa ASC LIMIT ?"
        params.append(limite)
        with _connection() as con:
            lignes = con.execute(sql, params).fetchall()
            biens = [_bien_resume(r) for r in lignes]
            if biens:
                return {"nombre": len(biens), "biens": biens, "message": "Resultats tries par loyer croissant."}
            zones = [r[0] for r in con.execute("SELECT DISTINCT quartier FROM biens WHERE disponibilite='disponible' ORDER BY 1")]
        return {
            "nombre": 0,
            "biens": [],
            "message": "Aucun bien ne correspond a ces criteres. Ne propose aucun bien.",
            "quartiers_avec_biens_disponibles": zones,
        }
        
    # outils detail_bien 
    @mcp.tool()
    def detail_bien(bien_id: str) -> dict:
        """Fiche complete d'un bien a partir de son identifiant (format "SK-007").

        Renvoie l'adresse, le loyer, les charges, la caution (2 mois de loyer), la surface,
        les equipements, la disponibilite et le conseiller responsable des visites.
        """
        bien_id = bien_id.strip().upper()
        with _connection() as con:
            r = con.execute("SELECT * FROM biens WHERE id = ?", (bien_id,)).fetchone()
        if r is None:
            raise ToolError(f"Aucun bien avec l'identifiant {bien_id}. Les identifiants vont de SK-001 a SK-030.")
        fiche = _bien_resume(r)
        fiche.update(
            {
                "adresse": r["adresse"],
                "equipements": r["equipements"].split(","),
                "caution_fcfa": 2 * r["loyer_fcfa"],
                "total_mensuel_fcfa": r["loyer_fcfa"] + r["charges_fcfa"],
            }
        )
        return fiche

    def _infos() -> dict:
        with _connection() as con:
            return json.loads(con.execute("SELECT valeur FROM agence WHERE cle='infos'").fetchone()[0])

    @mcp.tool()
    def infos_agence() -> dict:
        """Informations generales sur l'agence : horaires de visite, zones couvertes, conditions de location."""
        return _infos()

    @mcp.resource("agence://infos", mime_type="application/json")
    def ressource_agence() -> str:
        """Description de l'agence : horaires de visite, zones couvertes, conditions de location."""
        return json.dumps(_infos(), ensure_ascii=False, indent=2)

    return mcp


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    a = p.parse_args()
    serveur = creer_serveur()
    if a.transport == "stdio":
        serveur.run(transport="stdio", show_banner=False)
    else:
        serveur.run(transport="http", host=a.host, port=a.port)
