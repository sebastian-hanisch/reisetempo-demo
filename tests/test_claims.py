"""Jede Zahl der README-Tabelle „Befunde“ wird aus data/rtp_results.json mit denselben Auswertungsfunktionen wie in der App nachgerechnet (DEMO-PLAYBOOK §4).

Gerundete Aussagen der README (eine Nachkommastelle) werden mit der Rundungstoleranz geprüft, nie als Gleichheit von Gleitkommazahlen."""
import pytest

import rtp_constants as C
import rtp_results as R

RES = R.load_results()
ROUND1 = 0.06      # README nennt eine Nachkommastelle
ROUND2 = 0.006     # README nennt zwei Nachkommastellen
FAST, MID = C.TV_FAST, C.DEFAULT_TV


def power(peak, vmax, tv=FAST):
    return R.power_summary(RES, peak, vmax, tv)


def veh(name, tv, length=600):
    return R.vehicle_summary(RES, name, length, tv)


def pct(a, b):
    """Prozent, um die a über b liegt."""
    return 100 * (a / b - 1)


def test_the_sweep_has_the_documented_size():
    assert RES["meta"]["cases"] == 1415 and len(RES["rows"]) == 1415
    assert RES["meta"]["seeds"] == [100, 110] and RES["meta"]["tvs"] == [1, 2, 5, 10, 20, 30, 50, 100, 1000]


# ------------------------------------------------------------------ die Spanne
def test_the_spectrum_of_the_car_spans_half_the_consumption_for_almost_twice_the_time():
    eco, fast = veh("Pkw", 1), veh("Pkw", FAST)
    assert fast["cons_opt"] == pytest.approx(21.6, abs=ROUND1) and eco["cons_opt"] == pytest.approx(10.7, abs=ROUND1)
    assert pct(eco["cons_opt"], fast["cons_opt"]) == pytest.approx(-51.0, abs=0.5)                      # „−51 %“
    assert round(fast["t_opt"]) == 316 and round(eco["t_opt"]) == 596 and pct(eco["t_opt"], fast["t_opt"]) == pytest.approx(89.0, abs=0.5)
    assert fast["v_opt"] == pytest.approx(130.0, abs=0.5) and eco["v_opt"] == pytest.approx(C.V_MIN, abs=1.0)


def test_the_middle_of_the_spectrum_for_the_car():
    fast, mid, ten = veh("Pkw", FAST), veh("Pkw", MID), veh("Pkw", 10)
    assert pct(mid["t_opt"], fast["t_opt"]) == pytest.approx(9.7, abs=ROUND1) and pct(mid["cons_opt"], fast["cons_opt"]) == pytest.approx(-17.4, abs=ROUND1)
    assert round(mid["t_opt"]) == 346 and mid["cons_opt"] == pytest.approx(17.9, abs=ROUND1) and mid["v_opt"] == pytest.approx(112.0, abs=0.5)
    assert pct(ten["t_opt"], fast["t_opt"]) == pytest.approx(20.1, abs=ROUND1) and pct(ten["cons_opt"], fast["cons_opt"]) == pytest.approx(-28.0, abs=ROUND1)


def test_from_100_euro_per_hour_nothing_is_left_to_gain_for_cars_but_not_for_the_heavy_vehicles():
    for name in ("Kompaktwagen", "Pkw", "Großer Pkw"):
        assert abs(pct(veh(name, 100)["t_opt"], veh(name, FAST)["t_opt"])) < 0.05 and abs(pct(veh(name, 100)["cons_opt"], veh(name, FAST)["cons_opt"])) < 0.05, name
    assert pct(veh("Lieferwagen", 50)["t_opt"], veh("Lieferwagen", FAST)["t_opt"]) == pytest.approx(2.3, abs=ROUND1)
    assert pct(veh("Lieferwagen", 50)["cons_opt"], veh("Lieferwagen", FAST)["cons_opt"]) == pytest.approx(-10.2, abs=ROUND1)
    assert pct(veh("Elektro-Lkw", 50)["t_opt"], veh("Elektro-Lkw", FAST)["t_opt"]) == pytest.approx(7.2, abs=ROUND1)
    assert pct(veh("Elektro-Lkw", 50)["cons_opt"], veh("Elektro-Lkw", FAST)["cons_opt"]) == pytest.approx(-9.8, abs=ROUND1)
    assert abs(pct(veh("Elektro-Lkw", 100)["t_opt"], veh("Elektro-Lkw", FAST)["t_opt"])) < 0.05


@pytest.mark.parametrize("name,dt,dc", [("Kompaktwagen", 7.2, -19.3), ("Pkw", 9.7, -17.4), ("Großer Pkw", 9.0, -14.5), ("Lieferwagen", 9.3, -23.5), ("Elektro-Lkw", 25.5, -22.4)])
def test_the_middle_of_the_spectrum_by_vehicle(name, dt, dc):
    assert pct(veh(name, MID)["t_opt"], veh(name, FAST)["t_opt"]) == pytest.approx(dt, abs=ROUND1)
    assert pct(veh(name, MID)["cons_opt"], veh(name, FAST)["cons_opt"]) == pytest.approx(dc, abs=ROUND1)


def test_the_spectrum_is_monotone_in_time_and_consumption_for_every_vehicle():
    for name in C.VEHICLE_ORDER:
        pts = R.spectrum(RES, name, 600)
        assert all(b["t_opt"] <= a["t_opt"] * 1.001 for a, b in zip(pts, pts[1:])) and all(b["cons_opt"] >= a["cons_opt"] * 0.999 for a, b in zip(pts, pts[1:])), name


# ------------------------------------------------------------------ Praxisregel, Tempolimit, Geschwindigkeit
def test_free_speed_per_section_brings_almost_nothing():
    fv = R.free_vs_const(RES)
    assert fv["n"] == 1415
    assert fv["mean"] == pytest.approx(0.14, abs=0.006)
    assert fv["p95"] == pytest.approx(0.4, abs=0.05)
    assert fv["max"] == pytest.approx(2.0, abs=0.01)
    worst = max(R.rows_of(RES, "vehicle"), key=lambda r: R.gap_obj(r, "const_best"))
    assert (worst["vehicle"], worst["length"], worst["tv"]) == ("Elektro-Lkw", 300, 20)                  # das Maximum liegt beim Lkw im Mittelfeld der Spanne
    assert max(R.gap_obj(r, "const_best") for r in RES["rows"] if r["tv"] >= FAST) == pytest.approx(0.83, abs=ROUND2)       # bei „Zeit allein“ höchstens 0,83 %


@pytest.mark.parametrize("peak,vmax,expected", [(150.0, 130, 3.4), (50.0, 130, 9.0), (350.0, 130, 1.5), (50.0, 160, 21.3), (50.0, 180, 30.8), (150.0, 160, 5.1), (150.0, 180, 5.4)])
def test_rule_gap_to_the_optimum_with_time_alone(peak, vmax, expected):
    assert power(peak, vmax)["gap_rule"] == pytest.approx(expected, abs=ROUND1)


@pytest.mark.parametrize("peak,vmax,expected", [(150.0, 130, 3.4), (50.0, 130, 11.8), (50.0, 160, 33.8), (50.0, 180, 50.9), (150.0, 160, 14.3), (150.0, 180, 25.3)])
def test_rule_cost_gap_to_the_optimum_at_20_euro_per_hour(peak, vmax, expected):
    assert power(peak, vmax, MID)["gap_rule"] == pytest.approx(expected, abs=ROUND1)


def test_at_20_euro_per_hour_the_rule_costs_more_the_higher_the_speed_limit_is():
    for peak in RES["meta"]["peaks"]:
        gaps = [power(peak, vm, MID)["gap_rule"] for vm in RES["meta"]["vmaxes"]]
        assert all(b >= a - 0.05 for a, b in zip(gaps, gaps[1:])), (peak, gaps)             # Rasterrauschen unter 0,05 Punkten


def test_at_20_euro_per_hour_the_rule_is_faster_but_thirstier():
    s = power(150.0, 130, MID)
    assert s["tgap_rule"] == pytest.approx(-5.7, abs=ROUND1)                                              # 5,7 % schneller
    assert s["cons_rule"] == pytest.approx(21.6, abs=ROUND1) and s["cons_opt"] == pytest.approx(17.9, abs=ROUND1)
    assert power(150.0, 180, MID)["cons_rule"] == pytest.approx(35.2, abs=ROUND1)


@pytest.mark.parametrize("peak,vmax,expected", [(150.0, 130, 0.13), (50.0, 160, 5.2), (50.0, 180, 13.5)])
def test_speed_limit_with_optimal_charging_is_close_except_with_slow_chargers(peak, vmax, expected):
    assert power(peak, vmax)["gap_const_max"] == pytest.approx(expected, abs=0.06 if expected > 1 else ROUND2)


def test_speed_limit_with_optimal_charging_at_20_euro_per_hour():
    assert power(150.0, 130, MID)["gap_const_max"] == pytest.approx(1.4, abs=ROUND1)
    assert power(150.0, 160, MID)["gap_const_max"] == pytest.approx(11.6, abs=ROUND1) and power(150.0, 160, MID)["gap_rule"] == pytest.approx(14.3, abs=ROUND1)


@pytest.mark.parametrize("peak,vmax,expected", [(50.0, 130, 126.0), (50.0, 160, 134.0), (50.0, 180, 134.0), (150.0, 130, 130.0), (150.0, 160, 160.0), (150.0, 180, 173.5)])
def test_best_constant_speed_with_time_alone(peak, vmax, expected):
    assert power(peak, vmax)["v_best"] == pytest.approx(expected, abs=0.5)


@pytest.mark.parametrize("peak,expected", [(50.0, 100.0), (150.0, 110.0), (350.0, 120.0)])
def test_best_constant_speed_at_20_euro_per_hour_hardly_depends_on_the_speed_limit(peak, expected):
    for vmax in (130, 160, 180):
        assert power(peak, vmax, MID)["v_best"] == pytest.approx(expected, abs=0.5), vmax


def test_charging_target_of_the_optimum_is_about_half_at_five_minutes_fixed_time():
    targets = [power(p, 130)["tgt_opt"] for p in RES["meta"]["peaks"]]
    assert round(min(targets)) == 46 and round(max(targets)) == 50
    assert R.fix_summary(RES, 150.0, 5.0)["tgt_opt"] == pytest.approx(50.0, abs=0.5)


def test_charging_target_at_20_euro_per_hour_is_higher_with_a_faster_charger_and_there_is_one_stop():
    assert [round(power(p, 130, MID)["tgt_opt"]) for p in (50.0, 150.0, 350.0)] == [45, 59, 71]
    assert all(power(p, 130, MID)["stops_opt"] == pytest.approx(1.0) for p in (50.0, 150.0, 350.0))


def test_charging_target_grows_with_the_fixed_time_per_stop():
    assert round(R.fix_summary(RES, 50.0, 30.0)["tgt_opt"]) == 61
    assert round(R.fix_summary(RES, 350.0, 30.0)["tgt_opt"]) == 89
    assert round(R.fix_summary(RES, 150.0, 30.0)["tgt_opt"]) == 82
    for peak in (50.0, 150.0, 350.0):
        assert R.fix_summary(RES, peak, 30.0)["tgt_opt"] > R.fix_summary(RES, peak, 5.0)["tgt_opt"] > R.fix_summary(RES, peak, 1.0)["tgt_opt"] - 1e-9


# ------------------------------------------------------------------ Wind, Höhe, Fahrzeuge
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
def test_rule_gap_by_vehicle_at_600_km_with_time_alone(vehicle, expected):
    assert veh(vehicle, FAST)["gap_rule"] == pytest.approx(expected, abs=ROUND1)


def test_the_rule_is_at_most_0_08_percent_better_than_the_dp_optimum():
    gaps = [R.gap_obj(r, "rule") for r in RES["rows"]]
    assert min(gaps) < 0 and round(min(gaps), 2) == -0.08


def test_the_dp_optimum_is_never_worse_than_the_best_constant_speed_apart_from_rounding():
    assert all(r["j_opt"] <= r["j_const_best"] * (1 + 1e-4) for r in RES["rows"])                       # höchstens 0,004 % Rasterrauschen
    assert all(r["t_opt"] <= r["t_const_best"] * (1 + 1e-6) for r in RES["rows"] if r["tv"] >= FAST)    # bei „Zeit allein“ exakt
