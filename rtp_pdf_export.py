"""Ladeplan als PDF (fpdf2, Kernschrift Helvetica: Umlaute gehen, Gedankenstrich, Euro-Zeichen, Emoji und U+2212 nicht)."""
from __future__ import annotations

from fpdf import FPDF

_REPLACE = {"–": "-", "—": "-", "−": "-", "≤": "<=", "≥": ">=", "→": "->", "↔": "<->", "…": "...", "€": "EUR", "·": ".", "Ø": "Durchschnitt", "‰": " Promille", "²": "^2", "³": "^3"}


def _clean(text: str) -> str:
    for a, b in _REPLACE.items():
        text = text.replace(a, b)
    return text.encode("latin-1", "replace").decode("latin-1")


def speed_sections(v, dx: float) -> list:
    """Aufeinanderfolgende Zellen gleicher Geschwindigkeit zu Abschnitten zusammenfassen: (von km, bis km, km/h)."""
    out = []
    for i, x in enumerate(v):
        if out and out[-1][2] == float(x):
            out[-1] = (out[-1][0], (i + 1) * dx, float(x))
        else:
            out.append((i * dx, (i + 1) * dx, float(x)))
    return out


def table_rows(plan, dx: float) -> tuple:
    """Zeilen für die beiden Tabellen: Ladestopps (km, von %, auf %, Ladezeit min, Stoppdauer min) und Geschwindigkeitsabschnitte (von km, bis km, km/h)."""
    stops = [(s.km, s.soc_from, s.soc_to, s.charge_min, s.total_min) for s in plan.stops]
    return stops, speed_sections(plan.v, dx)


def generate_plan_pdf(plan, title: str, summary_lines: list, dx: float) -> bytes:
    """Ladeplan: je Ladestopp Kilometer, Ladestand vorher und nachher, Ladezeit; je Abschnitt die Reisegeschwindigkeit."""
    stops, sections = table_rows(plan, dx)
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, _clean(title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    for line in summary_lines:
        pdf.multi_cell(0, 5, _clean(line), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, _clean("Ladestopps"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, _clean("bei km | Ladestand vorher | Ladestand nachher | Ladezeit (min) | Stopp gesamt (min)"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    if not stops:
        pdf.cell(0, 5, _clean("Kein Ladestopp nötig."), new_x="LMARGIN", new_y="NEXT")
    for km, a, b, ch, tot in stops:
        pdf.cell(0, 5, _clean(f"{km:.0f} | {a:.0f} % | {b:.0f} % | {ch:.0f} | {tot:.0f}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, _clean("Reisegeschwindigkeit"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, _clean("von km | bis km | km/h"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    for a, b, v in sections:
        pdf.cell(0, 5, _clean(f"{a:.0f} | {b:.0f} | {v:.0f}"), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
