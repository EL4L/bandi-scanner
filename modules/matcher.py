"""Abbinamento bandi / clienti, scheda sintetica e scoring."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from typing import Any

from modules.log_utils import log_error
from modules.schema import DIMENSIONE_IMPRESA_KEYS

# Pesi scoring (0–100): regione 30, ATECO 40, dimensione 20, fatturato 10.
WEIGHT_REGIONE = 30
WEIGHT_ATECO = 40
WEIGHT_DIMENSIONE = 20
WEIGHT_FATTURATO = 10

# Punteggi ATECO quando il bando ha solo attivita_ammesse (senza codici numerici).
SCORE_ATECO_ATTIVITA_INCERTO = 15
SCORE_ATECO_ATTIVITA_PARZIALE = 15
SCORE_ATECO_ATTIVITA_BUONO = 30

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)

_MESI_IT = (
    "gennaio",
    "febbraio",
    "marzo",
    "aprile",
    "maggio",
    "giugno",
    "luglio",
    "agosto",
    "settembre",
    "ottobre",
    "novembre",
    "dicembre",
)


def _unwrap_bando(bando: dict[str, Any]) -> dict[str, Any]:
    """Restituisce il dict interno 'bando' se presente."""
    inner = bando.get("bando")
    if isinstance(inner, dict):
        return inner
    return bando


def _norm_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _norm_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_norm_str(v) for v in value if _norm_str(v)]


def _ateco_prefix_two(code: str | None) -> str:
    """Primi due caratteri significativi del codice ATECO (es. '62' da '62.01')."""
    if not code:
        return ""
    c = _norm_str(code).replace(" ", "")
    if "." in c:
        return c.split(".", 1)[0][:2]
    return c[:2]


def _dimensioni_ammesse(bando: dict[str, Any]) -> list[str]:
    dim = bando.get("dimensione") or bando.get("dimensione_impresa")
    if isinstance(dim, str) and dim.strip():
        return [p.strip() for p in dim.split(",") if p.strip()]
    if isinstance(dim, dict):
        return [k for k in DIMENSIONE_IMPRESA_KEYS if dim.get(k)]
    if isinstance(dim, list):
        return [_norm_str(d) for d in dim if _norm_str(d)]
    return []


def _regioni_bando(bando: dict[str, Any]) -> list[str]:
    return _norm_list(bando.get("regioni") or bando.get("regioni_ammesse"))


def _codici_ateco_bando(bando: dict[str, Any]) -> list[str]:
    return _norm_list(
        bando.get("codici_ateco")
        or bando.get("codici_ateco_ammessi")
    )


def _attivita_ammesse_bando(bando: dict[str, Any]) -> list[str]:
    return _norm_list(bando.get("attivita_ammesse"))


def _tokenize(text: str) -> set[str]:
    """Token significativi (>= 4 caratteri) per overlap attività–descrizione cliente."""
    return {
        m.group(0).lower()
        for m in _TOKEN_RE.finditer(text)
        if len(m.group(0)) >= 4
    }


def _max_word_overlap(descrizione: str, attivita: list[str]) -> int:
    """Massimo numero di parole in comune tra descrizione cliente e una voce attività."""
    cliente_tokens = _tokenize(descrizione)
    if not cliente_tokens or not attivita:
        return 0
    best = 0
    for voce in attivita:
        common = len(cliente_tokens & _tokenize(voce))
        if common > best:
            best = common
    return best


def _bando_has_constraints(bando: dict[str, Any]) -> bool:
    """Return True if the bando contains any explicit constraints used for matching.

    We consider regioni, codici ATECO, attivita_ammesse, dimensione_impresa,
    contributo_max/fatturato_max or ateco_aperto_a_tutti=True as constraints. If
    none are present we treat the bando as 'no constraint info' and avoid
    giving maximal default scores.
    """
    if not isinstance(bando, dict):
        return False
    if bando.get("ateco_aperto_a_tutti") is True:
        return True
    if _codici_ateco_bando(bando):
        return True
    if _attivita_ammesse_bando(bando):
        return True
    if _regioni_bando(bando):
        return True
    if _dimensioni_ammesse(bando):
        return True
    if bando.get("contributo_max") is not None or bando.get("fatturato_max") is not None:
        return True
    return False


def bando_has_constraints(bando: dict[str, Any]) -> bool:
    """Public wrapper that returns True if the bando contains explicit constraints."""
    b = _unwrap_bando(bando if isinstance(bando, dict) else {})
    return _bando_has_constraints(b)


def get_score_breakdown(bando: dict[str, Any], cliente: dict[str, Any]) -> dict[str, int]:
    """Return a breakdown dict with individual contributions and total score.

    Keys: regione, ateco, dimensione, fatturato, total
    """
    b = _unwrap_bando(bando if isinstance(bando, dict) else {})
    c = cliente if isinstance(cliente, dict) else {}
    r = _score_regione(b, c)
    a = _score_ateco(b, c)
    d = _score_dimensione(b, c)
    f = _score_fatturato(b, c)
    total = max(0, min(100, int(r + a + d + f)))
    return {"regione": int(r), "ateco": int(a), "dimensione": int(d), "fatturato": int(f), "total": int(total)}


def bando_solo_attivita_ammesse(bando: dict[str, Any]) -> bool:
    """True se il bando vincola il settore solo tramite attivita_ammesse (no codici ATECO)."""
    b = _unwrap_bando(bando if isinstance(bando, dict) else {})
    if b.get("ateco_aperto_a_tutti") is True:
        return False
    if _codici_ateco_bando(b):
        return False
    return bool(_attivita_ammesse_bando(b))


def settore_da_verificare(bando: dict[str, Any], cliente: dict[str, Any]) -> bool:
    """True se il match sul settore è incerto e va controllato manualmente."""
    b = _unwrap_bando(bando if isinstance(bando, dict) else {})
    if not bando_solo_attivita_ammesse(b):
        return False
    desc = _norm_str(
        cliente.get("descrizione_attivita") or cliente.get("descrizione_attività")
    )
    if not desc:
        return True
    return _max_word_overlap(desc, _attivita_ammesse_bando(b)) < 2


def _score_attivita_ammesse(bando: dict[str, Any], cliente: dict[str, Any]) -> int:
    """Punteggio settore da attivita_ammesse e descrizione attività del cliente."""
    attivita = _attivita_ammesse_bando(bando)
    if not attivita:
        return 0
    desc = _norm_str(
        cliente.get("descrizione_attivita") or cliente.get("descrizione_attività")
    )
    if not desc:
        return SCORE_ATECO_ATTIVITA_INCERTO
    overlap = _max_word_overlap(desc, attivita)
    if overlap >= 2:
        return SCORE_ATECO_ATTIVITA_BUONO
    if overlap == 1:
        return SCORE_ATECO_ATTIVITA_PARZIALE
    return 0


def _score_regione(bando: dict[str, Any], cliente: dict[str, Any]) -> int:
    regioni = _regioni_bando(bando)
    if not regioni:
        return WEIGHT_REGIONE
    lowered = {r.lower() for r in regioni}
    if "tutte" in lowered:
        return WEIGHT_REGIONE
    cliente_regione = _norm_str(cliente.get("regione"))
    if not cliente_regione:
        return 0
    if cliente_regione.lower() in lowered:
        return WEIGHT_REGIONE
    return 0


def _score_ateco(bando: dict[str, Any], cliente: dict[str, Any]) -> int:
    if bando.get("ateco_aperto_a_tutti") is True:
        return WEIGHT_ATECO
    codici = _codici_ateco_bando(bando)
    attivita = _attivita_ammesse_bando(bando)
    codice_cliente = _norm_str(cliente.get("codice_ateco") or cliente.get("ateco"))

    if codici:
        if not codice_cliente:
            return 0
        cliente_lower = codice_cliente.lower()
        for cod in codici:
            if cod.lower() == cliente_lower:
                return WEIGHT_ATECO
        pref_cliente = _ateco_prefix_two(codice_cliente)
        if len(pref_cliente) >= 2:
            for cod in codici:
                if _ateco_prefix_two(cod) == pref_cliente:
                    return WEIGHT_ATECO // 2
        return 0

    if attivita:
        return _score_attivita_ammesse(bando, cliente)

    if not codice_cliente:
        return WEIGHT_ATECO
    return WEIGHT_ATECO


def _score_dimensione(bando: dict[str, Any], cliente: dict[str, Any]) -> int:
    ammesse = _dimensioni_ammesse(bando)
    # If the bando does not specify allowed sizes, do not award the
    # dimensione weight by default (previously returned full weight).
    # This avoids giving free points when the field is absent.
    if not ammesse:
        return 0
    dim_cliente = _norm_str(
        cliente.get("dimensione_impresa") or cliente.get("dimensione")
    )
    if not dim_cliente:
        return 0
    if dim_cliente.lower() in {d.lower() for d in ammesse}:
        return WEIGHT_DIMENSIONE
    return 0


def _score_fatturato(bando: dict[str, Any], cliente: dict[str, Any]) -> int:
    contributo_max = bando.get("contributo_max")
    fatturato_max = bando.get("fatturato_max")
    fatturato_cliente = cliente.get("fatturato")
    # If the bando does not specify any economic cap, do not award the
    # fatturato weight by default.
    if contributo_max is None and fatturato_max is None:
        return 0
    try:
        fat_cli = float(fatturato_cliente) if fatturato_cliente is not None else 0.0
    except (TypeError, ValueError):
        fat_cli = 0.0
    if fatturato_max is not None:
        try:
            if fat_cli <= float(fatturato_max):
                return WEIGHT_FATTURATO
        except (TypeError, ValueError):
            return WEIGHT_FATTURATO
    if contributo_max is not None:
        try:
            if fat_cli <= float(contributo_max) * 10:
                return WEIGHT_FATTURATO
        except (TypeError, ValueError):
            pass
        return WEIGHT_FATTURATO // 2
    return WEIGHT_FATTURATO


def calculate_score(bando: dict[str, Any], cliente: dict[str, Any]) -> int:
    """Calcola lo score di compatibilità bando–cliente (0–100)."""
    b = _unwrap_bando(bando if isinstance(bando, dict) else {})
    c = cliente if isinstance(cliente, dict) else {}
    total = (
        _score_regione(b, c)
        + _score_ateco(b, c)
        + _score_dimensione(b, c)
        + _score_fatturato(b, c)
    )
    return max(0, min(100, int(total)))


def run_matching_for_bando(bando_id: int, conn: sqlite3.Connection) -> None:
    """Esegue il matching di un bando con tutti i clienti e salva/aggiorna match_results."""
    try:
        row = conn.execute(
            "SELECT json_completo FROM bandi WHERE id = ?",
            (bando_id,),
        ).fetchone()
        if not row:
            log_error(f"run_matching_for_bando: bando {bando_id} non trovato")
            return

        payload = json.loads(row["json_completo"])
        bando_data = payload if isinstance(payload, dict) else {}

        # If the extracted bando is empty/invalid, don't treat it as "open to all"
        # (which would give maximal scores). Instead, set score 0 for all clients
        # and log the condition for manual inspection.
        inner = _unwrap_bando(bando_data)
        if not inner or not _bando_has_constraints(inner):
            log_error(
                f"run_matching_for_bando: bando {bando_id} vuoto o senza vincoli espliciti — imposto score 0 per tutti i clienti"
            )
            # Log a small diagnostic of the bando content for debugging
            try:
                log_error(f"bando {bando_id} content keys: {list(inner.keys())}")
            except Exception:
                pass
            clienti = conn.execute("SELECT * FROM clienti").fetchall()
            for cliente_row in clienti:
                cliente = dict(cliente_row)
                score = 0
                existing = conn.execute(
                    """
                    SELECT id FROM match_results
                    WHERE cliente_id = ? AND bando_id = ?
                    """,
                    (cliente["id"], bando_id),
                ).fetchone()
                if existing:
                    conn.execute(
                        """
                        UPDATE match_results
                        SET score = ?, data_match = datetime('now')
                        WHERE id = ?
                        """,
                        (score, existing["id"]),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO match_results (cliente_id, bando_id, score)
                        VALUES (?, ?, ?)
                        """,
                        (cliente["id"], bando_id, score),
                    )
            conn.commit()
            return

        clienti = conn.execute("SELECT * FROM clienti").fetchall()
        for cliente_row in clienti:
            cliente = dict(cliente_row)
            score = calculate_score(bando_data, cliente)
            existing = conn.execute(
                """
                SELECT id FROM match_results
                WHERE cliente_id = ? AND bando_id = ?
                """,
                (cliente["id"], bando_id),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE match_results
                    SET score = ?, data_match = datetime('now')
                    WHERE id = ?
                    """,
                    (score, existing["id"]),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO match_results (cliente_id, bando_id, score)
                    VALUES (?, ?, ?)
                    """,
                    (cliente["id"], bando_id, score),
                )
        conn.commit()
    except Exception as exc:
        log_error(f"run_matching_for_bando({bando_id}): {exc}")


def run_matching_for_all_bandi(conn: sqlite3.Connection) -> None:
    """Ricalcola il matching per tutti i bandi in archivio."""
    try:
        rows = conn.execute("SELECT id FROM bandi").fetchall()
        for row in rows:
            run_matching_for_bando(int(row["id"]), conn)
    except Exception as exc:
        log_error(f"run_matching_for_all_bandi: {exc}")


def format_scadenza_italiana(raw: str | None) -> str | None:
    """Formatta una data ISO in italiano (es. '30 giugno 2026')."""
    if not raw or not _norm_str(raw):
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            dt = datetime.strptime(_norm_str(raw), fmt)
            return f"{dt.day} {_MESI_IT[dt.month - 1]} {dt.year}"
        except ValueError:
            continue
    return _norm_str(raw)


def _format_euro(value: Any) -> str | None:
    if value is None:
        return None
    try:
        n = float(value)
        return f"€ {n:,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return None


def _chi_puo_accedere(bando: dict[str, Any]) -> str | None:
    parts: list[str] = []
    regioni = _regioni_bando(bando)
    if regioni:
        parts.append("**Regioni:** " + ", ".join(regioni))
    if bando.get("ateco_aperto_a_tutti") is True:
        parts.append("**ATECO:** aperto a tutti i settori")
    else:
        codici = _codici_ateco_bando(bando)
        if codici:
            parts.append("**ATECO ammessi:** " + ", ".join(codici))
        attivita = _norm_list(bando.get("attivita_ammesse"))
        if attivita:
            parts.append("**Attività:** " + ", ".join(attivita))
    dim = _dimensioni_ammesse(bando)
    if dim:
        parts.append("**Dimensioni impresa:** " + ", ".join(dim))
    if not parts:
        return None
    return "\n\n".join(parts)


def genera_scheda(bando: dict[str, Any]) -> str:
    """Genera la scheda markdown 'Bando in 1 minuto' dal JSON bando."""
    b = _unwrap_bando(bando if isinstance(bando, dict) else {})
    lines: list[str] = []

    titolo = _norm_str(b.get("titolo"))
    ente = _norm_str(b.get("ente"))
    if titolo:
        lines.append(f"# {titolo}")
    if ente:
        lines.append(f"**Ente:** {ente}")

    scadenza = format_scadenza_italiana(b.get("data_scadenza"))
    if scadenza:
        lines.append(f"**Scadenza:** {scadenza}")

    accesso = _chi_puo_accedere(b)
    if accesso:
        lines.append("## Chi può accedere\n\n" + accesso)

    contributo = _format_euro(b.get("contributo_max"))
    pct = b.get("percentuale_fondo_perduto")
    econ_parts: list[str] = []
    if contributo:
        econ_parts.append(f"**Contributo massimo:** {contributo}")
    if pct is not None:
        try:
            econ_parts.append(
                f"**Fondo perduto:** {float(pct):.0f}%"
                if float(pct) == int(float(pct))
                else f"**Fondo perduto:** {float(pct)}%"
            )
        except (TypeError, ValueError):
            pass
    if econ_parts:
        lines.append("## Contributi\n\n" + "\n\n".join(econ_parts))

    spese = _norm_list(b.get("spese_ammissibili"))
    if spese:
        lines.append("## Spese ammissibili\n\n" + "\n".join(f"- {s}" for s in spese))

    link = _norm_str(
        b.get("url_fonte")
        or b.get("link_fonte_ufficiale")
        or b.get("link_fonte")
    )
    if link:
        lines.append(f"## Fonte ufficiale\n\n[{link}]({link})")

    return "\n\n".join(lines) if lines else "*Scheda non disponibile — dati bando insufficienti.*"


def get_fonte_url(bando: dict[str, Any]) -> str | None:
    """URL fonte ufficiale se presente nel JSON."""
    b = _unwrap_bando(bando if isinstance(bando, dict) else {})
    link = _norm_str(
        b.get("url_fonte")
        or b.get("link_fonte_ufficiale")
        or b.get("link_fonte")
    )
    return link or None


def load_dashboard_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Carica match_results con join bando e cliente, ordinati per score decrescente."""
    rows = conn.execute(
        """
        SELECT
            mr.bando_id,
            mr.cliente_id,
            mr.score,
            mr.data_match,
            b.titolo AS bando_titolo,
            b.ente AS bando_ente,
            b.data_scadenza,
            b.json_completo,
            c.ragione_sociale AS cliente_nome,
            c.codice_ateco AS cliente_codice_ateco,
            c.descrizione_attivita AS cliente_descrizione_attivita
        FROM match_results mr
        JOIN bandi b ON b.id = mr.bando_id
        JOIN clienti c ON c.id = mr.cliente_id
        ORDER BY mr.score DESC, b.titolo COLLATE NOCASE
        """
    ).fetchall()
    return [dict(r) for r in rows]


def count_bandi(conn: sqlite3.Connection) -> int:
    """Numero di bandi salvati in archivio."""
    row = conn.execute("SELECT COUNT(*) AS n FROM bandi").fetchone()
    return int(row["n"]) if row else 0
