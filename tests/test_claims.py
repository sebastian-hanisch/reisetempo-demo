"""Jede Zahl der README-Tabelle „Befunde“ wird aus data/rtp_results.json mit denselben Auswertungsfunktionen wie in der App nachgerechnet (DEMO-PLAYBOOK §4).

Gerundete Aussagen der README (eine Nachkommastelle) werden mit der Rundungstoleranz geprüft, nie als Gleichheit von Gleitkommazahlen."""
import pytest

import rtp_results as R

RES = R.load_results()
ROUND1 = 0.06      # README nennt eine Nachkommastelle
ROUND2 = 0.006     # README nennt zwei Nachkommastellen


def power(peak, vmax):
    return R.power_summary(RES, peak, vmax)


def test_the_sweep_has_the_documented_size():
    assert RES["meta"]["cases"] == 795 and len(RES["rows"]) == 795
    assert RES["meta"]["seeds"] == [100, 110]


def test_free_speed_per_section_brings_almost_nothing():
    fv = R.free_vs_const(RES)
    assert fv["n"] == 795
    assert fv["mean"] == pytest.approx(0.17, abs=0.006)
    assert fv["p95"] == pytest.approx(0.4, abs=0.05)
    assert fv["max"] == pytest.approx(0.83, abs=0.006)


@pytest.mark.parametrize("peak,vmax,expected", [(150.0, 130, 3.4), (50.0, 130, 9.0), (350.0, 130, 1.5), (50.0, 160, 21.3), (50.0, 180, 30.8), (150.0, 160, 5.1), (150.0, 180, 5.4)])
def test_rule_gap_to_the_optimum(peak, vmax, expected):
    assert power(peak, vmax)["gap_rule"] == pytest.approx(expected, abs=ROUND1)


@pytest.mark.parametrize("peak,vmax,expected", [(150.0, 130, 0.13), (50.0, 160, 5.2), (50.0, 180, 13.5)])
def test_speed_limit_with_optimal_charging_is_close_except_with_slow_chargers(peak, vmax, expected):
    assert power(peak, vmax)["gap_const_max"] == pytest.approx(expected, abs=0.06 if expected > 1 else ROUND2)


@pytest.mark.parametrize("peak,vmax,expected", [(50.0, 130, 126.0), (50.0, 160, 134.0), (50.0, 180, 134.0), (150.0, 130, 130.0), (150.0, 160, 160.0), (150.0, 180, 173.5)])
def test_best_constant_speed(peak, vmax, expected):
    assert power(peak, vmax)["v_best"] == pytest.approx(expected, abs=0.5)


def test_charging_target_of_the_optimum_is_about_half_at_five_minutes_fixed_time():
    targets = [power(p, 130)["tgt_opt"] for p in RES["meta"]["peaks"]]
    assert round(min(targets)) == 46 and round(max(targets)) == 50
    assert R.fix_summary(RES, 150.0, 5.0)["tgt_opt"] == pytest.approx(50.0, abs=0.5)


def test_charging_target_grows_with_the_fixed_time_per_stop():
    assert round(R.fix_summary(RES, 50.0, 30.0)["tgt_opt"]) == 61
    assert round(R.fix_summary(RES, 350.0, 30.0)["tgt_opt"]) == 89
    assert round(R.fix_summary(RES, 150.0, 30.0)["tgt_opt"]) == 82
    for peak in (50.0, 150.0, 350.0):
        assert R.fix_summary(RES, peak, 30.0)["tgt_opt"] > R.fix_summary(RES, peak, 5.0)["tgt_opt"] > R.fix_summary(RES, peak, 1.0)["tgt_opt"] - 1e-9


def test_cold_costs_travel_time_and_stops():
    ref = R.temp_summary(RES, 20, 600)["t_opt"]
    assert 100 * (R.temp_summary(RES, -10, 600)["t_opt"] / ref - 1) == pytest.approx(13.0, abs=ROUND1)
    assert 100 * (R.temp_summary(RES, -20, 600)["t_opt"] / ref - 1) == pytest.approx(17.9, abs=ROUND1)
    assert R.temp_summary(RES, -10, 1000)["stops_opt"] == pytest.approx(8.0, abs=0.05)
    assert R.temp_summary(RES, 20, 1000)["stops_opt"] == pytest.approx(5.0, abs=0.05)


def test_wind_shifts_the_best_constant_speed_for_slow_chargers_only():
    def mean_v(peak, wind):
        return sum(R.wind_summary(RES, peak, p, wind)["v_best"] for p in RES["meta"]["profiles"]) / len(RES["meta"]["profiles"])

    assert mean_v(50.0, -30) == pytest.approx(145.0, abs=0.5)
    assert mean_v(50.0, 0) == pytest.approx(133.0, abs=0.5)
    assert mean_v(50.0, 30) == pytest.approx(124.0, abs=0.5)
    assert all(mean_v(150.0, w) == pytest.approx(160.0, abs=1e-9) for w in RES["meta"]["winds"])


def test_height_costs_the_truck_more_than_the_car():
    car0, car1 = R.height_summary(RES, "Pkw", "flach", 0), R.height_summary(RES, "Pkw", "flach", 1000)
    truck0, truck1 = R.height_summary(RES, "Elektro-Lkw", "flach", 0), R.height_summary(RES, "Elektro-Lkw", "flach", 1000)
    assert 100 * (car1["t_opt"] / car0["t_opt"] - 1) == pytest.approx(1.2, abs=ROUND1)
    assert (car0["cons_opt"], car1["cons_opt"]) == (pytest.approx(21.6, abs=ROUND1), pytest.approx(22.7, abs=ROUND1))
    assert 100 * (truck1["t_opt"] / truck0["t_opt"] - 1) == pytest.approx(3.5, abs=ROUND1)
    assert (truck0["cons_opt"], truck1["cons_opt"]) == (pytest.approx(112.8, abs=ROUND1), pytest.approx(124.9, abs=ROUND1))
    assert 100 * (truck1["cons_opt"] / truck0["cons_opt"] - 1) == pytest.approx(10.7, abs=ROUND1)
    assert 100 * (R.height_summary(RES, "Pkw", "pass", 0)["t_opt"] / car0["t_opt"] - 1) == pytest.approx(0.2, abs=ROUND1)


@pytest.mark.parametrize("vehicle,expected", [("Kompaktwagen", 4.5), ("Pkw", 3.4), ("Großer Pkw", 0.3), ("Lieferwagen", 10.4), ("Elektro-Lkw", 0.0)])
def test_rule_gap_by_vehicle_at_600_km(vehicle, expected):
    assert R.vehicle_summary(RES, vehicle, 600)["gap_rule"] == pytest.approx(expected, abs=ROUND1)


def test_the_rule_is_at_most_0_08_percent_better_than_the_dp_optimum():
    gaps = [R.gap(r, "rule") for r in RES["rows"]]
    assert min(gaps) < 0 and round(min(gaps), 2) == -0.08


def test_the_dp_optimum_is_never_worse_than_the_best_constant_speed():
    assert all(r["t_opt"] <= r["t_const_best"] * (1 + 1e-6) for r in RES["rows"])
