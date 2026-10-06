"""Szenario: Steigungsprofile, Strecke mit Höhe und Wind, Geschwindigkeitsraster und Umrechnung der Einstellungen in eine Fahrt."""
import dataclasses

import numpy as np
import pytest

import rtp_constants as C
import rtp_scenario as S


def runs_of(g):
    """Zerlegt ein Profil in Stücke gleicher Werte."""
    return np.split(g, np.nonzero(np.diff(g))[0] + 1)


# ------------------------------------------------------------------ Steigungsprofile
def test_unknown_profile_is_rejected():
    with pytest.raises(ValueError):
        S.make_grades("berg", 120, 1)


def test_profiles_are_deterministic_per_seed_and_differ_between_seeds_and_types():
    for typ in ("huegelig", "mittelgebirge", "pass"):
        a, b = S.make_grades(typ, 120, 3), S.make_grades(typ, 120, 3)
        assert np.array_equal(a, b) and not np.array_equal(a, S.make_grades(typ, 120, 4)), typ
    assert not np.array_equal(S.make_grades("huegelig", 120, 3), S.make_grades("mittelgebirge", 120, 3))
    assert all(len(S.make_grades(t, 77, 5)) == 77 for t in C.PROFILE_TYPES)


def test_flat_profile_is_all_zero_for_every_seed():
    for seed in range(5):
        assert np.abs(S.make_grades("flach", 120, seed)).max() < 1e-12


@pytest.mark.parametrize("typ", ["huegelig", "mittelgebirge"])
def test_hilly_profiles_have_zero_mean_height_difference(typ):
    for seed in range(30):
        g = S.make_grades(typ, 120, seed)
        assert abs(g.mean()) < 1e-9 and abs(g.sum() * 5.0) < 1e-6, seed              # Höhenunterschied Start bis Ziel null (Steigung in Promille mal 5 km)


def test_rolling_hills_use_integer_levels_within_plus_minus_20_in_pieces_of_three_to_eight_cells():
    for seed in range(30):
        g = S.make_grades("huegelig", 120, seed)
        d = g - g[0]
        assert np.abs(d - np.round(d)).max() < 1e-9 and d.max() - d.min() <= 40 + 1e-9     # Stufen sind ganzzahlige Promille; Spanne höchstens −20 bis 20
        assert all(len(r) >= 3 for r in runs_of(g)[:-1])                                     # gleiche Nachbarwerte können Stücke nur verlängern; nur das letzte darf kürzer sein


def test_mountain_profile_is_steeper_than_rolling_hills_and_bounded():
    spans = [np.ptp(S.make_grades("mittelgebirge", 120, s)) for s in range(30)]
    hills = [np.ptp(S.make_grades("huegelig", 120, s)) for s in range(30)]
    assert max(spans) <= 100 + 1e-9 and np.mean(spans) > np.mean(hills)                    # Werte auf ±50 Promille beschnitten (vor dem Zentrieren)
    assert all(len(r) >= 2 for s in range(30) for r in runs_of(S.make_grades("mittelgebirge", 120, s))[:-1])


@pytest.mark.parametrize("n", [20, 60, 120, 300])
def test_pass_has_one_climb_and_one_descent_of_equal_length_and_slope(n):
    for seed in range(60):
        g = S.make_grades("pass", n, seed)
        up, down = np.nonzero(g >= 40)[0], np.nonzero(g <= -40)[0]
        k = len(up)
        assert 2 <= k <= 10 and len(down) == k, (n, seed)                                    # gleiche Länge (6 bis 10 Zellen, bei kurzer Strecke weniger)
        assert up[-1] - up[0] + 1 == k and down[-1] - down[0] + 1 == k                       # je ein zusammenhängender Block
        assert down[0] >= up[-1] + 1                                                         # erst der Anstieg, dann der Abstieg
        assert 40 <= g[up[0]] <= 50 and bool(np.all(g[up] == g[up[0]])) and bool(np.all(g[down] == -g[up[0]]))
        assert float(g[up[0]]) == int(g[up[0]])
        rest = np.ones(n, dtype=bool)
        rest[up], rest[down] = False, False
        assert np.abs(g[rest]).max() <= 5 + 1e-9                                             # außerhalb Rauschen von höchstens ±5 Promille
        assert g[up].sum() + g[down].sum() == pytest.approx(0.0)                             # Anstieg und Abstieg heben sich auf


def test_pass_climb_is_about_40_km_long_for_the_standard_route():
    lengths = {int((S.make_grades("pass", 120, s) >= 40).sum()) * 5 for s in range(60)}
    assert min(lengths) >= 30 and max(lengths) <= 50 and len(lengths) > 3


def test_pass_works_on_the_shortest_slider_route():
    n = int(C.LENGTH_MIN / C.DX_KM)                                                           # 20 Zellen
    for seed in range(100):
        g = S.make_grades("pass", n, seed)
        assert (g >= 40).sum() == (g <= -40).sum() >= 2


# ------------------------------------------------------------------ Strecke
def test_route_cells_length_and_shapes():
    r = S.make_route(600.0, "huegelig", 7, 0.0, "konstant")
    assert r.n == 120 and r.length == 600.0 and len(r.grade) == len(r.wind) == 120 and len(r.height) == 121
    assert r.profile == "huegelig" and r.seed == 7 and r.height[0] == 0.0
    assert S.make_route(612.0, "flach", 1, 0.0, "konstant").length == 610.0                    # auf Zellen von 5 km gerundet


def test_route_that_is_too_short_or_with_unknown_wind_mode_is_rejected():
    with pytest.raises(ValueError):
        S.make_route(10.0, "flach", 1, 0.0, "konstant")
    with pytest.raises(ValueError):
        S.make_route(600.0, "flach", 1, 0.0, "böig")
    assert S.make_route(20.0, "flach", 1, 0.0, "konstant").n == 4


def test_route_grade_is_the_profile_in_promille_as_a_fraction():
    r = S.make_route(600.0, "huegelig", 7, 0.0, "konstant")
    assert r.grade == pytest.approx(S.make_grades("huegelig", 120, 7) / 1000.0, abs=1e-15)


def test_route_height_is_the_sum_of_grade_times_5_km():
    r = S.make_route(600.0, "mittelgebirge", 9, 0.0, "konstant")
    h = 0.0
    for i in range(r.n):
        assert r.height[i] == pytest.approx(h, abs=1e-6)
        h += r.grade[i] * 5000.0                                                              # Steigung (Anteil) mal Zellenlänge in Metern
    assert r.height[-1] == pytest.approx(h, abs=1e-6)
    assert abs(r.height[-1]) < 1e-6                                                           # Mittelgebirge: Höhenunterschied null


@pytest.mark.parametrize("profile", C.PROFILE_TYPES)
@pytest.mark.parametrize("rise", [-1000.0, -300.0, 500.0, 1000.0])
def test_rise_shifts_the_end_height_by_exactly_rise_meters(profile, rise):
    base = S.make_route(600.0, profile, 11, 0.0, "konstant", 0.0)
    r = S.make_route(600.0, profile, 11, 0.0, "konstant", rise)
    assert r.height[-1] - base.height[-1] == pytest.approx(rise, abs=1e-6)
    assert r.height[60] - base.height[60] == pytest.approx(rise / 2, abs=1e-6)                 # gleichmäßig verteilt


def test_flat_route_with_rise_is_a_straight_ramp():
    r = S.make_route(100.0, "flach", 1, 0.0, "konstant", 200.0)
    assert r.height == pytest.approx([10.0 * i for i in range(21)])                            # 200 m auf 20 Zellen: 10 m je Zelle
    assert r.grade == pytest.approx([0.002] * 20)                                              # 200 m auf 100 km = 2 Promille


def test_constant_wind_is_the_headwind_in_every_cell_and_independent_of_the_seed():
    for seed in (1, 2):
        r = S.make_route(300.0, "flach", seed, 25.0, "konstant")
        assert r.wind == pytest.approx([25.0] * 60)
    assert S.make_route(300.0, "flach", 1, -15.0, "konstant").wind == pytest.approx([-15.0] * 60)


def test_changing_wind_adds_pieces_of_integer_deviations_within_15_kmh():
    r = S.make_route(600.0, "flach", 4, 10.0, "wechselnd")
    dev = r.wind - 10.0
    assert np.abs(dev).max() <= 15 + 1e-9 and np.abs(dev - np.round(dev)).max() < 1e-9 and np.ptp(dev) > 0
    assert all(len(p) >= 4 for p in runs_of(dev)[:-1])                                         # Stücke von mindestens 4 Zellen
    again = S.make_route(600.0, "flach", 4, 10.0, "wechselnd")
    other = S.make_route(600.0, "flach", 5, 10.0, "wechselnd")
    assert np.array_equal(r.wind, again.wind) and not np.array_equal(r.wind, other.wind)


def test_changing_wind_does_not_change_the_height_profile():
    a = S.make_route(300.0, "huegelig", 4, 0.0, "konstant")
    b = S.make_route(300.0, "huegelig", 4, 0.0, "wechselnd")
    assert np.array_equal(a.height, b.height) and not np.array_equal(a.wind, b.wind)


# ------------------------------------------------------------------ Geschwindigkeitsraster
def test_speed_grid_runs_from_the_minimum_speed_to_the_limit_in_steps_of_5():
    g = S.speed_grid(130)
    assert C.V_MIN == 60 and g[0] == 60 and g[-1] == 130 and len(g) == 15 and all(b - a == 5 for a, b in zip(g, g[1:]))       # (130 − 60) / 5 + 1
    assert len(S.speed_grid(180)) == 25


def test_speed_grid_rounds_the_limit_down_to_the_grid_and_has_a_minimum():
    assert S.speed_grid(133)[-1] == 130 and S.speed_grid(134.9)[-1] == 130 and S.speed_grid(135)[-1] == 135
    assert S.speed_grid(60) == [60] and S.speed_grid(62) == [60] and S.speed_grid(10) == [60]
    assert S.speed_grid(65) == [60, 65]
    assert all(isinstance(v, int) for v in S.speed_grid(90))


# ------------------------------------------------------------------ Fahrt
SETTINGS = {"vehicle": "Pkw", "cap": 80.0, "mass": 2100.0, "cda": 0.7, "cr": 0.012, "peak": 120.0, "aux": 1.2, "curve": "Lange Spitze", "loss": 12.0, "stop_min": 15.0, "length": 200,
            "profile": "pass", "rise": 100, "seed": 3, "headwind": 10, "wind_mode": "wechselnd", "tv": 20, "price": 0.6, "soc0": 50, "smin_stop": 10, "smin_dest": 5, "vmax": 140}


def test_make_trip_converts_percent_to_kwh_and_minutes_to_hours():
    t = S.make_trip(SETTINGS)
    assert t.soc0 == pytest.approx(40.0) and t.smin_stop == pytest.approx(8.0) and t.smin_dest == pytest.approx(4.0)      # 80 kWh · 50 %, 10 %, 5 %
    assert t.stop_h == pytest.approx(0.25)                                                                                 # 15 min
    assert t.vmax == 140 and t.loss == 12.0 and isinstance(t.vmax, int)
    v = t.vehicle
    assert (v.cap, v.mass, v.cda, v.cr, v.peak, v.aux, v.curve) == (80.0, 2100.0, 0.7, 0.012, 120.0, 1.2, "Lange Spitze")


def test_make_trip_builds_the_route_from_the_settings():
    t = S.make_trip(SETTINGS)
    ref = S.make_route(200.0, "pass", 3, 10.0, "wechselnd", 100.0)
    assert t.route.n == 40 and np.array_equal(t.route.grade, ref.grade) and np.array_equal(t.route.wind, ref.wind) and t.route.height[-1] == pytest.approx(ref.height[-1])


def test_make_trip_without_rise_means_zero_and_the_base_scenario_works():
    s = {k: v for k, v in SETTINGS.items() if k != "rise"}
    assert S.make_trip(s).route.height[-1] == pytest.approx(S.make_trip({**SETTINGS, "rise": 0}).route.height[-1])
    t = S.make_trip(C.BASE_SCENARIO)
    assert t.vehicle.cap == 77.0 and t.soc0 == pytest.approx(77.0) and t.smin_stop == pytest.approx(7.7) and t.stop_h == pytest.approx(5.0 / 60.0) and t.route.n == 120


def test_vehicle_is_immutable():
    with pytest.raises(dataclasses.FrozenInstanceError):
        S.make_trip(SETTINGS).vehicle.cap = 1.0


# ------------------------------------------------------------------ Gewichte der Zielfunktion
def test_objective_weights_by_hand():
    # Zeit allein: Zielfunktion = Reisezeit in Stunden, die Energie kostet nichts
    assert S.objective_weights(C.TV_FAST, 0.5, 10.0) == (1.0, 0.0)
    assert S.objective_weights(C.TV_FAST + 5, 0.9, 30.0) == (1.0, 0.0)
    # 20 €/h, 0,45 €/kWh bei 10 % Ladeverlust: eine Batterie-kWh kostet 0,45 / 0,9 = 0,5 €
    wt, we = S.objective_weights(20, 0.45, 10.0)
    assert wt == 20.0 and we == pytest.approx(0.5)
    assert S.objective_weights(1, 0.6, 25.0)[1] == pytest.approx(0.8) and S.objective_weights(1, 0.6, 0.0)[1] == pytest.approx(0.6)


def test_make_trip_sets_the_weights_from_the_time_value_the_price_and_the_loss():
    t = S.make_trip({**SETTINGS, "tv": 30, "price": 0.45, "loss": 10.0})
    assert t.w_time == 30.0 and t.w_energy == pytest.approx(0.5)
    fast = S.make_trip({**SETTINGS, "tv": C.TV_FAST})
    assert fast.w_time == 1.0 and fast.w_energy == 0.0
    assert S.make_trip(C.BASE_SCENARIO).w_time == float(C.DEFAULT_TV)
    assert S.make_trip(C.BASE_SCENARIO).w_energy == pytest.approx(C.DEFAULT_PRICE / (1.0 - C.DEFAULT_LOSS / 100.0))
