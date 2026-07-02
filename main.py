import csv
import io
import json
import logging
import re
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from modules.database import (
    DIMENSIONI_IMPRESA,
    REGIONI_ITALIANE,
    create_cliente,
    deduplica_bandi,
    delete_bando,
    delete_cliente,
    ensure_database,
    find_duplicate_bando,
    get_cliente,
    get_connection,
    list_clienti,
    save_bando_from_json,
    update_cliente,
)
from modules.matcher import (
    bando_has_constraints,
    count_bandi,
    format_scadenza_italiana,
    genera_scheda,
    genera_spiegazione_score,
    get_fonte_url,
    get_score_breakdown,
    giorni_alla_scadenza,
    load_dashboard_rows,
    run_matching_for_all_bandi,
    run_matching_for_bando,
    settore_da_verificare,
)
from modules.extractor import EmptyPDFException, calcola_urgenza, extract_bando_data, extract_text_from_pdf
from modules.log_utils import log_prompt_run
from modules.validator import fields_status, validate_bando

ROOT = Path(__file__).resolve().parent
TEMP_DIR = ROOT / "temp"
TEMP_DIR.mkdir(exist_ok=True)
FRONTEND_DIST = ROOT / "frontend" / "dist"

app = FastAPI(title="Bandi Scanner AI")


@app.on_event("startup")
def on_startup() -> None:
    ensure_database()


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


def _dashboard_payload() -> dict:
    with get_connection() as conn:
        n_bandi = count_bandi(conn)
        rows = load_dashboard_rows(conn)

    export_rows = _build_export_rows(rows) if rows else []

    by_bando: dict[int, dict] = {}
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
            }
            try:
                bd = get_score_breakdown(payload, cliente_row)
                bd_error = None
            except Exception as e:
                bd = {"total": 0, "ateco": 0, "regione": 0, "dimensione": 0, "fatturato": 0}
                bd_error = str(e)

            cliente_match = {"codice_ateco": m.get("cliente_codice_ateco"), "descrizione_attivita": m.get("cliente_descrizione_attivita")}
            try:
                spiegazione = genera_spiegazione_score(payload, cliente_row, bd)
            except Exception:
                spiegazione = None

            matches.append({
                "nome": m["cliente_nome"],
                "score": score_cliente,
                "score_badge_class": score_badge_class(score_cliente),
                "breakdown": bd,
                "breakdown_error": bd_error,
                "settore_da_verificare": settore_da_verificare(payload, cliente_match),
                "discrepanza": score_cliente != int(bd["total"]),
                "spiegazione_score": spiegazione,
            })

        scadenza_grezza_card = info.get("data_scadenza")
        cards.append({
            "id": bid,
            "titolo": info["titolo"],
            "ente": info["ente"],
            "contributo_max": contributo_max,
            "scadenza": scad_fmt,
            "giorni_alla_scadenza": giorni_alla_scadenza(scadenza_grezza_card),
            "urgenza": calcola_urgenza(scadenza_grezza_card),
            "max_score": max_sc,
            "color_class": get_color_class(max_sc),
            "has_constraints": bando_has_constraints(payload),
            "matches": matches,
            "scheda": info.get("scheda_cached") or genera_scheda(payload),
            "fonte_url": get_fonte_url(payload),
        })

    return {
        "n_bandi": n_bandi,
        "totale_abbinamenti": len(rows) if rows else 0,
        "has_export_data": bool(export_rows),
        "cards": cards,
    }


@app.get("/api/dashboard")
def api_dashboard():
    return _dashboard_payload()


class DeduplicaRequest(BaseModel):
    strict: bool = True


@app.post("/api/bandi/deduplica")
def api_deduplica_bandi(body: DeduplicaRequest = DeduplicaRequest()):
    try:
        eliminati = deduplica_bandi(strict=body.strict)
        if eliminati > 0:
            with get_connection() as conn:
                run_matching_for_all_bandi(conn)
        return {"status": "ok", "eliminati": eliminati, "strict": body.strict}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(exc)})


@app.post("/api/bandi/recalc")
def api_recalc_matches():
    try:
        with get_connection() as conn:
            run_matching_for_all_bandi(conn)
        return {"status": "ok"}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(exc)})


@app.get("/api/bandi")
def api_bandi_list():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, titolo, ente, data_scadenza, contributo_max, regioni FROM bandi ORDER BY id DESC"
        ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["urgenza"] = calcola_urgenza(d.get("data_scadenza"))
        d["giorni_alla_scadenza"] = giorni_alla_scadenza(d.get("data_scadenza"))
        result.append(d)
    return {"bandi": result}


class MatchRunRequest(BaseModel):
    soglia_minima: int = 0


@app.post("/api/match/run")
def api_match_run(payload: MatchRunRequest = None):
    soglia = payload.soglia_minima if payload else 0
    try:
        with get_connection() as conn:
            run_matching_for_all_bandi(conn, soglia_minima=soglia)
        return {"status": "ok", "soglia_minima": soglia}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(exc)})


@app.get("/api/export/matching.csv")
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


@app.delete("/api/bandi/{bando_id}")
def api_bando_delete(bando_id: int):
    deleted = delete_bando(bando_id)
    if not deleted:
        return JSONResponse(status_code=404, content={"detail": "Bando non trovato"})
    return {"status": "ok"}


@app.get("/api/bandi/{bando_id}/scheda")
def api_bando_scheda_json(bando_id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT json_completo, scheda_cached FROM bandi WHERE id = %s", (bando_id,)).fetchone()
    if not row:
        return JSONResponse(status_code=404, content={"detail": "Bando non trovato"})
    scheda = row["scheda_cached"] or genera_scheda(json.loads(row["json_completo"]))
    return {"bando_id": bando_id, "scheda": scheda}


@app.get("/api/bandi/{bando_id}/scheda.md")
def api_download_scheda(bando_id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT json_completo, scheda_cached FROM bandi WHERE id = %s", (bando_id,)).fetchone()
    scheda = (row["scheda_cached"] or genera_scheda(json.loads(row["json_completo"]))) if row else genera_scheda({})
    return Response(
        content=scheda,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=Scheda_Bando_{bando_id}.md"},
    )


# ---------------------------------------------------------
# ESTRAZIONE BANDI
# ---------------------------------------------------------

@app.post("/api/estrazione")
def api_estrazione_submit(file: UploadFile = File(...)):
    safe_name = Path(file.filename).name
    file_path = TEMP_DIR / safe_name
    file_bytes = file.file.read()

    result = {
        "filename": safe_name,
        "size_kb": len(file_bytes) / 1024,
    }

    try:
        with open(file_path, "wb") as f:
            f.write(file_bytes)
    except OSError as exc:
        result["save_error"] = str(exc)
        return result

    try:
        try:
            text = extract_text_from_pdf(str(file_path))
        except EmptyPDFException:
            result["empty_pdf"] = True
            return result

        result["raw_text_preview"] = text[:1000]

        try:
            raw_data = extract_bando_data(text)
            validation = validate_bando(raw_data, raw_text=text)
            data = validation["data"]
            bando_info = data.get("bando", {})

            result["data"] = data
            result["bando_info"] = bando_info
            result["warnings"] = validation.get("warnings", [])
            result["errors"] = validation.get("errors", [])

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
                        return JSONResponse(content={
                            "status": "duplicato",
                            "messaggio": "Bando già presente in archivio",
                            "bando_id": existing_id,
                            "filename": result["filename"],
                            "size_kb": result["size_kb"],
                            "scheda": genera_scheda(data),
                            "warnings": validation.get("warnings", []),
                        })

                    scheda = genera_scheda(data)
                    bando_id = save_bando_from_json(data, scheda=scheda)
                    with get_connection() as conn:
                        run_matching_for_bando(bando_id, conn)

                    scadenza_estratta = bando_info.get("data_scadenza")
                    result["bando_id"] = bando_id
                    result["scadenza_estratta"] = scadenza_estratta
                    result["null_percentage"] = validation.get("null_percentage", 0)

                    ok_fields, null_fields = fields_status(data)
                    log_prompt_run(filename=safe_name, fields_ok=ok_fields, fields_null=null_fields, notes="Validazione OK")

                    result["scheda"] = scheda
                except Exception as exc:
                    result["save_error"] = str(exc)
        except Exception as exc:
            result["extraction_error"] = str(exc)

        return result
    finally:
        file_path.unlink(missing_ok=True)


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


@app.get("/api/clienti")
def api_clienti_list():
    return {
        "clienti": list_clienti(),
        "regioni": REGIONI_ITALIANE,
        "dimensioni": DIMENSIONI_IMPRESA,
    }


@app.get("/api/clienti/{cliente_id}")
def api_cliente_get(cliente_id: int):
    cliente = get_cliente(cliente_id)
    if not cliente:
        return JSONResponse(status_code=404, content={"detail": "Cliente non trovato"})
    return cliente


@app.get("/api/clienti/{cliente_id}/bandi")
def api_cliente_bandi(cliente_id: int):
    cliente = get_cliente(cliente_id)
    if not cliente:
        return JSONResponse(status_code=404, content={"detail": "Cliente non trovato"})
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT mr.score, b.id AS bando_id, b.titolo, b.ente, b.data_scadenza, b.json_completo
            FROM match_results mr
            JOIN bandi b ON b.id = mr.bando_id
            WHERE mr.cliente_id = %s AND mr.score > 0
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
        result.append({
            "bando_id": d["bando_id"],
            "titolo": d["titolo"],
            "ente": d["ente"],
            "score": int(d["score"]),
            "breakdown": bd,
            "scadenza": format_scadenza_italiana(d.get("data_scadenza")),
            "giorni_alla_scadenza": giorni_alla_scadenza(d.get("data_scadenza")),
        })
    return {"cliente_id": cliente_id, "bandi": result}


@app.post("/api/clienti")
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
        return JSONResponse(status_code=400, content={"errors": [f"Errore salvataggio: {exc}"]})

    return JSONResponse(status_code=201, content={"id": new_id})


@app.put("/api/clienti/{cliente_id}")
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
        return JSONResponse(status_code=400, content={"errors": [f"Errore salvataggio: {exc}"]})

    return {"id": cliente_id}


@app.delete("/api/clienti/{cliente_id}")
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


@app.get("/{full_path:path}")
def spa_catch_all(full_path: str):
    if full_path.startswith("api/"):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    index_path = FRONTEND_DIST / "index.html"
    if index_path.is_file():
        return FileResponse(str(index_path))
    return JSONResponse(status_code=503, content={"detail": "Frontend non compilato (frontend/dist assente). Esegui 'npm run build' in frontend/."})
