"""Configuration commune des tests : base SQLite et traces dans un dossier temporaire."""

import os
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

_TMP = Path(tempfile.mkdtemp(prefix="samaker-tests-"))
# avant tout import du serveur : il lit le chemin de la base a l'import
os.environ["CATALOGUE_DB_PATH"] = str(_TMP / "catalogue.db")
os.environ["TRACES_DIR"] = str(_TMP / "traces")
os.environ["MCP_SERVER_URL"] = "stdio"
