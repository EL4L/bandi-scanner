"""Inizializzazione schema SQLite (idempotente, non cancella dati esistenti)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "bandi.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS clienti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ragione_sociale TEXT NOT NULL,
    p_iva TEXT,
    codice_ateco TEXT,
    descrizione_attivita TEXT,
    regione TEXT,
    fatturato REAL,
    dimensione_impresa TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bandi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titolo TEXT,
    ente TEXT,
    data_scadenza TEXT,
    codici_ateco TEXT,
    regioni TEXT,
    dimensione TEXT,
    contributo_max REAL,
    json_completo TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS match_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL,
    bando_id INTEGER NOT NULL,
    score REAL NOT NULL,
    data_match TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (cliente_id) REFERENCES clienti(id) ON DELETE CASCADE,
    FOREIGN KEY (bando_id) REFERENCES bandi(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_match_cliente ON match_results(cliente_id);
CREATE INDEX IF NOT EXISTS idx_match_bando ON match_results(bando_id);
"""


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """Aggiunge colonne nuove su DB esistenti senza cancellare dati."""
    cols = {
        row[1] for row in conn.execute("PRAGMA table_info(clienti)").fetchall()
    }
    if "descrizione_attivita" not in cols:
        conn.execute(
            "ALTER TABLE clienti ADD COLUMN descrizione_attivita TEXT"
        )


def init_database(db_path: Path | None = None) -> Path:
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA_SQL)
        _migrate_schema(conn)
        conn.commit()
    return path


def main() -> None:
    path = init_database()
    print(f"Database inizializzato: {path}")


if __name__ == "__main__":
    main()
