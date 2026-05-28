"""Simula localmente il matching bando->clienti senza chiamare l'API AI.

Esegue 4 casi di test (coerenti con i PDF di test) e stampa lo score e il dettaglio
dei contributi (regione, ateco, dimensione, fatturato) per ogni cliente nel DB.

Esegui dalla root del progetto:
    python scripts/simulate_matching.py
"""
from pathlib import Path
import sys
import json

# Ensure project root is on sys.path so `modules` package is importable when
# running this script directly from the repository root.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.database import list_clienti
from modules.matcher import (
    calculate_score,
    _score_regione,
    _score_ateco,
    _score_dimensione,
    _score_fatturato,
    _unwrap_bando,
)


SAMPLES = {
    "bando_ateco_specifico": {
        "bando": {
            "titolo": "Contributi per servizi digitali",
            "ente": "Comune di Pescara",
            "codici_ateco_ammessi": ["62.01"],
            "regioni_ammesse": ["Abruzzo"],
            "attivita_ammesse": ["servizi IT", "sviluppo software"],
        }
    },
    "bando_aperto_a_tutti": {
        "bando": {
            "titolo": "Fondo per rilancio locale",
            "ente": "Provincia di Roma",
            "ateco_aperto_a_tutti": True,
            "attivita_ammesse": [],
        }
    },
    "bando_regioni": {
        "bando": {
            "titolo": "Incentivi per turismo in Lazio",
            "ente": "Regione Lazio",
            "regioni_ammesse": ["Lazio"],
        }
    },
    "bando_senza_vincoli": {"bando": {"titolo": "Avviso pubblico"}},
}


def print_results_for(sample_name: str, sample: dict):
    print("\n" + "=" * 60)
    print(f"Campione: {sample_name}")
    print(json.dumps(sample, ensure_ascii=False, indent=2))
    print("-" * 60)

    clients = list_clienti()
    if not clients:
        print("Nessun cliente in DB. Aggiungi clienti nella scheda Profilo cliente prima di simulare.")
        return

    rows = []
    for c in clients:
        total = calculate_score(sample, c)
        # breakdown
        b = _unwrap_bando(sample if isinstance(sample, dict) else {})
        r = _score_regione(b, c)
        a = _score_ateco(b, c)
        d = _score_dimensione(b, c)
        f = _score_fatturato(b, c)
        rows.append((total, c, dict(regione=r, ateco=a, dimensione=d, fatturato=f)))

    # sort desc
    rows.sort(key=lambda x: x[0], reverse=True)

    for total, c, breakdown in rows:
        print(f"Cliente: {c.get('id')} — {c.get('ragione_sociale')} | Score: {total}/100")
        print(f"  Regione: {breakdown['regione']} | ATECO: {breakdown['ateco']} | Dimensione: {breakdown['dimensione']} | Fatturato: {breakdown['fatturato']}")


def main():
    for name, sample in SAMPLES.items():
        print_results_for(name, sample)


if __name__ == '__main__':
    main()
