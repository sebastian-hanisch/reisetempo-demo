"""Der DP-Kern einheitenweise (DEMO-PLAYBOOK §1b): jede Einheit an einer Mini-Instanz mit von Hand gerechneten Erwartungen, danach Eigenschaften des ganzen Plans.

Die Mini-Fahrten (tests/helpers_core.py) haben weder Roll- noch Luftwiderstand: Eine ebene Zelle zu 5 km kostet nur die Nebenverbraucher aux · 5 / v. Mit aux = 6,3 kW und v = 50 km/h
sind das 6,3 · 0,1 = 0,63 kWh je Zelle (bei 100 km/h 0,315 kWh). Das Ladestandsraster hat bei 10 kWh Kapazität den Schritt 10 / 500 = 0,02 kWh."""
import math

import numpy as np
import pytest

import rtp_algorithm as A
import rtp_constants as C
import rtp_physics as P
import rtp_scenario as S
from helpers_core import flat_curve, mini_trip, preset_run, single_speed_plans  # noqa: F401  (flat_curve ist eine Fixture)
from rtp_rng import SplitMix64

INF = A.INF


# ------------------------------------------------------------------ interp_value
def test_interp_value_between_nodes_and_at_nodes():
    arr = np.array([10.0, 8.0, 6.0, 4.0])      # Schritt 2: Wert 10 bei 0, 8 bei 2, 6 bei 4, 4 bei 6
    assert A.interp_value(arr, 2.0, 1.0) == pytest.approx(9.0)         # Mitte zwischen 10 und 8
    assert A.interp_value(arr, 2.0, 3.0) == pytest.approx(7.0)
    assert A.interp_value(arr, 2.0, 5.5) == pytest.approx(4.5)         # 6 + 0,75 · (4 − 6) = 4,5
    assert A.interp_value(arr, 2.0, 0.5) == pytest.approx(9.5)         # 10 + 0,25 · (8 − 10)
    for x, expected in [(0.0, 10.0), (2.0, 8.0), (4.0, 6.0), (6.0, 4.0)]:
        assert A.interp_value(arr, 2.0, x) == pytest.approx(expected)
    out = A.interp_value(arr, 2.0, np.array([1.0, 3.0, 5.0]))           # Feld rein, Feld raus
    assert out.tolist() == pytest.approx([9.0, 7.0, 5.0])


def test_interp_value_below_zero_is_infeasible_and_above_capacity_is_the_full_battery_value():
    arr = np.array([10.0, 8.0, 6.0, 4.0])
    assert A.interp_value(arr, 2.0, -0.5) == INF and A.interp_value(arr, 2.0, -3.0) == INF
    assert A.interp_value(arr, 2.0, -1e-12) == pytest.approx(10.0)      # innerhalb der Rechentoleranz noch zulässig
    assert A.interp_value(arr, 2.0, 7.0) == pytest.approx(4.0) and A.interp_value(arr, 2.0, 600.0) == pytest.approx(4.0)   # über der Kapazität: Wert der vollen Batterie
    assert A.interp_value(arr, 2.0, 6.0) == pytest.approx(4.0)


def test_interp_value_is_infeasible_if_one_of_the_two_neighbours_is_infeasible():
    arr = np.array([INF, 8.0, 6.0, INF])
    assert A.interp_value(arr, 2.0, 1.0) == INF                 # linker Nachbar unzulässig
    assert A.interp_value(arr, 2.0, 3.0) == pytest.approx(7.0)  # beide zulässig
    assert A.interp_value(arr, 2.0, 5.0) == INF                 # rechter Nachbar unzulässig
    assert A.interp_value(arr, 2.0, 4.5) == INF
    assert A.interp_value(np.full(4, INF), 2.0, 3.0) == INF
    assert (A.interp_value(arr, 2.0, np.array([1.0, 3.0, 5.0])) >= INF / 2).tolist() == [True, False, True]


# ------------------------------------------------------------------ with_charging
def test_with_charging_takes_the_suffix_minimum_of_best_plus_charging_time():
    # Rechenweg: h = best + tch = [3, 10, 3, 11]; Suffix-Minimum ab Index j = [3, 3, 3, 11]; „später“ (Ladeziel strikt höher) = [3, 3, 11, INF].
    # g(s) = min(best, Fixzeit − tch + später) mit Fixzeit 0,5: [min(3, 0,5 − 0 + 3), min(9, 0,5 − 1 + 3), min(1, 0,5 − 2 + 11), best] = [3, 2,5, 1, 8]
    best = np.array([3.0, 9.0, 1.0, 8.0])
    tch = np.array([0.0, 1.0, 2.0, 3.0])
    g = A.with_charging(best, tch, 0.5, np.ones(4, dtype=bool))
    assert g.tolist() == pytest.approx([3.0, 2.5, 1.0, 8.0])


def test_with_charging_second_example_with_a_flat_gain():
    # best = [10, 8, 6, 5, 4], tch = [0, 0,5, 1, 1,5, 2], Fixzeit 1: h = [10, 8,5, 7, 6,5, 6], Suffix-Minimum = [6, 6, 6, 6, 6], später = [6, 6, 6, 6, INF]
    # g = [min(10, 1 + 6), min(8, 1 − 0,5 + 6), min(6, 1 − 1 + 6), min(5, 1 − 1,5 + 6), 4] = [7, 6,5, 6, 5, 4]
    best = np.array([10.0, 8.0, 6.0, 5.0, 4.0])
    tch = np.array([0.0, 0.5, 1.0, 1.5, 2.0])
    g = A.with_charging(best, tch, 1.0, np.ones(5, dtype=bool))
    assert g.tolist() == pytest.approx([7.0, 6.5, 6.0, 5.0, 4.0])


def test_with_charging_fixed_time_is_paid_per_stop_and_a_huge_fixed_time_prevents_charging():
    best = np.array([3.0, 9.0, 1.0, 8.0])
    tch = np.array([0.0, 1.0, 2.0, 3.0])
    assert A.with_charging(best, tch, 0.0, np.ones(4, dtype=bool)).tolist() == pytest.approx([3.0, 2.0, 1.0, 8.0])     # Fixzeit 0: 0 − 1 + 3 = 2 statt 2,5
    assert A.with_charging(best, tch, 100.0, np.ones(4, dtype=bool)).tolist() == pytest.approx(best.tolist())


def test_with_charging_not_allowed_below_the_minimum_state_of_charge():
    best = np.array([3.0, 9.0, 1.0, 8.0])
    tch = np.array([0.0, 1.0, 2.0, 3.0])
    can = np.array([False, False, True, True])
    g = A.with_charging(best, tch, 0.5, can)
    assert g.tolist() == pytest.approx([3.0, 9.0, 1.0, 8.0])           # Index 1 würde mit Laden 2,5 erreichen, darf aber nicht
    g_all = A.with_charging(best, tch, 0.5, np.ones(4, dtype=bool))
    assert g_all[1] == pytest.approx(2.5)


def test_with_charging_can_rescue_an_infeasible_state_by_charging_to_a_feasible_one():
    # best = [INF, 4, INF], tch = [0, 1, 2], Fixzeit 0,5: g(0) = 0,5 − 0 + (Suffix-Minimum der später liegenden: min(4 + 1, INF + 2) = 5) = 5,5; g(1) = best = 4 (später ist INF); g(2) bleibt INF
    best = np.array([INF, 4.0, INF])
    tch = np.array([0.0, 1.0, 2.0])
    g = A.with_charging(best, tch, 0.5, np.ones(3, dtype=bool))
    assert g[0] == pytest.approx(5.5) and g[1] == pytest.approx(4.0) and g[2] >= INF / 2


# ------------------------------------------------------------------ make_grid, cell_energies
def test_make_grid_has_n_soc_equal_steps_from_zero_to_capacity():
    grid, ds = A.make_grid(50.0)
    assert len(grid) == C.N_SOC + 1 == 501 and ds == pytest.approx(0.1)
    assert grid[0] == 0.0 and grid[1] == pytest.approx(0.1) and grid[250] == pytest.approx(25.0) and grid[-1] == pytest.approx(50.0)
    assert np.diff(grid) == pytest.approx(np.full(500, 0.1))
    g2, ds2 = A.make_grid(10.0)
    assert ds2 == pytest.approx(0.02) and g2[-1] == pytest.approx(10.0)


def test_cell_energies_is_a_matrix_cells_by_speeds_with_the_hand_values():
    # Fahrzeug 1000 kg, cr = cda = 0, aux 6 kW; Zelle 0 eben, Zelle 1 mit 10 % Steigung, Zelle 2 mit 10 % Gefälle; Geschwindigkeiten 50 und 100 km/h.
    # eben: nur aux: 6 · 5 / 50 = 0,6 bzw. 6 · 5 / 100 = 0,3.
    # Steigung 10 %: sin(arctan 0,1) = 0,0995037 → Kraft 1000 · 9,81 · 0,0995037 = 976,13 N, Arbeit 976,13 · 5000 / 3,6e6 = 1,35574 kWh, / 0,9 = 1,50638: + 0,6 = 2,10638 bzw. + 0,3 = 1,80638
    # Gefälle 10 %: −1,35574 · 0,65 = −0,88123: + 0,6 = −0,28123 bzw. + 0,3 = −0,58123
    trip = mini_trip(3, grade=[0.0, 0.1, -0.1], aux=6.0, mass=1000.0)
    E = A.cell_energies(trip, [50, 100])
    assert E.shape == (3, 2)
    assert E == pytest.approx(np.array([[0.6, 0.3], [2.10638, 1.80638], [-0.28123, -0.58123]]), abs=2e-5)


# ------------------------------------------------------------------ value_functions auf einer Strecke aus 2 Zellen
def _two_cell_trip(stop_h):
    # Kapazität 10 kWh (Schritt 0,02), v = 50 km/h: 0,63 kWh und 0,1 h je Zelle; Mindestladestand am Stopp 2,0, am Ziel 1,0; Ladeleistung 60 kW konstant (Ladeverlust 0)
    return mini_trip(2, cap=10.0, soc0=1.0, smin_stop=2.0, smin_dest=1.0, stop_h=stop_h)


def _two_cell_functions(stop_h):
    trip = _two_cell_trip(stop_h)
    grid, ds = A.make_grid(10.0)
    tch = P.charge_time_table(trip.vehicle, trip.loss, grid)
    E = A.cell_energies(trip, [50])
    f, g = A.value_functions(trip, [50], E, grid, ds, tch)
    return trip, grid, f, g


def test_value_functions_with_two_cells_by_hand_and_a_huge_stop_time(flat_curve):
    # Mit riesiger Fixzeit lohnt kein Stopp, g = f.
    # f[2] (Ziel): 0 ab Ladestand 1,0 (Index 50), sonst unzulässig.
    # f[1]: eine Zelle fahren: 0,1 h + f[2](s − 0,63): s − 0,63 muss mit beiden Rasternachbarn zulässig sein, also ≥ Index 50 (1,00) und der Nachbar 51: s − 0,63 ≥ 1,00 → s ≥ 1,63,
    #       Raster 1,64 (Index 82): s − 0,63 = 1,01 liegt zwischen Index 50 und 51: zulässig. Index 81 (1,62): 0,99 liegt zwischen 49 und 50: unzulässig.
    # f[0]: 0,1 + g[1](s − 0,63): s − 0,63 ≥ 1,64 (Index 82, Nachbar 83) → s ≥ 2,27; Index 114 (2,28): 1,65 liegt zwischen 82 und 83: zulässig; Index 113 (2,26): 1,63: unzulässig.
    trip, grid, f, g = _two_cell_functions(100.0)
    assert len(f) == len(g) == 3
    assert np.all(f[2][:50] >= INF / 2) and np.all(f[2][50:] == 0.0)
    assert np.all(f[1][:82] >= INF / 2) and f[1][82:] == pytest.approx(np.full(419, 0.1))
    assert np.all(f[0][:114] >= INF / 2) and f[0][114:] == pytest.approx(np.full(387, 0.2))
    assert np.all(g[1][:82] >= INF / 2) and g[1][82:] == pytest.approx(f[1][82:])
    assert g[0][114:] == pytest.approx(f[0][114:]) and np.all(g[0][:100] >= INF / 2)


def test_value_functions_with_two_cells_by_hand_with_charging(flat_curve):
    # Fixzeit 0,1 h, 60 kW. g[1]: Laden erlaubt ab Ladestand 2,0 (Index 100), dort ist f[1] schon 0,1, Laden lohnt nicht → g[1] = f[1], unter 1,64 unzulässig
    #   (Index 81 würde mit Laden gehen, ist aber unter dem Mindestladestand 2,0 für einen Stopp: bleibt unzulässig).
    # g[0](2,00) = Laden auf 2,28 (Index 114): 0,1 h Fixzeit + (2,28 − 2,00) / 60 h Ladezeit + f[0](2,28) = 0,1 + 0,0046667 + 0,2 = 0,3046667 h;
    # g[0](2,20) = 0,1 + 0,08 / 60 + 0,2 = 0,3013333; ab Index 114 (2,28) ist g[0] = f[0] = 0,2 (Laden lohnt nie); unter Ladestand 2,0 (Index 99) unzulässig, weil dort kein Stopp erlaubt ist.
    trip, grid, f, g = _two_cell_functions(0.1)
    assert g[0][100] == pytest.approx(0.1 + 0.28 / 60 + 0.2) and g[0][110] == pytest.approx(0.1 + 0.08 / 60 + 0.2)
    assert g[0][114] == pytest.approx(0.2) and g[0][300] == pytest.approx(0.2)
    assert g[0][99] >= INF / 2 and g[1][81] >= INF / 2 and f[1][81] >= INF / 2
    assert g[1][82] == pytest.approx(0.1) and f[0][100] >= INF / 2


def test_value_function_decreases_with_the_state_of_charge_up_to_the_first_feasible_level(flat_curve):
    trip, grid, f, g = _two_cell_functions(0.1)
    for arr in g[:2]:
        feas = arr[arr < INF / 2]
        assert np.all(np.diff(feas) <= 1e-12)           # mehr Ladestand ist nie schlechter


# ------------------------------------------------------------------ solve auf Mini-Strecken
def test_solve_without_a_stop_takes_the_fastest_speed(flat_curve):
    # 4 Zellen, nur aux: bei 100 km/h 0,315 kWh je Zelle (weniger als bei 50), 4 · 0,315 = 1,26 kWh, Start 10 kWh voll → kein Stopp; Zeit = 20 km / 100 km/h = 0,2 h; Endladestand 10 − 1,26 = 8,74
    trip = mini_trip(4, soc0=10.0)
    plan = A.solve(trip, [50, 100], "opt")
    assert plan.feasible and plan.method == "opt" and plan.stops == []
    assert plan.v.tolist() == [100.0] * 4
    assert plan.time_h == pytest.approx(0.2) and plan.value == pytest.approx(0.2)
    assert plan.drive_h == pytest.approx(0.2) and plan.charge_h == 0.0 and plan.fix_h == 0.0 and plan.charged_kwh == 0.0
    assert plan.soc_end == pytest.approx(8.74) and plan.energy.tolist() == pytest.approx([0.315] * 4)
    assert plan.time_min == pytest.approx(12.0) and plan.mean_speed == pytest.approx(100.0)


def test_solve_with_one_necessary_stop_charges_just_enough(flat_curve):
    # 6 Zellen bei 50 km/h (nur eine Geschwindigkeit): 0,63 kWh und 0,1 h je Zelle, 3,78 kWh, Fahrzeit 0,6 h. Start 2,5, Mindestladestand am Ziel 0,5: Bedarf 3,78 + 0,5 = 4,28, Fehlmenge 1,78 kWh.
    # Ein Stopp (Fixzeit 0,1 h) lädt 1,78 kWh bei 60 kW: 0,02967 h; Gesamtzeit 0,6 + 0,1 + 0,02967 = 0,72967 h (das Raster rundet das Ladeziel auf höchstens zwei Schritte à 0,02 kWh auf: +0,0007 h).
    # Wegen der konstanten Ladeleistung ist der Stopp-Ort gleichgültig, er muss nur bei Ankunft den Mindestladestand 1,0 haben: Ankunft 2,5 − 0,63 k ≥ 1,0 → k ≤ 2.
    trip = mini_trip(6, soc0=2.5, smin_stop=1.0, smin_dest=0.5, stop_h=0.1)
    plan = A.solve(trip, [50])
    assert plan.feasible and len(plan.stops) == 1
    st = plan.stops[0]
    assert st.km in (0.0, 5.0, 10.0) and 100 * (2.5 - 0.63 * st.km / 5) / 10 == pytest.approx(st.soc_from)
    assert plan.time_h == pytest.approx(0.72967, abs=1e-3) and plan.value == pytest.approx(0.72967, abs=1e-3)
    assert plan.fix_h == pytest.approx(0.1) and plan.drive_h == pytest.approx(0.6)
    assert plan.charged_kwh == pytest.approx(1.78, abs=0.05) and 0.5 <= plan.soc_end <= 0.56
    assert plan.charge_h == pytest.approx(plan.charged_kwh / 60.0)
    assert st.charge_min == pytest.approx(60 * plan.charge_h) and st.total_min == pytest.approx(60 * (plan.charge_h + 0.1))


def test_solve_charges_at_the_start_when_the_start_is_below_the_minimum_for_a_stop(flat_curve):
    # Zwei Zellen, Start 1,0 kWh (unter dem Mindestladestand 2,0 für Stopps), Mindestladestand am Ziel 1,0: ohne Laden am Start ist das Ziel nicht erreichbar.
    # Von Hand: Laden auf 2,28 kWh (Raster) am Start: Fixzeit 0,1 + 1,28 / 60 = 0,121333 h, Fahrzeit 0,2 h: 0,321333 h; Anfang 10 % → 22,8 %.
    plan = A.solve(_two_cell_trip(0.1), [50])
    assert plan.feasible and len(plan.stops) == 1
    st = plan.stops[0]
    assert st.km == 0.0 and st.soc_from == pytest.approx(10.0) and st.soc_to == pytest.approx(22.8)
    assert st.charge_min == pytest.approx(60 * 1.28 / 60) and st.total_min == pytest.approx(1.28 + 6.0)
    assert plan.time_h == pytest.approx(0.2 + 0.1 + 1.28 / 60) and plan.value == pytest.approx(0.2 + 0.1 + 1.28 / 60)
    assert plan.soc_end == pytest.approx(22.8 * 0.1 - 1.26) and plan.charged_kwh == pytest.approx(1.28)


def test_solve_is_infeasible_with_a_note_if_the_destination_cannot_be_reached(flat_curve):
    # Mindestladestand am Ziel 11 kWh über der Kapazität 10: nie erreichbar
    plan = A.solve(mini_trip(3, smin_dest=11.0), [50])
    assert not plan.feasible and math.isnan(plan.time_h) and plan.value is None and "nicht erreichbar" in plan.note and plan.stops == []
    # Akku 1 kWh, Mindestladestand am Stopp 0,5: nach einer Zelle (0,63) bleibt höchstens 0,37 < 0,5, ein zweiter Stopp ist nie erlaubt, vier Zellen brauchen 2,52 kWh
    plan2 = A.solve(mini_trip(4, cap=1.0, soc0=1.0, smin_stop=0.5, smin_dest=0.0), [50])
    assert not plan2.feasible and "nicht erreichbar" in plan2.note
    # Eine Zelle, die allein mehr als die ganze Batterie braucht (Steigung 10 % bei 1000 kg: 1,5 + 0,6 kWh über 2 kWh Kapazität)
    plan3 = A.solve(mini_trip(4, grade=0.1, aux=6.0, cap=2.0, soc0=2.0, smin_stop=0.1, smin_dest=0.0, mass=1000.0), [50])
    assert not plan3.feasible


def test_best_constant_picks_the_smallest_value_and_reports_unreachable(flat_curve):
    # Bei nur aux wird mit höherer Geschwindigkeit weniger Energie je Zelle gebraucht (aux · dx / v): die schnellste ist beste und billigste
    plan = A.best_constant(mini_trip(4, soc0=10.0), [40, 50, 100])
    assert plan.feasible and plan.method == "const_best" and plan.v.tolist() == [100.0] * 4 and plan.time_h == pytest.approx(0.2)
    bad = A.best_constant(mini_trip(3, smin_dest=11.0), [50, 100])
    assert not bad.feasible and bad.note


def test_plan_without_cells_has_nan_mean_speed():
    p = A.Plan("opt", False)
    assert math.isnan(p.mean_speed) and math.isnan(p.time_min) and p.stops == [] and p.trace == [] and math.isnan(p.soc_end)


# ------------------------------------------------------------------ Verlauf (trace), Zeitsumme, Mindestladestände
def test_trace_starts_at_the_initial_soc_and_ends_at_the_final_soc(flat_curve):
    trip = mini_trip(6, soc0=2.5, smin_stop=1.0, smin_dest=0.5, stop_h=0.1)
    plan = A.solve(trip, [50])
    tr = plan.trace
    assert tr[0] == (0.0, 2.5) and tr[-1][0] == pytest.approx(30.0) and tr[-1][1] == pytest.approx(plan.soc_end)
    assert len(tr) == 6 + 1 + 2 * len(plan.stops)               # Zellgrenzen plus zwei Einträge je Stopp (vor und nach dem Laden)
    kms = [k for k, _ in tr]
    assert kms == sorted(kms)
    st = plan.stops[0]
    at = [s for k, s in tr if k == st.km]
    assert len(at) == 3 and at[-2] == pytest.approx(0.1 * st.soc_from) and at[-1] == pytest.approx(0.1 * st.soc_to)     # Ende der Vorzelle, vor dem Laden, nach dem Laden
    # Zwischen zwei Zellgrenzen ohne Stopp sinkt der Ladestand um 0,63
    soc_by_km = {}
    for k, s in tr:
        soc_by_km.setdefault(k, []).append(s)
    for k in (15.0, 20.0, 25.0):
        assert soc_by_km[k + 5.0][-1] == pytest.approx(soc_by_km[k][-1] - 0.63)


def test_time_is_the_sum_of_driving_charging_and_fixed_time_in_every_plan():
    for name in ("Standard", "Möglichst sparsam", "Gegenwind", "Langsamer Lader"):
        trip, plans = preset_run(name)
        for plan in plans.values():
            if not plan.feasible:
                continue
            assert plan.time_h == pytest.approx(plan.drive_h + plan.charge_h + plan.fix_h, rel=1e-12)
            assert plan.fix_h == pytest.approx(len(plan.stops) * trip.stop_h)
            assert plan.drive_h == pytest.approx(sum(C.DX_KM / v for v in plan.v))
            assert plan.charge_h == pytest.approx(sum(s.charge_min for s in plan.stops) / 60.0, rel=1e-9)
            assert plan.charged_kwh == pytest.approx(sum((s.soc_to - s.soc_from) * trip.vehicle.cap / 100.0 for s in plan.stops), rel=1e-9, abs=1e-9)
            assert plan.trace[0] == (0.0, trip.soc0) and plan.trace[-1][1] == pytest.approx(plan.soc_end)
            assert plan.trace[-1][0] == pytest.approx(trip.route.length)
            assert plan.energy.tolist() == pytest.approx([P.cell_energy(trip.vehicle, plan.v[i], trip.route.grade[i], trip.route.wind[i]) for i in range(trip.route.n)])


def test_minimum_state_of_charge_holds_at_every_stop_and_at_the_destination_in_every_plan():
    for name in C.PRESET_ORDER:
        trip, plans = preset_run(name)
        for key, plan in plans.items():
            if not plan.feasible:
                continue
            chk = A.check_plan(trip, plan)
            assert chk["ok"] and chk["soc_end"] >= trip.smin_dest - 1e-6 and chk["min_soc"] >= -1e-6, (name, key)
            assert chk["min_stop_arrival"] >= trip.smin_stop - 1e-6, (name, key)
            for st in plan.stops:
                if st.km > 0:
                    assert st.soc_from >= 100.0 * trip.smin_stop / trip.vehicle.cap - 1e-6
                assert 0.0 <= st.soc_from < st.soc_to <= 100.0 + 1e-9


# ------------------------------------------------------------------ Eigenschaften der Verfahren
@pytest.mark.parametrize("name", C.PRESET_ORDER)
def test_optimum_is_not_costlier_than_the_best_constant_which_is_not_costlier_than_any_single_speed(name):
    trip, plans = preset_run(name)
    opt, best = plans["opt"], plans["const_best"]
    assert opt.feasible and best.feasible
    assert A.plan_cost(trip, opt) <= A.plan_cost(trip, best) * 1.003
    for v, p in single_speed_plans(name).items():
        if p.feasible:
            assert A.plan_cost(trip, best) <= A.plan_cost(trip, p) * 1.003, (name, v)
    assert len(set(best.v.tolist())) == 1                         # konstant: eine Geschwindigkeit für alle Zellen
    assert A.plan_cost(trip, best) <= A.plan_cost(trip, plans["const_max"]) * 1.003


@pytest.mark.parametrize("name", C.PRESET_ORDER)
def test_dp_value_is_close_to_the_replay_cost(name):
    trip, plans = preset_run(name)
    for key in ("opt", "const_best", "const_max"):
        p = plans[key]
        assert abs(p.value - A.plan_cost(trip, p)) <= 0.005 * A.plan_cost(trip, p), (name, key)


def test_dp_value_is_close_to_the_replay_cost_with_a_large_battery():
    # Regression: Mit 500 Stufen bei 600 kWh (1,2 kWh je Stufe) legte die Nachfahrt einen Zusatzstopp ein (Wert 2,6176 h gegen Zeit 2,6978 h, 3,1 %);
    # die Stufenweite ist deshalb auf DS_MAX begrenzt. Geprüft für die reine Reisezeit und für einen Zeitwert von 20 €/h.
    for tv in (C.TV_FAST, 20):
        s = {**C.BASE_SCENARIO, **C.vehicle_scenario("Elektro-Lkw"), "length": 150, "profile": "flach", "seed": 3871, "headwind": 0, "soc0": 30, "vmax": 180, "peak": 250.0,
             "stop_min": 5.0, "rise": 500, "tv": tv}
        trip = S.make_trip(s)
        plan = A.best_constant(trip, S.speed_grid(trip.vmax))
        assert plan.feasible and abs(plan.value - A.plan_cost(trip, plan)) <= 0.005 * A.plan_cost(trip, plan), tv


def test_regeneration_helps_a_downhill_track_needs_no_stop_where_the_flat_one_does():
    # Pkw, 100 km (20 Zellen), 100 km/h eben: 0,78574 kWh je Zelle (siehe Orakel-Test), 15,7 kWh; Start 10 kWh, Mindestladestand 7,7 kWh am Ziel: eben ist ein Stopp nötig.
    # Bei 3 % Gefälle ist die Hangabtriebskraft (588 N) größer als Rollen + Luft (483 N): das Fahrzeug rekuperiert, kein Stopp, die Batterie wird nicht leerer.
    kw = dict(cap=77.0, mass=2000.0, cda=0.62, cr=0.01, peak=150.0, aux=0.8, curve="Standard", soc0=10.0, smin_stop=7.7, smin_dest=7.7, stop_h=5 / 60, vmax=100, loss=10.0)
    flat = A.solve(mini_trip(20, **kw), [100])
    down = A.solve(mini_trip(20, grade=-0.03, **kw), [100])
    assert flat.feasible and len(flat.stops) >= 1
    assert down.feasible and down.stops == [] and down.time_h == pytest.approx(1.0)
    assert down.time_h < flat.time_h
    assert float(np.sum(down.energy)) < 0.0 < float(np.sum(flat.energy))
    assert down.soc_end > 10.0 - 1e-9                                   # rekuperiert: Ladestand höher als am Start


def test_regeneration_is_lost_above_the_capacity(flat_curve):
    # Volle Batterie (10 kWh), Gefälle: der Ladestand wird auf die Kapazität begrenzt (nicht 10 + Rückgewinn)
    trip = mini_trip(2, grade=-0.1, aux=6.0, mass=1000.0, soc0=10.0)
    plan = A.solve(trip, [50])
    assert plan.feasible and plan.soc_end == pytest.approx(10.0) and plan.trace[1][1] == pytest.approx(10.0)


def test_regeneration_above_the_capacity_is_not_credited_in_the_cost(flat_curve):
    # Gefälle 10 % bei 1000 kg: −0,28123 kWh je Zelle bei 50 km/h (0,1 h je Zelle). Volle Batterie: nichts passt hinein, es wird nichts entnommen und nichts gutgeschrieben.
    full = mini_trip(2, grade=-0.1, aux=6.0, mass=1000.0, soc0=10.0, w_time=20.0, w_energy=1.0)
    plan = A.solve(full, [50])
    assert plan.used_kwh == pytest.approx(0.0, abs=1e-12) and plan.value == pytest.approx(20.0 * 0.2, abs=1e-9) and A.plan_cost(full, plan) == pytest.approx(4.0, abs=1e-9)
    # 0,1 kWh Platz: die erste Zelle nimmt nur 0,1 auf (Gutschrift 0,1 · 1 €/kWh), die zweite nichts mehr
    part = mini_trip(2, grade=-0.1, aux=6.0, mass=1000.0, soc0=9.9, w_time=20.0, w_energy=1.0)
    plan = A.solve(part, [50])
    assert plan.used_kwh == pytest.approx(-0.1) and plan.value == pytest.approx(4.0 - 0.1, abs=1e-6) and A.plan_cost(part, plan) == pytest.approx(3.9, abs=1e-6)
    assert A.check_plan(part, plan)["used_kwh"] == pytest.approx(-0.1) and A.check_plan(part, plan)["cost"] == pytest.approx(3.9, abs=1e-6)


def test_weights_scale_the_value_and_move_the_optimum_between_time_and_energy(flat_curve):
    # nur aux: je Zelle 6,3 · 5 / v kWh und 5 / v h. Zeit allein: schnell; Energie allein (kleiner Zeitwert): ebenfalls schnell, weil aux · dx / v mit v fällt;
    # mit Roll- und Luftwiderstand gibt es dazwischen einen Zielkonflikt: hier ein Fahrzeug mit Luftwiderstand, ebene Strecke, ohne Laden
    kw = dict(cap=80.0, soc0=80.0, smin_stop=0.0, smin_dest=0.0, aux=0.8, mass=2000.0, cda=0.62, cr=0.01)
    speeds = [60, 80, 100, 120, 140]
    fast = A.solve(mini_trip(10, w_time=1.0, w_energy=0.0, **kw), speeds)
    cheap = A.solve(mini_trip(10, w_time=1.0, w_energy=100.0, **kw), speeds)
    mid = A.solve(mini_trip(10, w_time=20.0, w_energy=0.55, **kw), speeds)
    assert fast.v.tolist() == [140.0] * 10 and cheap.v.tolist() == [60.0] * 10 and 60.0 < mid.v.mean() < 140.0
    assert fast.time_h < mid.time_h < cheap.time_h and fast.used_kwh > mid.used_kwh > cheap.used_kwh
    # Skalierung: doppelte Gewichte, doppelter Wert, gleicher Plan
    twice = A.solve(mini_trip(10, w_time=40.0, w_energy=1.1, **kw), speeds)
    assert twice.v.tolist() == mid.v.tolist() and twice.value == pytest.approx(2 * mid.value, rel=1e-9)


def _base(**kw):
    """Fahrt über 450 km mit der reinen Reisezeit als Zielfunktion („Zeit allein“), wenn kein Zeitwert genannt ist."""
    return S.make_trip({**C.BASE_SCENARIO, "length": 450, "tv": C.TV_FAST, **kw})


@pytest.mark.parametrize("key,values", [("peak", [30.0, 50.0, 100.0, 150.0, 250.0])])
def test_more_charging_power_is_never_slower(key, values):
    times = [A.solve(_base(**{key: v}), S.speed_grid(130)).value for v in values]
    assert all(b <= a * 1.003 for a, b in zip(times, times[1:]))
    assert times[0] > times[-1] * 1.01                                 # der Einfluss ist hier tatsächlich sichtbar


def test_more_fixed_time_per_stop_is_never_faster():
    times = [A.solve(_base(stop_min=m, peak=50.0), S.speed_grid(130)).value for m in (1.0, 5.0, 15.0, 30.0)]
    assert all(b >= a * (1 - 0.003) for a, b in zip(times, times[1:]))
    assert times[-1] > times[0] * 1.02


def test_stronger_headwind_is_never_faster():
    times = [A.solve(_base(headwind=w, vmax=130), S.speed_grid(130)).value for w in (-20, 0, 15, 30, 40)]
    assert all(b >= a * (1 - 0.003) for a, b in zip(times, times[1:]))
    assert times[-1] > times[0] * 1.02


def test_more_speed_choices_are_never_slower_for_the_same_trip():
    trip = _base(vmax=130, stop_min=10.0, peak=50.0)
    few = A.solve(trip, [130]).value
    more = A.solve(trip, S.speed_grid(130)).value
    assert more <= few * 1.001


# ------------------------------------------------------------------ check_plan
def _manual_plan(v, stops=()):
    p = A.Plan("opt", True)
    p.v = np.array(v, dtype=float)
    p.stops = list(stops)
    return p


def test_check_plan_by_hand_on_a_mini_route(flat_curve):
    trip = mini_trip(6, soc0=2.5, smin_stop=1.0, smin_dest=0.5, stop_h=0.1)
    # Stopp vor Zelle 1 (km 5): Ankunft 2,5 − 0,63 = 1,87 ≥ 1,0, Ladeziel 4,0 (40 %); danach 5 Zellen: 4,0 − 3,15 = 0,85 ≥ 0,5.
    # Zeit: 0,6 h Fahren + 0,1 h Fixzeit + (4,0 − 1,87) / 60 = 0,0355 h Laden = 0,7355 h
    good = _manual_plan([50] * 6, [A.Stop(5.0, 18.7, 40.0, 0.0, 0.0)])
    chk = A.check_plan(trip, good)
    assert chk["ok"] and chk["time_h"] == pytest.approx(0.7355) and chk["soc_end"] == pytest.approx(0.85)
    assert chk["min_stop_arrival"] == pytest.approx(1.87) and chk["min_soc"] == pytest.approx(0.85)
    # Stopp am Start (km 0) zählt nicht als Ankunftsstopp: Laden von 2,5 auf 4,3 (1,8 kWh = 0,03 h), 4,3 − 3,78 = 0,52 ≥ 0,5
    start = _manual_plan([50] * 6, [A.Stop(0.0, 25.0, 43.0, 0.0, 0.0)])
    chk0 = A.check_plan(trip, start)
    assert chk0["ok"] and chk0["min_stop_arrival"] == math.inf and chk0["time_h"] == pytest.approx(0.6 + 0.1 + 0.03) and chk0["soc_end"] == pytest.approx(0.52)


def test_check_plan_rejects_a_plan_that_runs_below_zero(flat_curve):
    trip = mini_trip(6, soc0=2.5, smin_stop=1.0, smin_dest=0.5, stop_h=0.1)
    chk = A.check_plan(trip, _manual_plan([50] * 6))              # ohne Stopp: 2,5 − 3,78 = −1,28
    assert not chk["ok"] and chk["min_soc"] == pytest.approx(-1.28) and chk["soc_end"] == pytest.approx(-1.28) and chk["time_h"] == pytest.approx(0.6)


def test_check_plan_rejects_arrival_at_a_stop_below_the_minimum(flat_curve):
    trip = mini_trip(6, soc0=2.5, smin_stop=1.0, smin_dest=0.5, stop_h=0.1)
    # Stopp vor Zelle 3 (km 15): Ankunft 2,5 − 1,89 = 0,61 < 1,0, danach auf 4,0 laden: Ende 4,0 − 1,89 = 2,11 (Ziel ist in Ordnung, nur der Stopp verletzt)
    chk = A.check_plan(trip, _manual_plan([50] * 6, [A.Stop(15.0, 6.1, 40.0, 0.0, 0.0)]))
    assert not chk["ok"] and chk["min_stop_arrival"] == pytest.approx(0.61) and chk["soc_end"] == pytest.approx(2.11) and chk["min_soc"] >= 0.0
    assert chk["time_h"] == pytest.approx(0.6 + 0.1 + (4.0 - 0.61) / 60)


def test_check_plan_rejects_a_plan_that_misses_the_destination_minimum(flat_curve):
    trip = mini_trip(6, soc0=2.5, smin_stop=1.0, smin_dest=0.5, stop_h=0.1)
    chk = A.check_plan(trip, _manual_plan([50] * 6, [A.Stop(5.0, 18.7, 38.0, 0.0, 0.0)]))      # 3,8 − 3,15 = 0,65 ≥ 0,5 ist in Ordnung
    assert chk["ok"] and chk["soc_end"] == pytest.approx(0.65)
    chk2 = A.check_plan(trip, _manual_plan([50] * 6, [A.Stop(5.0, 18.7, 33.0, 0.0, 0.0)]))      # 3,3 − 3,15 = 0,15 < 0,5
    assert not chk2["ok"] and chk2["soc_end"] == pytest.approx(0.15) and chk2["min_soc"] == pytest.approx(0.15)


def test_check_plan_uses_the_plan_speed_per_cell_and_caps_at_the_capacity(flat_curve):
    trip = mini_trip(2, grade=[-0.1, 0.0], aux=6.0, mass=1000.0, soc0=9.9, smin_stop=1.0, smin_dest=0.0)
    # Zelle 0 mit Gefälle bei 50 km/h: −0,28123 kWh → 9,9 + 0,28123 = 10,18 → auf 10 begrenzt; Zelle 1 eben bei 100 km/h: 0,3 kWh: Ende 9,7; Zeit 0,1 + 0,05 = 0,15 h
    chk = A.check_plan(trip, _manual_plan([50, 100]))
    assert chk["soc_end"] == pytest.approx(9.7) and chk["time_h"] == pytest.approx(0.15) and chk["ok"]


@pytest.mark.parametrize("name", C.PRESET_ORDER)
def test_check_plan_time_equals_the_plan_time(name):
    trip, plans = preset_run(name)
    for plan in plans.values():
        if plan.feasible:
            assert A.check_plan(trip, plan)["time_h"] == pytest.approx(plan.time_h, rel=1e-9)


# ------------------------------------------------------------------ Hilfseinheit des Szenarios: Näherung der Normalverteilung (Mittelgebirge-Profil)
def test_normal_approximation_is_centred_with_the_requested_spread_and_clipped():
    """Irwin-Hall: Summe von zwölf Gleichverteilten (je 0 bis 999) minus 6000, geteilt durch 1000, hat Mittelwert 0 und Standardabweichung 1 (12 · (1/12) = 1).
    4000 Ziehungen mit festem Startwert: Mittelwert des Ergebnisses innerhalb ±2,5 (Standardfehler 0,4), Standardabweichung 22 bis 28, nie jenseits der Beschneidung ±50."""
    rng = SplitMix64(12345)
    xs = np.array([S._normal(rng, 25.0, 50.0) for _ in range(4000)])
    assert abs(xs.mean()) < 2.5 and 22.0 < xs.std() < 28.0 and xs.min() >= -50.0 and xs.max() <= 50.0
    assert xs.min() < -40.0 and xs.max() > 40.0                               # die Ausläufer werden erreicht (beschnitten bei ±50 = ±2 Standardabweichungen)


def test_grid_step_is_capped_for_large_batteries():
    grid, ds = A.make_grid(600.0)
    assert ds <= C.DS_MAX + 1e-12 and grid[-1] == pytest.approx(600.0) and len(grid) == 2401
    grid, ds = A.make_grid(77.0)
    assert len(grid) == C.N_SOC + 1 and ds == pytest.approx(77.0 / 500)
