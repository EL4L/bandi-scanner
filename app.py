import json

import streamlit as st
from pathlib import Path

from modules.database import (
    DIMENSIONI_IMPRESA,
    REGIONI_ITALIANE,
    create_cliente,
    delete_cliente,
    ensure_database,
    get_cliente,
    get_connection,
    list_clienti,
    save_bando_from_json,
    update_cliente,
)
from modules.matcher import (
    count_bandi,
    format_scadenza_italiana,
    genera_scheda,
    get_fonte_url,
    load_dashboard_rows,
    run_matching_for_all_bandi,
    run_matching_for_bando,
    settore_da_verificare,
)
from modules.extractor import (
    EmptyPDFException,
    InvalidJSONResponse,
    MissingAPIKeyError,
    extract_bando_data,
    extract_text_from_pdf,
)
from modules.log_utils import log_error, log_prompt_run
from modules.validator import fields_status, validate_bando

st.set_page_config(page_title="Bandi Scanner", layout="wide")

ROOT = Path(__file__).resolve().parent
TEMP_DIR = ROOT / "temp"
TEMP_DIR.mkdir(exist_ok=True)

ensure_database()

st.title("Bandi Scanner")

tab_dashboard, tab_estrazione, tab_clienti = st.tabs(
    ["Dashboard", "Estrazione bandi", "Profilo cliente"]
)


def render_disclaimer(bando_payload: dict) -> None:
    """Disclaimer obbligatorio e link fonte ufficiale se disponibile."""
    st.warning(
        "⚠️ Dati estratti tramite AI — verificare sempre sulla fonte ufficiale "
        "prima di procedere."
    )
    url = get_fonte_url(bando_payload)
    if url:
        st.markdown(f"[Apri la fonte ufficiale]({url})")


def render_colored_progress(score: int) -> None:
    """Barra di progresso con colore verde / giallo / rosso in base allo score."""
    if score > 70:
        color = "#22c55e"
    elif score >= 40:
        color = "#eab308"
    else:
        color = "#ef4444"
    pct = max(0, min(100, score))
    st.markdown(
        f'<div style="background:#e5e7eb;border-radius:6px;height:14px;margin:4px 0;">'
        f'<div style="width:{pct}%;background:{color};height:14px;'
        f'border-radius:6px;"></div></div>'
        f'<span style="font-size:0.9rem;color:#374151;">Compatibilità: {score}/100</span>',
        unsafe_allow_html=True,
    )


with tab_dashboard:
    st.header("Dashboard alert")
    st.caption("RF-005 / RF-006 — Match bando↔cliente e schede sintetiche.")

    with get_connection() as conn:
        n_bandi = count_bandi(conn)
        if n_bandi == 0:
            st.info(
                "Nessun bando in archivio. Carica il primo PDF dalla scheda "
                "**Estrazione bandi** per popolare la dashboard."
            )
        else:
            rows = load_dashboard_rows(conn)
            if not rows:
                st.warning(
                    "Ci sono bandi salvati ma nessun match. Aggiungi almeno un "
                    "profilo cliente o ricarica un bando per ricalcolare gli abbinamenti."
                )
            else:
                by_bando: dict[int, dict] = {}
                for row in rows:
                    bid = row["bando_id"]
                    if bid not in by_bando:
                        by_bando[bid] = {
                            "titolo": row["bando_titolo"] or f"Bando #{bid}",
                            "ente": row["bando_ente"],
                            "data_scadenza": row["data_scadenza"],
                            "json_completo": row["json_completo"],
                            "matches": [],
                            "max_score": row["score"],
                        }
                    by_bando[bid]["matches"].append(row)
                    by_bando[bid]["max_score"] = max(
                        by_bando[bid]["max_score"], row["score"]
                    )

                for bid in sorted(
                    by_bando.keys(),
                    key=lambda x: by_bando[x]["max_score"],
                    reverse=True,
                ):
                    info = by_bando[bid]
                    titolo_exp = info["titolo"]
                    max_sc = int(info["max_score"])
                    with st.expander(f"{titolo_exp} — score max {max_sc}/100"):
                        render_colored_progress(max_sc)
                        if info["data_scadenza"]:
                            scad_fmt = (
                                format_scadenza_italiana(info["data_scadenza"])
                                or info["data_scadenza"]
                            )
                            st.markdown(f"**Scadenza:** {scad_fmt}")
                        if info["ente"]:
                            st.markdown(f"**Ente:** {info['ente']}")

                        st.markdown("**Clienti compatibili**")
                        try:
                            payload = json.loads(info["json_completo"])
                        except (json.JSONDecodeError, TypeError):
                            payload = {}
                        for m in sorted(
                            info["matches"],
                            key=lambda x: x["score"],
                            reverse=True,
                        ):
                            cliente_match = {
                                "codice_ateco": m.get("cliente_codice_ateco"),
                                "descrizione_attivita": m.get(
                                    "cliente_descrizione_attivita"
                                ),
                            }
                            line = (
                                f"- **{m['cliente_nome']}** — score "
                                f"{int(m['score'])}/100"
                            )
                            if settore_da_verificare(payload, cliente_match):
                                line += (
                                    " — ⚠️ *compatibilità settore da verificare*"
                                )
                            st.markdown(line)

                        st.divider()
                        st.subheader("Bando in 1 minuto")
                        render_disclaimer(payload)
                        st.markdown(genera_scheda(payload))


def render_cliente_form(
    key_prefix: str,
    defaults: dict | None = None,
) -> dict | None:
    d = defaults or {}
    with st.form(f"form_cliente_{key_prefix}"):
        ragione_sociale = st.text_input(
            "Ragione sociale *",
            value=d.get("ragione_sociale", ""),
        )
        p_iva = st.text_input("Partita IVA", value=d.get("p_iva", "") or "")
        codice_ateco = st.text_input(
            "Codice ATECO",
            value=d.get("codice_ateco", "") or "",
            help='Formato standard, es. "62.01"',
        )
        descrizione_attivita = st.text_area(
            "Descrizione attività",
            value=d.get("descrizione_attivita", "") or "",
            help=(
                "Descrivi l'attività in parole (es. noleggio strutture per eventi). "
                "Serve per bandi con attivita_ammesse ma senza codici ATECO numerici."
            ),
        )
        regione = st.selectbox(
            "Regione *",
            options=REGIONI_ITALIANE,
            index=(
                REGIONI_ITALIANE.index(d["regione"])
                if d.get("regione") in REGIONI_ITALIANE
                else 0
            ),
        )
        fatturato = st.number_input(
            "Fatturato annuo (€)",
            min_value=0.0,
            value=float(d.get("fatturato") or 0.0),
            step=1000.0,
            format="%.0f",
        )
        dim_default = d.get("dimensione_impresa", DIMENSIONI_IMPRESA[0])
        dimensione_idx = (
            DIMENSIONI_IMPRESA.index(dim_default)
            if dim_default in DIMENSIONI_IMPRESA
            else 0
        )
        dimensione_impresa = st.radio(
            "Dimensione impresa *",
            options=DIMENSIONI_IMPRESA,
            index=dimensione_idx,
            horizontal=True,
        )
        submitted = st.form_submit_button("Salva profilo")

    if not submitted:
        return None
    if not ragione_sociale.strip():
        st.error("La ragione sociale è obbligatoria.")
        return None
    return {
        "ragione_sociale": ragione_sociale,
        "p_iva": p_iva,
        "codice_ateco": codice_ateco,
        "descrizione_attivita": descrizione_attivita,
        "regione": regione,
        "fatturato": fatturato,
        "dimensione_impresa": dimensione_impresa,
    }


with tab_clienti:
    st.header("Profilo cliente")
    st.caption("RF-001 — Anagrafica clienti salvata su database SQLite.")

    st.subheader("Nuovo cliente")
    nuovo = render_cliente_form("nuovo")
    if nuovo:
        try:
            cid = create_cliente(**nuovo)
            with get_connection() as conn:
                run_matching_for_all_bandi(conn)
            st.success(
                f"Cliente salvato (id {cid}): {nuovo['ragione_sociale']}. "
                "Abbinamenti ricalcolati."
            )
            st.rerun()
        except Exception as exc:
            st.error(f"Errore salvataggio: {exc}")
            log_error(f"Salvataggio cliente fallito: {exc}")

    st.divider()
    st.subheader("Clienti caricati")
    clienti = list_clienti()
    if not clienti:
        st.info("Nessun cliente in archivio. Compila il form sopra per aggiungerne uno.")
    else:
        st.dataframe(
            clienti,
            use_container_width=True,
            hide_index=True,
        )

        st.subheader("Modifica o elimina")
        opzioni = {
            f"{c['id']} — {c['ragione_sociale']}": c["id"] for c in clienti
        }
        scelta = st.selectbox("Seleziona cliente", options=list(opzioni.keys()))
        cliente_id = opzioni[scelta]
        cliente = get_cliente(cliente_id)

        if cliente:
            col_edit, col_del = st.columns(2)
            with col_edit:
                st.markdown("**Modifica dati**")
                aggiornato = render_cliente_form("modifica", defaults=cliente)
                if aggiornato:
                    try:
                        if update_cliente(cliente_id, **aggiornato):
                            with get_connection() as conn:
                                run_matching_for_all_bandi(conn)
                            st.success(
                                "Cliente aggiornato. Abbinamenti ricalcolati."
                            )
                            st.rerun()
                        else:
                            st.error("Aggiornamento non riuscito.")
                    except Exception as exc:
                        st.error(f"Errore aggiornamento: {exc}")
                        log_error(f"Aggiornamento cliente {cliente_id}: {exc}")

            with col_del:
                st.markdown("**Elimina cliente**")
                st.warning("L'operazione è irreversibile.")
                if st.button("Elimina cliente selezionato", type="secondary"):
                    try:
                        if delete_cliente(cliente_id):
                            st.success("Cliente eliminato.")
                            st.rerun()
                        else:
                            st.error("Cliente non trovato.")
                    except Exception as exc:
                        st.error(f"Errore eliminazione: {exc}")
                        log_error(f"Eliminazione cliente {cliente_id}: {exc}")


with tab_estrazione:
    st.header("Estrazione bandi")
    uploaded_file = st.file_uploader("Carica un bando PDF", type=["pdf"])

    if uploaded_file:
        safe_name = Path(uploaded_file.name).name
        file_path = TEMP_DIR / safe_name
        file_bytes = uploaded_file.getvalue()

        try:
            with open(file_path, "wb") as f:
                f.write(file_bytes)
        except OSError as exc:
            st.error(f"Impossibile salvare il file: {exc}")
            log_error(f"Salvataggio PDF fallito: {exc}")
            st.stop()

        st.success(f"File caricato: {safe_name}")
        st.info(f"Dimensione: {len(file_bytes) / 1024:.2f} KB")

        try:
            text = extract_text_from_pdf(str(file_path))
            st.success("Testo estratto correttamente dal PDF (nessun costo API)")
            with st.expander("Anteprima testo estratto (primi 1000 caratteri)"):
                st.text(text[:1000])

            st.divider()
            st.markdown(
                "**Estrazione JSON con AI** — consuma crediti Anthropic "
                "(circa pochi centesimi per PDF). "
                "Clicca il pulsante solo quando serve."
            )

            if st.button("Estrai dati bando con AI", type="primary"):
                with st.spinner("Chiamata a Claude in corso…"):
                    try:
                        raw_data = extract_bando_data(text)
                        result = validate_bando(raw_data, raw_text=text)
                        data = result["data"]

                        st.subheader("Dati bando estratti")
                        st.json(data)

                        for w in result.get("warnings", []):
                            st.info(w)

                        if result["errors"]:
                            st.error("Errori di validazione:")
                            for err in result["errors"]:
                                st.markdown(f"- {err}")

                        if result["needs_manual_review"]:
                            st.warning(
                                "Da revisionare manualmente — oltre il 50% dei campi "
                                f"è vuoto o nullo ({result['null_percentage']:.0f}%)."
                            )

                        if not result["errors"] and not result["needs_manual_review"]:
                            st.success("Validazione completata senza errori")

                        if not result["errors"]:
                            try:
                                bando_id = save_bando_from_json(data)
                                with get_connection() as conn:
                                    run_matching_for_bando(bando_id, conn)
                                st.success(
                                    f"Bando salvato (id {bando_id}) e matching "
                                    "eseguito con tutti i clienti."
                                )
                            except Exception as exc:
                                st.error(f"Salvataggio bando o matching fallito: {exc}")
                                log_error(
                                    f"Salvataggio/matching bando {safe_name}: {exc}"
                                )

                        ok_fields, null_fields = fields_status(data)
                        log_prompt_run(
                            filename=safe_name,
                            fields_ok=ok_fields,
                            fields_null=null_fields,
                            notes=(
                                f"Validazione: {len(result['errors'])} errori, "
                                f"{result['null_percentage']:.0f}% campi vuoti"
                            ),
                        )

                    except MissingAPIKeyError as exc:
                        st.error(str(exc))
                        log_error(str(exc))
                    except InvalidJSONResponse as exc:
                        st.error(str(exc))
                        log_error(f"JSON invalido per {safe_name}: {exc}")
                    except Exception as exc:
                        st.error(f"Errore durante l'estrazione AI: {exc}")
                        log_error(f"Estrazione AI fallita per {safe_name}: {exc}")

        except EmptyPDFException as exc:
            st.error(
                "PDF vuoto o illeggibile — impossibile estrarre testo sufficiente. "
                "Verifica che il PDF contenga testo selezionabile (non solo immagini)."
            )
            log_error(f"PDF illeggibile {safe_name}: {exc}")
