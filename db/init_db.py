"""Inizializzazione schema Postgres/Neon (idempotente, non cancella dati esistenti)."""

from __future__ import annotations

import os

import psycopg2

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS clienti (
    id SERIAL PRIMARY KEY,
    ragione_sociale TEXT NOT NULL,
    p_iva TEXT,
    codice_ateco TEXT,
    descrizione_attivita TEXT,
    regione TEXT,
    fatturato REAL,
    dimensione_impresa TEXT NOT NULL,
    data_costituzione DATE,
    numero_dipendenti INTEGER,
    forma_giuridica TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bandi (
    id SERIAL PRIMARY KEY,
    titolo TEXT,
    ente TEXT,
    data_scadenza TEXT,
    codici_ateco TEXT,
    regioni TEXT,
    dimensione TEXT,
    contributo_max REAL,
    json_completo TEXT NOT NULL,
    scheda_cached TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS match_results (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER NOT NULL,
    bando_id INTEGER NOT NULL,
    score REAL NOT NULL,
    data_match TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (cliente_id) REFERENCES clienti(id) ON DELETE CASCADE,
    FOREIGN KEY (bando_id) REFERENCES bandi(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_match_cliente ON match_results(cliente_id);
CREATE INDEX IF NOT EXISTS idx_match_bando ON match_results(bando_id);
"""


def _migrate_schema(conn) -> None:
    """Aggiunge colonne nuove su DB esistenti senza cancellare dati."""
    cur = conn.cursor()
    cur.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'clienti'"
    )
    cols = {row[0] for row in cur.fetchall()}
    if "descrizione_attivita" not in cols:
        cur.execute("ALTER TABLE clienti ADD COLUMN descrizione_attivita TEXT")
    if "data_costituzione" not in cols:
        cur.execute("ALTER TABLE clienti ADD COLUMN data_costituzione DATE")
    if "numero_dipendenti" not in cols:
        cur.execute("ALTER TABLE clienti ADD COLUMN numero_dipendenti INTEGER")
    if "forma_giuridica" not in cols:
        cur.execute("ALTER TABLE clienti ADD COLUMN forma_giuridica TEXT")

    cur.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'bandi'"
    )
    bandi_cols = {row[0] for row in cur.fetchall()}
    if "scheda_cached" not in bandi_cols:
        cur.execute("ALTER TABLE bandi ADD COLUMN scheda_cached TEXT")


def init_database(database_url: str | None = None) -> None:
    url = database_url or os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL non configurata. Inserisci la connection string Neon nel file .env.")
    with psycopg2.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
        _migrate_schema(conn)
        conn.commit()


def main() -> None:
    init_database()
    print("Database Neon inizializzato.")


if __name__ == "__main__":
    main()
