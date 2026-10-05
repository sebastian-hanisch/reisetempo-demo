"""Ladeplan als PDF: Abschnitte aus Zellen, Tabellenzeilen, gültige Datei, Zeichenersatz für die Kernschrift und Inhalt (PDF unkomprimiert, damit der Text lesbar ist)."""
import re

import numpy as np
import pytest
from fpdf import FPDF

import rtp_pdf_export as P
from helpers_fake import plan, stop


class RawPDF(FPDF):
    """FPDF ohne Kompression: Textstücke stehen im Klartext in den Bytes."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.set_compression(False)


@pytest.fixture
def raw_pdf(monkeypatch):
    monkeypatch.setattr(P, "FPDF", RawPDF)


# ------------------------------------------------------------------ speed_sections
def test_speed_sections_merge_neighbouring_cells_of_equal_speed():
    assert P.speed_sections([100, 100, 120, 120, 120, 100], 5.0) == [(0.0, 10.0, 100.0), (10.0, 25.0, 120.0), (25.0, 30.0, 100.0)]


def test_speed_sections_keep_separate_stretches_apart_and_handle_extremes():
    assert P.speed_sections([100, 120, 100], 5.0) == [(0.0, 5.0, 100.0), (5.0, 10.0, 120.0), (10.0, 15.0, 100.0)]
    assert P.speed_sections([110.0] * 4, 5.0) == [(0.0, 20.0, 110.0)]
    assert P.speed_sections([90], 5.0) == [(0.0, 5.0, 90.0)] and P.speed_sections([], 5.0) == []
    assert P.speed_sections(np.array([100.0, 100.0, 105.0]), 2.5) == [(0.0, 5.0, 100.0), (5.0, 7.5, 105.0)]           # numpy-Felder und andere Zellenlänge


def test_speed_sections_cover_the_whole_route_without_gaps():
    v = [100, 100, 90, 90, 90, 110, 100, 100]
    sec = P.speed_sections(v, 5.0)
    assert sec[0][0] == 0.0 and sec[-1][1] == 5.0 * len(v) and all(a[1] == b[0] for a, b in zip(sec, sec[1:])) and all(a[2] != b[2] for a, b in zip(sec, sec[1:]))


# ------------------------------------------------------------------ table_rows
def test_table_rows_hold_stops_and_sections():
    p = plan("opt", 2.0, v=[100, 100, 120], stops=[stop(km=10.0, soc_from=12.4, soc_to=79.6, charge_min=21.3, total_min=26.3), stop(km=90.0, soc_from=15.0, soc_to=40.0, charge_min=9.0, total_min=14.0)])
    stops, sections = P.table_rows(p, 5.0)
    assert stops == [(10.0, 12.4, 79.6, 21.3, 26.3), (90.0, 15.0, 40.0, 9.0, 14.0)] and sections == [(0.0, 10.0, 100.0), (10.0, 15.0, 120.0)]
    assert P.table_rows(plan("opt", 1.0, v=[100]), 5.0) == ([], [(0.0, 5.0, 100.0)])


# ------------------------------------------------------------------ Zeichenersatz
def test_clean_replaces_characters_the_core_font_cannot_draw():
    assert P._clean("A – B — C − D ≤ E ≥ F → G ↔ H … € Ø v² v³ 5‰ a·b") == "A - B - C - D <= E >= F -> G <-> H ... EUR Durchschnitt v^2 v^3 5 Promille a.b"
    assert P._clean("Größe äöüß ÄÖÜ") == "Größe äöüß ÄÖÜ"                      # Umlaute gehen in der Kernschrift
    assert P._clean("Emoji 🚄 und 中") == "Emoji ? und ?" and P._clean("") == ""


# ------------------------------------------------------------------ Datei
def make_plan():
    return plan("opt", 2.0, v=[100, 100, 120, 120, 90], stops=[stop(km=10.0, soc_from=12.4, soc_to=79.6, charge_min=21.3, total_min=26.3)])


def test_pdf_is_a_valid_document():
    data = P.generate_plan_pdf(make_plan(), "Ladeplan Optimum", ["Pkw, 600 km"], 5.0)
    assert isinstance(data, bytes) and data.startswith(b"%PDF") and data.rstrip().endswith(b"%%EOF") and len(data) > 1000


def test_pdf_with_umlauts_and_special_characters_does_not_break():
    lines = ["Strecke: 600 km – Höhe ≤ 1 000 m → Ankunft … Ø 120 km/h, Kosten 5 €", "Steigung 40 ‰, v² und v³, Größe, Rückenwind, 🚄 und 中 und ΩΩ", "Kälte −10 °C"]
    data = P.generate_plan_pdf(make_plan(), "Ladeplan für Größe – äöüß ≥ Ø", lines, 5.0)
    assert data.startswith(b"%PDF") and data.rstrip().endswith(b"%%EOF")


def test_pdf_without_stops_and_with_long_content():
    flat = plan("opt", 1.0, v=[100.0] * 4)
    assert P.generate_plan_pdf(flat, "Ohne Stopp", [], 5.0).startswith(b"%PDF")
    many = plan("opt", 9.0, v=[40.0 + 5.0 * (i % 2) for i in range(300)], stops=[stop(km=5.0 * i) for i in range(120)])
    data = P.generate_plan_pdf(many, "Sehr viele Zeilen", ["lange Zeile " * 40] * 3, 5.0)
    pages = re.findall(rb"/Type\s*/Page(?![a-z])", data)
    assert data.startswith(b"%PDF") and len(pages) >= 3                                      # mehrere Seiten durch den automatischen Umbruch


def test_pdf_text_contains_title_summary_stop_row_and_sections(raw_pdf):
    data = P.generate_plan_pdf(make_plan(), "Ladeplan Größe – €", ["Zeile ä ö ü ß ≤ 5 ‰", "zweite Zeile"], 5.0)
    assert b"(Ladeplan Gr\xf6\xdfe - EUR)" in data                                          # Titel, Latin-1 und ersetztes Sonderzeichen
    assert b"(Zeile \xe4 \xf6 \xfc \xdf <= 5  Promille)" in data and b"(zweite Zeile)" in data
    assert b"(Ladestopps)" in data and b"(Reisegeschwindigkeit)" in data
    assert b"(10 | 12 % | 80 % | 21 | 26)" in data                                          # km 10, 12,4 % auf 79,6 %, Ladezeit 21,3 min, Stopp 26,3 min, jeweils gerundet
    assert b"(0 | 10 | 100)" in data and b"(10 | 20 | 120)" in data and b"(20 | 25 | 90)" in data
    assert b"Kein Ladestopp" not in data


def test_pdf_without_stops_says_so(raw_pdf):
    data = P.generate_plan_pdf(plan("opt", 1.0, v=[100.0, 100.0]), "Titel", [], 5.0)
    assert b"(Kein Ladestopp n\xf6tig.)" in data and b"(0 | 10 | 100)" in data
