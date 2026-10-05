"""Gemeinsame Hilfen der Kerntests (Algorithmus, Strategien, Orakel): Mini-Fahrten mit frei wählbaren Zellen, eine Ladekurve mit konstanter Leistung,
und ein Zwischenspeicher für die vollen Läufe der Szenarien (ein Lauf je Szenario für alle Testdateien).

Die Mini-Fahrt `mini_trip` ist so gebaut, dass sich die Erwartungen im Kopf rechnen lassen: Ohne Rollwiderstand und Luftwiderstand (cr = cda = 0) verbraucht eine ebene Zelle nur die
Nebenverbraucher (aux · dx / v, bei 20 °C ohne Kältefaktor). Mit aux = 6,3 kW und v = 50 km/h sind das 6,3 · 5 / 50 = 0,63 kWh je Zelle."""
from __future__ import annotations

import functools

import numpy as np
import pytest

import rtp_algorithm as A
import rtp_constants as C
import rtp_scenario as S
import rtp_strategies as ST

FLAT_CURVE = "Flach"


@pytest.fixture
def flat_curve(monkeypatch):
    """Ladekurve mit konstanter Leistung (Anteil 1 bei jedem Ladestand): dann ist die Ladezeit = Energie / (Spitzenleistung · Wirkungsgrad)."""
    monkeypatch.setitem(C.CURVES, FLAT_CURVE, ((0.0, 1.0), (1.0, 1.0)))


def mini_trip(n, grade=0.0, wind=0.0, cap=10.0, soc0=10.0, smin_stop=1.0, smin_dest=1.0, aux=6.3, peak=60.0, stop_h=0.1, mass=1000.0, cda=0.0, cr=0.0,
              temp=20.0, loss=0.0, curve=FLAT_CURVE, vmax=50):
    """Fahrt mit n Zellen zu je 5 km; Ladestände in kWh; grade und wind als Zahl (alle Zellen gleich) oder als Liste je Zelle."""
    veh = S.Vehicle(cap, mass, cda, cr, peak, aux, curve)
    g = np.full(n, float(grade)) if np.isscalar(grade) else np.asarray(grade, dtype=float)
    w = np.full(n, float(wind)) if np.isscalar(wind) else np.asarray(wind, dtype=float)
    height = np.concatenate([[0.0], np.cumsum(g * C.DX_KM * 1000.0)])
    route = S.Route(n * C.DX_KM, g, w, height, "flach", 0)
    return S.Trip(veh, route, float(temp), float(soc0), float(smin_stop), float(smin_dest), int(vmax), float(loss), float(stop_h))


@functools.lru_cache(maxsize=None)
def preset_run(name: str, length: int | None = None):
    """Alle vier Verfahren für ein Preset (optional mit anderer Streckenlänge); ein Lauf je Schlüssel für die ganze Testsitzung."""
    s = dict(C.PRESETS[name])
    if length is not None:
        s["length"] = length
    trip = S.make_trip(s)
    return trip, ST.run_all(trip)


@functools.lru_cache(maxsize=None)
def single_speed_plans(name: str, length: int | None = None):
    """DP-Pläne mit je einer einzigen Geschwindigkeit der Liste (Zeit je Geschwindigkeit)."""
    trip, _ = preset_run(name, length)
    return {v: A.solve(trip, [v]) for v in S.speed_grid(trip.vmax)}
