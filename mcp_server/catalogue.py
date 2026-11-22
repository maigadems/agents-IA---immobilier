import sqlite3
from pathlib import Path
import sys
import unicodedata
import json

RACINE = Path(__file__).resolve().parent.parent
DB_DEFAUT = RACINE / "data" / "catalogue.db"
CONSEILLERS = ["Awa Diop", "Moussa Ndiaye", "Fatou Sow"]

def norme(s: str) -> str:
    "minuscules sans accents, pour des recherches tolerantes."
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("-", " ").strip()


# les biens
# type, quartier, adresse, pieces, surface_m2, loyer, charges, meuble, dispo, conseiller(1-3), equipements
BIENS = [
    ("appartement", "Mermoz", "Rue MZ 12, Mermoz Pyrotechnie", 3, 78, 380000, 25000, 0, "disponible", 1, "climatisation,parking,gardien"),
    ("appartement", "Mermoz", "Cite Keur Gorgui, Mermoz", 3, 85, 450000, 30000, 1, "disponible", 1, "climatisation,ascenseur,groupe electrogene"),
    ("appartement", "Mermoz", "Rue MZ 40, Mermoz", 3, 72, 350000, 20000, 0, "loue", 1, "parking"),
    ("appartement", "Mermoz", "Mermoz Sacre-Coeur Extension, Mermoz", 2, 55, 280000, 15000, 0, "disponible", 1, "climatisation"),
    ("studio", "Ouakam", "Rue OK 8, Ouakam", 1, 28, 150000, 10000, 1, "disponible", 2, "wifi,climatisation"),
    ("studio", "Ouakam", "Pres de la Mosquee de Ouakam", 1, 30, 130000, 5000, 0, "disponible", 2, "chauffe-eau"),
    ("appartement", "Ouakam", "Cite Avion, Ouakam", 2, 60, 250000, 15000, 0, "disponible", 2, "climatisation,parking"),
    ("appartement", "Ouakam", "Route de Ouakam, Ouakam", 3, 90, 420000, 30000, 1, "disponible", 2, "climatisation,piscine commune,gardien"),
    ("villa", "Almadies", "Route des Almadies, Almadies", 5, 220, 1500000, 80000, 1, "disponible", 3, "piscine,jardin,groupe electrogene,gardien"),
    ("appartement", "Almadies", "Residence Les Palmiers, Almadies", 3, 95, 650000, 40000, 1, "disponible", 3, "climatisation,ascenseur,vue mer"),
    ("duplex", "Almadies", "Cite Aviation, Almadies", 4, 140, 900000, 50000, 0, "reserve", 3, "terrasse,parking"),
    ("appartement", "Sacre-Coeur", "Sacre-Coeur 3, VDN", 2, 62, 300000, 20000, 0, "disponible", 1, "climatisation,ascenseur"),
    ("appartement", "Sacre-Coeur", "Sacre-Coeur 1, pres du rond-point", 3, 80, 400000, 25000, 0, "disponible", 1, "climatisation,parking"),
    ("studio", "Sacre-Coeur", "Sacre-Coeur 2", 1, 25, 120000, 5000, 1, "disponible", 1, "wifi"),
    ("appartement", "Point E", "Rue 6 x Bourguiba, Point E", 3, 88, 480000, 30000, 0, "disponible", 2, "climatisation,ascenseur,gardien"),
    ("appartement", "Point E", "Rue 12, Point E", 2, 58, 320000, 20000, 1, "disponible", 2, "climatisation,wifi"),
    ("appartement", "Fann", "Fann Residence, pres de l'universite", 2, 65, 350000, 25000, 0, "disponible", 3, "climatisation,gardien"),
    ("villa", "Fann", "Fann Hock", 4, 180, 1200000, 70000, 0, "loue", 2, "jardin,garage"),
    ("appartement", "Plateau", "Avenue Pompidou, Plateau", 3, 100, 600000, 45000, 1, "disponible", 3, "ascenseur,climatisation,vue port"),
    ("studio", "Plateau", "Rue Felix Faure, Plateau", 1, 32, 180000, 12000, 1, "disponible", 3, "climatisation,wifi,ascenseur"),
    ("appartement", "Liberte 6", "Liberte 6 Extension", 3, 75, 300000, 15000, 0, "disponible", 2, "parking,chauffe-eau"),
    ("appartement", "Liberte 6", "Liberte 6, pres de la VDN", 2, 52, 220000, 10000, 0, "disponible", 2, "climatisation"),
    ("appartement", "Mamelles", "Les Mamelles, pres du Phare", 4, 110, 700000, 50000, 1, "disponible", 1, "vue mer,piscine commune,ascenseur"),
    ("studio", "Yoff", "Yoff Virage", 1, 27, 110000, 5000, 0, "disponible", 2, "chauffe-eau"),
    ("appartement", "Yoff", "Yoff Layene", 2, 50, 200000, 10000, 0, "disponible", 2, "parking"),
    ("appartement", "Ngor", "Village de Ngor, face a l'ile", 2, 64, 400000, 25000, 1, "disponible", 3, "vue mer,climatisation,wifi"),
    ("appartement", "Parcelles Assainies", "Unite 15, Parcelles Assainies", 3, 70, 200000, 10000, 0, "disponible", 1, "parking"),
    ("villa", "Rufisque", "Rufisque Est, pres du marche Thiawlene", 4, 150, 350000, 15000, 0, "disponible", 2, "jardin,garage"),
    ("appartement", "Sicap Liberte", "Sicap Liberte 4", 3, 82, 330000, 20000, 0, "disponible", 1, "climatisation,gardien"),
    ("appartement", "Medina", "Rue 11 x Blaise Diagne, Medina", 2, 48, 150000, 5000, 0, "disponible", 3, "chauffe-eau"),
]
# les informationsde l'agence
INFOS_AGENCE = {
    "nom": "Sama Ker Immobilier",
    "ville": "Dakar",
    "type_activite": "Location uniquement (pas de vente).",
    "horaires_visite": "Du lundi au samedi, de 9h a 18h (fuseau Africa/Dakar). Une visite dure 45 minutes. Pas de visite le dimanche.",
    "zones_couvertes": ["Mermoz", "Ouakam", "Almadies", "Sacre-Coeur", "Point E", "Fann", "Plateau",
                        "Liberte 6", "Sicap Liberte", "Mamelles", "Yoff", "Ngor", "Parcelles Assainies",
                        "Rufisque", "Medina"],
    "conditions_location": {
        "caution": "2 mois de loyer",
        "avance": "1 mois de loyer",
        "frais_agence": "1 mois de loyer, une seule fois a la signature",
        "pieces_a_fournir": "Piece d'identite, justificatif de revenus ou contrat de travail",
        "duree_bail": "1 an renouvelable",
        "remarque": "Le loyer affiche est mensuel, en F CFA. Les charges sont en plus du loyer.",
    },
    "conseillers": CONSEILLERS,
    "hors_perimetre": "Reclamations, negociation de loyer et litiges sont traites uniquement par un conseiller humain.",
}

# creer la base de donnees sqlite
def creer(db_path: Path = DB_DEFAUT) -> Path:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    con.executescript(
        """
        CREATE TABLE biens (
            id TEXT PRIMARY KEY,
            type_bien TEXT NOT NULL CHECK (type_bien IN ('appartement','studio','villa','duplex')),
            quartier TEXT NOT NULL,
            quartier_norm TEXT NOT NULL,
            adresse TEXT NOT NULL,
            pieces INTEGER NOT NULL,
            surface_m2 INTEGER NOT NULL,
            loyer_fcfa INTEGER NOT NULL,
            charges_fcfa INTEGER NOT NULL,
            meuble INTEGER NOT NULL,
            disponibilite TEXT NOT NULL CHECK (disponibilite IN ('disponible','reserve','loue')),
            conseiller TEXT NOT NULL,
            equipements TEXT NOT NULL
        );
        CREATE INDEX idx_biens_quartier ON biens(quartier_norm);
        CREATE INDEX idx_biens_loyer ON biens(loyer_fcfa);
        CREATE TABLE agence (cle TEXT PRIMARY KEY, valeur TEXT);
        """
    )
    for i, (t, q, adr, p, s, loyer, ch, m, dispo, c, eq) in enumerate(BIENS, start=1):
        con.execute(
            "INSERT INTO biens VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"SK-{i:03d}", t, q, norme(q), adr, p, s, loyer, ch, m, dispo, CONSEILLERS[c - 1], eq),
        )
    con.execute("INSERT INTO agence VALUES ('infos', ?)", (json.dumps(INFOS_AGENCE, ensure_ascii=False),))
    con.commit()
    con.close()
    return db_path


if __name__ == "__main__":
    chemin = creer(Path(sys.argv[1]) if len(sys.argv) > 1 else DB_DEFAUT)
    print(f"Catalogue cree : {chemin} ({len(BIENS)} biens)")
