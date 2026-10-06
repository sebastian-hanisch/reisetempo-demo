"""Die vier Verfahren und die Praxisregel: Einheiten an ebenen Mini-Strecken mit von Hand gerechneten Erwartungen, dann die Reihenfolge der Verfahren auf den Presets.

Mini-Strecken (tests/helpers_core.py): ohne Roll- und Luftwiderstand kostet eine ebene Zelle zu 5 km bei 50 km/h und aux = 6,3 kW genau 6,3 · 0,1 = 0,63 kWh und 0,1 h; Ladeleistung 60 kW
konstant, Kapazität 10 kWh, Fixzeit 0,1 h je Stopp, Mindestladestand am Stopp und am Ziel je 1,0 kWh. Die Praxisregel lädt bis höchstens 80 % (8,0 kWh)."""
import math

import numpy as np
import pytest

import rtp_algorithm as A
import rtp_constants as C
import rtp_scenario as S
import rtp_strategies as ST
from helpers_core import flat_curve, mini_trip, preset_run  # noqa: F401  (flat_curve ist eine Fixture)


# ------------------------------------------------------------------ simulate_ahead
def test_simulate_ahead_returns_the_lowest_state_and_the_final_state():
    E = np.array([0.6, 0.6, 0.6, 0.6])
    # ab Zelle 1 mit 3,0: 2,4, 1,8, 1,2 → kleinster Stand 1,2, Endstand 1,2
    low, end = ST.simulate_ahead(E, 10.0, 3.0, 1)
    assert low == pytest.approx(1.2) and end == pytest.approx(1.2)
    low, end = ST.simulate_ahead(E, 10.0, 1.0, 0)                  # 1,0 → 0,4 → −0,2 → −0,8 → −1,4: kleinster Stand −1,4
    assert low == pytest.approx(-1.4) and end == pytest.approx(-1.4)
    assert ST.simulate_ahead(E, 10.0, 3.0, 4) == (3.0, 3.0)         # keine Zelle mehr: Start = Ziel
    assert ST.simulate_ahead(E, 10.0, 3.0, 3) == (pytest.approx(2.4), pytest.approx(2.4))


def test_simulate_ahead_loses_regeneration_above_the_capacity_and_reports_the_minimum_before_the_end():
    # E = [1, −3, 1], Kapazität 3, Start 2: 2 − 1 = 1 (Minimum 1); 1 + 3 = 4 → auf 3 begrenzt; 3 − 1 = 2: Ende 2 (ohne Begrenzung wäre es 3)
    low, end = ST.simulate_ahead(np.array([1.0, -3.0, 1.0]), 3.0, 2.0, 0)
    assert low == pytest.approx(1.0) and end == pytest.approx(2.0)
    # Start oberhalb der ersten Rekuperation: E = [−2, 0,5], Kapazität 10, Start 9: 11 → 10; 9,5: Minimum ist der Start 9
    low, end = ST.simulate_ahead(np.array([-2.0, 0.5]), 10.0, 9.0, 0)
    assert low == pytest.approx(9.0) and end == pytest.approx(9.5)


# ------------------------------------------------------------------ needed_soc
def test_needed_soc_on_a_flat_track_is_the_destination_minimum_plus_the_remaining_energy():
    E = np.full(10, 0.6)
    assert ST.needed_soc(E, 10.0, 4, 1.0) == pytest.approx(1.0 + 6 * 0.6, abs=1e-9)           # 6 Zellen übrig: 4,6 kWh
    assert ST.needed_soc(E, 10.0, 0, 1.0) == pytest.approx(7.0, abs=1e-9)
    assert ST.needed_soc(E, 10.0, 10, 1.0) == pytest.approx(1.0, abs=1e-9)                    # kein Weg mehr: nur der Mindestladestand am Ziel
    assert ST.needed_soc(E, 10.0, 4, 0.0) == pytest.approx(3.6, abs=1e-9)                     # ohne Mindestladestand am Ziel: Stand darf bis null fallen
    assert ST.needed_soc(np.full(10, 0.5), 10.0, 0, 1.0) == pytest.approx(6.0, abs=1e-9)


def test_needed_soc_is_infinite_if_even_a_full_battery_does_not_reach_the_destination():
    assert ST.needed_soc(np.full(10, 0.6), 3.0, 0, 1.0) == math.inf          # 6 + 1 = 7 > 3
    assert ST.needed_soc(np.full(10, 0.6), 10.0, 0, 5.0) == math.inf         # 6 + 5 = 11 > 10
    assert ST.needed_soc(np.array([5.0, 5.0]), 6.0, 0, 0.0) == math.inf     # die erste Zelle ginge, die zweite nicht (nach 1 bleibt 1 < 5)


def test_needed_soc_with_regeneration_and_the_minimum_along_the_way():
    # E = [−1, 2] bei Kapazität 5: Stand s + 1, dann − 2: s − 1 ≥ 0 → s ≥ 1; mit Mindestladestand am Ziel 0,5 ist es 1,5
    assert ST.needed_soc(np.array([-1.0, 2.0]), 5.0, 0, 0.0) == pytest.approx(1.0, abs=1e-9)
    assert ST.needed_soc(np.array([-1.0, 2.0]), 5.0, 0, 0.5) == pytest.approx(1.5, abs=1e-9)
    # E = [3, −3, 1]: der Stand darf unterwegs nicht unter null: s − 3 ≥ 0 → s ≥ 3 (Ziel 0), auch wenn das Ende höher läge
    assert ST.needed_soc(np.array([3.0, -3.0, 1.0]), 8.0, 0, 0.0) == pytest.approx(3.0, abs=1e-9)
    # mit Ziel-Mindeststand 2 wirkt der Endstand: s − 3 + 3 − 1 ≥ 2 → s ≥ 3, und das Minimum s − 3 ≥ 0 → ebenfalls 3
    assert ST.needed_soc(np.array([3.0, -3.0, 1.0]), 8.0, 0, 2.0) == pytest.approx(3.0, abs=1e-9)
    # Rekuperation über der Kapazität geht verloren: E = [−4, 3], Kapazität 5, Ziel 0: Start s: min(s + 4, 5) − 3 ≥ 0 gilt immer, also 0
    assert ST.needed_soc(np.array([-4.0, 3.0]), 5.0, 0, 0.0) == pytest.approx(0.0, abs=1e-9)
    # mit Ziel-Mindeststand 2: ab Start 1 wird auf 5 begrenzt (5 − 3 = 2), darunter gilt s + 4 − 3 ≥ 2 → s ≥ 1
    assert ST.needed_soc(np.array([-4.0, 3.0]), 5.0, 0, 2.0) == pytest.approx(1.0, abs=1e-9)


# ------------------------------------------------------------------ rule_plan auf ebener Mini-Strecke
def _stops(plan):
    return [(st.km, st.soc_from, st.soc_to) for st in plan.stops]


def test_rule_plan_charges_only_as_much_as_needed_at_the_last_stop(flat_curve):
    # 20 Zellen (100 km), Start 10 kWh voll. Nach k Zellen 10 − 0,63 k; Stopp, sobald die nächste Zelle unter 1,0 drücken würde: 10 − 0,63 (i + 1) < 1 → i ≥ 14 (Stand 1,18 bei km 70).
    # Rest 6 Zellen: 6 · 0,63 + 1,0 = 4,78 kWh < 8,0 (Ladeziel 80 %): geladen wird nur auf 4,78 (47,8 %). Ladezeit (4,78 − 1,18) / 60 = 0,06 h, Fixzeit 0,1 h, Fahren 2,0 h: 2,16 h.
    plan = ST.rule_plan(mini_trip(20), 50.0)
    assert plan.feasible and plan.method == "rule" and len(plan.stops) == 1
    km, a, b = _stops(plan)[0]
    assert km == 70.0 and a == pytest.approx(11.8) and b == pytest.approx(47.8, abs=1e-6)
    assert plan.stops[0].charge_min == pytest.approx(3.6, abs=1e-6) and plan.stops[0].total_min == pytest.approx(3.6 + 6.0, abs=1e-6)
    assert plan.time_h == pytest.approx(2.16, abs=1e-6) and plan.drive_h == pytest.approx(2.0) and plan.fix_h == pytest.approx(0.1) and plan.charge_h == pytest.approx(0.06, abs=1e-8)
    assert plan.soc_end == pytest.approx(1.0, abs=1e-6) and plan.charged_kwh == pytest.approx(3.6, abs=1e-6)
    assert plan.v.tolist() == [50.0] * 20 and plan.energy.tolist() == pytest.approx([0.63] * 20)
    assert plan.trace[0] == (0.0, 10.0) and plan.trace[-1][0] == pytest.approx(100.0) and len(plan.trace) == 20 + 1 + 2


def test_rule_plan_charges_to_80_percent_except_at_the_last_stop(flat_curve):
    # 40 Zellen (200 km): Stopp 1 bei i = 14 (km 70, Stand 1,18): Rest 26 Zellen brauchen 17,38 > 8 → Ladeziel 8,0 (80 %), Ladezeit 6,82 / 60.
    # Danach 8,0 − 0,63 (m + 1) < 1 → m = 11: Stopp 2 bei i = 25 (km 125, Stand 1,07): Rest 15 Zellen brauchen 10,45 > 8 → wieder 8,0, Ladezeit 6,93 / 60.
    # Stopp 3 bei i = 36 (km 180, Stand 1,07): Rest 4 Zellen brauchen 3,52 < 8 → nur auf 3,52 (35,2 %), Ladezeit 2,45 / 60.
    # Zeit: 4,0 h Fahren + 3 · 0,1 h + (6,82 + 6,93 + 2,45) / 60 = 4,0 + 0,3 + 0,27 = 4,57 h
    plan = ST.rule_plan(mini_trip(40), 50.0)
    assert plan.feasible and len(plan.stops) == 3
    s = _stops(plan)
    assert [x[0] for x in s] == [70.0, 125.0, 180.0]
    assert [x[1] for x in s] == pytest.approx([11.8, 10.7, 10.7])
    assert [x[2] for x in s] == pytest.approx([80.0, 80.0, 35.2], abs=1e-6)
    assert [st.charge_min for st in plan.stops] == pytest.approx([6.82, 6.93, 2.45], abs=1e-6)
    assert plan.time_h == pytest.approx(4.57, abs=1e-6) and plan.charged_kwh == pytest.approx(6.82 + 6.93 + 2.45, abs=1e-6)


def test_rule_plan_charges_at_the_start_if_the_start_is_below_the_minimum(flat_curve):
    # Start 0,5 kWh < Mindestladestand 1,0: die erste Zelle würde unter 1,0 drücken: Stopp bei km 0, Rest braucht mehr als die Kapazität → Ladeziel 8,0 (7,5 kWh in 7,5 / 60 h)
    plan = ST.rule_plan(mini_trip(40, soc0=0.5), 50.0)
    assert plan.feasible
    s = _stops(plan)
    assert s[0][0] == 0.0 and s[0][1] == pytest.approx(5.0) and s[0][2] == pytest.approx(80.0)
    assert plan.stops[0].charge_min == pytest.approx(7.5)
    # weitere Stopps nach 11 Zellen bei Stand 1,07: km 55 und 110, dann 165 mit Ziel 5,41 (54,1 %); Zeit 4,0 + 4 · 0,1 + (7,5 + 6,93 + 6,93 + 4,34) / 60 = 4,82833 h
    assert [x[0] for x in s] == [0.0, 55.0, 110.0, 165.0]
    assert s[3][2] == pytest.approx(54.1, abs=1e-6)
    assert plan.time_h == pytest.approx(4.82833, abs=1e-4)


def test_rule_plan_without_a_necessary_stop_has_no_stop(flat_curve):
    plan = ST.rule_plan(mini_trip(10, soc0=10.0), 50.0)           # 10 · 0,63 = 6,3: Ende 3,7 ≥ 1,0
    assert plan.feasible and plan.stops == [] and plan.time_h == pytest.approx(1.0) and plan.soc_end == pytest.approx(3.7)


def test_rule_plan_does_not_stop_when_the_destination_is_reachable_even_below_the_stop_minimum(flat_curve):
    # 10 Zellen: 6,3 kWh; Start 7,5: Ende 1,2 ≥ 1,0. Der Stand fällt auf dem Weg unter den Stopp-Mindeststand 2,0 (bei i = 8: 2,46 − 0,63 = 1,83 < 2,0),
    # aber das Ziel ist ohne Stopp erreichbar: kein Stopp.
    plan = ST.rule_plan(mini_trip(10, soc0=7.5, smin_stop=2.0), 50.0)
    assert plan.feasible and plan.stops == [] and plan.soc_end == pytest.approx(1.2)


def test_rule_plan_stop_condition_boundaries_with_exact_halves(flat_curve):
    # aux = 5 kW → 0,5 kWh je Zelle, alle Ladestände sind exakte Vielfache von 0,5. 20 Zellen, Start 10, Mindestladestand 1,0.
    # i = 17: Stand 1,5, nach der Zelle genau 1,0 = Mindestladestand: noch kein Stopp. i = 18: Stand 1,0 → 0,5 < 1,0: Stopp bei km 90, Rest 2 Zellen brauchen 1,0 + 1,0 = 2,0 kWh,
    # Ladeziel 2,0 (20 %), 1,0 kWh in 1/60 h; Zeit 2,0 + 0,1 + 1/60 = 2,116667 h.
    plan = ST.rule_plan(mini_trip(20, aux=5.0), 50.0)
    assert plan.feasible and len(plan.stops) == 1
    km, a, b = _stops(plan)[0]
    assert km == 90.0 and a == pytest.approx(10.0) and b == pytest.approx(20.0, abs=1e-6)
    assert plan.time_h == pytest.approx(2.0 + 0.1 + 1.0 / 60, abs=1e-6)


def test_rule_plan_finish_check_boundary_with_exact_halves(flat_curve):
    # 10 Zellen zu 0,5 kWh, Start 6,0, Mindestladestand am Ziel 1,0: Ende genau 1,0 = Mindestladestand: erreichbar, kein Stopp, obwohl der Stand unterwegs unter den Stopp-Mindeststand 2,0 fällt
    plan = ST.rule_plan(mini_trip(10, aux=5.0, soc0=6.0, smin_stop=2.0), 50.0)
    assert plan.feasible and plan.stops == [] and plan.soc_end == pytest.approx(1.0)
    # Start 5,5: Ende 0,5 < 1,0: Stopp nötig (Stopp bei i = 7: Stand 2,0 → nach der Zelle 1,5 < 2,0), Ladeziel = Bedarf 1,0 + 3 · 0,5 = 2,5
    plan2 = ST.rule_plan(mini_trip(10, aux=5.0, soc0=5.5, smin_stop=2.0), 50.0)
    assert plan2.feasible and len(plan2.stops) == 1 and plan2.stops[0].km == 35.0 and plan2.stops[0].soc_to == pytest.approx(25.0, abs=1e-6)


def test_rule_plan_is_infeasible_if_the_charging_target_does_not_reach_the_destination(flat_curve):
    # 95 kW aux → 9,5 kWh je Zelle bei Kapazität 10: schon die erste Zelle drückt unter den Mindeststand; der Bedarf übersteigt die Kapazität (unendlich), das Ladeziel 8,0 liegt unter dem Start 10:
    plan = ST.rule_plan(mini_trip(4, aux=95.0), 50.0)
    assert not plan.feasible and "80 %" in plan.note and "Praxisregel" in plan.note and math.isnan(plan.time_h) and plan.stops == []


def test_rule_plan_is_infeasible_if_it_ends_below_the_destination_minimum(flat_curve):
    # 7,5 kWh je Zelle (aux 75 kW), 3 Zellen, Kapazität 10, Mindestladestand am Ziel 3,0. Zelle 0: 10 − 7,5 = 2,5 ≥ 1,0, kein Stopp. Zelle 1: 2,5 − 7,5 < 1,0: Stopp, der Bedarf (über 10) ist
    # unendlich, Ladeziel 8,0 > 2,5: laden auf 8,0, danach 0,5. Zelle 2: wieder Stopp (Ziel 8,0), danach 0,5 < 3,0 am Ziel: „erreicht das Ziel nicht“.
    plan = ST.rule_plan(mini_trip(3, aux=75.0, smin_dest=3.0), 50.0)
    assert not plan.feasible and plan.note == "Die Praxisregel erreicht das Ziel nicht."


def test_rule_plan_gives_up_after_too_many_stops(flat_curve, monkeypatch):
    trip = mini_trip(40)                      # braucht drei Stopps (siehe oben)
    monkeypatch.setattr(ST, "MAX_STOPS", 3)
    assert ST.rule_plan(trip, 50.0).feasible
    monkeypatch.setattr(ST, "MAX_STOPS", 2)
    plan = ST.rule_plan(trip, 50.0)
    assert not plan.feasible and "Zu viele Stopps" in plan.note


def test_rule_plan_uses_the_given_speed_for_time_and_energy(flat_curve):
    # bei 100 km/h: 6,3 · 0,05 = 0,315 kWh je Zelle, 0,05 h je Zelle; 10 Zellen: 3,15 kWh, 0,5 h
    plan = ST.rule_plan(mini_trip(10), 100.0)
    assert plan.v.tolist() == [100.0] * 10 and plan.energy.tolist() == pytest.approx([0.315] * 10) and plan.time_h == pytest.approx(0.5) and plan.soc_end == pytest.approx(10 - 3.15)
    assert plan.used_kwh == pytest.approx(3.15)


def test_rule_plan_counts_the_energy_taken_from_the_battery_including_stops(flat_curve):
    # 40 Zellen bei 50 km/h: 0,63 kWh je Zelle, 25,2 kWh; die entnommene Energie ist unabhängig von den Stopps (Energieerhaltung: Start + geladen − Ende)
    trip = mini_trip(40)
    plan = ST.rule_plan(trip, 50.0)
    assert plan.feasible and plan.stops and plan.used_kwh == pytest.approx(25.2)
    assert plan.used_kwh == pytest.approx(trip.soc0 + plan.charged_kwh - plan.soc_end)


def test_rule_plan_loses_regeneration_above_the_capacity_in_the_energy_count(flat_curve):
    # Gefälle 10 % bei 1000 kg: −0,28123 kWh je Zelle; Start voll (10 kWh): die Rekuperation passt nicht in die Batterie, es wird nichts entnommen
    trip = mini_trip(2, grade=-0.1, aux=6.0, mass=1000.0, soc0=10.0)
    plan = ST.rule_plan(trip, 50.0)
    assert plan.feasible and plan.used_kwh == pytest.approx(0.0, abs=1e-12) and plan.soc_end == pytest.approx(10.0)
    start_low = mini_trip(2, grade=-0.1, aux=6.0, mass=1000.0, soc0=9.9)                    # 0,1 kWh Platz: die erste Zelle nimmt 0,28123 auf, 0,1 passt hinein
    p2 = ST.rule_plan(start_low, 50.0)
    assert p2.used_kwh == pytest.approx(-0.1) and p2.soc_end == pytest.approx(10.0)


# ------------------------------------------------------------------ run_all
@pytest.mark.parametrize("name", C.PRESET_ORDER)
def test_run_all_returns_the_four_plans_in_the_documented_order(name):
    trip, plans = preset_run(name)
    assert list(plans) == ["rule", "const_max", "const_best", "opt"] and tuple(plans) == tuple(C.METHODS)
    top = S.speed_grid(trip.vmax)[-1]
    assert plans["rule"].v.tolist() == [float(top)] * trip.route.n and plans["const_max"].v.tolist() == [float(top)] * trip.route.n
    assert [plans[k].method for k in ("rule", "const_max", "const_best", "opt")] == ["rule", "const_max", "const_best", "opt"]
    assert all(p.feasible for p in plans.values())


@pytest.mark.parametrize("name", C.PRESET_ORDER)
def test_optimum_is_not_costlier_than_the_best_constant_which_is_not_costlier_than_the_speed_limit(name):
    trip, plans = preset_run(name)
    opt, best, top = (A.plan_cost(trip, plans[k]) for k in ("opt", "const_best", "const_max"))
    assert opt <= best * 1.003 and best <= top * 1.003


@pytest.mark.parametrize("name", C.PRESET_ORDER)
def test_the_practice_rule_is_never_cheaper_than_the_optimum_apart_from_rounding(name):
    trip, plans = preset_run(name)
    assert A.plan_cost(trip, plans["rule"]) >= A.plan_cost(trip, plans["opt"]) * (1 - 0.003)


def test_the_practice_rule_loses_clearly_with_a_slow_charger_and_headwind():
    for name in ("Langsamer Lader", "Gegenwind"):                                # Zeit allein: Reisezeit
        _, plans = preset_run(name)
        assert plans["rule"].time_h > 1.10 * plans["opt"].time_h                 # gemessen: rund 20 bis 25 %
    _, plans = preset_run("Elektro-Lkw")
    assert plans["rule"].time_h > plans["opt"].time_h                            # gemessen: rund 4 %
    trip, plans = preset_run("Ohne Tempolimit")                                  # 20 €/h: die Regel zahlt mit Energie
    assert A.plan_cost(trip, plans["rule"]) > 1.15 * A.plan_cost(trip, plans["opt"]) and plans["rule"].used_kwh > 1.5 * plans["opt"].used_kwh


def test_the_practice_rule_does_not_depend_on_the_time_value_and_the_other_methods_do():
    base = {**C.BASE_SCENARIO, "length": 300}
    plans = {tv: ST.run_all(S.make_trip({**base, "tv": tv})) for tv in (1, 10, C.TV_FAST)}
    for tv in (1, 10):
        a, b = plans[tv]["rule"], plans[C.TV_FAST]["rule"]
        assert a.v.tolist() == b.v.tolist() and a.time_h == b.time_h and a.used_kwh == b.used_kwh and [(s.km, s.soc_to) for s in a.stops] == [(s.km, s.soc_to) for s in b.stops]
    assert plans[1]["opt"].mean_speed < plans[10]["opt"].mean_speed < plans[C.TV_FAST]["opt"].mean_speed
    assert plans[1]["const_best"].mean_speed < plans[10]["const_best"].mean_speed < plans[C.TV_FAST]["const_best"].mean_speed


def test_the_optimum_trades_time_for_energy_along_the_time_values():
    base = {**C.BASE_SCENARIO, "length": 300}
    runs = [ST.run_all(S.make_trip({**base, "tv": tv}))["opt"] for tv in C.TV_OPTIONS]
    times, used = [p.time_h for p in runs], [p.used_kwh for p in runs]
    assert all(b <= a + 1e-9 for a, b in zip(times, times[1:])) and all(b >= a - 1e-9 for a, b in zip(used, used[1:]))        # mehr Zeitwert: schneller und mehr Energie
    assert times[0] > 1.5 * times[-1] and used[0] < 0.6 * used[-1]


def test_the_extremes_of_the_spectrum_are_the_minimum_speed_and_the_speed_limit():
    base = {**C.BASE_SCENARIO, "length": 300}
    eco = ST.run_all(S.make_trip({**base, "tv": min(C.TV_OPTIONS)}))["opt"]
    fast = ST.run_all(S.make_trip({**base, "tv": C.TV_FAST}))["opt"]
    assert eco.v.min() == C.V_MIN and eco.mean_speed < C.V_MIN + 5 and fast.v.max() == 130.0 and fast.mean_speed > 125.0


def test_run_all_with_a_tiny_battery_reports_unreachable_plans_with_notes():
    trip = S.make_trip({**C.BASE_SCENARIO, **C.vehicle_scenario("Elektro-Lkw"), "cap": 1.0, "length": 100})
    plans = ST.run_all(trip)
    assert set(plans) == set(C.METHODS)
    for p in plans.values():
        assert not p.feasible and p.note and math.isnan(p.time_h)


def test_run_all_best_constant_is_one_speed_of_the_list_and_the_stop_free_trip_has_equal_plans():
    trip, plans = preset_run("Elektro-Lkw", 450)             # 450 km mit 600 kWh: ohne Stopp, alle Verfahren fahren gleich schnell (90 km/h Tempolimit)
    assert all(len(p.stops) == 0 for p in plans.values())
    assert [p.time_h for p in plans.values()] == pytest.approx([5.0] * 4)
    assert plans["const_best"].v.tolist() == [90.0] * trip.route.n
