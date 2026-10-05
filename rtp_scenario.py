"""Szenario: Fahrzeug, Strecke mit Höhenprofil und Wind, Randbedingungen der Fahrt. Zufall nur über SplitMix64 (Ganzzahl-Arithmetik, plattformstabil)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

import rtp_constants as C
from rtp_rng import SplitMix64


@dataclass(frozen=True)
class Vehicle:
    cap: float      # Nettokapazität (kWh)
    mass: float     # Gesamtmasse (kg)
    cda: float      # Luftwiderstandsfläche c_w · A (m²)
    cr: float       # Rollwiderstandsbeiwert
    peak: float     # Spitzenladeleistung am Anschluss (kW)
    aux: float      # Nebenverbraucher (kW)
    curve: str      # Name der Ladekurve (C.CURVES)


@dataclass
class Route:
    length: float           # km
    grade: np.ndarray       # Steigung je Zelle (Anteil, 0,02 = 2 %)
    wind: np.ndarray        # Gegenwind je Zelle (km/h, negativ = Rückenwind)
    height: np.ndarray      # Höhe an den Zellgrenzen (m), Start 0
    profile: str
    seed: int

    @property
    def n(self) -> int:
        return len(self.grade)


@dataclass
class Trip:
    vehicle: Vehicle
    route: Route
    temp: float           # °C
    soc0: float           # Anfangsladestand (kWh)
    smin_stop: float      # Mindestladestand bei Ankunft an einem Ladestopp (kWh)
    smin_dest: float      # Mindestladestand am Ziel (kWh)
    vmax: int             # Tempolimit (km/h)
    loss: float           # Ladeverlust bei Referenztemperatur (Prozent)
    stop_h: float         # Fixzeit je Ladestopp (Stunden)


def _pieces(rng, n: int, lo_len: int, hi_len: int, draw) -> np.ndarray:
    """Stückweise konstante Werte: Stücke von lo_len bis hi_len Zellen Länge."""
    out = np.zeros(n)
    i = 0
    while i < n:
        ln = rng.between(lo_len, hi_len)
        out[i:i + ln] = draw()
        i += ln
    return out


def _normal(rng, sd: float, lim: float) -> float:
    """Näherung der Normalverteilung (Summe von zwölf Gleichverteilten minus 6, Irwin-Hall), beschnitten auf ±lim."""
    z = (sum(rng.below(1000) for _ in range(12)) - 6000) / 1000.0
    return float(min(max(sd * z, -lim), lim))


def make_grades(profile: str, n: int, seed: int) -> np.ndarray:
    """Steigung je Zelle in Promille. Typen: flach, huegelig (Höhenunterschied null), mittelgebirge (Höhenunterschied null), pass (ein Anstieg und ein Abstieg)."""
    if profile not in C.PROFILE_TYPES:
        raise ValueError(profile)
    rng = SplitMix64(1_000_003 * (C.PROFILE_TYPES.index(profile) + 1) + seed)
    if profile == "flach":
        return np.zeros(n)
    if profile == "huegelig":
        g = _pieces(rng, n, 3, 8, lambda: float(rng.between(-20, 20)))
        return g - g.mean()
    if profile == "mittelgebirge":
        g = _pieces(rng, n, 2, 6, lambda: _normal(rng, 25.0, 50.0))
        return g - g.mean()
    g = _pieces(rng, n, 4, 10, lambda: float(rng.between(-5, 5)))
    k = max(2, min(rng.between(6, 10), (n - 2) // 2))
    lo = max(1, n // 8)
    hi = max(lo, n // 2 - k)
    s1 = rng.between(lo, hi)
    s2 = min(s1 + k + rng.between(0, 6), n - k)
    up = float(rng.between(40, 50))
    g[s1:s1 + k] = up
    g[s2:s2 + k] = -up
    return g


def make_route(length: float, profile: str, seed: int, headwind: float, wind_mode: str, rise: float = 0.0) -> Route:
    """Strecke aus Zellen zu DX_KM: Steigungsprofil und Wind je Zelle, Höhe an den Zellgrenzen. `rise` (m) ist der zusätzliche Höhenunterschied Start bis Ziel, gleichmäßig verteilt."""
    n = int(round(length / C.DX_KM))
    if n < 4:
        raise ValueError("Strecke zu kurz")
    grade = make_grades(profile, n, seed) / 1000.0 + rise / (n * C.DX_KM * 1000.0)
    wind = np.full(n, float(headwind))
    if wind_mode == "wechselnd":
        rng = SplitMix64(7_000_007 + seed)
        wind = wind + _pieces(rng, n, 4, 10, lambda: float(rng.between(-15, 15)))
    elif wind_mode != "konstant":
        raise ValueError(wind_mode)
    height = np.concatenate([[0.0], np.cumsum(grade * C.DX_KM * 1000.0)])
    return Route(float(n * C.DX_KM), grade, wind, height, profile, int(seed))


def speed_grid(vmax: float) -> list[int]:
    """Wählbare Reisegeschwindigkeiten V_MIN bis zum Tempolimit im Raster V_STEP (das Limit wird auf das Raster abgerundet)."""
    top = int(vmax // C.V_STEP) * C.V_STEP
    return list(range(C.V_MIN, max(top, C.V_MIN) + 1, C.V_STEP))


def make_trip(s: dict) -> Trip:
    """Fahrt aus einem Einstellungs-Wörterbuch (Schlüssel siehe C.SCENARIO_KEYS)."""
    veh = Vehicle(cap=float(s["cap"]), mass=float(s["mass"]), cda=float(s["cda"]), cr=float(s["cr"]), peak=float(s["peak"]), aux=float(s["aux"]), curve=str(s["curve"]))
    route = make_route(float(s["length"]), str(s["profile"]), int(s["seed"]), float(s["headwind"]), str(s["wind_mode"]), float(s.get("rise", 0.0)))
    cap = veh.cap
    return Trip(veh, route, float(s["temp"]), cap * float(s["soc0"]) / 100.0, cap * float(s["smin_stop"]) / 100.0, cap * float(s["smin_dest"]) / 100.0, int(s["vmax"]),
                float(s["loss"]), float(s["stop_min"]) / 60.0)
