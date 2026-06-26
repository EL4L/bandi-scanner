"""Accesso Postgres (Neon): clienti, bandi, match_results."""

from __future__ import annotations

import json
import os
from typing import Any

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

REGIONI_ITALIANE: tuple[str, ...] = (
    "Abruzzo",
    "Basilicata",
    "Calabria",
    "Campania",
    "Emilia-Romagna",
    "Friuli-Venezia Giulia",
    "Lazio",
    "Liguria",
    "Lombardia",
    "Marche",
    "Molise",
    "Piemonte",
    "Puglia",
    "Sardegna",
    "Sicilia",
    "Toscana",
    "Trentino-Alto Adige",
    "Umbria",
    "Valle d'Aosta",
    "Veneto",
)

DIMENSIONI_IMPRESA: tuple[str, ...] = ("micro", "piccola", "media", "grande")


class _PGConnection:
    """Adatta psycopg2 all'API usata nel codice esistente (conn.execute con placeholder '?')."""

    def __init__(self, raw_conn):
        self._conn = raw_conn

    def execute(self, sql: str, params: tuple = ()):
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql.replace("?", "%s"), params)
        return cur

    def commit(self) -> None:
        self._conn.commit()

    def __enter__(self) -> "_PGConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
        finally:
            self._conn.close()
        return False


def get_connection() -> _PGConnection:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL non configurata. Inserisci la connection string Neon nel file .env.")
    raw_conn = psycopg2.connect(DATABASE_URL)
    return _PGConnection(raw_conn)


def ensure_database() -> None:
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from db.init_db import init_database

    init_database()


def create_cliente(
    ragione_sociale: str,
    p_iva: str,
    codice_ateco: str,
    regione: str,
    fatturato: float,
    dimensione_impresa: str,
    descrizione_attivita: str = "",
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO clienti (
                ragione_sociale, p_iva, codice_ateco, descrizione_attivita,
                regione, fatturato, dimensione_impresa
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                ragione_sociale.strip(),
                p_iva.strip() or None,
                codice_ateco.strip() or None,
                descrizione_attivita.strip() or None,
                regione.strip(),
                fatturato,
                dimensione_impresa,
            ),
        )
        new_id = int(cur.fetchone()["id"])
        conn.commit()
        return new_id


def list_clienti() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, ragione_sociale, p_iva, codice_ateco, descrizione_attivita,
                   regione, fatturato, dimensione_impresa, created_at
            FROM clienti
            ORDER BY LOWER(ragione_sociale)
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_cliente(cliente_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM clienti WHERE id = ?", (cliente_id,)
        ).fetchone()
    return dict(row) if row else None


def update_cliente(
    cliente_id: int,
    ragione_sociale: str,
    p_iva: str,
    codice_ateco: str,
    regione: str,
    fatturato: float,
    dimensione_impresa: str,
    descrizione_attivita: str = "",
) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            """
            UPDATE clienti SET
                ragione_sociale = ?,
                p_iva = ?,
                codice_ateco = ?,
                descrizione_attivita = ?,
                regione = ?,
                fatturato = ?,
                dimensione_impresa = ?,
                updated_at = NOW()
            WHERE id = ?
            """,
            (
                ragione_sociale.strip(),
                p_iva.strip() or None,
                codice_ateco.strip() or None,
                descrizione_attivita.strip() or None,
                regione.strip(),
                fatturato,
                dimensione_impresa,
                cliente_id,
            ),
        )
        updated = cur.rowcount > 0
        conn.commit()
        return updated


def delete_cliente(cliente_id: int) -> bool:
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM clienti WHERE id = ?", (cliente_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        return deleted


def deduplica_bandi(strict: bool = True) -> int:
    """
    Rimuove duplicati mantenendo il bando con id più alto.
    Elimina prima i match_results collegati ai duplicati.

    strict=True  → duplicato = stesso titolo + stesso ente (case-insensitive)
    strict=False → duplicato = stesso titolo (case-insensitive, spazi rimossi),
                   indipendentemente dall'ente

    Restituisce il numero di bandi eliminati.
    """
    with get_connection() as conn:
        if strict:
            rows = conn.execute(
                """
                SELECT
                    LOWER(COALESCE(titolo, '')) AS titolo_key,
                    LOWER(COALESCE(ente, ''))   AS ente_key,
                    array_agg(id ORDER BY id DESC) AS ids
                FROM bandi
                GROUP BY LOWER(COALESCE(titolo, '')), LOWER(COALESCE(ente, ''))
                HAVING COUNT(*) > 1
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT
                    LOWER(TRIM(COALESCE(titolo, ''))) AS titolo_key,
                    array_agg(id ORDER BY id DESC) AS ids
                FROM bandi
                GROUP BY LOWER(TRIM(COALESCE(titolo, '')))
                HAVING COUNT(*) > 1
                """
            ).fetchall()

        deleted = 0
        for row in rows:
            ids_to_delete = list(row["ids"])[1:]  # tieni il primo (id più alto)
            for did in ids_to_delete:
                conn.execute("DELETE FROM match_results WHERE bando_id = ?", (did,))
                conn.execute("DELETE FROM bandi WHERE id = ?", (did,))
                deleted += 1

        conn.commit()
    return deleted


def find_duplicate_bando(
    titolo: str | None,
    ente: str | None,
    strict: bool = True,
) -> int | None:
    """
    Restituisce l'id del bando già presente, o None.

    strict=True  → controlla titolo + ente (case-insensitive)
    strict=False → controlla solo titolo (case-insensitive, spazi rimossi)
    """
    if not (titolo or "").strip():
        return None
    with get_connection() as conn:
        if strict:
            row = conn.execute(
                """
                SELECT id FROM bandi
                WHERE LOWER(COALESCE(titolo, '')) = LOWER(COALESCE(?, ''))
                  AND LOWER(COALESCE(ente,   '')) = LOWER(COALESCE(?, ''))
                ORDER BY id DESC
                LIMIT 1
                """,
                (titolo or "", ente or ""),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT id FROM bandi
                WHERE LOWER(TRIM(COALESCE(titolo, ''))) = LOWER(TRIM(COALESCE(?, '')))
                ORDER BY id DESC
                LIMIT 1
                """,
                (titolo or "",),
            ).fetchone()
    return int(row["id"]) if row else None


def save_bando_from_json(data: dict[str, Any]) -> int:
    """Salva estrazione bando (per Fase 3). data = {"bando": {...}}."""
    bando = data.get("bando") if isinstance(data.get("bando"), dict) else {}
    dim = bando.get("dimensione_impresa")
    if isinstance(dim, dict):
        dim_parts = [k for k in DIMENSIONI_IMPRESA if dim.get(k)]
        dimensione_str = ",".join(dim_parts) if dim_parts else None
    else:
        dimensione_str = None

    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO bandi (
                titolo, ente, data_scadenza, codici_ateco, regioni,
                dimensione, contributo_max, json_completo
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                bando.get("titolo"),
                bando.get("ente"),
                bando.get("data_scadenza"),
                json.dumps(bando.get("codici_ateco_ammessi") or [], ensure_ascii=False),
                json.dumps(bando.get("regioni_ammesse") or [], ensure_ascii=False),
                dimensione_str,
                bando.get("contributo_max"),
                json.dumps(data, ensure_ascii=False),
            ),
        )
        new_id = int(cur.fetchone()["id"])
        conn.commit()
        return new_id
