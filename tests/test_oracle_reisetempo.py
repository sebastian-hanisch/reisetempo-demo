"""Orakel-Tests (ORACLE-PLAYBOOK, Verfahrenstyp „exakt: DP“ und „geschlossene Formel“): Das DP über (Ort, Ladestand) wird gegen andere Rechenwege geprüft.

(a) Vollaufzählung auf Mini-Strecken: jede Geschwindigkeitsfolge und jede Ladeentscheidung (Laden an einer Zellgrenze auf jedes Rasterniveau oder nicht), eigene
    Simulation des stetigen Ladestands, Zeit aus den Physikfunktionen und `charge_time_exact`. Zielfunktion Zeitwert · Zeit + Energiegewicht · entnommene Energie, die entnommene
    Energie aus der Energieerhaltung (Anfangsladestand + geladen − Endladestand), unabhängig von der Zellrechnung des DP. Es werden bis zu zwei Stopps aufgezählt; die Szenarien sind
    so gewählt, dass ein dritter Stopp nie lohnt (jeder Stopp kostet Fixzeit); lohnte er doch, wäre das DP besser als die Aufzählung und der Test würde sichtbar rot.
(b) geschlossene Formel: ebene Strecke, eine Geschwindigkeit, ein Stopp: T(Stoppzellgrenze) analytisch, das Minimum durch Absuchen gegen `solve([v])`; ohne Laden
    zerfällt die Wahl der Geschwindigkeit in unabhängige Zellen (kleinste Kosten je Zelle).
(c) `charge_time_exact` gegen numerische Quadratur (feine Mittelpunktsregel) und gegen die Tabelle `charge_time_table`.
(d) Energie je Zelle gegen eine eigene Leistungsbilanz (P = F · v statt Kraft mal Weg).
(e) `check_plan` und eine eigene Nachrechnung gegen die Zeit der Pläne.
Die Ladezeit der Aufzählung kommt aus `charge_time_exact` (Gegenprobe dafür ist (c)), die Energie aus `cell_energy` (Gegenprobe (d))."""
import itertools
import math

import numpy as np
import pytest

import rtp_algorithm as A
import rtp_constants as C
import rtp_physics as P
import rtp_scenario as S
from helpers_core import flat_curve, mini_trip, preset_run  # noqa: F401  (flat_curve ist eine Fixture)

EPS = 1e-9


# ------------------------------------------------------------------ eigene Hilfen (unabhängig vom Algorithmus-Modul)
def quad_charge_time(veh, loss, s_from, s_to, n=200_000):
    """Ladezeit (h) durch Mittelpunktsregel für das Integral von dE / P(E); P(E) aus den Stützpunkten der Ladekurve, selbst interpoliert."""
    if s_to <= s_from:
        return 0.0
    pts = C.CURVES[veh.curve]
    xs = np.array([p[0] for p in pts]) * veh.cap
    ys = np.array([p[1] for p in pts])
    eta = 1.0 - loss / 100.0
    e = s_from + (np.arange(n) + 0.5) * (s_to - s_from) / n
    j = np.clip(np.searchsorted(xs, e, side="right") - 1, 0, len(xs) - 2)
    frac = (e - xs[j]) / (xs[j + 1] - xs[j])
    power = (ys[j] + frac * (ys[j + 1] - ys[j])) * veh.peak * eta
    return float(np.sum((s_to - s_from) / n / power))


def power_energy(veh, v, grade, wind, dx=C.DX_KM):
    """Energie einer Zelle aus einer Leistungsbilanz: Leistung am Rad (kW) = Kraft · Geschwindigkeit, mal Fahrzeit; Neigungswinkel über Wurzelformeln statt arctan."""
    root = math.sqrt(1.0 + grade * grade)
    cos_t, sin_t = 1.0 / root, grade / root
    v_ms = v / 3.6
    rel = (v + wind) / 3.6
    force = veh.mass * C.G_ACC * (veh.cr * cos_t + sin_t) + 0.5 * C.RHO * veh.cda * rel * abs(rel)
    hours = dx / v
    wheel_kwh = force * v_ms / 1000.0 * hours
    batt = wheel_kwh / C.ETA_DRIVE if wheel_kwh > 0 else wheel_kwh * C.ETA_REGEN
    return batt + veh.aux * hours


def simulate(trip, speeds_per_cell, stops):
    """Eine Fahrt Zelle für Zelle mit stetigem Ladestand: stops = {Zellindex: Ladeziel in kWh}. Liefert (Zeit, Endladestand, kleinster Ladestand, kleinster Ankunftsstand an einem Stopp nach dem Start,
    entnommene Energie aus der Energieerhaltung: Anfangsladestand + geladen − Endladestand)."""
    veh, rt = trip.vehicle, trip.route
    s, t, charged = trip.soc0, 0.0, 0.0
    low, arr = s, math.inf
    for i in range(rt.n):
        if i in stops:
            if i > 0:
                arr = min(arr, s)
            t += quad_charge_time(veh, trip.loss, s, stops[i]) + trip.stop_h
            charged += stops[i] - s
            s = stops[i]
        v = speeds_per_cell[i]
        s = min(s - power_energy(veh, v, rt.grade[i], rt.wind[i]), veh.cap)
        t += C.DX_KM / v
        low = min(low, s)
    return t, s, low, arr, trip.soc0 + charged - s


def cost_of(trip, time_h, used_kwh):
    """Zielfunktion der Aufzählung: Zeitwert · Zeit + Energiegewicht · entnommene Energie."""
    return trip.w_time * time_h + trip.w_energy * used_kwh


def walk(s, energies, cap):
    """Mehrere Ausgangsladestände gleichzeitig durch Zellen fahren: (Endladestand, kleinster Ladestand unterwegs); oberhalb der Kapazität geht Rekuperation verloren."""
    s = np.asarray(s, dtype=float)
    low = s.copy()
    for e in energies:
        s = np.minimum(s - e, cap)
        low = np.minimum(low, s)
    return s, low


def enumerate_optimum(trip, speeds):
    """Kleinste Kosten (Zeitwert · Zeit + Energiegewicht · entnommene Energie; bei Gewichten 1 und 0 die Reisezeit) über alle Geschwindigkeitsfolgen und alle Ladeentscheidungen (kein Stopp,
    ein Stopp, zwei Stopps; Ladeziel jedes Rasterniveau). Rückgabe (Kosten, Beschreibung)."""
    veh, rt = trip.vehicle, trip.route
    n, cap = rt.n, veh.cap
    levels = np.linspace(0.0, cap, C.N_SOC + 1)
    nodes = np.linspace(0.0, cap, 4001)
    tex_nodes = np.array([P.charge_time_exact(veh, trip.loss, 0.0, x) for x in nodes])
    wt, we = trip.w_time, trip.w_energy

    def tex(x):
        return np.interp(x, nodes, tex_nodes)

    energy = [[P.cell_energy(veh, v, rt.grade[i], rt.wind[i]) for v in speeds] for i in range(n)]
    best = (math.inf, None)
    for combo in itertools.product(range(len(speeds)), repeat=n):
        e = [energy[i][k] for i, k in enumerate(combo)]
        drive = sum(C.DX_KM / speeds[k] for k in combo)
        end, low = walk(trip.soc0, e, cap)
        cost0 = wt * drive + we * (trip.soc0 - end)
        if low >= -EPS and end >= trip.smin_dest - EPS and cost0 < best[0]:
            best = (float(cost0), (combo, ()))
        pre, s, lo = [], trip.soc0, trip.soc0              # Ladestand vor Zelle a und kleinster Stand davor
        for a in range(n):
            pre.append((s, lo))
            s = min(s - e[a], cap)
            lo = min(lo, s)
        for a in range(n):
            s_a, low_a = pre[a]
            if low_a < -EPS or (a > 0 and s_a < trip.smin_stop - EPS):
                continue
            t1 = levels[levels > s_a + 1e-12]
            end, low = walk(t1, e[a:], cap)
            total = np.where((low >= -EPS) & (end >= trip.smin_dest - EPS),
                             wt * (drive + trip.stop_h + tex(t1) - tex(s_a)) + we * (trip.soc0 + (t1 - s_a) - end), np.inf)
            if t1.size:
                j = int(np.argmin(total))
                if total[j] < best[0]:
                    best = (float(total[j]), (combo, ((a, float(t1[j])),)))
            for b in range(a + 1, n):
                sb, low1 = walk(t1, e[a:b], cap)
                rows = (low1 >= -EPS) & (sb >= trip.smin_stop - EPS)
                if not rows.any():
                    continue
                t1r, sbr = t1[rows], sb[rows]
                end2, low2 = walk(levels, e[b:], cap)
                ok2 = (low2 >= -EPS) & (end2 >= trip.smin_dest - EPS)
                cost = (wt * (drive + 2 * trip.stop_h + (tex(t1r) - tex(s_a))[:, None] + tex(levels)[None, :] - tex(sbr)[:, None])
                        + we * (trip.soc0 + (t1r - s_a)[:, None] + (levels[None, :] - sbr[:, None]) - end2[None, :]))
                cost = np.where((levels[None, :] > sbr[:, None] + 1e-12) & ok2[None, :], cost, np.inf)
                idx = np.unravel_index(np.argmin(cost), cost.shape)
                if cost[idx] < best[0]:
                    best = (float(cost[idx]), (combo, ((a, float(t1r[idx[0]])), (b, float(levels[idx[1]])))))
    return best


# ------------------------------------------------------------------ (a) Vollaufzählung
def _veh(cap=12.0, peak=15.0, aux=1.5, mass=2500.0, cda=1.4, cr=0.01, curve="Standard"):
    return dict(cap=cap, peak=peak, aux=aux, mass=mass, cda=cda, cr=cr, curve=curve)


ENUM_CASES = {
    "eben": (dict(n=4, soc0=2.2, smin_stop=0.5, smin_dest=0.5, stop_h=0.06, **_veh()), [60, 90, 120]),
    "gefaelle_rekuperation": (dict(n=4, grade=[0.05, -0.07, -0.07, 0.04], soc0=2.2, smin_stop=0.5, smin_dest=0.5, stop_h=0.06, **_veh()), [60, 90, 120]),
    "gegenwind_dann_rueckenwind": (dict(n=4, wind=[40.0, 40.0, -20.0, -20.0], soc0=2.2, smin_stop=0.5, smin_dest=0.5, stop_h=0.06, **_veh()), [60, 90, 120]),
    "ladeverlust": (dict(n=4, loss=25.0, soc0=2.2, smin_stop=0.4, smin_dest=0.6, stop_h=0.06, **_veh()), [60, 90, 120]),
    "gemischt": (dict(n=4, grade=[0.03, 0.0, -0.04, 0.02], wind=[10.0, -10.0, 20.0, 0.0], soc0=2.5, smin_stop=1.0, smin_dest=1.0, stop_h=0.06, **_veh()), [60, 90, 120]),
    "huegel_kleiner_akku": (dict(n=3, grade=[0.0, 0.06, -0.06], soc0=1.8, smin_stop=0.8, smin_dest=0.3, stop_h=0.06, **_veh(cap=6.0)), [50, 70, 90, 110, 130]),
    "ohne_stopp": (dict(n=4, soc0=12.0, smin_stop=0.5, smin_dest=0.5, stop_h=0.06, **_veh()), [60, 90, 120]),
    # Zielfunktion mit Energiegewicht: Zeitwert 20 €/h, Strom 0,5 €/kWh bei Wirkungsgrad 0,9
    "kosten_eben": (dict(n=4, soc0=2.2, smin_stop=0.5, smin_dest=0.5, stop_h=0.06, w_time=20.0, w_energy=0.5 / 0.9, **_veh()), [60, 90, 120]),
    "kosten_huegel": (dict(n=4, grade=[0.05, -0.07, -0.07, 0.04], soc0=2.2, smin_stop=0.5, smin_dest=0.5, stop_h=0.06, w_time=20.0, w_energy=0.5 / 0.9, **_veh()), [60, 90, 120]),
    "kosten_gemischt_billige_zeit": (dict(n=4, grade=[0.03, 0.0, -0.04, 0.02], wind=[10.0, -10.0, 20.0, 0.0], soc0=2.5, smin_stop=1.0, smin_dest=1.0, stop_h=0.06, w_time=4.0, w_energy=0.6, **_veh()), [60, 90, 120]),
    "kosten_kleiner_akku": (dict(n=3, grade=[0.0, 0.06, -0.06], soc0=1.8, smin_stop=0.8, smin_dest=0.3, stop_h=0.06, w_time=30.0, w_energy=0.7, **_veh(cap=6.0)), [50, 70, 90, 110, 130]),
    "kosten_ohne_stopp": (dict(n=4, soc0=12.0, smin_stop=0.5, smin_dest=0.5, stop_h=0.06, w_time=10.0, w_energy=0.6, **_veh()), [60, 90, 120]),
}


@pytest.mark.parametrize("name", list(ENUM_CASES))
def test_dp_equals_the_full_enumeration_of_speeds_and_charging_decisions(name):
    kw, speeds = ENUM_CASES[name]
    trip = mini_trip(**kw)
    ref, arg = enumerate_optimum(trip, speeds)
    assert math.isfinite(ref)
    # die Aufzählung rechnet ihren besten Plan mit der Quadratur und der Leistungsbilanz nach (Gegenprobe des Orakels selbst)
    combo, stops = arg
    t_re, s_end, low, arr, used = simulate(trip, [speeds[k] for k in combo], {a: x for a, x in stops})
    assert cost_of(trip, t_re, used) == pytest.approx(ref, rel=1e-4) and s_end >= trip.smin_dest - 1e-6 and low >= -1e-6 and arr >= trip.smin_stop - 1e-6
    plan = A.solve(trip, speeds)
    assert plan.feasible
    # das DP rechnet auf dem Raster mit linear interpolierter Wertfunktion: nie besser als die Aufzählung (Interpolation höchstens 0,2 %), höchstens 1 % schlechter
    assert ref * (1 - 0.002) <= plan.value <= ref * 1.01
    assert ref * (1 - 0.002) <= A.plan_cost(trip, plan) <= ref * 1.01


def test_enumeration_oracle_by_hand_on_a_single_cell_with_a_flat_charging_curve(flat_curve):
    """Orakel an einem Handbeispiel: eine Zelle zu 5 km, v = 50 oder 100 km/h, ohne Rollen und Luft: Energie = aux · 5 / v = 6,3 · 0,1 = 0,63 bzw. 0,315 kWh, Ladeleistung 60 kW,
    Anfangsladestand 1,0, Mindestladestand am Ziel 0,5: 100 km/h reichen ohne Laden (1,0 − 0,315 = 0,685 ≥ 0,5), Zeit 0,05 h."""
    trip = mini_trip(1, soc0=1.0, smin_stop=0.2, smin_dest=0.5, stop_h=0.1)
    ref, arg = enumerate_optimum(trip, [50, 100])
    assert ref == pytest.approx(0.05) and arg == ((1,), ())
    # Anfangsladestand 0,7: 100 km/h brauchen 0,315 und enden bei 0,385 < 0,5, also Laden: 0,115 kWh / 60 kW + 0,1 h Fixzeit; 50 km/h (0,63) wären langsamer.
    trip = mini_trip(1, soc0=0.7, smin_stop=0.2, smin_dest=0.5, stop_h=0.1)
    ref, arg = enumerate_optimum(trip, [50, 100])
    assert arg[0] == (1,) and len(arg[1]) == 1 and arg[1][0][0] == 0
    assert ref == pytest.approx(0.05 + 0.1 + (0.82 - 0.7) / 60, abs=2e-5)     # Ziel 0,5 + 0,315 = 0,815 kWh, aufgerundet auf das Rasterniveau 0,82 (Schritt 0,02)


def test_a_vehicle_that_cannot_reach_the_destination_is_infeasible_for_both():
    """Akku 3 kWh, Mindestladestand am Stopp 2,5: nach dem Laden bleibt nach einer Zelle (je über 1 kWh) weniger als 2,5, es gibt keinen zweiten Stopp, vier Zellen brauchen über 4 kWh."""
    trip = mini_trip(4, soc0=3.0, smin_stop=2.5, smin_dest=0.5, stop_h=0.06, **_veh(cap=3.0))
    ref, _ = enumerate_optimum(trip, [60, 90, 120])
    assert math.isinf(ref)
    plan = A.solve(trip, [60, 90, 120])
    assert not plan.feasible and plan.note


# ------------------------------------------------------------------ (b) geschlossene Formel
def _flat_cell_energy(veh, v):
    """Ebene Zelle ohne Wind in kWh, eigene Schreibweise: Rollen + Luft, Wirkungsgrad, Nebenverbraucher."""
    force = veh.cr * veh.mass * C.G_ACC + 0.5 * C.RHO * veh.cda * (v / 3.6) ** 2
    return force * C.DX_KM * 1000.0 / 3.6e6 / C.ETA_DRIVE + veh.aux * C.DX_KM / v


def closed_form_time(trip, v):
    """Reisezeit mit einer Geschwindigkeit und höchstens einem Stopp auf ebener Strecke: kleinste Zeit über alle erlaubten Stoppzellgrenzen k; geladen wird genau so viel, wie das Ziel braucht."""
    veh, n = trip.vehicle, trip.route.n
    e = _flat_cell_energy(veh, v)
    drive = n * C.DX_KM / v
    best = math.inf
    if trip.soc0 - n * e >= trip.smin_dest - EPS:
        best = drive
    for k in range(n):
        s_k = trip.soc0 - k * e
        if s_k < -EPS or (k > 0 and s_k < trip.smin_stop - EPS):
            continue
        target = trip.smin_dest + (n - k) * e
        if target > veh.cap or target <= s_k:
            continue
        best = min(best, drive + trip.stop_h + quad_charge_time(veh, trip.loss, s_k, target, n=20_000))
    return best


FORMULA_CASES = [
    # Fahrzeug, Geschwindigkeit, Länge (km), Anfangsladestand (Anteil), Ladeverlust, Fixzeit (min), Mindestladestand Stopp/Ziel (Anteil)
    ("Pkw", 130, 400, 1.0, 10.0, 5.0, 0.10),
    ("Pkw", 100, 450, 0.8, 10.0, 5.0, 0.10),
    ("Kompaktwagen", 90, 380, 1.0, 10.0, 8.0, 0.10),
    ("Lieferwagen", 100, 250, 1.0, 10.0, 5.0, 0.15),
    ("Großer Pkw", 120, 380, 0.9, 12.0, 3.0, 0.10),
]


@pytest.mark.parametrize("tv", [C.TV_FAST, 20])
@pytest.mark.parametrize("vehicle,v,length,soc_frac,loss,stop_min,smin", FORMULA_CASES)
def test_one_speed_one_stop_on_a_flat_track_matches_the_closed_formula(vehicle, v, length, soc_frac, loss, stop_min, smin, tv):
    s = {**C.BASE_SCENARIO, **C.vehicle_scenario(vehicle), "profile": "flach", "length": length, "headwind": 0, "loss": loss, "stop_min": stop_min,
         "soc0": 100 * soc_frac, "smin_stop": 100 * smin, "smin_dest": 100 * smin, "rise": 0, "tv": tv}
    trip = S.make_trip(s)
    ref = closed_form_time(trip, v)
    assert math.isfinite(ref)
    plan = A.solve(trip, [v])
    assert plan.feasible and len(plan.stops) == 1                         # der Fall gehört zur Formel (genau ein Stopp)
    assert plan.time_h == pytest.approx(ref, rel=0.005)
    # mit nur einer Geschwindigkeit hängt die entnommene Energie nicht vom Laden ab: Kosten = Zeitwert · Zeit + Energiegewicht · (Zellen · Energie je Zelle)
    ref_cost = trip.w_time * ref + trip.w_energy * trip.route.n * _flat_cell_energy(trip.vehicle, v)
    assert plan.value == pytest.approx(ref_cost, rel=0.005)
    assert plan.used_kwh == pytest.approx(trip.route.n * _flat_cell_energy(trip.vehicle, v), rel=1e-9)
    # die Zeit des Stopps in der Formel: die Fixzeit plus die Ladezeit des einen Stopps
    assert plan.fix_h == pytest.approx(stop_min / 60.0) and plan.drive_h == pytest.approx(length / v)


def test_closed_formula_by_hand_for_the_pkw_at_100_kmh_without_stop():
    """Handrechnung: Pkw 100 km/h eben: Rollen 0,01 · 2000 · 9,81 = 196,2 N, Luft 0,5 · 1,2 · 0,62 · (100 / 3,6)² = 287,04 N, zusammen 483,24 N; je 5 km 483,24 · 5000 / 3,6e6 = 0,67117 kWh
    am Rad, / 0,9 = 0,74574, plus Nebenverbraucher 0,8 · 5 / 100 = 0,04: 0,78574 kWh je Zelle, 15,715 kWh / 100 km. 120 Zellen (600 km) brauchen 94,3 kWh, der Akku fasst 77."""
    veh = S.make_trip(C.PRESETS["Standard"]).vehicle
    assert _flat_cell_energy(veh, 100.0) == pytest.approx(0.78574, abs=2e-5)
    assert P.consumption_flat(veh, 100.0) == pytest.approx(15.715, abs=5e-3)


# ------------------------------------------------------------------ (c) Ladezeit
CHARGE_CASES = [(cap, curve, loss, a, b) for cap, curve, loss, a, b in [
    (77.0, "Standard", 10.0, 0.0, 77.0),
    (77.0, "Standard", 10.0, 7.7, 61.6),
    (77.0, "Standard", 25.0, 5.0, 40.0),
    (100.0, "Lange Spitze", 0.0, 12.0, 95.0),
    (100.0, "Lange Spitze", 15.0, 30.0, 31.0),
    (80.0, "Früh abfallend", 10.0, 0.0, 80.0),
    (80.0, "Früh abfallend", 30.0, 20.0, 75.0),
    (600.0, "Standard", 10.0, 60.0, 480.0),
]]


@pytest.mark.parametrize("cap,curve,loss,a,b", CHARGE_CASES)
def test_charge_time_exact_matches_numerical_quadrature(cap, curve, loss, a, b):
    veh = S.Vehicle(cap, 2000.0, 0.62, 0.01, 150.0, 0.8, curve)
    assert P.charge_time_exact(veh, loss, a, b) == pytest.approx(quad_charge_time(veh, loss, a, b), rel=1e-4)


@pytest.mark.parametrize("cap,curve,loss,a,b", CHARGE_CASES)
def test_charge_time_exact_is_additive_and_matches_the_table(cap, curve, loss, a, b):
    veh = S.Vehicle(cap, 2000.0, 0.62, 0.01, 150.0, 0.8, curve)
    mid = 0.5 * (a + b)
    assert P.charge_time_exact(veh, loss, a, mid) + P.charge_time_exact(veh, loss, mid, b) == pytest.approx(P.charge_time_exact(veh, loss, a, b), rel=1e-9)
    grid, _ = A.make_grid(cap)
    tab = P.charge_time_table(veh, loss, grid)
    for lo, hi in [(0, 500), (50, 300), (120, 460), (200, 201)]:
        assert tab[hi] - tab[lo] == pytest.approx(P.charge_time_exact(veh, loss, grid[lo], grid[hi]), rel=2e-3, abs=1e-9)


def test_charge_time_by_hand_with_a_constant_power_and_with_one_linear_piece(flat_curve):
    """Konstante Leistung 60 kW (Ladeverlust 0): 6 kWh brauchen 0,1 h. Eine Strecke der Standardkurve, Anteil 0,1 bis 0,35 mit Leistungsanteil 1: Pkw 150 kW, Wirkungsgrad 0,9
    ergibt 135 kW, 77 · 0,25 = 19,25 kWh dauern 19,25 / 135 = 0,14259 h."""
    veh = S.Vehicle(10.0, 1000.0, 0.0, 0.0, 60.0, 1.0, "Flach")
    assert P.charge_time_exact(veh, 0.0, 2.0, 8.0) == pytest.approx(0.1)
    pkw = S.Vehicle(77.0, 2000.0, 0.62, 0.01, 150.0, 0.8, "Standard")
    assert P.charge_time_exact(pkw, 10.0, 7.7, 26.95) == pytest.approx(19.25 / 135.0)
    assert P.charge_time_exact(pkw, 10.0, 26.95, 7.7) == 0.0 and P.charge_time_exact(pkw, 10.0, 30.0, 30.0) == 0.0


# ------------------------------------------------------------------ (d) Energie je Zelle
@pytest.mark.parametrize("vehicle", C.VEHICLE_ORDER)
def test_cell_energy_matches_an_independent_power_balance(vehicle):
    veh = S.make_trip({**C.BASE_SCENARIO, **C.vehicle_scenario(vehicle)}).vehicle
    for v in (60, 65, 90, 120, 150, 180):
        for grade in (-0.08, -0.03, 0.0, 0.015, 0.05, 0.1):
            for wind in (-40.0, -10.0, 0.0, 25.0, 40.0):
                assert P.cell_energy(veh, v, grade, wind) == pytest.approx(power_energy(veh, v, grade, wind), rel=1e-9, abs=1e-12)


def test_cell_energy_by_hand_on_slopes_without_rolling_and_air_resistance():
    """Masse 1000 kg, cr = cda = 0, aux 6 kW, 50 km/h: Hang 10 %: sin(arctan 0,1) = 0,0995037, Kraft 1000 · 9,81 · 0,0995037 = 976,13 N, Arbeit 976,13 · 5000 / 3,6e6 = 1,35574 kWh,
    / 0,9 = 1,50638 + Nebenverbraucher 6 · 5 / 50 = 0,6: 2,10638 kWh. Gefälle 10 %: −1,35574 · 0,65 = −0,88123 + 0,6 = −0,28123 kWh (Rekuperation übersteigt den Nebenverbrauch)."""
    veh = S.Vehicle(50.0, 1000.0, 0.0, 0.0, 100.0, 6.0, "Standard")
    assert P.cell_energy(veh, 50.0, 0.1, 0.0) == pytest.approx(2.10638, abs=2e-5)
    assert P.cell_energy(veh, 50.0, -0.1, 0.0) == pytest.approx(-0.28123, abs=2e-5)


# ------------------------------------------------------------------ (e) check_plan und eigene Nachrechnung
@pytest.mark.parametrize("name", C.PRESET_ORDER)
def test_check_plan_and_an_own_resimulation_agree_with_the_plan_time(name):
    trip, plans = preset_run(name)
    rt = trip.route
    for key, plan in plans.items():
        if not plan.feasible:
            continue
        chk = A.check_plan(trip, plan)
        assert chk["ok"], (name, key)
        assert chk["time_h"] == pytest.approx(plan.time_h, rel=1e-9) and chk["soc_end"] == pytest.approx(plan.soc_end, abs=1e-6)
        stops = {int(round(st.km / C.DX_KM)): trip.vehicle.cap * st.soc_to / 100.0 for st in plan.stops}
        t, s_end, low, arr, used = simulate(trip, [float(v) for v in plan.v], stops)
        assert t == pytest.approx(plan.time_h, rel=2e-4), (name, key)          # Quadratur statt Geschlossene Form, Leistungsbilanz statt Kraft
        assert used == pytest.approx(plan.used_kwh, rel=1e-6, abs=1e-6) and chk["used_kwh"] == pytest.approx(plan.used_kwh, rel=1e-9, abs=1e-9), (name, key)     # Energieerhaltung gegen Zellrechnung
        assert chk["cost"] == pytest.approx(A.plan_cost(trip, plan), rel=1e-9) and cost_of(trip, t, used) == pytest.approx(A.plan_cost(trip, plan), rel=2e-4), (name, key)
        assert s_end == pytest.approx(plan.soc_end, abs=1e-4) and s_end >= trip.smin_dest - 1e-6 and low >= -1e-6
        assert len(plan.v) == rt.n and len(plan.energy) == rt.n
        for i in range(rt.n):
            assert plan.energy[i] == pytest.approx(power_energy(trip.vehicle, plan.v[i], rt.grade[i], rt.wind[i]), rel=1e-9, abs=1e-12)
        if any(st.km > 0 for st in plan.stops):
            assert arr >= trip.smin_stop - 1e-6


# ------------------------------------------------------------------ (f) ohne Laden zerfällt die Geschwindigkeitswahl in unabhängige Zellen
COST_CELL_CASES = [
    # (Zeitwert €/h, Energiegewicht €/kWh, Gefälle je Zelle, Gegenwind je Zelle)
    (20.0, 0.5 / 0.9, [0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0]),
    (5.0, 0.6, [0.04, -0.03, 0.0, 0.02], [0.0, 20.0, -20.0, 0.0]),
    (60.0, 0.6, [0.0, 0.03, -0.05, 0.0], [30.0, 30.0, -10.0, 0.0]),
    (1.0, 0.6, [0.01, 0.0, 0.0, -0.01], [0.0, 0.0, 0.0, 0.0]),
]


@pytest.mark.parametrize("w_time,w_energy,grade,wind", COST_CELL_CASES)
def test_without_charging_each_cell_takes_the_speed_with_the_smallest_cell_cost(w_time, w_energy, grade, wind):
    """Großer Akku, Start voll, Ziel ohne Mindestladestand: Es wird nie geladen, und die Kosten sind eine Summe über die Zellen. Jede Zelle nimmt die Geschwindigkeit mit den kleinsten Zellkosten
    Zeitwert · dx / v + Energiegewicht · Energie (eigene Leistungsbilanz, Rekuperation unterhalb der Kapazität)."""
    speeds = [60, 70, 80, 90, 100, 110, 120, 130]
    trip = mini_trip(4, grade=grade, wind=wind, soc0=80.0, smin_stop=0.0, smin_dest=0.0, stop_h=0.1, w_time=w_time, w_energy=w_energy, **_veh(cap=80.0))
    plan = A.solve(trip, speeds)
    assert plan.feasible and plan.stops == []
    expected, total = [], 0.0
    for i in range(4):
        costs = [w_time * C.DX_KM / v + w_energy * power_energy(trip.vehicle, v, grade[i], wind[i]) for v in speeds]
        expected.append(speeds[int(np.argmin(costs))])
        total += min(costs)
    assert plan.v.tolist() == [float(v) for v in expected]
    assert plan.value == pytest.approx(total, rel=1e-6) and A.plan_cost(trip, plan) == pytest.approx(total, rel=1e-6)
