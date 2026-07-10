from pathlib import Path

# Wiring shim for the Knowledge Research module (copied from NexusYTSync):
# points the module's raw-sqlite repository at QVault's SQLite database.
ROOT = Path(__file__).resolve().parents[3]

DB_PATH = ROOT / "database" / "qvault.db"
