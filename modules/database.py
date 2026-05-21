"""Accesso SQLite: clienti, bandi, match_results."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parents[1] / "db" / "bandi.db"

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


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_database() -> None:
    import sys

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from db.init_db import init_database

    init_database(DB_PATH)


def create_cliente(
    ragione_sociale: str,
    p_iva: str,
    codice_ateco: str,
    regione: str,
    fatturato: float,
    dimensione_impresa: str,
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO clienti (
                ragione_sociale, p_iva, codice_ateco, regione,
                fatturato, dimensione_impresa
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                ragione_sociale.strip(),
                p_iva.strip() or None,
                codice_ateco.strip() or None,
                regione.strip(),
                fatturato,
                dimensione_impresa,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_clienti() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, ragione_sociale, p_iva, codice_ateco, regione,
                   fatturato, dimensione_impresa, created_at
            FROM clienti
            ORDER BY ragione_sociale COLLATE NOCASE
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
) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            """
            UPDATE clienti SET
                ragione_sociale = ?,
                p_iva = ?,
                codice_ateco = ?,
                regione = ?,
                fatturato = ?,
                dimensione_impresa = ?,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                ragione_sociale.strip(),
                p_iva.strip() or None,
                codice_ateco.strip() or None,
                regione.strip(),
                fatturato,
                dimensione_impresa,
                cliente_id,
            ),
        )
        conn.commit()
        return cur.rowcount > 0


def delete_cliente(cliente_id: int) -> bool:
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM clienti WHERE id = ?", (cliente_id,))
        conn.commit()
        return cur.rowcount > 0


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
        conn.commit()
        return int(cur.lastrowid)
