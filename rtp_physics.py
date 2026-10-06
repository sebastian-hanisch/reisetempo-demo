"""Physik der Demo: Energiebedarf einer Streckenzelle (Rollen, Hang, Luft mit Wind, Nebenverbraucher, Rekuperation) und Ladezeit aus der Ladekurve (konstante, milde Temperatur).

Einheiten: Geschwindigkeit km/h, Strecke km, Energie kWh, Leistung kW, Zeit Stunden, Kraft N."""
from __future__ import annotations

import numpy as np

import rtp_constants as C
from rtp_scenario import Vehicle


def wheel_force(veh: Vehicle, v: float, grade: float, wind: float) -> float:
    """Kraft am Rad (N) bei Geschwindigkeit v (km/h), Steigung grade (Anteil) und Gegenwind wind (km/h): Rollen + Hangabtrieb + Luft mit Relativgeschwindigkeit."""
    theta = np.arctan(grade)
    rel = (v + wind) / 3.6
    return float(veh.cr * veh.mass * C.G_ACC * np.cos(theta) + veh.mass * C.G_ACC * np.sin(theta) + 0.5 * C.RHO * veh.cda * rel * abs(rel))


def cell_energy(veh: Vehicle, v: float, grade: float, wind: float, dx: float = C.DX_KM) -> float:
    """Energie (kWh) aus der Batterie für eine Zelle der Länge dx bei konstanter Geschwindigkeit v: positiv = Verbrauch, negativ = Rekuperation (nur Fahrarbeit, die Nebenverbraucher kommen dazu)."""
    work = wheel_force(veh, v, grade, wind) * dx * 1000.0 / 3.6e6
    drive = work / C.ETA_DRIVE if work > 0 else work * C.ETA_REGEN
    return drive + veh.aux * (dx / v)


def consumption_flat(veh: Vehicle, v: float, wind: float = 0.0) -> float:
    """Verbrauch auf ebener Strecke in kWh/100 km (zur Anzeige und für Tests)."""
    return 100.0 * cell_energy(veh, v, 0.0, wind, dx=1.0)


def eta_charge(loss: float) -> float:
    """Ladewirkungsgrad: 1 − Ladeverlust (Prozent)."""
    return 1.0 - loss / 100.0


def charge_power(veh: Vehicle, soc_frac, loss: float):
    """Leistung, die in der Batterie ankommt (kW), über dem Ladestand (Anteil 0 bis 1)."""
    pts = np.array(C.CURVES[veh.curve])
    return np.interp(soc_frac, pts[:, 0], pts[:, 1]) * veh.peak * eta_charge(loss)


def charge_time_table(veh: Vehicle, loss: float, grid: np.ndarray) -> np.ndarray:
    """Tch(s) in Stunden: Zeit, um von 0 kWh auf s zu laden (Trapezregel für das Integral von dE / P)."""
    inv = 1.0 / charge_power(veh, grid / veh.cap, loss)
    return np.concatenate([[0.0], np.cumsum(0.5 * (inv[1:] + inv[:-1]) * np.diff(grid))])


def charge_time_exact(veh: Vehicle, loss: float, s_from: float, s_to: float) -> float:
    """Ladezeit in Stunden von s_from auf s_to (kWh) in geschlossener Form: Die Ladekurve ist stückweise linear, das Integral von dE / P je Stück ergibt einen Logarithmus.
    Unabhängig von der Tabelle `charge_time_table` (Gegenprobe und Nachfahrt eines Plans)."""
    if s_to <= s_from:
        return 0.0
    pts = C.CURVES[veh.curve]
    scale = veh.peak * eta_charge(loss)
    total = 0.0
    for (x0, p0), (x1, p1) in zip(pts[:-1], pts[1:]):
        lo, hi = max(s_from, x0 * veh.cap), min(s_to, x1 * veh.cap)
        if hi <= lo:
            continue
        slope = (p1 - p0) / (x1 - x0) / veh.cap               # Leistungsanteil je kWh
        pa = p0 + slope * (lo - x0 * veh.cap)                 # Leistungsanteil bei lo
        pb = p0 + slope * (hi - x0 * veh.cap)
        total += (hi - lo) / (scale * pa) if abs(pb - pa) < 1e-12 else np.log(pb / pa) / (scale * slope)
    return float(total)
