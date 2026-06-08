import json
import pandas as pd
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
    bando_has_constraints,
    get_score_breakdown,
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

# Configurazione pagina in stile SaaS
st.set_page_config(page_title="Bandi Scanner AI", layout="wide", initial_sidebar_state="expanded")

ROOT = Path(__file__).resolve().parent
TEMP_DIR = ROOT / "temp"
TEMP_DIR.mkdir(exist_ok=True)

# 1. Custom CSS per i componenti estetici (Cerchi e Barre di progresso)
custom_css = """
<style>
.match-circle {
    display: flex; flex-direction: column; align-items: center; justify-content: center; margin: auto;
}
.circle-value {
    font-size: 1.8rem; font-weight: 800; border-radius: 50%; width: 85px; height: 85px; 
    display: flex; align-items: center; justify-content: center; margin-bottom: 5px;
}
.circle-green { color: #10b981; border: 5px solid #d1fae5; background: #ecfdf5; }
.circle-yellow { color: #eab308; border: 5px solid #fef08a; background: #fefce8; }
.circle-red { color: #ef4444; border: 5px solid #fecaca; background: #fef2f2; }
.match-label { font-size: 0.75rem; font-weight: 700; color: #94a3b8; letter-spacing: 1px; text-transform: uppercase; }

.progress-container { margin-bottom: 12px; }
.progress-header { display: flex; justify-content: space-between; font-size: 0.9rem; font-weight: 600; margin-bottom: 4px; color: #1e293b; }
.progress-bg { background: #e2e8f0; border-radius: 6px; height: 10px; width: 100%; overflow: hidden; }
.progress-fill { height: 100%; border-radius: 6px; transition: width 0.4s ease; }
.fill-purple { background: #6366f1; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

ensure_database()

def render_disclaimer(bando_payload: dict) -> None:
    st.warning("⚠️ Dati estratti tramite AI — verificare sempre sulla fonte ufficiale prima di procedere.")
    url = get_fonte_url(bando_payload)
    if url:
        st.markdown(f"[Apri la fonte ufficiale]({url})")

def get_color_class(score: int) -> str:
    if score > 70: return "circle-green"
    if score >= 40: return "circle-yellow"
    return "circle-red"

def render_progress_bar(label: str, score: int, max_score: int):
    pct = int((score / max_score) * 100) if max_score > 0 else 0
    html = f"""
    <div class="progress-container">
        <div class="progress-header"><span>{label}</span><span>{score}/{max_score}</span></div>
        <div class="progress-bg"><div class="progress-fill fill-purple" style="width: {pct}%;"></div></div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

# ---------------------------------------------------------
# SIDEBAR (Navigazione)
# ---------------------------------------------------------
st.sidebar.markdown("## 🧭 Menu Principale")
page = st.sidebar.radio(
    "Navigazione",
    ["📊 Dashboard", "📄 Estrazione bandi", "🏢 Profilo cliente"],
    label_visibility="collapsed"
)

st.sidebar.divider()
st.sidebar.caption("⚠️ **Disclaimer AI:** I dati estratti sono generati dall'intelligenza artificiale e non hanno valore legale. Verifica sempre i bandi ufficiali degli Enti erogatori.")

# ---------------------------------------------------------
# PAGINA: DASHBOARD
# ---------------------------------------------------------
if page == "📊 Dashboard":
    with get_connection() as conn:
        n_bandi = count_bandi(conn)
        rows = load_dashboard_rows(conn)

    st.title("I tuoi bandi")
    st.markdown(f"<span style='color:#64748b; font-size:1.1rem;'>L'AI ha scansionato le fonti. Hai **{n_bandi} bandi** in target.</span>", unsafe_allow_html=True)
    st.write("")

    # --- CALCOLO DEI DATI REALI PER I KPI (CORRETTO) ---
    totale_contributi = 0
    totale_abbinamenti = len(rows) if rows else 0
    bandi_calcolati = set()

    if rows:
        for r in rows:
            bid = r["bando_id"]
            if bid not in bandi_calcolati:
                try:
                    payload = json.loads(r["json_completo"])
                    # CORREZIONE: Entriamo dentro la chiave "bando"
                    bando_payload = payload.get("bando", {}) if isinstance(payload, dict) else {}
                    c_max = bando_payload.get("contributo_max", 0)
                    if isinstance(c_max, (int, float)):
                        totale_contributi += c_max
                except:
                    pass
                bandi_calcolati.add(bid)

      

    # KPI in alto con tre colonne e dati dinamici reali
    kpi2, kpi3 = st.columns(2)
    kpi2.metric("BANDI SCANSIONATI", f"{n_bandi}", "Elaborati dall'AI")
    kpi3.metric("ABBINAMENTI ATTIVI", f"{totale_abbinamenti}", "Match trovati")
    
    st.divider()
    
    col_action_left, col_action_right = st.columns([1, 1])
    with col_action_left:
        st.subheader("LA TUA PIPELINE")
    with col_action_right:
        if st.button("🔄 Ricalcola tutti i match", use_container_width=True):
            try:
                with get_connection() as conn:
                    run_matching_for_all_bandi(conn)
                st.success("Ricalcolo completato.")
                st.rerun()
            except Exception as exc:
                st.error(f"Ricalcolo fallito: {exc}")

    if n_bandi == 0:
        st.info("Nessun bando in archivio. Carica il primo PDF dalla sezione **Estrazione bandi**.")
    elif not rows:
        st.warning("Ci sono bandi salvati ma nessun match. Aggiungi almeno un profilo cliente.")
    else:
        # Raggruppa i dati per bando
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
            by_bando[bid]["max_score"] = max(by_bando[bid]["max_score"], row["score"])

        # Generazione visiva delle Card dei Bandi
        for bid in sorted(by_bando.keys(), key=lambda x: by_bando[x]["max_score"], reverse=True):
            info = by_bando[bid]
            max_sc = int(info["max_score"])
            
            try:
                payload = json.loads(info["json_completo"])
            except:
                payload = {}
            
            bando_payload = payload.get("bando", {}) if isinstance(payload, dict) else {}
            
            # 1. Contributo Max: se è un numero lo formatta, altrimenti "N/D"
            valore_contributo = bando_payload.get("contributo_max")
            if isinstance(valore_contributo, (int, float)):
                contributo_max = f"€ {valore_contributo:,.0f}"
            else:
                contributo_max = "N/D"

            # 2. Scadenza: se è vuota o c'è scritto "None", scrivi "N/D"
            scadenza_grezza = info.get("data_scadenza")
            scad_fmt = format_scadenza_italiana(scadenza_grezza) or scadenza_grezza
            
            if not scad_fmt or str(scad_fmt).strip().lower() in ["none", "null", ""]:
                scad_fmt = "N/D"

           # Costruzione dell'interfaccia a card
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"### {info['titolo']}")
                    st.markdown(f"<span style='color:#64748b; font-size:1rem;'>{info['ente']}</span>", unsafe_allow_html=True)
                    st.write("")
                    
                    # Logica per l'etichetta gialla del Contributo
                    if contributo_max == "N/D":
                        contributo_html = "<span style='background:#fef3c7; padding:4px 10px; border-radius:6px; font-weight:600; color:#b45309;'>N/D</span>"
                    else:
                        contributo_html = f"<span style='font-size:1.2rem; font-weight:700;'>{contributo_max}</span>"

                    c1_a, c1_b = st.columns(2)
                    c1_a.markdown(f"**Contributo Max**<br><div style='margin-top:5px;'>{contributo_html}</div>", unsafe_allow_html=True)
                    c1_b.markdown(f"**Scadenza**<br><div style='margin-top:5px;'><span style='background:#fef3c7; padding:4px 10px; border-radius:6px; font-weight:600; color:#b45309;'>{scad_fmt}</span></div>", unsafe_allow_html=True)
                
                with c2:
                    color_cls = get_color_class(max_sc)
                    circle_html = f"""
                    <div class="match-circle">
                        <div class="circle-value {color_cls}">{max_sc}%</div>
                        <div class="match-label">MATCH MAX</div>
                    </div>
                    """
                    st.markdown(circle_html, unsafe_allow_html=True)

                st.write("")
                with st.expander("Vedi Clienti Compatibili & Dettagli Match"):
                    if not bando_has_constraints(payload):
                        st.warning("⚠️ Bando senza vincoli espliciti. Lo score potrebbe non essere rilevante.")
                    
                    for m in sorted(info["matches"], key=lambda x: x["score"], reverse=True):
                        cliente_id = m.get("cliente_id")
                        score_cliente = int(m['score'])
                        
                        cl_col1, cl_col2 = st.columns([1, 2])
                        with cl_col1:
                            st.markdown(f"#### {m['cliente_nome']}")
                            st.markdown(f"**Score totale:** {score_cliente}/100")
                            cliente_match = {"codice_ateco": m.get("cliente_codice_ateco"), "descrizione_attivita": m.get("cliente_descrizione_attivita")}
                            if settore_da_verificare(payload, cliente_match):
                                st.caption("⚠️ Compatibilità settore da verificare")
                        
                        with cl_col2:
                            with get_connection() as conn:
                                cliente_row_db = conn.execute("SELECT * FROM clienti WHERE id = ?", (cliente_id,)).fetchone()
                                if cliente_row_db:
                                    cliente_row = dict(cliente_row_db)
                                else:
                                    cliente_row = {
                                        "id": cliente_id, "ragione_sociale": m.get("cliente_nome"),
                                        "codice_ateco": m.get("cliente_codice_ateco"), "regione": m.get("cliente_regione"),
                                        "fatturato": m.get("cliente_fatturato"), "dimensione_impresa": m.get("cliente_dimensione_impresa"),
                                    }
                            try:
                                bd = get_score_breakdown(payload, cliente_row)
                                render_progress_bar("Codice ATECO", bd['ateco'], 40)
                                render_progress_bar("Regione", bd['regione'], 30)
                                render_progress_bar("Dimensione Impresa", bd['dimensione'], 20)
                                render_progress_bar("Fatturato", bd['fatturato'], 10)
                                
                                if score_cliente != int(bd["total"]):
                                    st.caption(f"*(Discrepanza: score DB={score_cliente}, calcolato={bd['total']})*")
                            except Exception as e:
                                st.error(f"Errore caricamento breakdown: {e}")
                                
                    st.divider()
                    st.markdown("**Sintesi Bando**")
                    render_disclaimer(payload)
                    st.markdown(genera_scheda(payload))

# ---------------------------------------------------------
# PAGINA: ESTRAZIONE BANDI
# ---------------------------------------------------------
elif page == "📄 Estrazione bandi":
    st.header("Estrazione bandi con AI")
    st.write("Carica il PDF ufficiale del bando. L'Intelligenza Artificiale leggerà il documento ed estrarrà automaticamente i vincoli, le scadenze e i massimali.")
    
    with st.container(border=True):
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
            st.stop()

        st.success(f"File caricato: {safe_name} ({len(file_bytes) / 1024:.2f} KB)")

        try:
            text = extract_text_from_pdf(str(file_path))
            with st.expander("Anteprima testo grezzo PDF"):
                st.text(text[:1000])

            if st.button("🚀 Avvia Estrazione AI", type="primary", use_container_width=True):
                with st.spinner("L'AI sta analizzando il documento. L'operazione può richiedere alcuni secondi..."):
                    try:
                        raw_data = extract_bando_data(text)
                        result = validate_bando(raw_data, raw_text=text)
                        data = result["data"]

                        st.subheader("Risultato Estrazione")
                        with st.expander("Vedi JSON Grezzo"):
                            st.json(data)
                            
                        # Logica Esclusioni
                        bando_info = data.get("bando", {})
                        if bando_info.get("ateco_aperto_a_tutti") is False:
                            st.warning("⚠️ Bando con limitazioni settoriali")
                            escl = bando_info.get("note_esclusioni", {})
                            if isinstance(escl, dict):
                                attivita = escl.get("attivita_vietate", [])
                                sezioni = escl.get("sezioni_ateco_escluse", [])
                                if sezioni:
                                    st.markdown(f"**Sezioni ATECO escluse:**\n" + "\n".join([f"- {s}" for s in sezioni]))
                                if attivita:
                                    st.markdown(f"**Attività vietate:**\n" + "\n".join([f"- {a}" for a in attivita]))
                            else:
                                st.markdown(f"**Note esclusioni:** {str(escl)}")

                        for w in result.get("warnings", []): st.info(w)

                        if result["errors"]:
                            st.error("Errori di validazione trovati nell'estrazione:")
                            for err in result["errors"]: st.markdown(f"- {err}")

                        if result["needs_manual_review"]:
                            st.warning(f"Da revisionare manualmente — molti campi mancanti ({result['null_percentage']:.0f}%).")

                        if not result["errors"] and not result["needs_manual_review"]:
                            st.success("✅ Validazione completata senza errori")

                        if not result["errors"]:
                            try:
                                bando_id = save_bando_from_json(data)
                                with get_connection() as conn:
                                    run_matching_for_bando(bando_id, conn)
                                st.success(f"Bando salvato (id {bando_id}) e matching completato con i clienti in database.")

                                # Sintesi visiva
                                bando_payload = data.get("bando", {}) if isinstance(data, dict) else {}
                                st.divider()
                                st.subheader("📋 Sintesi Rapida")
                                
                                c1, c2 = st.columns(2)
                                contributo = bando_payload.get("contributo_max")
                                c1.markdown(f"**Contributo Max:** {f'{contributo:,.0f} €' if isinstance(contributo, (int, float)) else 'N/D'}")
                                f_perduto = bando_payload.get("percentuale_fondo_perduto")
                                c1.markdown(f"**Fondo Perduto:** {f'{f_perduto:.0f}%' if isinstance(f_perduto, (int, float)) else 'N/D'}")
                                
                                c2.markdown(f"**Scadenza:** {bando_payload.get('data_scadenza', 'N/D')}")
                                dim_impresa = bando_payload.get("dimensione_impresa", {})
                                dim_attive = [k for k, v in dim_impresa.items() if v] if isinstance(dim_impresa, dict) else []
                                c2.markdown(f"**Dimensioni:** {', '.join(dim_attive) if dim_attive else 'N/D'}")

                                # Vincoli Fase 5
                                spesa_min = bando_payload.get("spesa_minima_ammissibile")
                                forme_giuridiche = bando_payload.get("forme_giuridiche_ammesse", [])
                                anzianita = bando_payload.get("anzianita_impresa", {})
                                mesi_min = anzianita.get("mesi_minimi_dalla_costituzione")
                                mesi_max = anzianita.get("mesi_massimi_dalla_costituzione")

                                if any([spesa_min, forme_giuridiche, mesi_min, mesi_max]):
                                    st.markdown("---")
                                    st.markdown("🔒 **Vincoli Stringenti Estratti**")
                                    if spesa_min: st.error(f"💰 **Investimento Minimo:** {spesa_min:,.0f} €")
                                    if mesi_min or mesi_max:
                                        t_anz = "🏢 **Anzianità:** "
                                        if mesi_min: t_anz += f"Min {mesi_min} mesi. "
                                        if mesi_max: t_anz += f"Max {mesi_max} mesi. "
                                        st.warning(t_anz)
                                    if forme_giuridiche: st.info(f"🏛️ **Forme Giuridiche:** {', '.join(forme_giuridiche).title()}")

                                ok_fields, null_fields = fields_status(data)
                                log_prompt_run(filename=safe_name, fields_ok=ok_fields, fields_null=null_fields, notes=f"Validazione OK")

                            except Exception as exc:
                                st.error(f"Salvataggio fallito: {exc}")

                    except Exception as exc:
                        st.error(f"Errore durante l'estrazione: {exc}")
        except EmptyPDFException:
            st.error("PDF vuoto o illeggibile (solo immagini o scansioni).")


# ---------------------------------------------------------
# PAGINA: PROFILO CLIENTE
# ---------------------------------------------------------
elif page == "🏢 Profilo cliente":
    import re # Importiamo le librerie per le espressioni regolari
    st.header("Gestione Clienti")
    
    tab_nuovo, tab_gestisci = st.tabs(["➕ Nuovo Cliente", "📋 Archivio Clienti"])
    
    with tab_nuovo:
        def render_cliente_form(key_prefix: str, defaults: dict | None = None) -> dict | None:
            d = defaults or {}
            with st.form(f"form_cliente_{key_prefix}"):
                c1, c2 = st.columns(2)
                ragione_sociale = c1.text_input("Ragione sociale *", value=d.get("ragione_sociale", ""))
                p_iva = c2.text_input("Partita IVA *", value=d.get("p_iva", "") or "", help="Deve contenere esattamente 11 cifre numeriche.")
                
                c3, c4 = st.columns(2)
                codice_ateco = c3.text_input("Codice ATECO *", value=d.get("codice_ateco", "") or "", help="Formato accettato: XX.XX o XX.XX.XX")
                regione = c4.selectbox("Regione *", options=REGIONI_ITALIANE, index=REGIONI_ITALIANE.index(d["regione"]) if d.get("regione") in REGIONI_ITALIANE else 0)
                
                descrizione_attivita = st.text_area("Descrizione attività (Opzionale)", value=d.get("descrizione_attivita", "") or "")
                
                c5, c6 = st.columns(2)
                fatturato = c5.number_input("Fatturato annuo (€) *", min_value=1.0, value=float(d.get("fatturato") or 1.0), step=1000.0)
                dim_default = d.get("dimensione_impresa", DIMENSIONI_IMPRESA[0])
                dimensione_impresa = c6.selectbox("Dimensione impresa *", options=DIMENSIONI_IMPRESA, index=DIMENSIONI_IMPRESA.index(dim_default) if dim_default in DIMENSIONI_IMPRESA else 0)
                
                submitted = st.form_submit_button("Salva Profilo", type="primary")

            if not submitted: 
                return None
            
            # --- BLOCCO DI VALIDAZIONE STRETTA ---
            errori = []
            
            # Controllo campi vuoti
            if not ragione_sociale.strip():
                errori.append("La ragione sociale è obbligatoria.")
            
            # Controllo Partita IVA (Esattamente 11 numeri)
            p_iva = p_iva.strip()
            if not p_iva:
                errori.append("La Partita IVA è obbligatoria.")
            elif not re.fullmatch(r"\d{11}", p_iva):
                errori.append("La Partita IVA non è valida. Deve contenere esattamente 11 numeri (niente lettere o spazi).")
                
            # Controllo Codice ATECO (Formato Numerico con punti)
            codice_ateco = codice_ateco.strip()
            if not codice_ateco:
                errori.append("Il Codice ATECO è obbligatorio.")
            elif not re.fullmatch(r"\d{2}\.\d{2}(?:\.\d{2})?", codice_ateco):
                errori.append("Il Codice ATECO non è valido. Usa il formato corretto, es: 62.01 o 62.01.12")
                
            # Mostra gli errori e blocca il salvataggio
            if errori:
                for err in errori:
                    st.error(f"❌ {err}")
                return None
            
            # Se passa tutti i controlli, restituisce i dati puliti
            return {
                "ragione_sociale": ragione_sociale, 
                "p_iva": p_iva, 
                "codice_ateco": codice_ateco, 
                "descrizione_attivita": descrizione_attivita, 
                "regione": regione, 
                "fatturato": fatturato, 
                "dimensione_impresa": dimensione_impresa
            }

        nuovo = render_cliente_form("nuovo")
        if nuovo:
            try:
                cid = create_cliente(**nuovo)
                with get_connection() as conn: run_matching_for_all_bandi(conn)
                st.success(f"Cliente {nuovo['ragione_sociale']} salvato! (Abbinamenti ricalcolati)")
            except Exception as exc:
                st.error(f"Errore salvataggio: {exc}")

    with tab_gestisci:
        clienti = list_clienti()
        if not clienti:
            st.info("Nessun cliente in archivio.")
        else:
            st.dataframe(clienti, use_container_width=True, hide_index=True)
            
            st.subheader("Modifica / Elimina")
            opzioni = {f"{c['id']} — {c['ragione_sociale']}": c["id"] for c in clienti}
            scelta = st.selectbox("Seleziona cliente", options=list(opzioni.keys()))
            cliente_id = opzioni[scelta]
            cliente = get_cliente(cliente_id)

            if cliente:
                with st.expander("Modifica dati", expanded=True):
                    aggiornato = render_cliente_form("modifica", defaults=cliente)
                    if aggiornato:
                        if update_cliente(cliente_id, **aggiornato):
                            with get_connection() as conn: run_matching_for_all_bandi(conn)
                            st.success("Cliente aggiornato.")
                            st.rerun()
                            
                st.write("")
                if st.button("🗑️ Elimina questo cliente", type="secondary"):
                    if delete_cliente(cliente_id):
                        st.success("Cliente eliminato.")
                        st.rerun()