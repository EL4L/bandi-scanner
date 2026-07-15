"""Accesso Postgres (Neon): clienti, bandi, match_results."""

from __future__ import annotations

import json
import hashlib
import os
import re
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
REVIEW_STATUS_PENDING = "da_revisionare"
REVIEW_STATUS_VALIDATED = "validato"


class _PGConnection:
    """Adatta psycopg2 all'API usata nel codice esistente (conn.execute con placeholder '?')."""

    def __init__(self, raw_conn):
        self._conn = raw_conn

    def execute(self, sql: str, params: tuple = ()):
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
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
    data_costituzione: str | None = None,
    numero_dipendenti: int | None = None,
    forma_giuridica: str | None = None,
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO clienti (
                ragione_sociale, p_iva, codice_ateco, descrizione_attivita,
                regione, fatturato, dimensione_impresa, data_costituzione,
                numero_dipendenti, forma_giuridica
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                data_costituzione or None,
                numero_dipendenti or None,
                forma_giuridica.strip() if forma_giuridica else None,
            ),
        )
        new_id = int(cur.fetchone()["id"])
        conn.commit()
        return new_id


def list_clienti() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.ragione_sociale, c.p_iva, c.codice_ateco, c.descrizione_attivita,
                   c.regione, c.fatturato, c.dimensione_impresa, c.created_at,
                   c.data_costituzione, c.numero_dipendenti, c.forma_giuridica,
                   COALESCE(m.match_count, 0) AS match_count
            FROM clienti c
            LEFT JOIN (
                SELECT cliente_id, COUNT(*) AS match_count
                FROM match_results
                WHERE score > 0
                GROUP BY cliente_id
            ) m ON m.cliente_id = c.id
            ORDER BY LOWER(c.ragione_sociale)
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_cliente(cliente_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM clienti WHERE id = %s", (cliente_id,)
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
    data_costituzione: str | None = None,
    numero_dipendenti: int | None = None,
    forma_giuridica: str | None = None,
) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            """
            UPDATE clienti SET
                ragione_sociale = %s,
                p_iva = %s,
                codice_ateco = %s,
                descrizione_attivita = %s,
                regione = %s,
                fatturato = %s,
                dimensione_impresa = %s,
                data_costituzione = %s,
                numero_dipendenti = %s,
                forma_giuridica = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (
                ragione_sociale.strip(),
                p_iva.strip() or None,
                codice_ateco.strip() or None,
                descrizione_attivita.strip() or None,
                regione.strip(),
                fatturato,
                dimensione_impresa,
                data_costituzione or None,
                numero_dipendenti or None,
                forma_giuridica.strip() if forma_giuridica else None,
                cliente_id,
            ),
        )
        updated = cur.rowcount > 0
        conn.commit()
        return updated


def delete_cliente(cliente_id: int) -> bool:
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM clienti WHERE id = %s", (cliente_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        return deleted


def delete_bando(bando_id: int) -> bool:
    with get_connection() as conn:
        conn.execute("DELETE FROM match_results WHERE bando_id = %s", (bando_id,))
        cur = conn.execute("DELETE FROM bandi WHERE id = %s", (bando_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        return deleted


def compute_document_hash(text: str | None) -> str | None:
    """Hash stabile del testo estratto, indipendente da spazi e maiuscole."""
    if not isinstance(text, str):
        return None
    normalized = re.sub(r"\s+", " ", text).strip().casefold()
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def find_duplicate_bando_by_hash(document_hash: str | None) -> int | None:
    """Trova lo stesso documento prima di invocare il modello AI."""
    if not (document_hash or "").strip():
        return None
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM bandi WHERE document_hash = %s ORDER BY id DESC LIMIT 1",
            (document_hash,),
        ).fetchone()
    return int(row["id"]) if row else None


def attach_pdf_to_bando(
    bando_id: int,
    pdf_bytes: bytes | None,
    pdf_filename: str | None,
) -> bool:
    """Associa il PDF originale a un bando che non lo possiede ancora."""
    if not pdf_bytes or not pdf_bytes.startswith(b"%PDF"):
        return False
    filename = (pdf_filename or f"Bando_{bando_id}.pdf").strip()
    with get_connection() as conn:
        cur = conn.execute(
            """
            UPDATE bandi
            SET pdf_original = %s, pdf_filename = %s
            WHERE id = %s AND pdf_original IS NULL
            """,
            (pdf_bytes, filename, bando_id),
        )
        updated = cur.rowcount > 0
        conn.commit()
        return updated


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
                HAVING COUNT(*) > 1 AND LOWER(COALESCE(titolo, '')) <> ''
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
                HAVING COUNT(*) > 1 AND LOWER(TRIM(COALESCE(titolo, ''))) <> ''
                """
            ).fetchall()

        deleted = 0
        for row in rows:
            ids_to_delete = list(row["ids"])[1:]  # tieni il primo (id più alto)
            for did in ids_to_delete:
                conn.execute("DELETE FROM match_results WHERE bando_id = %s", (did,))
                conn.execute("DELETE FROM bandi WHERE id = %s", (did,))
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
                WHERE LOWER(COALESCE(titolo, '')) = LOWER(COALESCE(%s, ''))
                  AND LOWER(COALESCE(ente,   '')) = LOWER(COALESCE(%s, ''))
                ORDER BY id DESC
                LIMIT 1
                """,
                (titolo or "", ente or ""),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT id FROM bandi
                WHERE LOWER(TRIM(COALESCE(titolo, ''))) = LOWER(TRIM(COALESCE(%s, '')))
                ORDER BY id DESC
                LIMIT 1
                """,
                (titolo or "",),
            ).fetchone()
    return int(row["id"]) if row else None


def save_bando_from_json(
    data: dict[str, Any],
    scheda: str | None = None,
    review_status: str = REVIEW_STATUS_VALIDATED,
    null_percentage: float = 0.0,
    review_reasons: list[str] | None = None,
    document_hash: str | None = None,
    pdf_bytes: bytes | None = None,
    pdf_filename: str | None = None,
) -> int:
    """Salva estrazione bando. data = {"bando": {...}}. scheda = markdown pre-calcolato."""
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
                dimensione, contributo_max, json_completo, scheda_cached,
                review_status, null_percentage, review_reasons,
                document_hash, pdf_original, pdf_filename
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                scheda,
                review_status,
                float(null_percentage),
                json.dumps(review_reasons or [], ensure_ascii=False),
                document_hash,
                pdf_bytes,
                pdf_filename,
            ),
        )
        new_id = int(cur.fetchone()["id"])
        conn.commit()
        return new_id
