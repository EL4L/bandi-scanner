"""Abbinamento bandi / clienti, scheda sintetica e scoring."""
from __future__ import annotations
import json
import re
from datetime import datetime
from typing import Any
from modules.log_utils import log_error
from modules.schema import DIMENSIONE_IMPRESA_KEYS

WEIGHT_REGIONE = 30
WEIGHT_ATECO = 40
WEIGHT_DIMENSIONE = 20
WEIGHT_FATTURATO = 10
SCORE_ATECO_ATTIVITA_INCERTO = 15
SCORE_ATECO_ATTIVITA_PARZIALE = 15
SCORE_ATECO_ATTIVITA_BUONO = 30
_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_MESI_IT = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre")

def _unwrap_bando(bando: dict[str, Any]) -> dict[str, Any]:
    inner = bando.get("bando")
    return inner if isinstance(inner, dict) else bando

def _norm_str(value: Any) -> str:
    return str(value).strip() if value is not None else ""

def _norm_list(value: Any) -> list[str]:
    return [_norm_str(v) for v in value if _norm_str(v)] if isinstance(value, list) else []

def _ateco_prefix_two(code: str | None) -> str:
    if not code: return ""
    c = _norm_str(code).replace(" ", "")
    return c.split(".", 1)[0][:2] if "." in c else c[:2]

def _dimensioni_ammesse(bando: dict[str, Any]) -> list[str]:
    dim = bando.get("dimensione") or bando.get("dimensione_impresa")
    if isinstance(dim, str) and dim.strip(): return [p.strip() for p in dim.split(",") if p.strip()]
    if isinstance(dim, dict): return [k for k in DIMENSIONE_IMPRESA_KEYS if dim.get(k)]
    if isinstance(dim, list): return [_norm_str(d) for d in dim if _norm_str(d)]
    return []

def _regioni_bando(bando: dict[str, Any]) -> list[str]:
    return _norm_list(bando.get("regioni") or bando.get("regioni_ammesse"))

def _codici_ateco_bando(bando: dict[str, Any]) -> list[str]:
    return _norm_list(bando.get("codici_ateco") or bando.get("codici_ateco_ammessi"))

def _attivita_ammesse_bando(bando: dict[str, Any]) -> list[str]:
    return _norm_list(bando.get("attivita_ammesse"))

def _tokenize(text: str) -> set[str]:
    return {m.group(0).lower() for m in _TOKEN_RE.finditer(text) if len(m.group(0)) >= 4}

def _max_word_overlap(descrizione: str, attivita: list[str]) -> int:
    cliente_tokens = _tokenize(descrizione)
    if not cliente_tokens or not attivita: return 0
    return max((len(cliente_tokens & _tokenize(voce)) for voce in attivita), default=0)

def bando_solo_attivita_ammesse(bando: dict[str, Any]) -> bool:
    b = _unwrap_bando(bando if isinstance(bando, dict) else {})
    if b.get("ateco_aperto_a_tutti") is True or _codici_ateco_bando(b): return False
    return bool(_attivita_ammesse_bando(b))

def settore_da_verificare(bando: dict[str, Any], cliente: dict[str, Any]) -> bool:
    b = _unwrap_bando(bando if isinstance(bando, dict) else {})
    if not bando_solo_attivita_ammesse(b): return False
    desc = _norm_str(cliente.get("descrizione_attivita") or cliente.get("descrizione_attività"))
    if not desc: return True
    return _max_word_overlap(desc, _attivita_ammesse_bando(b)) < 2

def _score_attivita_ammesse(bando: dict[str, Any], cliente: dict[str, Any]) -> int:
    attivita = _attivita_ammesse_bando(bando)
    if not attivita: return 0
    desc = _norm_str(cliente.get("descrizione_attivita") or cliente.get("descrizione_attività"))
    if not desc: return SCORE_ATECO_ATTIVITA_INCERTO
    overlap = _max_word_overlap(desc, attivita)
    if overlap >= 2: return SCORE_ATECO_ATTIVITA_BUONO
    if overlap == 1: return SCORE_ATECO_ATTIVITA_PARZIALE
    return 0

def _score_regione(bando: dict[str, Any], cliente: dict[str, Any]) -> int:
    regioni = _regioni_bando(bando)
    if not regioni: return WEIGHT_REGIONE
    lowered = {r.lower() for r in regioni}
    if "tutte" in lowered or "tutta italia" in lowered: return WEIGHT_REGIONE
    cliente_regione = _norm_str(cliente.get("regione"))
    if not cliente_regione: return 0
    return WEIGHT_REGIONE if cliente_regione.lower() in lowered else 0

def _score_ateco(bando: dict[str, Any], cliente: dict[str, Any]) -> int:
    if bando.get("ateco_aperto_a_tutti") is True: return WEIGHT_ATECO
    codici = _codici_ateco_bando(bando)
    attivita = _attivita_ammesse_bando(bando)
    codice_cliente = _norm_str(cliente.get("codice_ateco") or cliente.get("ateco"))
    if codici:
        if not codice_cliente: return 0
        cliente_lower = codice_cliente.lower()
        if any(cod.lower() == cliente_lower for cod in codici): return WEIGHT_ATECO
        pref_cliente = _ateco_prefix_two(codice_cliente)
        if len(pref_cliente) >= 2 and any(_ateco_prefix_two(cod) == pref_cliente for cod in codici): return WEIGHT_ATECO // 2
        return 0
    if attivita: return _score_attivita_ammesse(bando, cliente)
    # Nessun dato settoriale estratto: ambiguo, punteggio parziale invece di pieno
    return WEIGHT_ATECO // 2

def _score_dimensione(bando: dict[str, Any], cliente: dict[str, Any]) -> int:
    ammesse = _dimensioni_ammesse(bando)
    if not ammesse: return WEIGHT_DIMENSIONE
    dim_cliente = _norm_str(cliente.get("dimensione_impresa") or cliente.get("dimensione"))
    if not dim_cliente: return 0
    return WEIGHT_DIMENSIONE if dim_cliente.lower() in {d.lower() for d in ammesse} else 0

def _score_fatturato(bando: dict[str, Any], cliente: dict[str, Any]) -> int:
    fatturato_max = bando.get("fatturato_max")
    if fatturato_max is None:
        return WEIGHT_FATTURATO
    try:
        fat_cli = float(cliente.get("fatturato") or 0)
        if fat_cli <= float(fatturato_max):
            return WEIGHT_FATTURATO
    except (TypeError, ValueError):
        return WEIGHT_FATTURATO
    return 0

def bando_has_constraints(payload: dict[str, Any]) -> bool:
    bando = _unwrap_bando(payload)
    ateco_aperto = bando.get("ateco_aperto_a_tutti", False)
    codici_ateco = _codici_ateco_bando(bando)
    regioni = _regioni_bando(bando)
    fatturato_max = bando.get("fatturato_max")
    dimensioni = _dimensioni_ammesse(bando)
    if codici_ateco and not ateco_aperto: return True
    if regioni and len(regioni) > 0 and "Tutta Italia" not in [r.title() for r in regioni]: return True
    if fatturato_max: return True
    if dimensioni and len(dimensioni) > 0 and len(dimensioni) < 4: return True
    return False

def calculate_score(bando: dict[str, Any], cliente: dict[str, Any]) -> int:
    b = _unwrap_bando(bando if isinstance(bando, dict) else {})
    c = cliente if isinstance(cliente, dict) else {}
    if not bando_has_constraints(bando): return 0
    total = _score_regione(b, c) + _score_ateco(b, c) + _score_dimensione(b, c) + _score_fatturato(b, c)
    return max(0, min(100, int(total)))

def get_score_breakdown(payload: dict[str, Any], cliente: dict[str, Any]) -> dict[str, int]:
    bando = _unwrap_bando(payload)
    score_regione = _score_regione(bando, cliente)
    score_ateco = _score_ateco(bando, cliente)
    score_dim = _score_dimensione(bando, cliente)
    score_fat = _score_fatturato(bando, cliente)
    totale = 0 if not bando_has_constraints(payload) else (score_regione + score_ateco + score_dim + score_fat)
    return {"regione": score_regione, "ateco": score_ateco, "dimensione": score_dim, "fatturato": score_fat, "total": max(0, min(100, int(totale)))}

def run_matching_for_bando(bando_id: int, conn: Any, soglia_minima: int = 0) -> None:
    try:
        row = conn.execute("SELECT json_completo FROM bandi WHERE id = ?", (bando_id,)).fetchone()
        if not row: return
        payload = json.loads(row["json_completo"])
        bando_data = payload if isinstance(payload, dict) else {}
        clienti = conn.execute("SELECT * FROM clienti").fetchall()
        for cliente_row in clienti:
            cliente = dict(cliente_row)
            score = calculate_score(bando_data, cliente)
            if score < soglia_minima: continue
            existing = conn.execute("SELECT id FROM match_results WHERE cliente_id = ? AND bando_id = ?", (cliente["id"], bando_id)).fetchone()
            if existing: conn.execute("UPDATE match_results SET score = ?, data_match = NOW() WHERE id = ?", (score, existing["id"]))
            else: conn.execute("INSERT INTO match_results (cliente_id, bando_id, score) VALUES (?, ?, ?)", (cliente["id"], bando_id, score))
        conn.commit()
    except Exception as exc: log_error(f"run_matching_for_bando({bando_id}): {exc}")

def run_matching_for_all_bandi(conn: Any, soglia_minima: int = 0) -> None:
    try:
        for row in conn.execute("SELECT id FROM bandi").fetchall():
            run_matching_for_bando(int(row["id"]), conn, soglia_minima=soglia_minima)
    except Exception as exc: log_error(f"run_matching_for_all_bandi: {exc}")

def format_scadenza_italiana(raw: str | None) -> str | None:
    if not raw or not _norm_str(raw): return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            dt = datetime.strptime(_norm_str(raw), fmt)
            return f"{dt.day} {_MESI_IT[dt.month - 1]} {dt.year}"
        except ValueError: continue
    return _norm_str(raw)

def giorni_alla_scadenza(data_scadenza: str | None) -> int | None:
    """Giorni interi alla scadenza (negativo se già scaduto), None se data assente o non parsabile."""
    if not data_scadenza or not _norm_str(data_scadenza): return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            dt = datetime.strptime(_norm_str(data_scadenza), fmt)
            return (dt.date() - datetime.today().date()).days
        except ValueError: continue
    return None

def _format_euro(value: Any) -> str | None:
    if value is None: return None
    try: return f"€ {float(value):,.0f}".replace(",", ".")
    except (TypeError, ValueError): return None

def _chi_puo_accedere(bando: dict[str, Any]) -> str | None:
    parts = []
    regioni = _regioni_bando(bando)
    if regioni: parts.append("**Regioni:** " + ", ".join(regioni))
    if bando.get("ateco_aperto_a_tutti") is True: parts.append("**ATECO:** aperto a tutti i settori")
    else:
        codici = _codici_ateco_bando(bando)
        if codici: parts.append("**ATECO ammessi:** " + ", ".join(codici))
        attivita = _norm_list(bando.get("attivita_ammesse"))
        if attivita: parts.append("**Attività:** " + ", ".join(attivita))
    dim = _dimensioni_ammesse(bando)
    if dim: parts.append("**Dimensioni impresa:** " + ", ".join(dim))
    return "\n\n".join(parts) if parts else None

def genera_scheda(bando: dict[str, Any]) -> str:
    b = _unwrap_bando(bando if isinstance(bando, dict) else {})
    lines = []
    titolo = _norm_str(b.get("titolo"))
    ente = _norm_str(b.get("ente"))
    if titolo: lines.append(f"# {titolo}")
    if ente: lines.append(f"**Ente:** {ente}")
    scadenza = format_scadenza_italiana(b.get("data_scadenza"))
    if scadenza: lines.append(f"**Scadenza:** {scadenza}")
    accesso = _chi_puo_accedere(b)
    if accesso: lines.append("## Chi può accedere\n\n" + accesso)
    contributo = _format_euro(b.get("contributo_max"))
    pct = b.get("percentuale_fondo_perduto")
    econ_parts = []
    if contributo: econ_parts.append(f"**Contributo massimo:** {contributo}")
    if pct is not None:
        try: econ_parts.append(f"**Fondo perduto:** {float(pct):.0f}%" if float(pct) == int(float(pct)) else f"**Fondo perduto:** {float(pct)}%")
        except (TypeError, ValueError): pass
    if econ_parts: lines.append("## Contributi\n\n" + "\n\n".join(econ_parts))
    spese = _norm_list(b.get("spese_ammissibili"))
    if spese: lines.append("## Spese ammissibili\n\n" + "\n".join(f"- {s}" for s in spese))
    link = _norm_str(b.get("url_fonte") or b.get("link_fonte_ufficiale") or b.get("link_fonte"))
    if link: lines.append(f"## Fonte ufficiale\n\n[{link}]({link})")
    return "\n\n".join(lines) if lines else "*Scheda non disponibile — dati bando insufficienti.*"

def genera_spiegazione_score(
    bando: dict[str, Any],
    cliente: dict[str, Any],
    score_dettaglio: dict[str, int],
) -> str:
    """Stringa leggibile che spiega il punteggio per ogni dimensione.

    Usa ✅ per criteri soddisfatti pienamente, ⚠️ per parziali, ❌ per non soddisfatti.
    """
    b = _unwrap_bando(bando if isinstance(bando, dict) else {})
    c = cliente if isinstance(cliente, dict) else {}
    parts: list[str] = []

    # Regione
    regioni = _regioni_bando(b)
    score_reg = score_dettaglio.get("regione", 0)
    if not regioni or any(r.lower() in ("tutte", "tutta italia") for r in regioni):
        parts.append("✅ Regione: nessun vincolo")
    elif score_reg == WEIGHT_REGIONE:
        parts.append(f"✅ Regione compatibile ({_norm_str(c.get('regione'))})")
    else:
        parts.append(f"❌ Regione non compatibile ({_norm_str(c.get('regione')) or 'N/D'})")

    # ATECO
    score_ateco_val = score_dettaglio.get("ateco", 0)
    codice_cliente = _norm_str(c.get("codice_ateco") or c.get("ateco"))
    if b.get("ateco_aperto_a_tutti") is True:
        parts.append("✅ Settore: aperto a tutti")
    elif score_ateco_val == WEIGHT_ATECO:
        parts.append(f"✅ Settore ammesso ({codice_cliente})")
    elif score_ateco_val > 0:
        parts.append(f"⚠️ Settore parzialmente compatibile ({codice_cliente})")
    else:
        parts.append(f"❌ Settore non ammesso ({codice_cliente or 'N/D'})")

    # Dimensione
    score_dim = score_dettaglio.get("dimensione", 0)
    ammesse = _dimensioni_ammesse(b)
    dim_cliente = _norm_str(c.get("dimensione_impresa") or c.get("dimensione"))
    if not ammesse:
        parts.append("✅ Dimensione: nessun vincolo")
    elif score_dim == WEIGHT_DIMENSIONE:
        parts.append(f"✅ Dimensione compatibile ({dim_cliente})")
    else:
        parts.append(f"❌ Dimensione non compatibile ({dim_cliente or 'N/D'})")

    # Fatturato
    score_fat = score_dettaglio.get("fatturato", 0)
    has_fat_constraint = b.get("fatturato_max") is not None or b.get("contributo_max") is not None
    if not has_fat_constraint:
        parts.append("✅ Fatturato: nessun vincolo")
    elif score_fat == WEIGHT_FATTURATO:
        parts.append("✅ Fatturato entro i limiti")
    elif score_fat > 0:
        parts.append("⚠️ Fatturato al limite")
    else:
        parts.append("❌ Fatturato fuori dai limiti")

    return " · ".join(parts)


def get_fonte_url(bando: dict[str, Any]) -> str | None:
    b = _unwrap_bando(bando if isinstance(bando, dict) else {})
    link = _norm_str(b.get("url_fonte") or b.get("link_fonte_ufficiale") or b.get("link_fonte"))
    return link or None

def load_dashboard_rows(conn: Any) -> list[dict[str, Any]]:
    rows = conn.execute(
        '''SELECT mr.bando_id, mr.cliente_id, mr.score, mr.data_match,
        b.titolo AS bando_titolo, b.ente AS bando_ente, b.data_scadenza, b.json_completo,
        c.ragione_sociale AS cliente_nome, c.codice_ateco AS cliente_codice_ateco, c.descrizione_attivita AS cliente_descrizione_attivita,
        c.regione AS cliente_regione, c.fatturato AS cliente_fatturato, c.dimensione_impresa AS cliente_dimensione_impresa
        FROM match_results mr JOIN bandi b ON b.id = mr.bando_id JOIN clienti c ON c.id = mr.cliente_id
        ORDER BY mr.score DESC, LOWER(b.titolo)'''
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["giorni_alla_scadenza"] = giorni_alla_scadenza(d.get("data_scadenza"))
        result.append(d)
    return result

def count_bandi(conn: Any) -> int:
    row = conn.execute("SELECT COUNT(*) AS n FROM bandi").fetchone()
    return int(row["n"]) if row else 0