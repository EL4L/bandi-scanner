"""Ricerca data di scadenza nel testo grezzo del PDF (senza API)."""

from __future__ import annotations

import re
from datetime import date, datetime

# Priorità parole vicino alle quali cercare una data
_KEYWORDS: tuple[tuple[str, int], ...] = (
    ("scadenza presentazione", 10),
    ("termine di presentazione", 10),
    ("termine per la presentazione", 10),
    ("entro e non oltre", 9),
    ("data limite", 8),
    ("scadenza", 7),
    ("entro il", 5),
    ("fino al", 5),
    ("entro", 3),
)

_DATE_DMY = re.compile(
    r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b"
)
_DATE_DMY_DOTS = re.compile(
    r"\b(\d{2})\.(\d{2})\.(\d{4})\b"
)
_DATE_ISO = re.compile(
    r"\b(\d{4})-(\d{2})-(\d{2})\b"
)


def _parse_dmy(day: str, month: str, year: str) -> date | None:
    try:
        return datetime(int(year), int(month), int(day)).date()
    except ValueError:
        return None


def _find_dates_with_positions(text: str) -> list[tuple[int, date]]:
    found: list[tuple[int, date]] = []
    for pattern in (_DATE_DMY, _DATE_DMY_DOTS):
        for m in pattern.finditer(text):
            d = _parse_dmy(m.group(1), m.group(2), m.group(3))
            if d:
                found.append((m.start(), d))
    for m in _DATE_ISO.finditer(text):
        try:
            d = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
            found.append((m.start(), d))
        except ValueError:
            continue
    return found


def infer_data_scadenza_from_text(text: str) -> str | None:
    """
    Cerca la data di scadenza più probabile nel testo estratto dal PDF.
    Utile quando Claude lascia data_scadenza vuota ma la data è nel documento.
    """
    if not text or not text.strip():
        return None

    dates = _find_dates_with_positions(text)
    if not dates:
        return None

    text_lower = text.lower()
    scored: list[tuple[float, date]] = []

    for kw, kw_weight in _KEYWORDS:
        start = 0
        while True:
            pos = text_lower.find(kw, start)
            if pos < 0:
                break
            for date_pos, d in dates:
                distance = abs(date_pos - pos)
                if distance <= 400:
                    scored.append((kw_weight * 1000 - distance, d))
            start = pos + len(kw)

    today = date.today()
    future_dates = [d for _, d in dates if d > today]

    if scored:
        best = max(scored, key=lambda x: x[0])[1]
        return best.strftime("%Y-%m-%d")

    if future_dates:
        best_future = max(future_dates)
        return best_future.strftime("%Y-%m-%d")

    return None
