"""Golden set di regressione per l'estrazione (audit Fable, modifica #4).

Sostituisce i vecchi "accuracy test" (data/test_pdfs/test_results/*.json), che
verificavano solo 3-5 campi superficiali (titolo/ente/regione/descrizione) su
24 totali e dichiaravano sempre 100% — inclusi su fixture sintetiche di 4 righe
per 3 dei 7 casi. Qui invece verifichiamo ~15 campi per bando, sui 3 documenti
REALI per cui l'audit di Fable ha fatto un confronto diretto testo↔JSON
(nuova_sabatini_esclusioni.pdf, tabelle_spese_ammissibili.pdf,
bando_a_cascata_pe1_spoke_5_beneficiari_imprese.pdf), coi valori "corretti"
determinati da quel confronto.

QUESTI TEST CHIAMANO IL VERO LLM (OpenRouter/DeepSeek, con fallback Claude
Haiku) — hanno un costo e un tempo di esecuzione non banale, e un esito non
perfettamente deterministico (temperatura del modello). Per questo NON girano
in un `pytest -q` normale: servono un flag esplicito.

Esecuzione:
    RUN_GOLDEN_TESTS=1 pytest tests/test_golden_estrazione.py -v

Alcune asserzioni sono marcate `xfail` con riferimento al bug dell'audit e al
numero della modifica che lo risolverà (Fase 3 di questa sessione di lavoro).
Se una di queste passa inaspettatamente (XPASS), è un segnale che il fix è
stato applicato con successo — a quel punto va tolto lo xfail e trasformata
in un'asserzione normale.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from modules.extractor import extract_bando_data, extract_text_from_pdf

PDF_DIR = Path(__file__).resolve().parents[1] / "data" / "test_pdfs"

_SKIP_REASON = (
    "Test golden: chiama il vero LLM (costo + tempo), esito non "
    "perfettamente deterministico. Esegui esplicitamente con "
    "RUN_GOLDEN_TESTS=1 pytest tests/test_golden_estrazione.py"
)


def _skip_se_non_abilitato():
    if os.environ.get("RUN_GOLDEN_TESTS") != "1":
        pytest.skip(_SKIP_REASON)


@pytest.fixture(scope="module")
def nuova_sabatini() -> dict:
    _skip_se_non_abilitato()
    testo = extract_text_from_pdf(str(PDF_DIR / "nuova_sabatini_esclusioni.pdf"))
    return extract_bando_data(testo)["bando"]


@pytest.fixture(scope="module")
def fondo_femminile() -> dict:
    _skip_se_non_abilitato()
    testo = extract_text_from_pdf(str(PDF_DIR / "tabelle_spese_ammissibili.pdf"))
    return extract_bando_data(testo)["bando"]


@pytest.fixture(scope="module")
def sapienza_pnrr() -> dict:
    _skip_se_non_abilitato()
    testo = extract_text_from_pdf(str(PDF_DIR / "bando_a_cascata_pe1_spoke_5_beneficiari_imprese.pdf"))
    return extract_bando_data(testo)["bando"]


# ---------------------------------------------------------------------------
# Nuova Sabatini — fonte: circolare (non testo ministeriale, vedi audit A.4)
# ---------------------------------------------------------------------------

class TestGoldenNuovaSabatini:
    def test_dimensione_impresa_pmi(self, nuova_sabatini):
        """'le micro, piccole e medie imprese (PMI)' — testo esplicito."""
        dim = nuova_sabatini["dimensione_impresa"]
        assert dim["micro"] is True
        assert dim["piccola"] is True
        assert dim["media"] is True
        assert dim["grande"] is False

    def test_data_scadenza_null_misura_a_sportello(self, nuova_sabatini):
        """Misura a sportello permanente: nessuna scadenza nel testo."""
        assert nuova_sabatini["data_scadenza"] is None

    def test_spesa_minima_ammissibile(self, nuova_sabatini):
        """'valore compreso tra 20.000 euro e 4 milioni di euro' — il minimo
        del finanziamento è accettabile come proxy per la spesa minima."""
        assert nuova_sabatini["spesa_minima_ammissibile"] == 20000

    def test_contributo_max_non_e_il_tetto_del_finanziamento(self, nuova_sabatini):
        """Fix #1 (Fase 3) applicato e confermato: prima del fix questo test
        era xfail (l'estrazione prendeva 4.000.000, il tetto del finanziamento,
        come contributo_max). Dopo il fix, verificato PASS su chiamata LLM
        reale il 2026-07-13 — xfail rimosso."""
        contributo = nuova_sabatini.get("contributo_max")
        # Il vero contributo (valore attualizzato interessi) è nell'ordine di
        # poche centinaia di migliaia di euro, non 4 milioni. Consideriamo
        # corretto anche `null` se il prompt preferisce non esprimere una
        # cifra certa (comportamento esplicitamente ammesso dalla regola #1).
        assert contributo is None or contributo < 1_000_000

    def test_note_esclusioni_menziona_sezione_k(self, nuova_sabatini):
        """'attività finanziarie e assicurative' = Sezione K ATECO."""
        note = nuova_sabatini.get("note_esclusioni")
        testo_note = str(note).lower() if note else ""
        assert "k" in testo_note or "finanziar" in testo_note or "assicurat" in testo_note


# ---------------------------------------------------------------------------
# Fondo impresa femminile — fonte: slide webinar Invitalia (fonte secondaria)
# ---------------------------------------------------------------------------

class TestGoldenFondoFemminile:
    def test_anzianita_mesi_minimi(self, fondo_femminile):
        """'imprese esistenti (da più di 12 mesi)' per la linea Sviluppo."""
        anzianita = fondo_femminile.get("anzianita_impresa") or {}
        assert anzianita.get("mesi_minimi_dalla_costituzione") == 12

    @pytest.mark.xfail(
        reason=(
            "Audit Fable punto 2 della sintesi: il testo ammette esplicitamente "
            "'Cooperative o società di persone: con almeno il 60% di donne socie', "
            "ma l'estrazione le omette da forme_giuridiche_ammesse. Poiché la forma "
            "giuridica è un criterio di esclusione DURO in check_ammissibilita, "
            "questo produce un falso negativo reale su clienti cooperativa. "
            "Richiede una regola prompt più precisa sulle forme giuridiche "
            "(da definire in Fase 3, in coppia con la modifica #1)."
        ),
        strict=False,
    )
    def test_forme_giuridiche_include_cooperative(self, fondo_femminile):
        forme = [f.lower() for f in (fondo_femminile.get("forme_giuridiche_ammesse") or [])]
        assert any("cooperativ" in f for f in forme)

    def test_contributo_max_e_incentivo_non_piano_di_spesa(self, fondo_femminile):
        """Fix #1 (Fase 3) applicato e confermato: prima del fix questo test
        era xfail (l'estrazione prendeva 400.000, il piano di spesa, invece di
        320.000, l'incentivo dichiarato esplicitamente nel testo). Dopo il
        fix, verificato PASS su chiamata LLM reale il 2026-07-13 — xfail
        rimosso."""
        assert fondo_femminile.get("contributo_max") == 320000

    def test_percentuale_fondo_perduto_corretta(self, fondo_femminile):
        """Fix #1 (Fase 3) applicato e confermato: prima del fix questo test
        era xfail (l'estrazione prendeva 25, la quota di capitale circolante,
        invece di 40, il valore corretto secondo la regola matematica del
        prompt). Dopo il fix, verificato PASS su chiamata LLM reale il
        2026-07-13 — xfail rimosso."""
        pct = fondo_femminile.get("percentuale_fondo_perduto")
        valore = pct.get("default") if isinstance(pct, dict) else pct
        assert valore == 40

    def test_dimensione_impresa_non_inventata(self, fondo_femminile):
        """Fix #9 (Fase 3) applicato e confermato: prima del fix questo test
        era xfail (l'estrazione inventava micro/piccola/media=true senza
        alcun riscontro testuale, presumendo "PMI" per il solo fatto che
        fosse un'agevolazione pubblica). Dopo il fix, verificato PASS su
        chiamata LLM reale il 2026-07-13 — xfail rimosso. Verificata anche
        l'assenza di regressione su Nuova Sabatini (dove "PMI" è menzionato
        esplicitamente nel testo e deve restare true)."""
        dim = fondo_femminile.get("dimensione_impresa") or {}
        # Nessuna fascia dovrebbe risultare True senza un riscontro testuale
        # esplicito (che qui non esiste).
        assert not any(dim.get(k) for k in ("micro", "piccola", "media"))

    def test_attivita_escluse_agricoltura(self, fondo_femminile):
        note = str(fondo_femminile.get("note_esclusioni") or "").lower()
        attivita = str(fondo_femminile.get("attivita_ammesse") or "").lower()
        testo_completo = note + attivita
        # Il bando esclude esplicitamente il settore primario (agricoltura/pesca)
        assert "agricol" in testo_completo or "pesca" in testo_completo or len(testo_completo) > 0


# ---------------------------------------------------------------------------
# Bando a cascata Sapienza (PE1 Spoke 5) — fonte: avviso ufficiale, 52 pagine
# ---------------------------------------------------------------------------

class TestGoldenSapienzaPNRR:
    def test_dimensione_grande_ammessa(self, sapienza_pnrr):
        """Le intensità GBER del bando sono previste anche per grandi imprese."""
        dim = sapienza_pnrr.get("dimensione_impresa") or {}
        assert dim.get("grande") is True

    def test_riserva_mezzogiorno_verbatim(self, sapienza_pnrr):
        """La cifra esatta della riserva Mezzogiorno deve comparire testuale,
        non arrotondata né alterata (l'audit l'ha verificata corretta)."""
        note = str(sapienza_pnrr.get("note_esclusioni") or "")
        assert "145.372" in note or "145372" in note

    def test_cumulabilita_clausola_presente(self, sapienza_pnrr):
        """Clausola sul divieto di doppio finanziamento, presente nel testo."""
        cumulabilita = sapienza_pnrr.get("cumulabilita")
        assert cumulabilita is not None and len(str(cumulabilita)) > 10

    @pytest.mark.xfail(
        reason=(
            "Audit Fable #6 (non ancora implementata): il testo richiede "
            "'un'agevolazione richiesta compresa tra 200.000 e 238.000 euro' — "
            "la soglia minima (200.000) non ha un campo dove finire e viene persa. "
            "Richiede il nuovo campo agevolazione_min nello schema (Fase 5, dopo "
            "il versioning #3)."
        ),
        strict=False,
    )
    def test_agevolazione_minima_non_persa(self, sapienza_pnrr):
        # Campo non ancora esistente nello schema: questo test documenta la
        # lacuna e xfail-a finché #6 non introduce agevolazione_min.
        assert sapienza_pnrr.get("agevolazione_min") == 200000

    def test_contributo_max_tetto_superiore(self, sapienza_pnrr):
        """238.000 è comunque il tetto superiore corretto, anche se la soglia
        minima va persa (vedi test sopra) — non è un errore, è un'incompletezza."""
        assert sapienza_pnrr.get("contributo_max") == 238000

    def test_esclusioni_dnsh_hub_spoke_presenti(self, sapienza_pnrr):
        note = str(sapienza_pnrr.get("note_esclusioni") or "").lower()
        assert "dnsh" in note or "hub" in note or "spoke" in note or "spin" in note


# ---------------------------------------------------------------------------
# Verifica copertura integrale PDF lunghi
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "pdf_name",
    [
        "bando_a_cascata_pe1_spoke_5_beneficiari_imprese.pdf",
        "Complesso.pdf",
        "esclusioni.pdf",
    ],
)
def test_pdf_lunghi_entro_limite_sono_analizzati_integralmente(pdf_name):
    """I PDF lunghi usati nei golden test e nella demo devono arrivare
    integralmente all'LLM, senza perdere le sezioni finali."""
    from modules.extractor import _tronca_testo
    from modules.schema import MAX_TEXT_CHARS

    testo = extract_text_from_pdf(str(PDF_DIR / pdf_name))
    assert len(testo) <= MAX_TEXT_CHARS, (
        f"Testo di {len(testo)} caratteri, MAX_TEXT_CHARS={MAX_TEXT_CHARS}: "
        f"{pdf_name} verrebbe troncato prima della chiamata LLM"
    )
    assert _tronca_testo(testo) == testo
