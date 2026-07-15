import csv
import io
import json
import logging
import os
import re
import threading
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import urlparse

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from modules.database import (
    DIMENSIONI_IMPRESA,
    REGIONI_ITALIANE,
    REVIEW_STATUS_PENDING,
    REVIEW_STATUS_VALIDATED,
    attach_pdf_to_bando,
    create_cliente,
    deduplica_bandi,
    delete_bando,
    delete_cliente,
    ensure_database,
    compute_document_hash,
    find_duplicate_bando,
    find_duplicate_bando_by_hash,
    get_cliente,
    get_connection,
    list_clienti,
    save_bando_from_json,
    update_cliente,
)
from modules.document_relevance import classify_non_compatible_document
from modules.matcher import (
    bando_has_constraints,
    check_ammissibilita,
    count_bandi,
    format_scadenza_italiana,
    genera_scheda,
    genera_spiegazione_score,
    get_fonte_url,
    get_score_breakdown,
    giorni_alla_scadenza,
    load_dashboard_rows,
    run_matching_for_all_bandi,
    valida_coerenza_dimensione,
    run_matching_for_bando,
    settore_da_verificare,
)
from modules.extractor import (
    EmptyPDFException,
    PDFInvalidoException,
    PDFTroppoGrandeException,
    calcola_urgenza,
    extract_bando_data,
    extract_text_from_pdf,
)
from modules.log_utils import log_error, log_prompt_run
from modules.validator import fields_status, validate_bando
from modules.url_extractor import (
    InvalidUrlException,
    extract_text_from_html,
    fetch_url_safely,
)

ROOT = Path(__file__).resolve().parent
TEMP_DIR = ROOT / "temp"
TEMP_DIR.mkdir(exist_ok=True)
FRONTEND_DIST = ROOT / "frontend" / "dist"

app = FastAPI(title="Bandi Scanner AI")


@app.on_event("startup")
def on_startup() -> None:
    ensure_database()


# ---------------------------------------------------------------------------
# Autenticazione (API key statica) e rate limiting — audit D-3
# ---------------------------------------------------------------------------
# App ad uso interno senza login: una singola chiave condivisa via env,
# verificata su tutte le rotte /api/* (tranne /api/health, usato per il
# monitoraggio uptime). Non sostituisce un'autenticazione vera per-utente
# (vedi Fase 4 della roadmap): ferma l'abuso casuale di chi trova l'URL
# pubblico, non un attaccante che ispeziona il bundle JS del frontend, dove
# la chiave è necessariamente presente per poter chiamare le API.
APP_API_KEY = os.environ.get("APP_API_KEY", "").strip()


def verify_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    api_key_qs: str | None = Query(default=None, alias="api_key"),
) -> None:
    """Verifica la API key statica. Accetta sia l'header X-API-Key (chiamate
    fetch) sia il parametro ?api_key= in query string, necessario per i link
    di download diretti (<a href download>), su cui il browser non allega
    header custom."""
    if not APP_API_KEY:
        raise HTTPException(status_code=500, detail="Server non configurato: APP_API_KEY mancante.")
    fornita = x_api_key or api_key_qs
    if fornita != APP_API_KEY:
        raise HTTPException(status_code=401, detail="Non autorizzato: API key mancante o non valida.")


# Rate limit in-process (per IP) sulle chiamate di estrazione, per contenere
# l'uso di credito LLM in caso di abuso automatizzato. Contatore in memoria:
# si azzera ad ogni riavvio/redeploy e non è condiviso tra più worker o
# istanze — adeguato alla scala attuale (un solo processo su Render free).
ESTRAZIONE_RATE_LIMIT_MAX = int(os.environ.get("ESTRAZIONE_RATE_LIMIT_MAX", "10"))
ESTRAZIONE_RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("ESTRAZIONE_RATE_LIMIT_WINDOW_SECONDS", "3600"))
_rate_limit_lock = threading.Lock()
_rate_limit_hits: dict[str, deque] = defaultdict(deque)


def rate_limit_estrazione(request: Request) -> None:
    ip = request.client.host if request.client else "sconosciuto"
    now = time.time()
    with _rate_limit_lock:
        hits = _rate_limit_hits[ip]
        while hits and now - hits[0] > ESTRAZIONE_RATE_LIMIT_WINDOW_SECONDS:
            hits.popleft()
        if len(hits) >= ESTRAZIONE_RATE_LIMIT_MAX:
            raise HTTPException(status_code=429, detail="Troppe richieste di estrazione. Riprova più tardi.")
        hits.append(now)


def get_color_class(score: int) -> str:
    if score > 70:
        return "circle-green"
    if score >= 40:
        return "circle-yellow"
    return "circle-red"


def score_badge_class(score: int) -> str:
    if score > 70:
        return "match-score-high"
    if score >= 40:
        return "match-score-mid"
    return "match-score-low"


P_IVA_RE = re.compile(r"\d{11}")
ATECO_RE = re.compile(r"\d{2}\.\d{2}(?:\.\d{2})?")


def _validate_cliente_form(form_values: dict) -> list[str]:
    errori = []
    if not form_values["ragione_sociale"].strip():
        errori.append("La ragione sociale è obbligatoria.")

    p_iva = form_values["p_iva"].strip()
    if not p_iva:
        errori.append("La Partita IVA è obbligatoria.")
    elif not P_IVA_RE.fullmatch(p_iva):
        errori.append("La Partita IVA non è valida. Deve contenere esattamente 11 numeri (niente lettere o spazi).")

    codice_ateco = form_values["codice_ateco"].strip()
    if not codice_ateco:
        errori.append("Il Codice ATECO è obbligatorio.")
    elif not ATECO_RE.fullmatch(codice_ateco):
        errori.append("Il Codice ATECO non è valido. Usa il formato corretto, es: 62.01 o 62.01.12")

    try:
        fatturato = float(form_values["fatturato"]) if form_values.get("fatturato") not in (None, "") else None
    except (TypeError, ValueError):
        fatturato = None
    errori.extend(valida_coerenza_dimensione(
        form_values.get("dimensione_impresa"),
        fatturato,
        form_values.get("numero_dipendenti"),
    ))

    return errori


# ---------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------

def _build_export_rows(rows: list[dict]) -> list[dict]:
    export_rows = []
    for r in rows:
        try:
            payload = json.loads(r["json_completo"])
        except Exception:
            payload = {}

        cliente_row = {
            "id": r.get("cliente_id"), "ragione_sociale": r.get("cliente_nome"),
            "codice_ateco": r.get("cliente_codice_ateco"), "regione": r.get("cliente_regione"),
            "fatturato": r.get("cliente_fatturato"), "dimensione_impresa": r.get("cliente_dimensione_impresa"),
        }
        try:
            bd = get_score_breakdown(payload, cliente_row)
        except Exception:
            bd = {"total": 0, "ateco": 0, "regione": 0, "dimensione": 0, "fatturato": 0}

        export_rows.append({
            "cliente": r.get("cliente_nome", "N/D"),
            "bando": r.get("bando_titolo") or f"Bando #{r.get('bando_id')}",
            "score_totale": int(r.get("score", 0)),
            "score_regione": bd.get("regione", 0),
            "score_ateco": bd.get("ateco", 0),
            "score_dimensione": bd.get("dimensione", 0),
            "score_fatturato": bd.get("fatturato", 0),
        })
    return export_rows


def _parse_review_reasons(value: object) -> list[str]:
    """Normalizza i motivi di revisione salvati come JSON testuale."""
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return [value.strip()]
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    return []


def _review_reasons_from_validation(validation: dict) -> list[str]:
    warnings = validation.get("warnings") or []
    reasons = [
        str(warning).strip()
        for warning in warnings
        if isinstance(warning, str)
        and (
            "revisionare manualmente" in warning.lower()
            or warning.startswith("RF-007:")
        )
    ]
    if reasons:
        return list(dict.fromkeys(reasons))
    gaps = validation.get("critical_gaps") or []
    return [f"Campo critico mancante: {gap}" for gap in gaps]


def _with_review_disclaimer(
    scheda: str,
    review_status: str,
    null_percentage: float | int | None,
) -> str:
    if review_status != REVIEW_STATUS_PENDING:
        return scheda
    percentage = float(null_percentage or 0)
    return (
        "# ⚠️ Scheda in revisione\n\n"
        f"**Estrazione incompleta ({percentage:.0f}% di campi nulli). "
        "Il matching è sospeso e questa scheda non va condivisa senza una verifica manuale.**\n\n"
        "---\n\n"
        + scheda
    )


def _scheda_or_cached(payload: dict, scheda_cached: str | None) -> str:
    """Rigenera la scheda on-read (giorni/urgenza non devono fossilizzarsi in cache).
    Usa scheda_cached solo come fallback se la generazione fallisce."""
    try:
        return genera_scheda(payload)
    except Exception:
        return scheda_cached or genera_scheda({})


def _dedupe_cards(cards: list[dict]) -> tuple[list[dict], int]:
    """Raggruppa le card per coppia (titolo, ente) case-insensitive, fondendo i match.

    La dedup lato client confrontava solo titolo+ente sulle card già costruite,
    ma non fondeva i match: un cliente con match solo sul duplicato scartato
    spariva del tutto dalla dashboard, mentre le KPI restavano calcolate sulle
    card raw. Qui la card mantenuta è quella con id più alto; i match dei
    duplicati vengono uniti a quelli della card mantenuta (per cliente,
    tenendo lo score più alto) (ROADMAP #11).
    """
    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for card in cards:
        key = f"{(card['titolo'] or '').strip().lower()}|||{(card['ente'] or '').strip().lower()}"
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(card)

    merged_cards = []
    duplicates_count = 0
    for key in order:
        group = groups[key]
        duplicates_count += len(group) - 1
        primary = max(group, key=lambda c: c["id"])
        if len(group) > 1:
            matches_by_cliente: dict[str, dict] = {}
            for card in group:
                for m in card["matches"]:
                    nome = m.get("nome")
                    existing = matches_by_cliente.get(nome)
                    if not existing or m["score"] > existing["score"]:
                        matches_by_cliente[nome] = m
            merged_matches = sorted(matches_by_cliente.values(), key=lambda m: m["score"], reverse=True)
            primary = dict(primary)
            primary["matches"] = merged_matches
            eligible_scores = [
                m["score"] for m in merged_matches
                if m.get("ammissibilita", {}).get("ammissibile") is True
                and m.get("breakdown", {}).get("status") != "da_verificare"
            ]
            primary["max_score"] = max(eligible_scores, default=0)
            primary["nessun_cliente_ammissibile"] = bool(merged_matches) and all(
                m.get("ammissibilita", {}).get("ammissibile") is False
                for m in merged_matches
            )
            primary["color_class"] = get_color_class(primary["max_score"])
        if primary.get("review_status") == REVIEW_STATUS_PENDING:
            primary = dict(primary)
            primary["matches"] = []
            primary["max_score"] = 0
            primary["raw_max_score"] = 0
            primary["nessun_cliente_ammissibile"] = False
            primary["color_class"] = get_color_class(0)
        merged_cards.append(primary)

    merged_cards.sort(key=lambda c: c["max_score"], reverse=True)
    return merged_cards, duplicates_count


def _dashboard_payload() -> dict:
    with get_connection() as conn:
        n_bandi = count_bandi(conn)
        rows = load_dashboard_rows(conn)
        all_bandi_rows = conn.execute(
            """
            SELECT id, titolo, ente, data_scadenza, json_completo, scheda_cached,
                   review_status, null_percentage, review_reasons,
                   (pdf_original IS NOT NULL) AS has_pdf
            FROM bandi
            ORDER BY id DESC
            """
        ).fetchall()

    export_rows = _build_export_rows(rows) if rows else []

    by_bando: dict[int, dict] = {
        int(row["id"]): {
            "id": int(row["id"]),
            "titolo": row["titolo"] or f"Bando #{row['id']}",
            "ente": row["ente"],
            "data_scadenza": row["data_scadenza"],
            "json_completo": row["json_completo"],
            "scheda_cached": row.get("scheda_cached"),
            "has_pdf": bool(row.get("has_pdf")),
            "review_status": row.get("review_status") or REVIEW_STATUS_VALIDATED,
            "null_percentage": float(row.get("null_percentage") or 0),
            "review_reasons": _parse_review_reasons(row.get("review_reasons")),
            "matches": [],
            "max_score": 0,
        }
        for row in (dict(item) for item in all_bandi_rows)
    }
    for row in rows or []:
        bid = row["bando_id"]
        if bid not in by_bando:
            by_bando[bid] = {
                "id": bid,
                "titolo": row["bando_titolo"] or f"Bando #{bid}",
                "ente": row["bando_ente"],
                "data_scadenza": row["data_scadenza"],
                "json_completo": row["json_completo"],
                "scheda_cached": row.get("scheda_cached"),
                "has_pdf": bool(row.get("has_pdf")),
                "review_status": row.get("review_status") or REVIEW_STATUS_VALIDATED,
                "null_percentage": float(row.get("null_percentage") or 0),
                "review_reasons": _parse_review_reasons(row.get("review_reasons")),
                "matches": [],
                "max_score": row["score"],
            }
        by_bando[bid]["matches"].append(row)
        by_bando[bid]["max_score"] = max(by_bando[bid]["max_score"], row["score"])

    cards = []
    for bid in sorted(by_bando.keys(), key=lambda x: by_bando[x]["max_score"], reverse=True):
        info = by_bando[bid]
        max_sc = int(info["max_score"])
        try:
            payload = json.loads(info["json_completo"])
        except Exception:
            payload = {}
        bando_payload = payload.get("bando", {}) if isinstance(payload, dict) else {}
        review_status = info.get("review_status") or REVIEW_STATUS_VALIDATED

        valore_contributo = bando_payload.get("contributo_max")
        contributo_max = f"€ {valore_contributo:,.0f}" if isinstance(valore_contributo, (int, float)) else "N/D"

        scadenza_grezza = info.get("data_scadenza")
        scad_fmt = format_scadenza_italiana(scadenza_grezza) or scadenza_grezza
        if not scad_fmt or str(scad_fmt).strip().lower() in ["none", "null", ""]:
            scad_fmt = "N/D"

        matches = []
        for m in sorted(info["matches"], key=lambda x: x["score"], reverse=True):
            score_cliente = int(m["score"])
            cliente_row = {
                "id": m.get("cliente_id"), "ragione_sociale": m.get("cliente_nome"),
                "codice_ateco": m.get("cliente_codice_ateco"), "regione": m.get("cliente_regione"),
                "fatturato": m.get("cliente_fatturato"), "dimensione_impresa": m.get("cliente_dimensione_impresa"),
                "descrizione_attivita": m.get("cliente_descrizione_attivita"),
                "data_costituzione": m.get("cliente_data_costituzione"),
                "numero_dipendenti": m.get("cliente_numero_dipendenti"),
                "forma_giuridica": m.get("cliente_forma_giuridica"),
            }
            try:
                bd = get_score_breakdown(payload, cliente_row)
                bd_error = None
            except Exception as e:
                bd = {"total": 0, "ateco": 0, "regione": 0, "dimensione": 0, "fatturato": 0, "status": "ok"}
                bd_error = str(e)

            cliente_match = {"codice_ateco": m.get("cliente_codice_ateco"), "descrizione_attivita": m.get("cliente_descrizione_attivita")}
            try:
                spiegazione = genera_spiegazione_score(payload, cliente_row, bd)
            except Exception:
                spiegazione = None

            try:
                ammissibilita = check_ammissibilita(payload, cliente_row)
            except Exception:
                # #2 (audit Fable): NON fail-open. Un'eccezione nel controllo di
                # esclusione non deve mai tradursi in "ammissibile" silenzioso —
                # per uno strumento il cui valore è filtrare i clienti non
                # eleggibili, un bug qui non può produrre un falso via libera.
                ammissibilita = {
                    "ammissibile": None,
                    "motivi_esclusione": [],
                    "criteri_verificati": [],
                    "errore": True,
                }

            matches.append({
                "cliente_id": m.get("cliente_id"),
                "nome": m["cliente_nome"],
                "score": score_cliente,
                "score_badge_class": score_badge_class(score_cliente),
                "breakdown": bd,
                "breakdown_error": bd_error,
                "settore_da_verificare": settore_da_verificare(payload, cliente_match),
                "discrepanza": score_cliente != int(bd["total"]),
                "spiegazione_score": spiegazione,
                "ammissibilita": ammissibilita,
            })

        eligible_scores = [
            match["score"] for match in matches
            if match.get("ammissibilita", {}).get("ammissibile") is True
            and match.get("breakdown", {}).get("status") != "da_verificare"
        ]
        display_max_score = max(eligible_scores, default=0)
        nessun_cliente_ammissibile = bool(matches) and all(
            match.get("ammissibilita", {}).get("ammissibile") is False
            for match in matches
        )

        scadenza_grezza_card = info.get("data_scadenza")
        cards.append({
            "id": bid,
            "titolo": info["titolo"],
            "ente": info["ente"],
            "contributo_max": contributo_max,
            "contributo_max_valore": valore_contributo if isinstance(valore_contributo, (int, float)) else None,
            "scadenza": scad_fmt,
            "giorni_alla_scadenza": giorni_alla_scadenza(scadenza_grezza_card),
            "urgenza": calcola_urgenza(scadenza_grezza_card),
            "max_score": display_max_score,
            "raw_max_score": max_sc,
            "nessun_cliente_ammissibile": nessun_cliente_ammissibile,
            "color_class": get_color_class(display_max_score),
            "has_constraints": bando_has_constraints(payload),
            "matches": matches if review_status == REVIEW_STATUS_VALIDATED else [],
            "scheda": _scheda_or_cached(payload, info.get("scheda_cached")),
            "fonte_url": get_fonte_url(payload),
            "has_pdf": info["has_pdf"],
            "review_status": review_status,
            "null_percentage": float(info.get("null_percentage") or 0),
            "review_reasons": info.get("review_reasons") or [],
        })

    cards, duplicates_count = _dedupe_cards(cards)

    return {
        "n_bandi": n_bandi,
        "totale_abbinamenti": len(rows) if rows else 0,
        "has_export_data": bool(export_rows),
        "cards": cards,
        "duplicates_count": duplicates_count,
    }


@app.get("/api/dashboard", dependencies=[Depends(verify_api_key)])
def api_dashboard():
    return _dashboard_payload()


@app.get("/api/dashboard/bandi/{bando_id}", dependencies=[Depends(verify_api_key)])
def api_dashboard_bando_detail(bando_id: int):
    """Dettaglio analitico leggero: dati strutturati del bando e confronto con
    tutti i clienti. Rimane separato dalla lista dashboard per non trasferire
    fonti ed esclusioni complete per ogni card."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, titolo, ente, data_scadenza, json_completo, scheda_cached,
                   review_status, null_percentage, review_reasons,
                   (pdf_original IS NOT NULL) AS has_pdf
            FROM bandi
            WHERE id = %s
            """,
            (bando_id,),
        ).fetchone()

    if not row:
        return JSONResponse(status_code=404, content={"detail": "Bando non trovato"})

    record = dict(row)
    try:
        payload = json.loads(record["json_completo"])
    except Exception:
        return JSONResponse(status_code=500, content={"detail": "JSON bando non valido"})

    bando_data = payload.get("bando", {}) if isinstance(payload, dict) else {}
    if not isinstance(bando_data, dict):
        bando_data = {}

    review_status = record.get("review_status") or REVIEW_STATUS_VALIDATED
    clienti_match = []
    clienti_da_analizzare = list_clienti() if review_status == REVIEW_STATUS_VALIDATED else []
    for cliente in clienti_da_analizzare:
        try:
            breakdown = get_score_breakdown(payload, cliente)
            breakdown_error = None
        except Exception as exc:
            breakdown = {
                "total": 0, "ateco": 0, "regione": 0,
                "dimensione": 0, "fatturato": 0, "status": "ok",
            }
            breakdown_error = str(exc)

        try:
            ammissibilita = check_ammissibilita(payload, cliente)
        except Exception:
            ammissibilita = {
                "ammissibile": None,
                "motivi_esclusione": [],
                "criteri_verificati": [],
                "errore": True,
            }

        try:
            spiegazione = genera_spiegazione_score(payload, cliente, breakdown)
        except Exception:
            spiegazione = None

        clienti_match.append({
            "id": cliente.get("id"),
            "ragione_sociale": cliente.get("ragione_sociale"),
            "codice_ateco": cliente.get("codice_ateco"),
            "regione": cliente.get("regione"),
            "dimensione_impresa": cliente.get("dimensione_impresa"),
            "fatturato": cliente.get("fatturato"),
            "score": int(breakdown.get("total", 0)),
            "breakdown": breakdown,
            "breakdown_error": breakdown_error,
            "ammissibilita": ammissibilita,
            "spiegazione_score": spiegazione,
        })

    clienti_match.sort(
        key=lambda item: (
            item.get("ammissibilita", {}).get("ammissibile") is True,
            item.get("breakdown", {}).get("status") != "da_verificare",
            item.get("score", 0),
        ),
        reverse=True,
    )

    raw_scadenza = record.get("data_scadenza") or bando_data.get("data_scadenza")
    return {
        "bando": {
            "id": record["id"],
            "titolo": record.get("titolo") or bando_data.get("titolo") or f"Bando #{bando_id}",
            "ente": record.get("ente") or bando_data.get("ente"),
            "scadenza": format_scadenza_italiana(raw_scadenza),
            "giorni_alla_scadenza": giorni_alla_scadenza(raw_scadenza),
            "urgenza": calcola_urgenza(raw_scadenza),
            "fonte_url": get_fonte_url(payload),
            "has_pdf": bool(record.get("has_pdf")),
            "scheda": _scheda_or_cached(payload, record.get("scheda_cached")),
            "dati": bando_data,
            "review_status": review_status,
            "null_percentage": float(record.get("null_percentage") or 0),
            "review_reasons": _parse_review_reasons(record.get("review_reasons")),
        },
        "clienti": clienti_match,
    }


class DeduplicaRequest(BaseModel):
    strict: bool = True


@app.post("/api/bandi/deduplica", dependencies=[Depends(verify_api_key)])
def api_deduplica_bandi(body: DeduplicaRequest = DeduplicaRequest()):
    try:
        eliminati = deduplica_bandi(strict=body.strict)
        if eliminati > 0:
            with get_connection() as conn:
                run_matching_for_all_bandi(conn)
        return {"status": "ok", "eliminati": eliminati, "strict": body.strict}
    except Exception as exc:
        log_error(f"api_deduplica_bandi: {exc}")
        return JSONResponse(status_code=500, content={"status": "error", "detail": "Deduplica non riuscita. Riprova."})


@app.post("/api/bandi/recalc", dependencies=[Depends(verify_api_key)])
def api_recalc_matches():
    try:
        with get_connection() as conn:
            run_matching_for_all_bandi(conn)
        return {"status": "ok"}
    except Exception as exc:
        log_error(f"api_recalc_matches: {exc}")
        return JSONResponse(status_code=500, content={"status": "error", "detail": "Ricalcolo dei match non riuscito. Riprova."})


@app.get("/api/bandi", dependencies=[Depends(verify_api_key)])
def api_bandi_list():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, titolo, ente, data_scadenza, contributo_max, regioni,
                   review_status, null_percentage, review_reasons,
                   (pdf_original IS NOT NULL) AS has_pdf
            FROM bandi
            ORDER BY id DESC
            """
        ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["urgenza"] = calcola_urgenza(d.get("data_scadenza"))
        d["giorni_alla_scadenza"] = giorni_alla_scadenza(d.get("data_scadenza"))
        d["review_status"] = d.get("review_status") or REVIEW_STATUS_VALIDATED
        d["null_percentage"] = float(d.get("null_percentage") or 0)
        d["review_reasons"] = _parse_review_reasons(d.get("review_reasons"))
        result.append(d)
    return {"bandi": result}


@app.post("/api/bandi/{bando_id}/valida", dependencies=[Depends(verify_api_key)])
def api_bando_valida(bando_id: int):
    """Conferma la revisione manuale e pubblica il bando nel matching."""
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, review_status FROM bandi WHERE id = %s",
                (bando_id,),
            ).fetchone()
            if not row:
                return JSONResponse(status_code=404, content={"detail": "Bando non trovato"})

            conn.execute(
                """UPDATE bandi
                   SET review_status = %s, reviewed_at = NOW()
                   WHERE id = %s""",
                (REVIEW_STATUS_VALIDATED, bando_id),
            )
            # Elimina ogni eventuale risultato precedente prima del nuovo
            # calcolo, così l'attivazione pubblica solo dati aggiornati.
            conn.execute("DELETE FROM match_results WHERE bando_id = %s", (bando_id,))
            conn.commit()
            run_matching_for_bando(bando_id, conn)
        return {
            "status": REVIEW_STATUS_VALIDATED,
            "bando_id": bando_id,
            "matching_suspended": False,
        }
    except Exception as exc:
        log_error(f"api_bando_valida({bando_id}): {exc}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Validazione del bando non riuscita. Riprova."},
        )


class MatchRunRequest(BaseModel):
    soglia_minima: int = 0


@app.post("/api/match/run", dependencies=[Depends(verify_api_key)])
def api_match_run(payload: MatchRunRequest = None):
    soglia = payload.soglia_minima if payload else 0
    try:
        with get_connection() as conn:
            run_matching_for_all_bandi(conn, soglia_minima=soglia)
        return {"status": "ok", "soglia_minima": soglia}
    except Exception as exc:
        log_error(f"api_match_run: {exc}")
        return JSONResponse(status_code=500, content={"status": "error", "detail": "Matching non riuscito. Riprova."})


@app.get("/api/export/matching.csv", dependencies=[Depends(verify_api_key)])
def api_export_csv():
    with get_connection() as conn:
        rows = load_dashboard_rows(conn)
    export_rows = _build_export_rows(rows) if rows else []

    buffer = io.StringIO()
    fieldnames = ["cliente", "bando", "score_totale", "score_regione", "score_ateco", "score_dimensione", "score_fatturato"]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(export_rows)

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=matching_bandi.csv"},
    )


@app.delete("/api/bandi/{bando_id}", dependencies=[Depends(verify_api_key)])
def api_bando_delete(bando_id: int):
    deleted = delete_bando(bando_id)
    if not deleted:
        return JSONResponse(status_code=404, content={"detail": "Bando non trovato"})
    return {"status": "ok"}


@app.get("/api/bandi/{bando_id}/pdf", dependencies=[Depends(verify_api_key)])
def api_download_pdf_originale(bando_id: int):
    """Scarica il documento originale senza esporre il BYTEA nelle API JSON."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT pdf_original, pdf_filename FROM bandi WHERE id = %s",
            (bando_id,),
        ).fetchone()
    if not row:
        return JSONResponse(status_code=404, content={"detail": "Bando non trovato"})
    if row["pdf_original"] is None:
        return JSONResponse(
            status_code=404,
            content={"detail": "PDF originale non disponibile: ricarica il documento per associarlo al bando."},
        )

    pdf_bytes = bytes(row["pdf_original"])
    if not pdf_bytes.startswith(PDF_MAGIC):
        return JSONResponse(status_code=500, content={"detail": "PDF originale non valido"})

    original_name = Path(row["pdf_filename"] or f"Bando_{bando_id}.pdf").name
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", original_name).strip("._")
    if not safe_name:
        safe_name = f"Bando_{bando_id}.pdf"
    if not safe_name.lower().endswith(".pdf"):
        safe_name += ".pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )


@app.get("/api/bandi/{bando_id}/scheda", dependencies=[Depends(verify_api_key)])
def api_bando_scheda_json(bando_id: int):
    with get_connection() as conn:
        row = conn.execute(
            """SELECT json_completo, scheda_cached, review_status,
                      null_percentage, review_reasons
               FROM bandi WHERE id = %s""",
            (bando_id,),
        ).fetchone()
    if not row:
        return JSONResponse(status_code=404, content={"detail": "Bando non trovato"})
    try:
        scheda = _scheda_or_cached(json.loads(row["json_completo"]), row["scheda_cached"])
    except Exception:
        return JSONResponse(status_code=500, content={"detail": "JSON bando non valido"})
    return {
        "bando_id": bando_id,
        "scheda": scheda,
        "review_status": row.get("review_status") or REVIEW_STATUS_VALIDATED,
        "null_percentage": float(row.get("null_percentage") or 0),
        "review_reasons": _parse_review_reasons(row.get("review_reasons")),
    }


@app.post("/api/bandi/{bando_id}/rigenera-scheda", dependencies=[Depends(verify_api_key)])
def api_rigenera_scheda(bando_id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT json_completo FROM bandi WHERE id = %s", (bando_id,)).fetchone()
        if not row:
            return JSONResponse(status_code=404, content={"detail": "Bando non trovato"})
        try:
            payload = json.loads(row["json_completo"])
        except Exception:
            return JSONResponse(status_code=500, content={"detail": "JSON bando non valido"})
        scheda = genera_scheda(payload)
        conn.execute("UPDATE bandi SET scheda_cached = %s WHERE id = %s", (scheda, bando_id))
        conn.commit()
    return {"bando_id": bando_id, "scheda": scheda}


@app.get("/api/bandi/{bando_id}/scheda.md", dependencies=[Depends(verify_api_key)])
def api_download_scheda(bando_id: int):
    with get_connection() as conn:
        row = conn.execute(
            """SELECT json_completo, scheda_cached, review_status, null_percentage
               FROM bandi WHERE id = %s""",
            (bando_id,),
        ).fetchone()
    if row:
        try:
            scheda = _scheda_or_cached(json.loads(row["json_completo"]), row["scheda_cached"])
            scheda = _with_review_disclaimer(
                scheda,
                row.get("review_status") or REVIEW_STATUS_VALIDATED,
                row.get("null_percentage"),
            )
        except Exception:
            return JSONResponse(status_code=500, content={"detail": "JSON bando non valido"})
    else:
        scheda = genera_scheda({})
    return Response(
        content=scheda,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=Scheda_Bando_{bando_id}.md"},
    )


# ---------------------------------------------------------
# ESTRAZIONE BANDI
# ---------------------------------------------------------

PDF_MAGIC = b"%PDF"


def _process_and_save_bando(
    text: str,
    source_label: str,
    source_url: str | None = None,
    pdf_bytes: bytes | None = None,
    pdf_filename: str | None = None,
) -> dict:
    """Pipeline condivisa post-estrazione testo: LLM -> validazione -> dedup
    -> salvataggio -> matching. Usata sia da /api/estrazione (upload PDF)
    sia da /api/estrazione-url (#16), per non duplicare questa logica.

    Nota sul caso duplicato: a differenza della versione precedente (che
    ricostruiva una risposta minimale), qui il risultato include anche i
    campi già raccolti prima del controllo duplicati (raw_text_preview,
    data, bando_info, warnings, errors) — dati extra innocui per il
    frontend, che legge solo i campi che già conosce.
    """
    result: dict = {"raw_text_preview": text[:1000]}
    early_classification = classify_non_compatible_document(raw_text=text)
    if early_classification:
        result.update({
            "status": "non_compatibile",
            "messaggio": "Documento non compatibile con BandoMatch",
            "motivo_non_compatibile": early_classification["motivo"],
            "tipo_documento": early_classification["tipo"],
            "matching_suspended": True,
        })
        return result

    document_hash = compute_document_hash(text)
    try:
        existing_hash_id = find_duplicate_bando_by_hash(document_hash)
    except Exception as exc:
        log_error(f"_process_and_save_bando: controllo hash '{source_label}' fallito: {exc}")
        existing_hash_id = None
    if existing_hash_id:
        try:
            attach_pdf_to_bando(existing_hash_id, pdf_bytes, pdf_filename)
        except Exception as exc:
            log_error(f"_process_and_save_bando: associazione PDF duplicato #{existing_hash_id} fallita: {exc}")
        result.update({
            "status": "duplicato",
            "messaggio": "Questo documento è già presente in archivio",
            "bando_id": existing_hash_id,
        })
        return result
    try:
        raw_data = extract_bando_data(text)
        validation = validate_bando(raw_data, raw_text=text)
        data = validation["data"]
        bando_info = data.get("bando", {})

        classification = classify_non_compatible_document(data, text)
        if classification:
            result.update({
                "data": data,
                "bando_info": bando_info,
                "status": "non_compatibile",
                "messaggio": "Documento non compatibile con BandoMatch",
                "motivo_non_compatibile": classification["motivo"],
                "tipo_documento": classification["tipo"],
                "matching_suspended": True,
            })
            return result

        # La provenienza non va inferita dal contenuto del PDF: un URL scritto
        # nel documento può essere una home page generica o persino inventato.
        # Conserviamo invece l'indirizzo effettivamente usato dall'utente per
        # l'estrazione da URL; per un file locale l'origine resta sconosciuta.
        if isinstance(bando_info, dict):
            bando_info["link_fonte_ufficiale"] = None
            bando_info["url_documento_origine"] = source_url

        result["data"] = data
        result["bando_info"] = bando_info
        result["warnings"] = validation.get("warnings", [])
        result["errors"] = validation.get("errors", [])
        result["null_percentage"] = validation.get("null_percentage", 0)
        result["needs_manual_review"] = validation.get("needs_manual_review", False)
        result["critical_gaps"] = validation.get("critical_gaps", [])
        review_status = (
            REVIEW_STATUS_PENDING
            if result["needs_manual_review"]
            else REVIEW_STATUS_VALIDATED
        )
        review_reasons = _review_reasons_from_validation(validation)
        result["review_status"] = review_status
        result["review_reasons"] = review_reasons
        result["matching_suspended"] = review_status == REVIEW_STATUS_PENDING

        if bando_info.get("ateco_aperto_a_tutti") is False:
            escl = bando_info.get("note_esclusioni", {})
            if isinstance(escl, dict):
                result["sezioni_escluse"] = escl.get("sezioni_ateco_escluse", [])
                result["attivita_vietate"] = escl.get("attivita_vietate", [])
            else:
                result["note_esclusioni_raw"] = str(escl)

        if not validation["errors"]:
            try:
                existing_id = find_duplicate_bando(bando_info.get("titolo"), bando_info.get("ente"))
                if existing_id:
                    attach_pdf_to_bando(existing_id, pdf_bytes, pdf_filename)
                    result["status"] = "duplicato"
                    result["messaggio"] = "Bando già presente in archivio"
                    result["bando_id"] = existing_id
                    result["scheda"] = genera_scheda(data)
                    return result

                scheda = genera_scheda(data)
                bando_id = save_bando_from_json(
                    data,
                    scheda=scheda,
                    review_status=review_status,
                    null_percentage=result["null_percentage"],
                    review_reasons=review_reasons,
                    document_hash=document_hash,
                    pdf_bytes=pdf_bytes,
                    pdf_filename=pdf_filename,
                )
                if review_status == REVIEW_STATUS_VALIDATED:
                    with get_connection() as conn:
                        run_matching_for_bando(bando_id, conn)

                result["bando_id"] = bando_id
                result["scadenza_estratta"] = bando_info.get("data_scadenza")
                ok_fields, null_fields = fields_status(data)
                log_note = (
                    "Da revisionare: matching sospeso"
                    if review_status == REVIEW_STATUS_PENDING
                    else "Validazione OK: matching completato"
                )
                log_prompt_run(
                    filename=source_label,
                    fields_ok=ok_fields,
                    fields_null=null_fields,
                    notes=log_note,
                )

                result["scheda"] = scheda
            except Exception as exc:
                log_error(f"_process_and_save_bando: salvataggio bando '{source_label}' fallito: {exc}")
                result["save_error"] = "Impossibile salvare il bando estratto. Riprova."
    except Exception as exc:
        log_error(f"_process_and_save_bando: estrazione/validazione '{source_label}' fallita: {exc}")
        result["extraction_error"] = "Errore durante l'estrazione dei dati. Riprova o contatta l'assistenza."

    return result


@app.post("/api/estrazione", dependencies=[Depends(verify_api_key), Depends(rate_limit_estrazione)])
def api_estrazione_submit(file: UploadFile = File(...)):
    safe_name = Path(file.filename).name
    file_path = TEMP_DIR / f"{uuid.uuid4().hex}_{safe_name}"
    file_bytes = file.file.read()

    result = {
        "filename": safe_name,
        "size_kb": len(file_bytes) / 1024,
    }

    if len(file_bytes) > 10_000_000:
        return JSONResponse(status_code=400, content={
            "errors": [f"File troppo grande ({result['size_kb']:.0f} KB). Limite massimo: 10 MB."]
        })

    if not file_bytes.startswith(PDF_MAGIC):
        return JSONResponse(status_code=400, content={
            "errors": ["Il file non è un PDF valido (intestazione mancante). Verifica il formato e riprova."]
        })

    try:
        with open(file_path, "wb") as f:
            f.write(file_bytes)
    except OSError as exc:
        log_error(f"api_estrazione_submit: scrittura file temporaneo '{safe_name}' fallita: {exc}")
        result["save_error"] = "Impossibile salvare il file temporaneo. Riprova."
        return result

    try:
        try:
            text = extract_text_from_pdf(str(file_path))
        except EmptyPDFException:
            result["empty_pdf"] = True
            return result
        except PDFTroppoGrandeException as exc:
            log_error(f"api_estrazione_submit: '{safe_name}' rifiutato, troppo esteso: {exc}")
            return JSONResponse(status_code=400, content={
                "errors": ["Il PDF ha troppe pagine. Riduci il documento (o dividilo) e riprova."]
            })
        except PDFInvalidoException as exc:
            log_error(f"api_estrazione_submit: '{safe_name}' corrotto/non leggibile: {exc}")
            return JSONResponse(status_code=400, content={
                "errors": ["Il PDF risulta corrotto o non leggibile. Verifica il file e riprova."]
            })

        result.update(_process_and_save_bando(
            text,
            safe_name,
            pdf_bytes=file_bytes,
            pdf_filename=safe_name,
        ))
        return result
    finally:
        file_path.unlink(missing_ok=True)


class EstrazioneUrlIn(BaseModel):
    url: str


@app.post("/api/estrazione-url", dependencies=[Depends(verify_api_key), Depends(rate_limit_estrazione)])
def api_estrazione_url_submit(payload: EstrazioneUrlIn):
    """Estrazione bando da URL (#16): scarica la risorsa (PDF o pagina HTML),
    ne estrae il testo e riusa la stessa pipeline dell'upload PDF.

    Sicurezza: allow-list schema (solo https), blocco host privati/interni
    anche sui redirect, timeout e limite dimensione — vedi modules/url_extractor.py.
    """
    try:
        content_bytes, content_type, encoding, final_url = fetch_url_safely(payload.url)
    except InvalidUrlException as exc:
        return JSONResponse(status_code=400, content={"errors": [str(exc)]})
    except requests.RequestException as exc:
        log_error(f"api_estrazione_url_submit: fetch '{payload.url}' fallito: {exc}")
        return JSONResponse(status_code=400, content={
            "errors": ["Impossibile scaricare la pagina. Verifica il link e riprova."]
        })

    url_filename = Path(urlparse(final_url).path).name
    pdf_filename = url_filename if url_filename.lower().endswith(".pdf") else "bando.pdf"
    filename = pdf_filename if content_bytes.startswith(PDF_MAGIC) or "application/pdf" in content_type else (urlparse(final_url).hostname or payload.url)
    result = {"filename": filename, "size_kb": len(content_bytes) / 1024}

    is_pdf = content_bytes.startswith(PDF_MAGIC) or "application/pdf" in content_type
    file_path: Path | None = None
    try:
        if is_pdf:
            file_path = TEMP_DIR / f"{uuid.uuid4().hex}_estrazione_url.pdf"
            with open(file_path, "wb") as f:
                f.write(content_bytes)
            try:
                text = extract_text_from_pdf(str(file_path))
            except EmptyPDFException:
                result["empty_pdf"] = True
                return result
            except PDFTroppoGrandeException as exc:
                log_error(f"api_estrazione_url_submit: '{final_url}' rifiutato, PDF troppo esteso: {exc}")
                return JSONResponse(status_code=400, content={
                    "errors": ["Il PDF ha troppe pagine. Riduci il documento (o dividilo) e riprova."]
                })
            except PDFInvalidoException as exc:
                log_error(f"api_estrazione_url_submit: '{final_url}' PDF corrotto/non leggibile: {exc}")
                return JSONResponse(status_code=400, content={
                    "errors": ["Il PDF risulta corrotto o non leggibile. Verifica il link e riprova."]
                })
        else:
            try:
                html_text = content_bytes.decode(encoding or "utf-8", errors="replace")
            except (LookupError, UnicodeDecodeError):
                html_text = content_bytes.decode("utf-8", errors="replace")
            text = extract_text_from_html(html_text)
            if not text:
                result["empty_pdf"] = True
                return result
    finally:
        if file_path is not None:
            file_path.unlink(missing_ok=True)

    result.update(_process_and_save_bando(
        text,
        filename,
        source_url=final_url,
        pdf_bytes=content_bytes if is_pdf else None,
        pdf_filename=pdf_filename if is_pdf else None,
    ))
    return result


# ---------------------------------------------------------
# PROFILO CLIENTE
# ---------------------------------------------------------

class ClienteIn(BaseModel):
    ragione_sociale: str
    p_iva: str
    codice_ateco: str
    regione: str
    descrizione_attivita: str = ""
    fatturato: float
    dimensione_impresa: str
    data_costituzione: str | None = None
    numero_dipendenti: int | None = None
    forma_giuridica: str | None = None


@app.get("/api/clienti", dependencies=[Depends(verify_api_key)])
def api_clienti_list():
    clienti = list_clienti()
    if clienti:
        clienti_by_id = {int(cliente["id"]): cliente for cliente in clienti}
        with get_connection() as conn:
            match_rows = conn.execute(
                """
                SELECT mr.cliente_id, mr.bando_id, b.json_completo
                FROM match_results mr
                JOIN bandi b ON b.id = mr.bando_id
                WHERE mr.score > 0 AND b.review_status = 'validato'
                """
            ).fetchall()

        bandi_ammissibili: dict[int, set[int]] = defaultdict(set)
        for row in match_rows:
            cliente_id = int(row["cliente_id"])
            cliente = clienti_by_id.get(cliente_id)
            if cliente is None:
                continue
            try:
                payload = json.loads(row["json_completo"])
                ammissibilita = check_ammissibilita(payload, cliente)
                breakdown = get_score_breakdown(payload, cliente)
            except Exception as exc:
                # Fail-closed: un controllo non riuscito non può aumentare il
                # numero di bandi dichiarati realmente compatibili.
                log_error(f"api_clienti_list: verifica match cliente #{cliente_id} fallita: {exc}")
                continue
            if (
                ammissibilita.get("ammissibile") is True
                and breakdown.get("status") != "da_verificare"
            ):
                bandi_ammissibili[cliente_id].add(int(row["bando_id"]))

        for cliente_id, cliente in clienti_by_id.items():
            cliente["match_count"] = len(bandi_ammissibili.get(cliente_id, set()))

    return {
        "clienti": clienti,
        "regioni": REGIONI_ITALIANE,
        "dimensioni": DIMENSIONI_IMPRESA,
    }


@app.get("/api/clienti/{cliente_id}", dependencies=[Depends(verify_api_key)])
def api_cliente_get(cliente_id: int):
    cliente = get_cliente(cliente_id)
    if not cliente:
        return JSONResponse(status_code=404, content={"detail": "Cliente non trovato"})
    return cliente


@app.get("/api/clienti/{cliente_id}/bandi", dependencies=[Depends(verify_api_key)])
def api_cliente_bandi(cliente_id: int):
    cliente = get_cliente(cliente_id)
    if not cliente:
        return JSONResponse(status_code=404, content={"detail": "Cliente non trovato"})
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT mr.score, b.id AS bando_id, b.titolo, b.ente, b.data_scadenza,
                   b.json_completo, (b.pdf_original IS NOT NULL) AS has_pdf
            FROM match_results mr
            JOIN bandi b ON b.id = mr.bando_id
            WHERE mr.cliente_id = %s
              AND mr.score > 0
              AND b.review_status = 'validato'
            ORDER BY mr.score DESC
            """,
            (cliente_id,),
        ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        try:
            payload = json.loads(d["json_completo"])
        except Exception:
            payload = {}
        bd = get_score_breakdown(payload, cliente)
        try:
            ammissibilita = check_ammissibilita(payload, cliente)
        except Exception:
            # #2 (audit Fable): stesso principio della lista match — mai fail-open.
            ammissibilita = {
                "ammissibile": None,
                "motivi_esclusione": [],
                "criteri_verificati": [],
                "errore": True,
            }
        result.append({
            "bando_id": d["bando_id"],
            "titolo": d["titolo"],
            "ente": d["ente"],
            "score": int(d["score"]),
            "breakdown": bd,
            "scadenza": format_scadenza_italiana(d.get("data_scadenza")),
            "giorni_alla_scadenza": giorni_alla_scadenza(d.get("data_scadenza")),
            "ammissibilita": ammissibilita,
            "fonte_url": get_fonte_url(payload),
            "has_pdf": bool(d.get("has_pdf")),
        })
    return {"cliente_id": cliente_id, "bandi": result}


@app.post("/api/clienti", dependencies=[Depends(verify_api_key)])
def api_clienti_create(payload: ClienteIn):
    form_values = payload.model_dump()
    form_values["fatturato"] = str(form_values["fatturato"])
    errors = _validate_cliente_form(form_values)
    if errors:
        return JSONResponse(status_code=400, content={"errors": errors})

    try:
        new_id = create_cliente(
            ragione_sociale=payload.ragione_sociale, p_iva=payload.p_iva.strip(),
            codice_ateco=payload.codice_ateco.strip(), regione=payload.regione,
            fatturato=payload.fatturato, dimensione_impresa=payload.dimensione_impresa,
            descrizione_attivita=payload.descrizione_attivita,
            data_costituzione=payload.data_costituzione,
            numero_dipendenti=payload.numero_dipendenti,
            forma_giuridica=payload.forma_giuridica,
        )
        with get_connection() as conn:
            run_matching_for_all_bandi(conn)
    except Exception as exc:
        log_error(f"api_clienti_create: {exc}")
        return JSONResponse(status_code=400, content={"errors": ["Errore durante il salvataggio del cliente. Verifica i dati e riprova."]})

    return JSONResponse(status_code=201, content={"id": new_id})


@app.put("/api/clienti/{cliente_id}", dependencies=[Depends(verify_api_key)])
def api_clienti_update(cliente_id: int, payload: ClienteIn):
    form_values = payload.model_dump()
    form_values["fatturato"] = str(form_values["fatturato"])
    errors = _validate_cliente_form(form_values)
    if errors:
        return JSONResponse(status_code=400, content={"errors": errors})

    try:
        update_cliente(
            cliente_id, ragione_sociale=payload.ragione_sociale, p_iva=payload.p_iva.strip(),
            codice_ateco=payload.codice_ateco.strip(), regione=payload.regione,
            fatturato=payload.fatturato, dimensione_impresa=payload.dimensione_impresa,
            descrizione_attivita=payload.descrizione_attivita,
            data_costituzione=payload.data_costituzione,
            numero_dipendenti=payload.numero_dipendenti,
            forma_giuridica=payload.forma_giuridica,
        )
        with get_connection() as conn:
            run_matching_for_all_bandi(conn)
    except Exception as exc:
        log_error(f"api_clienti_update({cliente_id}): {exc}")
        return JSONResponse(status_code=400, content={"errors": ["Errore durante il salvataggio del cliente. Verifica i dati e riprova."]})

    return {"id": cliente_id}


@app.delete("/api/clienti/{cliente_id}", dependencies=[Depends(verify_api_key)])
def api_clienti_delete(cliente_id: int):
    delete_cliente(cliente_id)
    return {"status": "ok"}


@app.get("/api/health")
def api_health():
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "db": "ok" if db_ok else "error",
        "version": "3.2",
    }


# ---------------------------------------------------------
# SPA STATIC SERVING (built React app)
# ---------------------------------------------------------

if (FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


@app.get("/bandomatch-ai-logo.jpeg", include_in_schema=False)
def frontend_logo():
    """Serve il logo copiato da Vite nella radice di ``frontend/dist``.

    I file sotto ``/assets`` sono gestiti dal mount statico, mentre i file di
    ``frontend/public`` finiscono nella radice della build. Senza questa rotta
    la richiesta del logo verrebbe intercettata dal fallback SPA e riceverebbe
    ``index.html`` invece dell'immagine.
    """
    logo_path = FRONTEND_DIST / "bandomatch-ai-logo.jpeg"
    if logo_path.is_file():
        return FileResponse(str(logo_path), media_type="image/jpeg")
    return JSONResponse(status_code=404, content={"detail": "Logo non trovato"})


@app.get("/{full_path:path}")
def spa_catch_all(full_path: str):
    if full_path.startswith("api/"):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    index_path = FRONTEND_DIST / "index.html"
    if index_path.is_file():
        return FileResponse(str(index_path))
    return JSONResponse(status_code=503, content={"detail": "Frontend non compilato (frontend/dist assente). Esegui 'npm run build' in frontend/."})
