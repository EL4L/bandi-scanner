"""Logging errori su stdout e audit log su INCIDENTS.md / PROMPT_LOG.md."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPT_LOG = ROOT / "logs" / "PROMPT_LOG.md"
INCIDENTS_LOG = ROOT / "logs" / "INCIDENTS.md"

_logger = logging.getLogger("bandi_scanner")


def log_error(message: str) -> None:
    _logger.error(message)


def log_incident(description: str, impact: str, cause: str, fix: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d")
    line = (
        f"| {timestamp} | {description} | {impact} | {cause} | {fix} |\n"
    )
    try:
        path = INCIDENTS_LOG
        if path.stat().st_size < 200:
            with open(path, "a", encoding="utf-8") as f:
                f.write(
                    "\n| Data | Descrizione | Impatto | Causa | Fix |\n"
                    "|------|-------------|---------|-------|-----|\n"
                )
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError as exc:
        log_error(f"Impossibile scrivere INCIDENTS.md: {exc}")


def log_prompt_run(
    filename: str,
    fields_ok: list[str],
    fields_null: list[str],
    notes: str = "",
) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ok_str = ", ".join(fields_ok) if fields_ok else "—"
    null_str = ", ".join(fields_null) if fields_null else "—"
    entry = (
        f"\n### {filename} — {timestamp}\n"
        f"- **Campi estratti correttamente:** {ok_str}\n"
        f"- **Campi null/vuoti:** {null_str}\n"
    )
    if notes:
        entry += f"- **Note:** {notes}\n"
    try:
        with open(PROMPT_LOG, "a", encoding="utf-8") as f:
            f.write(entry)
    except OSError as exc:
        log_error(f"Impossibile scrivere PROMPT_LOG.md: {exc}")
