import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Literal
from mcp.server.fastmcp import FastMCP 

sys.path.insert(0, str(Path(__file__).parent))
from data.catalogue import DB_DEFAUT, creer, norme


DB_PATH = Path(os.getenv("CATALOGUE_DB", DB_DEFAUT))
LIMITE_MAX = 10

# connection avec le catalogue
def _connection() -> sqlite3.Connection:
    if not DB_PATH.exists():
        creer(DB_PATH)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection