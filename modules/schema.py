"""Schema JSON di output (oggetto radice con chiave 'bando')."""

import re
import unicodedata

DIMENSIONE_IMPRESA_KEYS: tuple[str, ...] = ("micro", "piccola", "media", "grande")

DEFAULT_DIMENSIONE_IMPRESA: dict[str, bool] = {
    "micro": False,
    "piccola": False,
    "media": False,
    "grande": False,
}

# Fasce dimensionali per percentuale_fondo_perduto (#17): non includono "grande"
# di proposito (le grandi imprese raramente accedono a fondo perduto graduato
# per fascia) e aggiungono "default" per il caso di percentuale unica non
# differenziata, o per retrocompatibilità con bandi salvati prima di #17
# (quando il campo era un numero singolo).
PERCENTUALE_FASCE_KEYS: tuple[str, ...] = ("micro", "piccola", "media", "default")

MODALITA_PRESENTAZIONE_VALUES: frozenset[str] = frozenset({
    "sportello", "click_day", "graduatoria", "mista",
})

TIPO_AGEVOLAZIONE_VALUES: frozenset[str] = frozenset({
    "fondo_perduto", "finanziamento_agevolato", "garanzia", "credito_imposta", "voucher",
})

CERTEZZA_FONTE_VALUES: frozenset[str] = frozenset({"alta", "media", "bassa"})

RUOLO_ENTE_VALUES: frozenset[str] = frozenset({
    "promotore", "gestore", "ente_attuatore", "intermediario_finanziario",
    "piattaforma", "altro",
})

# Campi dentro "bando"
BANDO_SCHEMA: dict[str, type | tuple[type, ...]] = {
    "titolo": (str, type(None)),
    "ente": (str, type(None)),
    "data_pubblicazione": (str, type(None)),
    "data_scadenza": (str, type(None)),
    "codici_ateco_ammessi": list,
    "attivita_ammesse": list,
    "ateco_aperto_a_tutti": bool,
    "regioni_ammesse": list,
    "dimensione_impresa": dict,
    "fatturato_max": (int, float, type(None)),
    "numero_dipendenti_min": (int, float, type(None)),
    "numero_dipendenti_max": (int, float, type(None)),
    "contributo_max": (int, float, type(None)),
    "percentuale_fondo_perduto": dict,
    "modalita_presentazione": (str, type(None)),
    "tipo_agevolazione": list,
    "cumulabilita": (str, type(None)),
    "spese_ammissibili": list,
    "link_fonte_ufficiale": (str, type(None)),
    "url_documento_origine": (str, type(None)),
    "note_esclusioni": (dict, str, type(None)), 
    "spesa_minima_ammissibile": (int, float, type(None)),
    "spesa_massima_ammissibile": (int, float, type(None)),
    "anzianita_impresa": dict,
    "forme_giuridiche_ammesse": list,
    "agevolazioni": list,
    "fonti": list,
    "enti_coinvolti": list,
    "copertura_estrazione": dict,
}


DATE_FIELDS: tuple[str, ...] = ("data_pubblicazione", "data_scadenza")

LIST_STRING_FIELDS: tuple[str, ...] = (
    "codici_ateco_ammessi",
    "attivita_ammesse",
    "regioni_ammesse",
    "spese_ammissibili",
)

MIN_TEXT_CHARS = 50
MAX_TEXT_CHARS = 250_000


def normalize_dimensione_impresa(value: object) -> dict[str, bool]:
    if not isinstance(value, dict):
        return dict(DEFAULT_DIMENSIONE_IMPRESA)
    return {key: bool(value.get(key, False)) for key in DIMENSIONE_IMPRESA_KEYS}


NUMERIC_FIELDS: frozenset[str] = frozenset({
    "contributo_max",
    "fatturato_max",
    "spesa_minima_ammissibile",
    "spesa_massima_ammissibile",
    "numero_dipendenti_min",
    "numero_dipendenti_max",
})

AGEVOLAZIONE_NUMERIC_FIELDS: tuple[str, ...] = (
    "importo_min",
    "importo_max",
    "percentuale",
    "tasso_interesse_percentuale",
    "durata_mesi",
    "preammortamento_mesi",
    "abbuono_rate",
)

_TEMPORAL_UNIT_MONTHS: dict[str, int] = {
    "mese": 1,
    "mesi": 1,
    "trimestre": 3,
    "trimestri": 3,
    "semestre": 6,
    "semestri": 6,
    "anno": 12,
    "anni": 12,
}
_TEMPORAL_VALUE_RE = re.compile(
    r"(?P<value>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>mesi?|trimestr[ei]|semestr[ei]|ann[oi])\b",
    re.IGNORECASE,
)

_PHRASE_STOPWORDS = {
    "a", "ad", "al", "alla", "alle", "allo", "anche", "che", "con", "da",
    "dal", "dalla", "delle", "dei", "del", "di", "e", "ed", "gli", "i", "il",
    "in", "la", "le", "lo", "nei", "nel", "nella", "o", "per", "su", "un", "una",
    "investimenti", "investimento", "attivita", "impianti", "connessi", "connesse",
    "legati", "legate",
}
_PHRASE_SYNONYMS = {
    "fabbricazione": "produzione",
    "commercializzazione": "commercio",
    "smaltimento": "smaltire",
    "smantellamento": "smantellare",
}


def _phrase_tokens(value: str) -> set[str]:
    folded = unicodedata.normalize("NFKD", value.lower())
    ascii_value = "".join(char for char in folded if not unicodedata.combining(char))
    tokens: set[str] = set()
    for token in re.findall(r"[a-z0-9]+", ascii_value):
        if (len(token) < 3 and not token.isdigit()) or token in _PHRASE_STOPWORDS:
            continue
        tokens.add(_PHRASE_SYNONYMS.get(token, token))
    return tokens


def deduplicate_semantic_phrases(value: object) -> list[str]:
    """Deduplica esclusioni quasi equivalenti conservando la voce più completa.

    Il confronto è volutamente prudente: due frasi vengono accorpate soltanto
    quando quasi tutti i concetti della più corta ricorrono anche nell'altra.
    Frasi sullo stesso settore che aggiungono condizioni diverse restano quindi
    separate, evitando perdita di informazione.
    """
    if not isinstance(value, list):
        return []

    result: list[str] = []
    token_sets: list[set[str]] = []
    for raw in value:
        if not isinstance(raw, str) or not raw.strip():
            continue
        phrase = re.sub(r"\s+", " ", raw).strip(" ,;.")
        phrase = re.sub(
            r"\b([A-Za-zÀ-ÿ]{3,})\s+(?:e|ed|,)\s+\1\b",
            r"\1",
            phrase,
            flags=re.IGNORECASE,
        )
        tokens = _phrase_tokens(phrase)
        duplicate_index: int | None = None
        for index, existing_tokens in enumerate(token_sets):
            if not tokens or not existing_tokens:
                current_plain = phrase.casefold()
                existing_plain = result[index].casefold()
                equivalent = current_plain == existing_plain or (
                    len(current_plain) >= 5
                    and re.search(rf"\b{re.escape(current_plain)}\b", existing_plain) is not None
                ) or (
                    len(existing_plain) >= 5
                    and re.search(rf"\b{re.escape(existing_plain)}\b", current_plain) is not None
                )
            else:
                overlap = len(tokens & existing_tokens)
                containment = overlap / min(len(tokens), len(existing_tokens))
                jaccard = overlap / len(tokens | existing_tokens)
                equivalent = containment >= 0.85 and (
                    jaccard >= 0.35 or min(len(tokens), len(existing_tokens)) <= 2
                )
            if equivalent:
                duplicate_index = index
                break

        if duplicate_index is None:
            result.append(phrase)
            token_sets.append(tokens)
            continue

        # La formulazione più lunga tende a contenere qualificazioni aggiuntive.
        if len(tokens) > len(token_sets[duplicate_index]) or (
            len(tokens) == len(token_sets[duplicate_index])
            and len(phrase) > len(result[duplicate_index])
        ):
            result[duplicate_index] = phrase
            token_sets[duplicate_index] = tokens
    return result


def normalize_note_esclusioni(value: object) -> dict[str, object] | str | None:
    if isinstance(value, str):
        return value.strip() or None
    if not isinstance(value, dict):
        return None
    lista_testuale = value.get("lista_testuale")
    return {
        "lista_testuale": (
            lista_testuale.strip()
            if isinstance(lista_testuale, str) and lista_testuale.strip()
            else None
        ),
        "sezioni_ateco_escluse": deduplicate_semantic_phrases(
            value.get("sezioni_ateco_escluse")
        ),
        "attivita_vietate": deduplicate_semantic_phrases(value.get("attivita_vietate")),
        "soggetti_esclusi": deduplicate_semantic_phrases(value.get("soggetti_esclusi")),
        "spese_non_ammissibili": deduplicate_semantic_phrases(
            value.get("spese_non_ammissibili")
        ),
        "altre_esclusioni": deduplicate_semantic_phrases(value.get("altre_esclusioni")),
    }


def _to_bool(val: object) -> bool:
    """Converte in bool in modo sicuro: "false" → False, "true" → True."""
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ("true", "sì", "si", "yes", "1")
    return bool(val) if val is not None else False


def _to_nullable_bool(val: object) -> bool | None:
    if val is None or val == "":
        return None
    return _to_bool(val)


def _to_number(val: object) -> float | int | None:
    """Converte in numero in modo sicuro, gestendo stringhe con %, €, punti migliaia."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return val
    if isinstance(val, str):
        s = val.strip()
        # rimuove simboli: %, €, spazi; normalizza separatori
        s = s.replace("%", "").replace("€", "").replace(" ", "")
        # il punto può essere separatore migliaia (1.000) o decimale (1.5):
        # se c'è anche la virgola, il punto è migliaia → rimuovilo
        if "," in s:
            s = s.replace(".", "").replace(",", ".")
        elif s.count(".") > 1 or (s.count(".") == 1 and len(s.split(".")[-1]) == 3):
            s = s.replace(".", "")
        try:
            f = float(s)
            return int(f) if f == int(f) else f
        except ValueError:
            return None
    return None


def normalize_duration_months(value: object) -> float | int | None:
    """Converte una durata esplicita in mesi senza affidarsi al modello AI.

    I numeri privi di unita restano espressi in mesi per compatibilita con i
    campi JSON ``durata_mesi`` e ``preammortamento_mesi``. Le stringhe che
    riportano unita diverse vengono convertite deterministicamente.
    """
    if isinstance(value, str):
        match = _TEMPORAL_VALUE_RE.search(value.strip())
        if match:
            amount = _to_number(match.group("value"))
            multiplier = _TEMPORAL_UNIT_MONTHS[match.group("unit").casefold()]
            if amount is None:
                return None
            months = amount * multiplier
            return int(months) if float(months).is_integer() else months
    return _to_number(value)


def _to_enum(val: object, allowed: frozenset[str]) -> str | None:
    """Normalizza a una delle stringhe enum consentite (case-insensitive).
    Un valore non riconosciuto (allucinazione LLM, refuso) diventa None
    invece di salvare rumore non filtrabile a valle."""
    if not isinstance(val, str):
        return None
    v = val.strip().lower()
    return v if v in allowed else None


def _to_enum_list(val: object, allowed: frozenset[str]) -> list[str]:
    """Normalizza a lista di sole stringhe enum consentite (case-insensitive,
    dedup mantenendo l'ordine di prima occorrenza)."""
    if not isinstance(val, list):
        return []
    seen: list[str] = []
    for item in val:
        if not isinstance(item, str):
            continue
        v = item.strip().lower()
        if v in allowed and v not in seen:
            seen.append(v)
    return seen


def normalize_percentuale_fondo_perduto(value: object) -> dict[str, float | int | None]:
    """Restituisce sempre {"micro", "piccola", "media", "default"}.

    Gestisce sia il nuovo formato (oggetto per fascia dimensionale, #17)
    sia il formato legacy (numero singolo, bandi salvati/estratti prima di
    #17): il numero legacy viene letto come "default", così `genera_scheda`
    può leggere qualunque bando — vecchio o nuovo — con la stessa funzione.
    """
    if isinstance(value, dict):
        return {key: _to_number(value.get(key)) for key in PERCENTUALE_FASCE_KEYS}
    numero = _to_number(value)
    return {"micro": None, "piccola": None, "media": None, "default": numero}


def normalize_fonte(value: object) -> dict[str, object] | None:
    """Normalizza una prova testuale senza inventare pagina o contenuto."""
    if not isinstance(value, dict):
        return None
    pagina = _to_number(value.get("pagina"))
    testo = value.get("testo")
    campo = value.get("campo")
    certezza = _to_enum(value.get("certezza"), CERTEZZA_FONTE_VALUES)
    normalized = {
        "campo": campo.strip() if isinstance(campo, str) and campo.strip() else None,
        "pagina": int(pagina) if pagina is not None and pagina >= 1 else None,
        "testo": testo.strip() if isinstance(testo, str) and testo.strip() else None,
        "certezza": certezza,
    }
    if not normalized["testo"] and not normalized["campo"]:
        return None
    return normalized


def normalize_fonti(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, object]] = []
    seen: set[tuple[object, ...]] = set()
    for item in value:
        fonte = normalize_fonte(item)
        if fonte is None:
            continue
        signature = (fonte["campo"], fonte["pagina"], fonte["testo"])
        if signature not in seen:
            seen.add(signature)
            result.append(fonte)
    return result


def normalize_enti_coinvolti(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, object]] = []
    by_name: dict[str, int] = {}
    role_priority = {
        "promotore": 6,
        "ente_attuatore": 5,
        "gestore": 4,
        "intermediario_finanziario": 3,
        "piattaforma": 2,
        "altro": 1,
        None: 0,
    }
    for item in value:
        if not isinstance(item, dict):
            continue
        name = item.get("nome")
        if not isinstance(name, str) or not name.strip():
            continue
        role = _to_enum(item.get("ruolo"), RUOLO_ENTE_VALUES)
        normalized_name = name.strip()
        folded_name = unicodedata.normalize("NFKD", normalized_name.casefold())
        name_key = re.sub(
            r"[^a-z0-9]",
            "",
            "".join(char for char in folded_name if not unicodedata.combining(char)),
        )
        normalized = {
            "nome": normalized_name,
            "ruolo": role,
            "fonti": normalize_fonti(item.get("fonti")),
        }
        existing_index = by_name.get(name_key)
        if existing_index is None:
            by_name[name_key] = len(result)
            result.append(normalized)
            continue
        existing = result[existing_index]
        existing["fonti"] = normalize_fonti(
            list(existing.get("fonti") or []) + list(normalized["fonti"] or [])
        )
        if role_priority[role] > role_priority.get(existing.get("ruolo"), 0):
            existing["nome"] = normalized_name
            existing["ruolo"] = role
    return result


def normalize_agevolazioni(value: object) -> list[dict[str, object]]:
    """Normalizza strumenti economici distinti senza confondere prestiti e contributi."""
    if not isinstance(value, list):
        return []
    result: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        tipo = _to_enum(item.get("tipo"), TIPO_AGEVOLAZIONE_VALUES)
        if tipo is None:
            continue
        normalized: dict[str, object] = {"tipo": tipo}
        for field in AGEVOLAZIONE_NUMERIC_FIELDS:
            if field in {"durata_mesi", "preammortamento_mesi"}:
                normalized[field] = normalize_duration_months(item.get(field))
            else:
                normalized[field] = _to_number(item.get(field))
        normalized["percentuali_per_dimensione"] = normalize_percentuale_fondo_perduto(
            item.get("percentuali_per_dimensione")
        )
        normalized["rimborso_richiesto"] = _to_nullable_bool(item.get("rimborso_richiesto"))
        for field in ("tasso_descrizione", "descrizione"):
            raw = item.get(field)
            normalized[field] = raw.strip() if isinstance(raw, str) and raw.strip() else None
        condizioni = item.get("condizioni")
        normalized["condizioni"] = (
            [x.strip() for x in condizioni if isinstance(x, str) and x.strip()]
            if isinstance(condizioni, list)
            else []
        )
        raw_fonti = item.get("fonti")
        if not isinstance(raw_fonti, list) and isinstance(item.get("fonte"), dict):
            raw_fonti = [item["fonte"]]
        normalized["fonti"] = normalize_fonti(raw_fonti)
        result.append(normalized)
    return result


def normalize_copertura_estrazione(value: object) -> dict[str, object]:
    source = value if isinstance(value, dict) else {}
    totale = _to_number(source.get("caratteri_totali"))
    analizzati = _to_number(source.get("caratteri_analizzati"))
    blocchi = _to_number(source.get("numero_blocchi"))
    return {
        "caratteri_totali": int(totale) if totale is not None else None,
        "caratteri_analizzati": int(analizzati) if analizzati is not None else None,
        "numero_blocchi": int(blocchi) if blocchi is not None else None,
        "completa": _to_nullable_bool(source.get("completa")),
    }


def reconcile_agevolazioni_legacy(bando: dict[str, object]) -> None:
    """Rende i campi legacy coerenti con gli strumenti strutturati.

    `agevolazioni` è più espressivo e quindi autorevole quando presente.
    In particolare, il massimale di un prestito non può sopravvivere dentro
    `contributo_max`, anche se il modello lo ha duplicato per errore.
    """
    agevolazioni = bando.get("agevolazioni")
    if not isinstance(agevolazioni, list) or not agevolazioni:
        return
    tipi = _to_enum_list(
        [item.get("tipo") for item in agevolazioni if isinstance(item, dict)],
        TIPO_AGEVOLAZIONE_VALUES,
    )
    if tipi:
        bando["tipo_agevolazione"] = tipi

    non_rimborsabili = {"fondo_perduto", "voucher", "credito_imposta"}
    if not (set(tipi) & non_rimborsabili):
        bando["contributo_max"] = None
        bando["percentuale_fondo_perduto"] = normalize_percentuale_fondo_perduto(None)
        return

    fondo_items = [
        item for item in agevolazioni
        if isinstance(item, dict) and item.get("tipo") in non_rimborsabili
    ]
    explicit_amounts = [
        item.get("importo_max") for item in fondo_items
        if isinstance(item.get("importo_max"), (int, float))
    ]
    if bando.get("contributo_max") is None and len(explicit_amounts) == 1:
        bando["contributo_max"] = explicit_amounts[0]

    legacy_percentages = bando.get("percentuale_fondo_perduto")
    legacy_empty = isinstance(legacy_percentages, dict) and all(
        value is None for value in legacy_percentages.values()
    )
    if legacy_empty and len(fondo_items) == 1:
        item = fondo_items[0]
        by_size = item.get("percentuali_per_dimensione")
        if isinstance(by_size, dict) and any(value is not None for value in by_size.values()):
            bando["percentuale_fondo_perduto"] = normalize_percentuale_fondo_perduto(by_size)
        elif item.get("percentuale") is not None:
            bando["percentuale_fondo_perduto"] = normalize_percentuale_fondo_perduto(
                item.get("percentuale")
            )


def normalize_response(data: dict) -> dict[str, object]:
    """Restituisce sempre {"bando": {...}} con tutte le chiavi schema."""
    if "bando" in data and isinstance(data["bando"], dict):
        source = data["bando"]
    else:
        source = data

    bando: dict[str, object] = {}
    for key in BANDO_SCHEMA:
        val = source.get(key) if isinstance(source, dict) else None
        
        if key == "dimensione_impresa":
            bando[key] = normalize_dimensione_impresa(val)
        elif key in (
            "codici_ateco_ammessi",
            "attivita_ammesse",
            "regioni_ammesse",
            "spese_ammissibili",
            "forme_giuridiche_ammesse",  # Nuovo campo lista Fase 5
        ):
            if key in {"attivita_ammesse", "spese_ammissibili"}:
                bando[key] = deduplicate_semantic_phrases(val)
            elif isinstance(val, list):
                bando[key] = list(dict.fromkeys(
                    item.strip() for item in val
                    if isinstance(item, str) and item.strip()
                ))
            else:
                bando[key] = []
        elif key == "ateco_aperto_a_tutti":
            bando[key] = _to_bool(val)
        elif key == "percentuale_fondo_perduto":
            bando[key] = normalize_percentuale_fondo_perduto(val)
        elif key == "modalita_presentazione":
            bando[key] = _to_enum(val, MODALITA_PRESENTAZIONE_VALUES)
        elif key == "tipo_agevolazione":
            bando[key] = _to_enum_list(val, TIPO_AGEVOLAZIONE_VALUES)
        elif key == "agevolazioni":
            bando[key] = normalize_agevolazioni(val)
        elif key == "fonti":
            bando[key] = normalize_fonti(val)
        elif key == "enti_coinvolti":
            bando[key] = normalize_enti_coinvolti(val)
        elif key == "copertura_estrazione":
            bando[key] = normalize_copertura_estrazione(val)
        elif key == "note_esclusioni":
            bando[key] = normalize_note_esclusioni(val)
        elif key == "cumulabilita":
            bando[key] = val.strip() if isinstance(val, str) and val.strip() else None
        elif key == "anzianita_impresa":
            if isinstance(val, dict):
                mesi_min = _to_number(val.get("mesi_minimi_dalla_costituzione"))
                mesi_max = _to_number(val.get("mesi_massimi_dalla_costituzione"))
                bando[key] = {
                    "mesi_minimi_dalla_costituzione": int(mesi_min) if mesi_min is not None else None,
                    "mesi_massimi_dalla_costituzione": int(mesi_max) if mesi_max is not None else None,
                }
            else:
                bando[key] = {
                    "mesi_minimi_dalla_costituzione": None,
                    "mesi_massimi_dalla_costituzione": None
                }
        else:
            bando[key] = _to_number(val) if key in NUMERIC_FIELDS else val
            
    # --- BLOCCO DI SICUREZZA FASE 5 ---
    # Forza la normalizzazione nel caso i nuovi campi non siano ancora in BANDO_SCHEMA
    if "spesa_minima_ammissibile" not in bando:
        bando["spesa_minima_ammissibile"] = source.get("spesa_minima_ammissibile")
        
    if "forme_giuridiche_ammesse" not in bando:
        f = source.get("forme_giuridiche_ammesse")
        bando["forme_giuridiche_ammesse"] = f if isinstance(f, list) else []
        
    if "anzianita_impresa" not in bando:
        a = source.get("anzianita_impresa")
        bando["anzianita_impresa"] = a if isinstance(a, dict) else {
            "mesi_minimi_dalla_costituzione": None,
            "mesi_massimi_dalla_costituzione": None
        }
    # --- FINE BLOCCO DI SICUREZZA ---

    exclusions = bando.get("note_esclusioni")
    if isinstance(exclusions, dict) and (
        exclusions.get("sezioni_ateco_escluse") or exclusions.get("attivita_vietate")
    ):
        # "Aperto a tutti" e presenza di settori vietati sono incompatibili.
        bando["ateco_aperto_a_tutti"] = False

    reconcile_agevolazioni_legacy(bando)

    return {"bando": bando}
