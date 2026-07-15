"""Abbinamento bandi / clienti, scheda sintetica e scoring."""
from __future__ import annotations
import json
import re
from datetime import datetime
from typing import Any
from modules.log_utils import log_error
from modules.schema import (
    DIMENSIONE_IMPRESA_KEYS,
    normalize_percentuale_fondo_perduto,
    normalize_response,
)

WEIGHT_REGIONE = 30
WEIGHT_ATECO = 40
WEIGHT_DIMENSIONE = 20
WEIGHT_FATTURATO = 10
SCORE_ATECO_ATTIVITA_INCERTO = 15
SCORE_ATECO_ATTIVITA_PARZIALE = 15
SCORE_ATECO_ATTIVITA_BUONO = 30
_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_MESI_IT = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre")

# ── Soglie dimensionali UE (Raccomandazione 2003/361/CE) ────────────────────
# Usate per verificare la coerenza tra dimensione_impresa dichiarata dal
# cliente e i suoi dati numerici (dipendenti, fatturato).
SOGLIE_DIMENSIONE_UE: dict[str, dict] = {
    "micro":   {"dip_min": None, "dip_max": 9,   "fatturato_max": 2_000_000},
    "piccola": {"dip_min": None, "dip_max": 49,  "fatturato_max": 10_000_000},
    "media":   {"dip_min": None, "dip_max": 249, "fatturato_max": 50_000_000},
    "grande":  {"dip_min": 250,  "dip_max": None, "fatturato_max": None},
}


def valida_coerenza_dimensione(
    dimensione: str | None,
    fatturato: float | None,
    numero_dipendenti: int | None,
) -> list[str]:
    """Verifica la coerenza tra la dimensione_impresa dichiarata e le soglie
    UE (dipendenti/fatturato). Ritorna una lista di messaggi di errore, vuota
    se coerente o se i dati non sono sufficienti per una verifica."""
    dim = _norm_str(dimensione).lower()
    soglie = SOGLIE_DIMENSIONE_UE.get(dim)
    if soglie is None:
        return []

    errori: list[str] = []

    dip_max = soglie.get("dip_max")
    if dip_max is not None and numero_dipendenti is not None and numero_dipendenti > dip_max:
        errori.append(
            f"Un'impresa '{dimensione}' non può avere più di "
            f"{dip_max} dipendenti (inseriti: {numero_dipendenti})"
        )

    dip_min = soglie.get("dip_min")
    if dip_min is not None and numero_dipendenti is not None:
        if numero_dipendenti < dip_min:
            errori.append(
                f"Un'impresa '{dimensione}' deve avere almeno "
                f"{dip_min} dipendenti (inseriti: {numero_dipendenti})"
            )

    fatturato_max = soglie.get("fatturato_max")
    if fatturato_max is not None and fatturato is not None and fatturato > fatturato_max:
        errori.append(
            f"Un'impresa '{dimensione}' non può avere fatturato superiore a "
            f"€ {fatturato_max:,.0f} (inserito: € {fatturato:,.0f})"
        )

    return errori

# ── Mappatura forme giuridiche specifiche → categoria generica ──────────────
# Usata da check_ammissibilita() per confrontare la forma giuridica del cliente
# (es. "S.r.l.") con le categorie generiche che il bando può ammettere
# (es. "società di capitali"), invece di un fragile confronto di stringa 1:1.
# Le chiavi sono già normalizzate (vedi _norm_fg): senza spazi/punti/trattini/slash,
# senza accenti, minuscolo. Alcune voci sono forme specifiche (es. "srl"),
# altre sono le categorie stesse già scritte per esteso (es. "societadicapitali"),
# perché il bando può indicare l'una o l'altra indifferentemente.
CAT_SOCIETA_CAPITALI = "società di capitali"
CAT_SOCIETA_PERSONE = "società di persone"
CAT_DITTE_INDIVIDUALI = "ditte individuali"
CAT_COOPERATIVE = "cooperative"
CAT_NOPROFIT = "associazioni ed enti no-profit"
CAT_PROFESSIONISTI = "liberi professionisti"

FORMA_GIURIDICA_CATEGORIE: dict[str, str] = {
    # Società di capitali
    "srls": CAT_SOCIETA_CAPITALI,
    "srl": CAT_SOCIETA_CAPITALI,
    "spa": CAT_SOCIETA_CAPITALI,
    "sapa": CAT_SOCIETA_CAPITALI,
    "responsabilitalimitata": CAT_SOCIETA_CAPITALI,  # copre "società (a/di) responsabilità limitata"
    "perazioni": CAT_SOCIETA_CAPITALI,               # copre "società per azioni"
    "societadicapitali": CAT_SOCIETA_CAPITALI,       # categoria già scritta per esteso dal bando
    # Società di persone
    "snc": CAT_SOCIETA_PERSONE,
    "sas": CAT_SOCIETA_PERSONE,
    "ss": CAT_SOCIETA_PERSONE,
    "nomecollettivo": CAT_SOCIETA_PERSONE,
    "accomanditasemplice": CAT_SOCIETA_PERSONE,
    "societasemplice": CAT_SOCIETA_PERSONE,
    "societadipersone": CAT_SOCIETA_PERSONE,
    # Ditte individuali / imprenditori individuali
    "dittaindividuale": CAT_DITTE_INDIVIDUALI,
    "imprenditoreindividuale": CAT_DITTE_INDIVIDUALI,
    "impresaindividuale": CAT_DITTE_INDIVIDUALI,
    "ditteindividuali": CAT_DITTE_INDIVIDUALI,
    "imprenditoriindividuali": CAT_DITTE_INDIVIDUALI,
    "impreseindividuali": CAT_DITTE_INDIVIDUALI,
    # Cooperative
    "societacooperativa": CAT_COOPERATIVE,
    "cooperativa": CAT_COOPERATIVE,
    "cooperative": CAT_COOPERATIVE,
    "coop": CAT_COOPERATIVE,
    "scarl": CAT_COOPERATIVE,
    "scrl": CAT_COOPERATIVE,
    "scpa": CAT_COOPERATIVE,
    # Associazioni / enti no-profit
    "associazione": CAT_NOPROFIT,
    "fondazione": CAT_NOPROFIT,
    "onlus": CAT_NOPROFIT,
    "ets": CAT_NOPROFIT,
    "aps": CAT_NOPROFIT,
    "odv": CAT_NOPROFIT,
    "associazionientinoprofit": CAT_NOPROFIT,
    # Liberi professionisti
    "liberoprofessionista": CAT_PROFESSIONISTI,
    "studioprofessionale": CAT_PROFESSIONISTI,
    "studioassociato": CAT_PROFESSIONISTI,
    "liberiprofessionisti": CAT_PROFESSIONISTI,
}
# Chiavi ordinate per lunghezza decrescente: usate per il matching "by containment"
# (es. "srlunipersonale" contiene "srl"), provando prima le chiavi più specifiche.
_FORMA_GIURIDICA_CHIAVI_ORDINATE = sorted(FORMA_GIURIDICA_CATEGORIE, key=len, reverse=True)
# Marcatore per riconoscere bandi che ammettono esplicitamente "tutte le forme
# giuridiche iscritte al Registro Imprese" (nessun vincolo reale di forma)
_REGISTRO_IMPRESE_MARKER = "registroimprese"

# ── Mappa sezioni ATECO → intervallo divisioni (classificazione ATECO 2007/2025) ──
# Usata per confrontare `note_esclusioni.sezioni_ateco_escluse` (lettere di sezione,
# es. "K") con il codice ATECO del cliente (divisione a 2 cifre, es. "64.19" → 64).
ATECO_SEZIONI_DIVISIONI: dict[str, tuple[int, int]] = {
    "A": (1, 3), "B": (5, 9), "C": (10, 33), "D": (35, 35), "E": (36, 39),
    "F": (41, 43), "G": (45, 47), "H": (49, 53), "I": (55, 56), "J": (58, 63),
    "K": (64, 66), "L": (68, 68), "M": (69, 75), "N": (77, 82), "O": (84, 84),
    "P": (85, 85), "Q": (86, 88), "R": (90, 93), "S": (94, 96), "T": (97, 98),
    "U": (99, 99),
}
ATECO_SEZIONI_LABELS: dict[str, str] = {
    "A": "Agricoltura, silvicoltura e pesca",
    "B": "Estrazione di minerali",
    "C": "Attività manifatturiere",
    "D": "Energia elettrica e gas",
    "E": "Acqua, reti fognarie e rifiuti",
    "F": "Costruzioni",
    "G": "Commercio",
    "H": "Trasporto e magazzinaggio",
    "I": "Alloggio e ristorazione",
    "J": "Servizi di informazione e comunicazione",
    "K": "Attività finanziarie e assicurative",
    "L": "Attività immobiliari",
    "M": "Attività professionali, scientifiche e tecniche",
    "N": "Servizi di supporto alle imprese",
    "O": "Amministrazione pubblica",
    "P": "Istruzione",
    "Q": "Sanità e assistenza sociale",
    "R": "Attività artistiche, sportive e di intrattenimento",
    "S": "Altre attività di servizi",
    "T": "Attività di famiglie e convivenze",
    "U": "Organizzazioni extraterritoriali",
}
_SEZIONE_LETTERA_RE = re.compile(r"\b([A-U])\b")

def _sezione_da_divisione(div: int) -> str | None:
    for sezione, (lo, hi) in ATECO_SEZIONI_DIVISIONI.items():
        if lo <= div <= hi:
            return sezione
    return None

def _divisione_da_codice(codice_ateco: str | None) -> int | None:
    pref = _ateco_prefix_two(codice_ateco)
    if not pref or not pref.isdigit():
        return None
    return int(pref)

def _estrai_lettera_sezione(voce: str) -> str | None:
    """Estrae la lettera di sezione ATECO (A-U) da una voce come "K" o "Sezione K - Attività finanziarie"."""
    m = _SEZIONE_LETTERA_RE.search(voce.strip().upper())
    return m.group(1) if m else None

def _sezione_cliente_esclusa(bando: dict[str, Any], cliente: dict[str, Any]) -> bool:
    """True se la sezione ATECO del cliente rientra tra le sezioni escluse dal bando."""
    note = bando.get("note_esclusioni")
    sezioni_escluse = _norm_list(note.get("sezioni_ateco_escluse")) if isinstance(note, dict) else []
    if not sezioni_escluse:
        return False
    codice_cliente = _norm_str(cliente.get("codice_ateco") or cliente.get("ateco"))
    div_cliente = _divisione_da_codice(codice_cliente)
    if div_cliente is None:
        return False
    sezione_cliente = _sezione_da_divisione(div_cliente)
    if sezione_cliente is None:
        return False
    lettere_escluse = {l for v in sezioni_escluse if (l := _estrai_lettera_sezione(v))}
    return sezione_cliente in lettere_escluse


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
    if _sezione_cliente_esclusa(bando, cliente): return 0
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
        return 0
    return 0

def bando_has_constraints(payload: dict[str, Any]) -> bool:
    bando = _unwrap_bando(payload)
    ateco_aperto = bando.get("ateco_aperto_a_tutti", False)
    codici_ateco = _codici_ateco_bando(bando)
    attivita_ammesse = _attivita_ammesse_bando(bando)
    regioni = _regioni_bando(bando)
    fatturato_max = bando.get("fatturato_max")
    dimensioni = _dimensioni_ammesse(bando)
    if codici_ateco and not ateco_aperto: return True
    if attivita_ammesse and not ateco_aperto: return True
    if regioni and len(regioni) > 0 and "Tutta Italia" not in [r.title() for r in regioni]: return True
    if fatturato_max: return True
    if dimensioni and len(dimensioni) > 0 and len(dimensioni) < 4: return True
    return False

def bando_ambiguo(payload: dict[str, Any]) -> bool:
    """True se dal bando non è stato estratto alcun dato utile a valutare la
    compatibilità (nessun vincolo di settore/regione/dimensione/fatturato e
    non dichiarato esplicitamente aperto a tutti): il match non è "incompatibile",
    sono "dati insufficienti" per esprimere un verdetto (ROADMAP #13)."""
    bando = _unwrap_bando(payload if isinstance(payload, dict) else {})
    return not bando_has_constraints(payload) and not bando.get("ateco_aperto_a_tutti")

def calculate_score(bando: dict[str, Any], cliente: dict[str, Any]) -> int:
    b = _unwrap_bando(bando if isinstance(bando, dict) else {})
    c = cliente if isinstance(cliente, dict) else {}
    total = _score_regione(b, c) + _score_ateco(b, c) + _score_dimensione(b, c) + _score_fatturato(b, c)
    return max(0, min(100, int(total)))

def get_score_breakdown(payload: dict[str, Any], cliente: dict[str, Any]) -> dict[str, Any]:
    bando = _unwrap_bando(payload)
    score_regione = _score_regione(bando, cliente)
    score_ateco = _score_ateco(bando, cliente)
    score_dim = _score_dimensione(bando, cliente)
    score_fat = _score_fatturato(bando, cliente)
    totale = score_regione + score_ateco + score_dim + score_fat
    return {
        "regione": score_regione, "ateco": score_ateco, "dimensione": score_dim, "fatturato": score_fat,
        "total": max(0, min(100, int(totale))),
        "status": "da_verificare" if bando_ambiguo(payload) else "ok",
    }

_ACCENTI_TRANS = str.maketrans("àèéìòùÀÈÉÌÒÙ", "aeeiouAEEIOU")

def _norm_fg(s: str | None) -> str:
    """Normalizza una forma giuridica per il confronto: rimuove spazi/punti/trattini/slash, accenti, minuscolo."""
    if not s: return ""
    senza_separatori = re.sub(r"[\s./\-]", "", _norm_str(s))
    return senza_separatori.translate(_ACCENTI_TRANS).lower()

def _categoria_forma(forma_norm: str) -> str | None:
    """Deduce la categoria generica di una forma giuridica già normalizzata.

    Prova prima l'uguaglianza esatta, poi il contenimento (chiavi più lunghe
    prima) per coprire varianti non standard come "srl unipersonale".
    Ritorna None se la forma non è riconosciuta.
    """
    if not forma_norm:
        return None
    diretto = FORMA_GIURIDICA_CATEGORIE.get(forma_norm)
    if diretto:
        return diretto
    for chiave in _FORMA_GIURIDICA_CHIAVI_ORDINATE:
        if chiave in forma_norm:
            return FORMA_GIURIDICA_CATEGORIE[chiave]
    return None

def check_ammissibilita(bando_json: dict[str, Any], cliente: dict[str, Any]) -> dict[str, Any]:
    """Controlla criteri binari di esclusione: anzianità, forma giuridica, spesa minima."""
    b = _unwrap_bando(bando_json if isinstance(bando_json, dict) else {})
    c = cliente if isinstance(cliente, dict) else {}

    ammissibile = True
    motivi_esclusione: list[str] = []
    criteri_verificati: list[str] = []

    # Helper: calcola mesi dalla data_costituzione
    data_cost_str = _norm_str(c.get("data_costituzione"))
    mesi_dalla_cost: int | None = None
    if data_cost_str:
        try:
            dt_cost = datetime.strptime(data_cost_str, "%Y-%m-%d").date()
            today = datetime.today().date()
            mesi_dalla_cost = (today.year - dt_cost.year) * 12 + (today.month - dt_cost.month)
        except (ValueError, TypeError):
            pass

    # Criterio 1: Anzianità minima
    anz_info = b.get("anzianita_impresa") or {}
    mesi_min = anz_info.get("mesi_minimi_dalla_costituzione")
    if mesi_min is not None and mesi_min > 0:
        if mesi_dalla_cost is None:
            criteri_verificati.append("Anzianità minima: non verificabile")
        elif mesi_dalla_cost < mesi_min:
            ammissibile = False
            motivi_esclusione.append(f"Azienda costituita da {mesi_dalla_cost} mesi, richiesti almeno {mesi_min}")
        else:
            criteri_verificati.append(f"Anzianità minima: OK ({mesi_dalla_cost} mesi su {mesi_min} richiesti)")

    # Criterio 2: Anzianità massima
    mesi_max = anz_info.get("mesi_massimi_dalla_costituzione")
    if mesi_max is not None and mesi_max > 0:
        if mesi_dalla_cost is None:
            criteri_verificati.append("Anzianità massima: non verificabile")
        elif mesi_dalla_cost > mesi_max:
            ammissibile = False
            motivi_esclusione.append(f"Azienda costituita da {mesi_dalla_cost} mesi, limite massimo {mesi_max}")
        else:
            criteri_verificati.append(f"Anzianità massima: OK ({mesi_dalla_cost} mesi, limite {mesi_max})")

    # Criterio 2bis: Sezione ATECO esclusa
    # Confronta la sezione ATECO del cliente (dedotta dalla divisione, es. "64.19" → K)
    # con `note_esclusioni.sezioni_ateco_escluse`: un'esclusione di sezione è un
    # criterio binario, non un semplice sconto di punteggio come in _score_ateco.
    if _sezione_cliente_esclusa(b, c):
        codice_cliente = _norm_str(c.get("codice_ateco") or c.get("ateco"))
        div_cliente = _divisione_da_codice(codice_cliente)
        sezione_cliente = _sezione_da_divisione(div_cliente) if div_cliente is not None else None
        ammissibile = False
        motivi_esclusione.append(
            f"Codice ATECO {codice_cliente} (Sezione {sezione_cliente}) escluso dal bando"
        )

    # Criterio 3: Forma giuridica
    # Confronto per categoria generica (es. "S.r.l." → "società di capitali"),
    # non per uguaglianza letterale: il bando spesso ammette categorie ampie
    # mentre il cliente ha una forma specifica, e le due stringhe non
    # coincidono mai a livello di puro testo.
    forme_ammesse = _norm_list(b.get("forme_giuridiche_ammesse"))
    if forme_ammesse:
        forma_cliente = _norm_str(c.get("forma_giuridica"))
        if not forma_cliente:
            criteri_verificati.append("Forma giuridica: non verificabile")
        else:
            forma_norm = _norm_fg(forma_cliente)
            categoria_cliente = _categoria_forma(forma_norm)

            # Caso speciale: il bando ammette esplicitamente "tutte le forme
            # giuridiche iscritte al Registro Imprese" → nessun vincolo reale
            apre_a_tutti = any(_REGISTRO_IMPRESE_MARKER in _norm_fg(voce) for voce in forme_ammesse)

            if apre_a_tutti:
                criteri_verificati.append(f"Forma giuridica: OK ({forma_cliente}, bando aperto a tutte le forme iscritte al Registro Imprese)")
            else:
                # Deduce la categoria (o, in fallback, il testo normalizzato)
                # di ogni voce ammessa dal bando: può essere già una forma
                # specifica ("S.r.l.") o una categoria scritta per esteso
                # ("società di capitali").
                categorie_bando: set[str] = set()
                fallback_testuale_bando: set[str] = set()
                for voce in forme_ammesse:
                    voce_norm = _norm_fg(voce)
                    categoria_voce = _categoria_forma(voce_norm)
                    if categoria_voce:
                        categorie_bando.add(categoria_voce)
                    else:
                        fallback_testuale_bando.add(voce_norm)

                if categoria_cliente is not None:
                    match = categoria_cliente in categorie_bando
                else:
                    # Forma cliente non mappata: ultima possibilità, identità
                    # testuale diretta con una voce non mappabile del bando
                    match = forma_norm in fallback_testuale_bando

                if match:
                    criteri_verificati.append(f"Forma giuridica: OK ({forma_cliente})")
                elif categoria_cliente is None:
                    # Non escludere una forma che non sappiamo classificare:
                    # serve verifica manuale, non un'esclusione automatica
                    criteri_verificati.append(f"Verifica forma giuridica: '{forma_cliente}' non riconosciuta, controlla manualmente")
                else:
                    ammissibile = False
                    motivi_esclusione.append(
                        f"Forma giuridica '{forma_cliente}' ({categoria_cliente}) non inclusa tra le ammesse: {', '.join(forme_ammesse)}"
                    )

    # Criterio 4: Spesa minima
    spesa_min = b.get("spesa_minima_ammissibile")
    if spesa_min is not None and spesa_min > 0:
        fatturato = c.get("fatturato")
        try:
            fat_num = float(fatturato) if fatturato else 0
        except (TypeError, ValueError):
            fat_num = 0

        if fat_num == 0:
            criteri_verificati.append("Spesa minima: non verificabile")
        elif fat_num < spesa_min:
            criteri_verificati.append(
                f"⚠️ Attenzione: fatturato € {fat_num:,.0f} inferiore alla spesa "
                f"minima di € {spesa_min:,.0f} — verificare la capacità di investimento"
            )
        else:
            criteri_verificati.append(f"Spesa minima: OK (€ {fat_num:,.0f} >= € {spesa_min:,.0f})")

    # Criterio 5: dimensione impresa
    # #11 (audit Fable): usa _dimensioni_ammesse invece di leggere dim_bando_raw
    # direttamente come dict — quest'ultimo approccio gestiva SOLO il formato dict,
    # mentre _dimensioni_ammesse (già usata dallo score) gestisce anche stringa/lista,
    # evitando che l'ammissibilità diverga silenziosamente dallo score su payload
    # in formato non-dict (es. legacy o non passati da normalize_response).
    ammesse = _dimensioni_ammesse(b)
    if ammesse:
        dim_cliente = _norm_str(
            c.get("dimensione_impresa") or c.get("dimensione")
        )
        if not dim_cliente:
            criteri_verificati.append(
                "Dimensione impresa: non verificabile (dato cliente assente)"
            )
        elif dim_cliente.lower() not in {d.lower() for d in ammesse}:
            ammissibile = False
            motivi_esclusione.append(
                f"Dimensione '{dim_cliente}' non ammessa dal bando "
                f"(ammesse: {', '.join(ammesse)})"
            )
        else:
            criteri_verificati.append(f"Dimensione impresa: OK ({dim_cliente})")

    # Criterio 6: fatturato massimo
    fat_max = b.get("fatturato_max")
    if fat_max is not None:
        try:
            fat_max_num = float(fat_max)
            fat_cliente = c.get("fatturato")
            if fat_cliente is not None:
                fat_cliente_num = float(fat_cliente)
                if fat_cliente_num > fat_max_num:
                    ammissibile = False
                    motivi_esclusione.append(
                        f"Fatturato € {fat_cliente_num:,.0f} supera il limite "
                        f"di € {fat_max_num:,.0f}"
                    )
                else:
                    criteri_verificati.append(
                        f"Fatturato: OK (€ {fat_cliente_num:,.0f} ≤ € {fat_max_num:,.0f})"
                    )
            else:
                criteri_verificati.append(
                    "Fatturato massimo: non verificabile (dato cliente assente)"
                )
        except (TypeError, ValueError):
            criteri_verificati.append("Fatturato massimo: non verificabile (dato non numerico)")

    # Criterio 7: numero dipendenti
    dip_min = b.get("numero_dipendenti_min")
    dip_max = b.get("numero_dipendenti_max")
    dip_cliente = c.get("numero_dipendenti")

    if dip_min is not None or dip_max is not None:
        if dip_cliente is None:
            criteri_verificati.append(
                "Numero dipendenti: non verificabile (dato cliente assente)"
            )
        else:
            try:
                dip_num = int(dip_cliente)
                if dip_min is not None and dip_num < int(dip_min):
                    ammissibile = False
                    motivi_esclusione.append(
                        f"Numero dipendenti insufficiente: {dip_num} "
                        f"(richiesti almeno {int(dip_min)})"
                    )
                elif dip_max is not None and dip_num > int(dip_max):
                    ammissibile = False
                    motivi_esclusione.append(
                        f"Numero dipendenti troppo alto: {dip_num} "
                        f"(massimo {int(dip_max)})"
                    )
                else:
                    criteri_verificati.append(
                        f"Numero dipendenti: OK ({dip_num})"
                    )
            except (TypeError, ValueError):
                criteri_verificati.append(
                    "Numero dipendenti: non verificabile (dato non numerico)"
                )

    # Criterio 8: regione
    regioni_bando = _regioni_bando(b)
    if regioni_bando:
        lowered = {r.lower() for r in regioni_bando}
        if "tutte" not in lowered and "tutta italia" not in lowered:
            regione_cliente = _norm_str(c.get("regione"))
            if not regione_cliente:
                criteri_verificati.append(
                    "Regione: non verificabile (dato cliente assente)"
                )
            elif regione_cliente.lower() not in lowered:
                ammissibile = False
                motivi_esclusione.append(
                    f"Regione '{regione_cliente}' non ammessa dal bando "
                    f"(ammesse: {', '.join(regioni_bando)})"
                )
            else:
                criteri_verificati.append(
                    f"Regione: OK ({regione_cliente})"
                )

    return {
        "ammissibile": ammissibile,
        "motivi_esclusione": motivi_esclusione,
        "criteri_verificati": criteri_verificati,
    }

def run_matching_for_bando(bando_id: int, conn: Any, soglia_minima: int = 0) -> None:
    try:
        row = conn.execute(
            "SELECT json_completo, review_status FROM bandi WHERE id = %s",
            (bando_id,),
        ).fetchone()
        if not row: return
        review_status = row.get("review_status", "validato")
        if review_status != "validato":
            # Un bando in revisione non deve conservare match calcolati in
            # precedenza: `null` significa dato sconosciuto, non via libera.
            conn.execute("DELETE FROM match_results WHERE bando_id = %s", (bando_id,))
            conn.commit()
            return
        payload = json.loads(row["json_completo"])
        bando_data = payload if isinstance(payload, dict) else {}
        clienti = conn.execute("SELECT * FROM clienti").fetchall()
        for cliente_row in clienti:
            cliente = dict(cliente_row)
            score = calculate_score(bando_data, cliente)
            if score < soglia_minima: continue
            existing = conn.execute("SELECT id FROM match_results WHERE cliente_id = %s AND bando_id = %s", (cliente["id"], bando_id)).fetchone()
            if existing: conn.execute("UPDATE match_results SET score = %s, data_match = NOW() WHERE id = %s", (score, existing["id"]))
            else: conn.execute("INSERT INTO match_results (cliente_id, bando_id, score) VALUES (%s, %s, %s)", (cliente["id"], bando_id, score))
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
    if regioni: parts.append("- **Territorio:** " + ", ".join(regioni))
    if bando.get("ateco_aperto_a_tutti") is True: parts.append("- **ATECO:** aperto a tutti i settori")
    else:
        codici = _codici_ateco_bando(bando)
        if codici: parts.append("- **ATECO ammessi:** " + ", ".join(codici))
        attivita = _norm_list(bando.get("attivita_ammesse"))
        spese = _norm_list(bando.get("spese_ammissibili"))
        # Se le spese sono disponibili sono la rappresentazione più schematica
        # degli interventi: non mostrare entrambe le liste nella stessa scheda.
        if attivita and not spese:
            parts.append("### Interventi ammessi\n\n" + _all_bullets(attivita))
    dim = _dimensioni_ammesse(bando)
    if dim: parts.append("- **Dimensioni impresa:** " + ", ".join(dim))
    return "\n".join(parts) if parts else None


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def _display_fallback(value: str, limit: int = 90) -> str:
    """Rende leggibile una voce non coperta dal catalogo senza toccare il dato."""
    compact = re.sub(r"\s+", " ", value).strip(" -–—,;.")
    compact = re.sub(
        r"^(?:spese?|costi?|investimenti?)\s+(?:ammissibili\s+)?(?:per|di|in)\s+",
        "",
        compact,
        flags=re.IGNORECASE,
    )
    if compact:
        compact = compact[0].upper() + compact[1:]
    return compact if len(compact) <= limit else compact[:limit - 1].rstrip() + "…"


def _compact_expense_labels(values: list[str]) -> list[str]:
    """Trasforma descrizioni verbose in categorie di spesa brevi per la scheda.

    La normalizzazione è solo di presentazione: il JSON originale conserva le
    formulazioni estratte, utili per audit e matching.
    """
    result: list[str] = []
    generic: list[str] = []
    for value in values:
        key = _norm_fg(value)
        matched = False

        rules: tuple[tuple[str, tuple[str, ...]], ...] = (
            ("Arredi", ("arred",)),
            ("Impianti", ("impiant",)),
            ("Macchinari", ("macchinar",)),
            ("Attrezzature", ("attrezzatur",)),
            ("Mezzi targati", ("mezzitargat", "veicol", "automezz")),
            ("Hardware", ("hardware",)),
            ("Software", ("software", "licenzeinformatic")),
            ("Brevetti", ("brevett",)),
            ("Certificazioni di qualità", ("certificaz", "sistemadiqualita")),
            ("Realizzazione sito web", ("sitoweb", "sitointernet", "portaleweb")),
            ("Adeguamento funzionale sede operativa", ("adeguamentofunzional",)),
            ("Ristrutturazione sede operativa", ("ristrutturazion",)),
            ("Ricerca e sviluppo", ("ricercaesviluppo",)),
            ("Consulenze specialistiche", ("consulenz",)),
            ("Formazione", ("formazion",)),
            ("Personale", ("costidelpersonale", "spesedipersonale")),
            ("Imposta di bollo", ("impostadibollo", "bollodovut")),
            ("Servizi di accompagnamento alla realizzazione", ("servizidiaccompagnamento",)),
        )
        for label, needles in rules:
            if any(needle in key for needle in needles):
                _append_unique(result, label)
                matched = True
        if re.search(r"\biva\b", value, re.IGNORECASE):
            _append_unique(result, "IVA")
            matched = True

        if matched:
            continue
        if key in {
            "investimentimaterialieimmateriali",
            "altrespeseconnesse",
            "altrespeseconnesseallarealizzazionedelprogetto",
        }:
            generic.append(_display_fallback(value))
        else:
            _append_unique(result, _display_fallback(value))

    # Le categorie ombrello aggiungono rumore quando sono già disponibili le
    # singole spese; restano visibili soltanto se il bando non offre dettaglio.
    if not result:
        for value in generic:
            _append_unique(result, value)
    return result


def _compact_forbidden_labels(values: list[str]) -> list[str]:
    """Riduce formulazioni normative a categorie autonome e deduplicate."""
    result: list[str] = []
    for value in values:
        key = _norm_fg(value)
        matched = False

        def add(label: str) -> None:
            nonlocal matched
            _append_unique(result, label)
            matched = True

        if "tabacc" in key:
            add("Tabacco (salvo bar tabacchi)" if "bartabacc" in key else "Tabacco")
        if any(token in key for token in ("giocodazzardo", "casedagioco", "casadagioco")):
            add("Gioco d'azzardo")
        if "pornograf" in key or "commerciosessual" in key:
            add("Pornografia e commercio sessuale")
        if "armi" in key or "munizion" in key:
            add("Armi e munizioni")
        if "nuclear" in key:
            add("Energia nucleare")
        if "pesc" in key or "acquacoltur" in key:
            add("Pesca e acquacoltura")
        if "produzioneprimaria" in key and ("agricol" in key or "prodottiagricoli" in key):
            add("Attività agricole primarie")
        if "sviluppoimmobiliar" in key and any(
            token in key for token in ("speculat", "unicoscopo", "rivendit", "rilocazion")
        ):
            add("Sviluppo immobiliare speculativo")
        if "esportazion" in key or "retedidistribuzion" in key:
            add("Attività di esportazione e reti di distribuzione")
        if "dirittiuman" in key or "dirittiindividual" in key:
            add("Violazioni dei diritti umani")
        if "clonazion" in key or "patrimoniogenetico" in key or "embrion" in key:
            add("Clonazione e modificazione genetica umana")
        if "animalivivi" in key and ("sperimental" in key or "scientific" in key):
            add("Sperimentazione animale")
        if "combustibilifossil" in key or "estrazionemineraria" in key:
            add("Combustibili fossili ed estrazione mineraria")
        if "discaric" in key:
            add("Smaltimento dei rifiuti in discarica")
        if "trattamentomeccanicobiologico" in key or "tmb" in key:
            add("Trattamento meccanico-biologico dei rifiuti")
        if "inceneritor" in key:
            add("Incenerimento dei rifiuti")
        if "infrastruttureaeroportual" in key:
            add("Infrastrutture aeroportuali")

        # Le attività finanziarie/assicurative e immobiliari generiche sono
        # rappresentate in "Settori esclusi", quindi non vanno ripetute qui.
        sector_only = (
            "finanziar" in key
            or "assicurativ" in key
            or ("immobiliar" in key and "sviluppoimmobiliar" not in key)
        )
        if not matched and not sector_only:
            add(_display_fallback(value))
    return result


def _sezione_esclusioni(b: dict[str, Any]) -> str | None:
    note = b.get("note_esclusioni")
    if isinstance(note, str) and note.strip():
        return f"## Esclusioni\n\n{note.strip()}"
    if not isinstance(note, dict):
        return None
    sections: list[str] = []
    sezioni = _norm_list(note.get("sezioni_ateco_escluse"))
    sezioni_leggibili: list[str] = []
    for voce in sezioni:
        lettera = _estrai_lettera_sezione(voce)
        label = ATECO_SEZIONI_LABELS.get(lettera or "")
        sezioni_leggibili.append(f"Sez. {lettera} – {label}" if lettera and label else voce)
    if sezioni_leggibili:
        sections.append("### Sezioni ATECO\n\n" + "\n".join(f"- {item}" for item in sezioni_leggibili))
    vietate = _norm_list(note.get("attivita_vietate"))
    settori: list[str] = []
    for voce in vietate:
        lowered = voce.casefold()
        settore = None
        if "finanziar" in lowered and "assicurativ" in lowered:
            settore = ATECO_SEZIONI_LABELS["K"]
        elif "finanziar" in lowered:
            settore = "Attività finanziarie"
        elif "assicurativ" in lowered:
            settore = "Attività assicurative"
        elif "immobiliar" in lowered:
            settore = ATECO_SEZIONI_LABELS["L"]
        if settore and settore not in settori:
            settori.append(settore)
    altre_vietate = _compact_forbidden_labels(vietate)
    if settori:
        sections.append("### Settori esclusi\n\n" + _all_bullets(settori))
    if altre_vietate:
        sections.append("### Attività vietate\n\n" + _all_bullets(altre_vietate))

    structured_groups = (
        ("Soggetti esclusi", "soggetti_esclusi"),
        ("Spese non ammissibili", "spese_non_ammissibili"),
        ("Altre esclusioni", "altre_esclusioni"),
    )
    for title, key in structured_groups:
        values = _norm_list(note.get(key))
        if values:
            sections.append(f"### {title}\n\n" + _all_bullets(values))

    # Compatibilità con estrazioni precedenti: il vecchio paragrafo libero è
    # mostrato solo quando non esiste alcuna informazione strutturata.
    testo = _norm_str(note.get("lista_testuale"))
    if testo and not sections:
        sections.append("### Nota\n\n" + testo)
    return "## Esclusioni\n\n" + "\n\n".join(sections) if sections else None

MODALITA_PRESENTAZIONE_LABELS: dict[str, str] = {
    "sportello": "Sportello (a esaurimento fondi)",
    "click_day": "Click day",
    "graduatoria": "Graduatoria a valutazione",
    "mista": "Mista (sportello + graduatoria)",
}

TIPO_AGEVOLAZIONE_LABELS: dict[str, str] = {
    "fondo_perduto": "Fondo perduto",
    "finanziamento_agevolato": "Finanziamento agevolato",
    "garanzia": "Garanzia",
    "credito_imposta": "Credito d'imposta",
    "voucher": "Voucher",
}

RUOLO_ENTE_LABELS: dict[str, str] = {
    "promotore": "Promotore",
    "gestore": "Gestore",
    "ente_attuatore": "Ente attuatore",
    "intermediario_finanziario": "Intermediario finanziario",
    "piattaforma": "Piattaforma",
    "altro": "Altro soggetto",
}

def _format_pct(value: Any) -> str | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f"{f:.0f}%" if f == int(f) else f"{f}%"


def _shorten(value: str, limit: int = 180) -> str:
    compact = re.sub(r"\s+", " ", value).strip()
    return compact if len(compact) <= limit else compact[:limit - 1].rstrip() + "…"


def _all_bullets(values: list[str]) -> str:
    return "\n".join(f"- {value}" for value in values)


def _compact_legal_forms(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = _norm_fg(value)
        if "responsabilitalimitatasemplificata" in key or key.startswith("srls"):
            canonical = "S.r.l.s."
        elif "responsabilitalimitata" in key or key.startswith("srl"):
            canonical = "S.r.l."
        elif "nomecollettivo" in key or key == "snc":
            canonical = "S.n.c."
        elif "accomanditasemplice" in key or key == "sas":
            canonical = "S.a.s."
        elif "cooperativ" in key:
            canonical = "Cooperative"
        elif "individual" in key:
            canonical = "Ditte individuali"
        elif "profession" in key:
            canonical = "Liberi professionisti"
        else:
            canonical = value
        signature = _norm_fg(canonical)
        if signature not in seen:
            seen.add(signature)
            result.append(canonical)
    return result


def _format_cumulabilita(value: Any) -> str | None:
    text = _norm_str(value)
    if not text:
        return None
    lowered = text.casefold()
    if "limiti di cumulo" in lowered and ("salvo" in lowered or "rispett" in lowered):
        return "Ammessa nel rispetto dei limiti di cumulo applicabili"
    if "non cumulabil" in lowered or "non è compatibil" in lowered or "non e compatibil" in lowered:
        return "Non cumulabile sul medesimo investimento"
    if "non aver beneficiato" in lowered and "medesimo investimento" in lowered:
        return "Non cumulabile sul medesimo investimento, salvo i limiti applicabili"
    if "de minimis" in lowered:
        return "Soggetta alle regole de minimis"
    return _shorten(text)


def _format_agevolazioni(agevolazioni: Any) -> list[str]:
    if not isinstance(agevolazioni, list):
        return []
    sections: list[str] = []
    for item in agevolazioni:
        if not isinstance(item, dict):
            continue
        tipo = item.get("tipo")
        label = TIPO_AGEVOLAZIONE_LABELS.get(tipo)
        if not label:
            continue
        details: list[str] = []
        importo_min = _format_euro(item.get("importo_min"))
        importo_max = _format_euro(item.get("importo_max"))
        if importo_min:
            label_min = "Importo minimo del finanziamento" if tipo == "finanziamento_agevolato" else "Importo minimo"
            details.append(f"{label_min}: {importo_min}")
        if importo_max:
            label_max = "Importo massimo del finanziamento" if tipo == "finanziamento_agevolato" else "Importo massimo"
            details.append(f"{label_max}: {importo_max}")
        percentage = _format_pct(item.get("percentuale"))
        if percentage:
            details.append(f"Copertura: {percentage}")
        percentages = normalize_percentuale_fondo_perduto(item.get("percentuali_per_dimensione"))
        by_size = [
            f"{size} {_format_pct(percentages[key])}"
            for key, size in (("micro", "Micro"), ("piccola", "Piccola"), ("media", "Media"))
            if percentages.get(key) is not None
        ]
        if by_size:
            details.append("Copertura per fascia: " + "; ".join(by_size))
        rate = _format_pct(item.get("tasso_interesse_percentuale"))
        rate_description = _norm_str(item.get("tasso_descrizione"))
        if rate:
            details.append(f"Tasso: {rate}")
        elif rate_description:
            details.append(f"Tasso: {rate_description}")
        if item.get("durata_mesi") is not None:
            details.append(f"Durata: {item['durata_mesi']} mesi")
        if item.get("preammortamento_mesi") is not None:
            details.append(f"Preammortamento: {item['preammortamento_mesi']} mesi")
        if item.get("abbuono_rate") is not None:
            details.append(f"Abbuono: {item['abbuono_rate']} rate")
        repayment = item.get("rimborso_richiesto")
        if repayment is not None:
            details.append("Rimborso richiesto: sì" if repayment else "Rimborso richiesto: no")
        conditions = _norm_list(item.get("condizioni"))
        if conditions:
            details.extend(f"Condizione: {_shorten(value, 120)}" for value in conditions[:2])
        body = "\n".join(f"- {detail}" for detail in details)
        sections.append(f"**{label}**" + (f"\n{body}" if body else ""))
    return sections

def genera_scheda(bando: dict[str, Any]) -> str:
    raw = _unwrap_bando(bando if isinstance(bando, dict) else {})
    b = normalize_response({"bando": raw})["bando"]
    lines = []
    titolo = _norm_str(b.get("titolo"))
    ente = _norm_str(b.get("ente"))
    if titolo: lines.append(f"# {titolo}")
    overview: list[str] = []
    if ente:
        overview.append(f"- **Ente promotore:** {ente}")
    modalita = MODALITA_PRESENTAZIONE_LABELS.get(b.get("modalita_presentazione") or "")
    involved = b.get("enti_coinvolti")
    involved_lines: list[str] = []
    if isinstance(involved, list):
        for item in involved:
            if not isinstance(item, dict):
                continue
            name = _norm_str(item.get("nome"))
            if not name:
                continue
            role = RUOLO_ENTE_LABELS.get(item.get("ruolo") or "", "Soggetto coinvolto")
            if item.get("ruolo") == "piattaforma":
                continue
            involved_lines.append(f"- **{role}:** {name}")
    scadenza = format_scadenza_italiana(b.get("data_scadenza"))
    if scadenza:
        gg = giorni_alla_scadenza(b.get("data_scadenza"))
        if gg is not None:
            if gg < 0:
                overview.append(f"- **Scadenza:** {scadenza} — SCADUTO")
            elif gg < 30:
                overview.append(f"- **Scadenza:** {scadenza} — {gg} giorni (urgenza alta)")
            elif gg < 90:
                overview.append(f"- **Scadenza:** {scadenza} — {gg} giorni")
            else:
                overview.append(f"- **Scadenza:** {scadenza} — {gg} giorni")
        else:
            overview.append(f"- **Scadenza:** {scadenza}")
    elif modalita == MODALITA_PRESENTAZIONE_LABELS["sportello"]:
        overview.append("- **Scadenza:** fino a esaurimento fondi")
    if modalita:
        overview.append(f"- **Presentazione:** {modalita}")
    if overview:
        lines.append("## Panoramica\n\n" + "\n".join(overview))
    if involved_lines:
        lines.append("## Soggetti coinvolti\n\n" + "\n".join(involved_lines))
    accesso = _chi_puo_accedere(b)
    if accesso: lines.append("## Beneficiari e interventi\n\n" + accesso)
    anz_info = b.get("anzianita_impresa") or {}
    requisiti = []
    spesa_min = b.get("spesa_minima_ammissibile")
    spesa_max = b.get("spesa_massima_ammissibile")
    mesi_min = anz_info.get("mesi_minimi_dalla_costituzione")
    mesi_max = anz_info.get("mesi_massimi_dalla_costituzione")
    forme = _compact_legal_forms(_norm_list(b.get("forme_giuridiche_ammesse")))
    if spesa_min is not None:
        try: requisiti.append(f"**Investimento minimo:** {_format_euro(spesa_min)}")
        except Exception: pass
    if spesa_max is not None:
        try: requisiti.append(f"**Investimento massimo:** {_format_euro(spesa_max)}")
        except Exception: pass
    if mesi_min is not None and int(mesi_min) > 0:
        requisiti.append(f"**Anzianità minima:** {int(mesi_min)} mesi")
    if mesi_max is not None and int(mesi_max) > 0:
        requisiti.append(f"**Anzianità massima:** {int(mesi_max)} mesi")
    if forme:
        requisiti.append(f"**Forme giuridiche:** {', '.join(forme)}")
    if requisiti:
        lines.append("## Requisiti principali\n\n" + "\n".join(f"- {item}" for item in requisiti))
    econ_parts = _format_agevolazioni(b.get("agevolazioni"))
    if not econ_parts:
        contributo = _format_euro(b.get("contributo_max"))
        pct_fasce = normalize_percentuale_fondo_perduto(b.get("percentuale_fondo_perduto"))
        if contributo: econ_parts.append(f"**Contributo massimo:** {contributo}")
        fasce_valorizzate = [
            (label, pct_fasce.get(chiave)) for chiave, label in (
                ("micro", "Micro"), ("piccola", "Piccola"), ("media", "Media"),
            ) if pct_fasce.get(chiave) is not None
        ]
        if fasce_valorizzate:
            dettaglio = "; ".join(f"{label} {_format_pct(val)}" for label, val in fasce_valorizzate)
            econ_parts.append(f"**Fondo perduto per fascia:** {dettaglio}")
        elif pct_fasce.get("default") is not None:
            econ_parts.append(f"**Fondo perduto:** {_format_pct(pct_fasce['default'])}")
        tipo_ag = [TIPO_AGEVOLAZIONE_LABELS[t] for t in _norm_list(b.get("tipo_agevolazione")) if t in TIPO_AGEVOLAZIONE_LABELS]
        if tipo_ag:
            econ_parts.append(f"**Tipo di agevolazione:** {', '.join(tipo_ag)}")
    cumulabilita = _format_cumulabilita(b.get("cumulabilita"))
    if cumulabilita:
        econ_parts.append(f"**Cumulabilità:** {cumulabilita}")
    if econ_parts: lines.append("## Contributi e agevolazioni\n\n" + "\n\n".join(econ_parts))
    spese = _compact_expense_labels(_norm_list(b.get("spese_ammissibili")))
    if spese: lines.append("## Spese ammissibili\n\n" + _all_bullets(spese))
    esclusioni = _sezione_esclusioni(b)
    if esclusioni: lines.append(esclusioni)
    link = _norm_str(b.get("url_documento_origine"))
    if link: lines.append(f"## Documento di origine\n\n[{link}]({link})")
    if not lines:
        return "*Scheda non disponibile — dati bando insufficienti.*"
    lines.append("---")
    lines.append(
        "*Dati estratti automaticamente tramite AI e potenzialmente incompleti o imprecisi. "
        "Verificare sempre scadenze, importi e requisiti sulla fonte ufficiale "
        "prima di qualsiasi utilizzo.*"
    )
    return "\n\n".join(lines)

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
    has_fat_constraint = b.get("fatturato_max") is not None
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
    link = _norm_str(b.get("url_documento_origine"))
    return link or None

def load_dashboard_rows(conn: Any) -> list[dict[str, Any]]:
    rows = conn.execute(
        '''SELECT mr.bando_id, mr.cliente_id, mr.score, mr.data_match,
        b.titolo AS bando_titolo, b.ente AS bando_ente, b.data_scadenza, b.json_completo, b.scheda_cached,
        b.review_status, b.null_percentage, b.review_reasons,
        (b.pdf_original IS NOT NULL) AS has_pdf,
        c.ragione_sociale AS cliente_nome, c.codice_ateco AS cliente_codice_ateco, c.descrizione_attivita AS cliente_descrizione_attivita,
        c.regione AS cliente_regione, c.fatturato AS cliente_fatturato, c.dimensione_impresa AS cliente_dimensione_impresa,
        c.data_costituzione AS cliente_data_costituzione, c.numero_dipendenti AS cliente_numero_dipendenti, c.forma_giuridica AS cliente_forma_giuridica
        FROM match_results mr JOIN bandi b ON b.id = mr.bando_id JOIN clienti c ON c.id = mr.cliente_id
        WHERE b.review_status = 'validato'
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
