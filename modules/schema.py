"""Schema JSON di output (oggetto radice con chiave 'bando')."""

DIMENSIONE_IMPRESA_KEYS: tuple[str, ...] = ("micro", "piccola", "media", "grande")

DEFAULT_DIMENSIONE_IMPRESA: dict[str, bool] = {
    "micro": False,
    "piccola": False,
    "media": False,
    "grande": False,
}

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
    "contributo_max": (int, float, type(None)),
    "percentuale_fondo_perduto": (int, float, type(None)),
    "spese_ammissibili": list,
    "link_fonte_ufficiale": (str, type(None)),
    "note_esclusioni": (str, type(None)),
}

DATE_FIELDS: tuple[str, ...] = ("data_pubblicazione", "data_scadenza")

LIST_STRING_FIELDS: tuple[str, ...] = (
    "codici_ateco_ammessi",
    "attivita_ammesse",
    "regioni_ammesse",
    "spese_ammissibili",
)

MIN_TEXT_CHARS = 50
MAX_TEXT_CHARS = 120_000


def normalize_dimensione_impresa(value: object) -> dict[str, bool]:
    if not isinstance(value, dict):
        return dict(DEFAULT_DIMENSIONE_IMPRESA)
    return {key: bool(value.get(key, False)) for key in DIMENSIONE_IMPRESA_KEYS}


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
        ):
            bando[key] = val if isinstance(val, list) else []
        elif key == "ateco_aperto_a_tutti":
            bando[key] = bool(val) if val is not None else False
        else:
            bando[key] = val
    return {"bando": bando}
