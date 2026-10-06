"""Auswertung der Messreihe an einer von Hand gerechneten Mini-Ergebnisdatei und Konsistenz der echten Messreihe (data/rtp_results.json) mit tools/sweep.py."""
import importlib.util
import json
import math
from pathlib import Path

import pytest

import rtp_constants as C
import rtp_results as R

ROOT = Path(__file__).resolve().parent.parent


def row(sweep, **kw):
    """Zeile der Messreihe; die Zielfunktion j_ ist, wenn nicht genannt, die Reisezeit (Zeit allein: j_ = t_ in Stunden), die Energie e_ null."""
    base = {"sweep": sweep, "peak": 150.0, "vmax": 130, "tv": C.TV_FAST, "length": 600, "headwind": 0, "profile": "huegelig", "vehicle": "Pkw", "stop_min": 5.0, "rise": 0,
            "t_rule": 105.0, "t_const_max": 101.0, "t_const_best": 100.5, "t_opt": 100.0, "v_best": 120.0, "v_opt": 118.0, "tgt_opt": 50.0, "stops_opt": 2, "cons_opt": 18.0}
    out = {**base, **kw}
    for key in ("rule", "const_max", "const_best", "opt"):
        out.setdefault(f"j_{key}", None if out[f"t_{key}"] is None else out[f"t_{key}"] / 60.0)
        out.setdefault(f"e_{key}", 0.0)
    return out


RES = {"meta": {}, "rows": [
    # Ladeleistung × Tempolimit (150 kW, 130 km/h): Lücken Praxisregel 5 und 10 %, Tempolimit 1 und 2 %, beste konstante je 0,5 %
    row("power", t_opt=100.0, t_rule=105.0, t_const_max=101.0, t_const_best=100.5, v_best=120.0, tgt_opt=50.0, stops_opt=2),
    row("power", t_opt=200.0, t_rule=220.0, t_const_max=204.0, t_const_best=201.0, v_best=110.0, tgt_opt=None, stops_opt=4),
    row("power", peak=50.0, t_opt=999.0, t_rule=1999.0),                                                     # andere Zelle, zählt nicht
    # dieselbe Zelle bei 20 €/h: die Zielfunktion ist in Euro; Optimum 250 €, Regel 265 € (+6 %), Tempolimit 255 € (+2 %), beste konstante 252,5 € (+1 %)
    row("power", tv=20, t_opt=600.0, t_rule=570.0, t_const_max=600.0, t_const_best=600.0, v_best=100.0, v_opt=101.0, tgt_opt=60.0, stops_opt=1, j_opt=250.0, j_rule=265.0, j_const_max=255.0,
        j_const_best=252.5, e_opt=100.0, e_rule=150.0),
    # Wind (50 kW, Pass, 15 km/h)
    row("wind", peak=50.0, profile="pass", headwind=15, t_opt=100.0, t_const_best=101.0, v_best=100.0),
    row("wind", peak=50.0, profile="pass", headwind=15, t_opt=200.0, t_const_best=204.0, v_best=110.0),
    row("wind", peak=50.0, profile="pass", headwind=0, t_opt=50.0),
    # Fahrzeug (Pkw, 300 km)
    row("vehicle", vehicle="Pkw", length=300, t_opt=100.0, t_rule=110.0, t_const_best=101.0, v_best=120.0, stops_opt=1),
    row("vehicle", vehicle="Pkw", length=300, t_opt=200.0, t_rule=210.0, t_const_best=202.0, v_best=100.0, stops_opt=3),
    row("vehicle", vehicle="Elektro-Lkw", length=300, t_opt=1.0),
    # Fixzeit (50 kW, 15 min)
    row("fix", peak=50.0, stop_min=15.0, t_opt=100.0, t_rule=104.0, stops_opt=2, tgt_opt=40.0), row("fix", peak=50.0, stop_min=15.0, t_opt=100.0, t_rule=106.0, stops_opt=4, tgt_opt=60.0),
    # Höhe (Pkw, Pass, +500 m)
    row("height", vehicle="Pkw", profile="pass", rise=500, t_opt=100.0, cons_opt=18.0), row("height", vehicle="Pkw", profile="pass", rise=500, t_opt=120.0, cons_opt=20.0),
]}


# ------------------------------------------------------------------ Bausteine
def test_mean_se_by_hand():
    m, se = R.mean_se([1, 3])
    assert m == pytest.approx(2.0) and se == pytest.approx(1.0)                      # Standardabweichung √2, geteilt durch √2
    assert R.mean_se([2, 4, 6])[1] == pytest.approx(2 / 3 ** 0.5)


def test_mean_se_skips_missing_values_and_handles_small_samples():
    m, se = R.mean_se([None, 5.0])
    assert m == 5.0 and math.isnan(se)
    assert R.mean_se([None, 1, None, 3])[0] == pytest.approx(2.0)
    m, se = R.mean_se([])
    assert math.isnan(m) and math.isnan(se) and math.isnan(R.mean_se([None])[0])
    assert R.mean_se(x for x in (1.0, 3.0))[0] == pytest.approx(2.0)                 # auch Generatoren


def test_rows_of_filters_by_sweep_and_all_conditions():
    assert len(R.rows_of(RES, "power")) == 4 and len(R.rows_of(RES, "power", peak=150.0)) == 3 and len(R.rows_of(RES, "power", peak=150.0, vmax=110)) == 0
    assert [r["t_opt"] for r in R.rows_of(RES, "power", peak=150.0, tv=C.TV_FAST)] == [100.0, 200.0] and [r["t_opt"] for r in R.rows_of(RES, "power", tv=20)] == [600.0] and R.rows_of(RES, "nope") == []


def test_gap_uses_the_reference_as_basis():
    r = row("x", t_opt=100.0, t_rule=105.0, t_const_best=104.0)
    assert R.gap(r, "rule") == pytest.approx(5.0) and R.gap(r, "const_best", "rule") == pytest.approx(100 * (104 / 105 - 1)) and R.gap(r, "opt") == pytest.approx(0.0, abs=1e-12)


def test_gap_obj_and_cons_use_the_objective_and_the_energy_of_the_row():
    r = row("x", t_opt=100.0, t_rule=90.0, j_opt=250.0, j_rule=265.0, e_opt=100.0, e_rule=150.0, length=500)
    assert R.gap_obj(r, "rule") == pytest.approx(6.0) and R.gap(r, "rule") == pytest.approx(-10.0)          # teurer und doch schneller
    assert R.gap_obj(r, "opt", "rule") == pytest.approx(100 * (250 / 265 - 1)) and R.gap_obj(r, "opt") == pytest.approx(0.0, abs=1e-12)
    assert R.cons(r, "opt") == pytest.approx(20.0) and R.cons(r, "rule") == pytest.approx(30.0)               # 100 kWh auf 500 km


def test_nearest_with_ties_takes_the_smaller_value():
    peaks = (50.0, 100.0, 150.0, 250.0, 350.0)
    assert R.nearest(peaks, 125.0) == 100.0 and R.nearest(peaks, 200.0) == 150.0 and R.nearest(peaks, 300.0) == 250.0       # genau in der Mitte: der kleinere
    assert R.nearest(peaks, 0.0) == 50.0 and R.nearest(peaks, 1000.0) == 350.0 and R.nearest(peaks, 140.0) == 150.0 and R.nearest(peaks, 99.0) == 100.0
    assert R.nearest((350.0, 50.0, 150.0), 200.0) == 150.0                           # Reihenfolge der Eingabe egal
    assert R.nearest((110, 130, 160, 180), 145) == 130 and R.nearest((110, 130, 160, 180), 146) == 160 and R.nearest((110, 130, 160, 180), 140) == 130


# ------------------------------------------------------------------ Zusammenfassungen
def test_power_summary_by_hand():
    s = R.power_summary(RES, 150.0, 130)
    assert s["n"] == 2 and s["peak"] == 150.0 and s["vmax"] == 130 and s["tv"] == C.TV_FAST and s["tgap_rule"] == pytest.approx(7.5) and s["v_opt"] == pytest.approx(118.0)
    assert s["gap_rule"] == pytest.approx(7.5) and s["gap_rule_se"] == pytest.approx(2.5)                   # 5 und 10 %: Standardabweichung 3,5355, geteilt durch √2
    assert s["gap_const_max"] == pytest.approx(1.5) and s["gap_const_max_se"] == pytest.approx(0.5)        # 1 und 2 %
    assert s["gap_const_best"] == pytest.approx(0.5) and s["gap_const_best_se"] == pytest.approx(0.0, abs=1e-9)
    assert s["v_best"] == pytest.approx(115.0) and s["v_best_se"] == pytest.approx(5.0)
    assert s["tgt_opt"] == pytest.approx(50.0)                                                              # der fehlende Wert (kein Stopp) zählt nicht mit
    assert s["t_opt"] == pytest.approx(150.0) and s["stops_opt"] == pytest.approx(3.0) and s["t_rule"] == pytest.approx(162.5) and s["cons_opt"] == pytest.approx(0.0)


def test_power_summary_of_a_priced_cell_uses_the_objective_in_euro():
    s = R.power_summary(RES, 150.0, 130, 20)
    assert s["n"] == 1 and s["tv"] == 20
    assert s["gap_rule"] == pytest.approx(6.0) and s["gap_const_max"] == pytest.approx(2.0) and s["gap_const_best"] == pytest.approx(1.0)        # Zielfunktion in Euro
    assert s["tgap_rule"] == pytest.approx(-5.0) and s["t_opt"] == pytest.approx(600.0) and s["t_rule"] == pytest.approx(570.0)                   # die Regel ist schneller
    assert s["cons_opt"] == pytest.approx(100 * 100.0 / 600) and s["cons_rule"] == pytest.approx(100 * 150.0 / 600) and s["v_best"] == pytest.approx(100.0) and s["tgt_opt"] == pytest.approx(60.0)


def test_summaries_of_an_empty_cell_are_nan_without_exception():
    s = R.power_summary(RES, 999.0, 130)
    assert s["n"] == 0 and math.isnan(s["gap_rule"]) and math.isnan(s["v_best"]) and math.isnan(s["t_opt"])
    assert R.power_summary(RES, 150.0, 130, 5)["n"] == 0 and math.isnan(R.wind_summary(RES, 1.0, "flach", 0)["v_best"]) and R.height_summary(RES, "Pkw", "flach", 77)["n"] == 0
    assert R.vehicle_summary(RES, "Pkw", 300, 5)["n"] == 0 and math.isnan(R.vehicle_summary(RES, "Pkw", 300, 5)["cons_opt"])



def test_wind_summary_by_hand():
    s = R.wind_summary(RES, 50.0, "pass", 15)
    assert s["n"] == 2 and s["v_best"] == pytest.approx(105.0) and s["v_best_se"] == pytest.approx(5.0) and s["t_opt"] == pytest.approx(150.0)
    assert s["gap_const_best"] == pytest.approx(1.5) and s["gap_const_best_se"] == pytest.approx(0.5)         # 1 % und 2 %
    assert R.wind_summary(RES, 50.0, "pass", 0)["t_opt"] == pytest.approx(50.0)


def test_vehicle_summary_by_hand():
    s = R.vehicle_summary(RES, "Pkw", 300)
    assert s["n"] == 2 and s["t_opt"] == pytest.approx(150.0) and s["stops_opt"] == pytest.approx(2.0) and s["v_best"] == pytest.approx(110.0) and s["tv"] == C.TV_FAST
    assert s["gap_rule"] == pytest.approx(7.5) and s["gap_rule_se"] == pytest.approx(2.5) and s["gap_const_best"] == pytest.approx(1.0)             # 10 und 5 %; je 1 %
    assert s["t_rule"] == pytest.approx(160.0) and s["v_opt"] == pytest.approx(118.0) and s["cons_opt"] == pytest.approx(0.0)
    assert R.vehicle_summary(RES, "Elektro-Lkw", 300)["n"] == 1


def test_vehicle_summary_and_spectrum_follow_the_time_values():
    res = {"meta": {"tvs": [1, 20, C.TV_FAST]}, "rows": [
        row("vehicle", tv=1, length=600, t_opt=200.0, e_opt=60.0, t_rule=100.0, e_rule=120.0, j_opt=10.0, j_rule=20.0, v_opt=60.0, stops_opt=0),
        row("vehicle", tv=20, length=600, t_opt=120.0, e_opt=90.0, t_rule=100.0, e_rule=120.0, j_opt=100.0, j_rule=110.0, v_opt=100.0, stops_opt=1),
        row("vehicle", tv=C.TV_FAST, length=600, t_opt=100.0, e_opt=120.0, t_rule=100.0, e_rule=120.0, v_opt=130.0, stops_opt=2),
        row("vehicle", tv=20, length=300, t_opt=1.0, e_opt=1.0, t_rule=1.0, e_rule=1.0)]}
    pts = R.spectrum(res, "Pkw", 600)
    assert [p["tv"] for p in pts] == [1, 20, C.TV_FAST] and all(p["n"] == 1 for p in pts)
    assert [p["t_opt"] for p in pts] == [200.0, 120.0, 100.0] and [p["cons_opt"] for p in pts] == pytest.approx([10.0, 15.0, 20.0])      # 60, 90, 120 kWh auf 600 km
    assert [p["v_opt"] for p in pts] == [60.0, 100.0, 130.0] and [p["stops_opt"] for p in pts] == [0, 1, 2]
    assert pts[0]["gap_rule"] == pytest.approx(100.0) and pts[1]["gap_rule"] == pytest.approx(10.0) and pts[2]["gap_rule"] == pytest.approx(0.0, abs=1e-9)
    assert pts[1]["t_rule"] == pytest.approx(100.0) and pts[1]["cons_rule"] == pytest.approx(20.0)


def test_fix_summary_by_hand():
    s = R.fix_summary(RES, 50.0, 15.0)
    assert s["n"] == 2 and s["gap_rule"] == pytest.approx(5.0) and s["gap_rule_se"] == pytest.approx(1.0) and s["stops_opt"] == pytest.approx(3.0) and s["tgt_opt"] == pytest.approx(50.0)


def test_height_summary_by_hand():
    s = R.height_summary(RES, "Pkw", "pass", 500)
    assert s["n"] == 2 and s["t_opt"] == pytest.approx(110.0) and s["cons_opt"] == pytest.approx(19.0)


def test_free_vs_const_by_hand():
    rows = [row("x", t_opt=100.0, t_const_best=100.0 + 0.1 * i) for i in range(21)] + [row("x", t_opt=100.0, t_const_best=None, j_const_best=None)]
    out = R.free_vs_const({"rows": rows})
    assert out["n"] == 21                                                                    # nicht erreichbare Fälle zählen nicht
    assert out["mean"] == pytest.approx(1.0) and out["max"] == pytest.approx(2.0) and out["p95"] == pytest.approx(1.9)     # 0 bis 2 % in Schritten von 0,1; Index 0,95 · 20 = 19
    priced = R.free_vs_const({"rows": [row("x", t_opt=100.0, t_const_best=100.0, j_opt=200.0, j_const_best=202.0), row("x", t_opt=100.0, t_const_best=100.0, j_opt=200.0, j_const_best=200.0)]})
    assert priced["mean"] == pytest.approx(0.5) and priced["max"] == pytest.approx(1.0)                                      # die Zielfunktion zählt, nicht die Zeit


def test_cell_exists_for_the_cells_of_the_power_sweep_only():
    s = {"peak": 150.0, "vmax": 130, "seed": 12345}
    assert R.cell_exists(s) and R.cell_exists({**s, "seed": 1}) and R.cell_exists({**s, "peak": 150, "vmax": 110}) and R.cell_exists({**s, "peak": 350.0, "vmax": 180})
    assert not R.cell_exists({**s, "peak": 140.0}) and not R.cell_exists({**s, "vmax": 120}) and not R.cell_exists({**s, "peak": 75.0})


def test_load_results_reads_a_file(tmp_path):
    f = tmp_path / "res.json"
    f.write_text(json.dumps({"meta": {"x": 1}, "rows": [{"sweep": "a", "ü": "ß"}]}, ensure_ascii=False), encoding="utf-8")
    assert R.load_results(f)["rows"][0]["ü"] == "ß" and R.load_results(str(f))["meta"] == {"x": 1}


# ------------------------------------------------------------------ echte Messreihe
@pytest.fixture(scope="module")
def real():
    return R.load_results()


@pytest.fixture(scope="module")
def sweep():
    spec = importlib.util.spec_from_file_location("rtp_sweep_tool", ROOT / "tools" / "sweep.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_real_results_have_the_expected_cases_per_sweep(real):
    counts = {k: len(R.rows_of(real, k)) for k in ("power", "wind", "vehicle", "fix", "height")}
    assert counts == {"power": 5 * 4 * 2 * 10, "wind": 2 * 4 * 5 * 5, "vehicle": 5 * 3 * 9 * 5, "fix": 3 * 4 * 5, "height": 2 * 2 * 4 * 5}
    assert sum(counts.values()) == len(real["rows"]) == real["meta"]["cases"] == 1415


def test_real_results_use_the_sweep_seeds_and_never_the_preset_seed(real, sweep):
    seeds = {r["seed"] for r in real["rows"]}
    assert seeds == set(range(100, 110)) and real["meta"]["seeds"] == [100, 110] and real["meta"]["seeds_small"] == [100, 105]
    assert C.DEFAULT_SEED not in seeds and all(p["seed"] not in seeds for p in C.PRESETS.values())
    assert sweep.SEEDS == tuple(range(100, 110)) and C.DEFAULT_SEED not in sweep.SEEDS


def test_real_results_match_the_sweep_definition(real, sweep):
    cases = sweep.cases()
    assert len(cases) == len(real["rows"])
    for case, r in zip(cases, real["rows"]):
        assert r["sweep"] == case["sweep"] and all(r[k] == case["s"][k] for k in C.SCENARIO_KEYS)
    m = real["meta"]
    assert (m["peaks"], m["vmaxes"], m["tvs"], m["power_tvs"], m["lengths"], m["winds"], m["profiles"], m["stops"], m["rises"], m["vehicles"]) == (
        list(sweep.PEAKS), list(sweep.VMAXES), list(sweep.TVS), list(sweep.POWER_TVS), list(sweep.LENGTHS), list(sweep.WINDS), list(sweep.PROFILES), list(sweep.STOPS), list(sweep.RISES),
        list(C.VEHICLE_ORDER))
    assert sweep.TVS == C.TV_OPTIONS and sweep.POWER_TVS == (C.TV_FAST, C.DEFAULT_TV) and {r["tv"] for r in real["rows"] if r["sweep"] in ("wind", "fix", "height")} == {C.TV_FAST}
    assert R.cell_exists({"peak": sweep.PEAKS[0], "vmax": sweep.VMAXES[0]}) and all(p in sweep.PEAKS for p in (50.0, 100.0, 150.0, 250.0, 350.0))


def test_real_results_are_plausible_in_every_row(real):
    for r in real["rows"]:
        assert all(r[f"t_{k}"] is not None and r[f"t_{k}"] > 0 and r[f"j_{k}"] > 0 and r[f"e_{k}"] > 0 for k in C.METHODS)
        assert R.gap_obj(r, "const_max") >= -0.02 and R.gap_obj(r, "const_best") >= -0.02, r      # das Optimum hat mehr Wahl als jede feste Geschwindigkeit (Rasterrauschen unter 0,02 %)
        assert R.gap_obj(r, "const_best") <= R.gap_obj(r, "const_max") + 0.02 and R.gap_obj(r, "rule") > -0.5          # die Praxisregel kann nur um das Rasterrauschen unter dem Optimum liegen
        assert C.V_MIN <= r["v_best"] <= r["vmax"] and r["v_opt_min"] <= r["v_opt"] <= r["v_opt_max"] <= r["vmax"] and r["cons_opt"] > 0
        assert r["cons_opt"] == pytest.approx(R.cons(r, "opt"), rel=1e-9)
        if r["tv"] >= C.TV_FAST:
            assert r["j_opt"] == pytest.approx(r["t_opt"] / 60.0, rel=1e-3)                                          # Zeit allein: Zielfunktion = Reisezeit in Stunden
        assert (r["tgt_opt"] is None) == (r["stops_opt"] == 0)


def test_real_summaries_run_over_every_cell(real, sweep):
    for p in sweep.PEAKS:
        for v in sweep.VMAXES:
            for tv in sweep.POWER_TVS:
                assert R.power_summary(real, p, v, tv)["n"] == 10
    assert all(R.wind_summary(real, p, prof, w)["n"] == 5 for p in (50.0, 150.0) for prof in sweep.PROFILES for w in sweep.WINDS)
    assert all(R.vehicle_summary(real, v, ln, tv)["n"] == 5 for v in C.VEHICLE_ORDER for ln in sweep.LENGTHS for tv in sweep.TVS)
    assert all(len(R.spectrum(real, v, 600)) == len(C.TV_OPTIONS) for v in C.VEHICLE_ORDER)
    assert all(R.fix_summary(real, p, s)["n"] == 5 for p in (50.0, 150.0, 350.0) for s in sweep.STOPS)
    assert all(R.height_summary(real, v, prof, rise)["n"] == 5 for v in ("Pkw", "Elektro-Lkw") for prof in ("flach", "pass") for rise in sweep.RISES)
    assert R.free_vs_const(real)["n"] == 1415


def test_one_real_row_per_sweep_is_reproduced_by_the_live_computation(real, sweep):
    """Die Messreihe ist aktuell: je Sweep der erste Fall neu gerechnet (Zeiten mit Toleranz gegen Rundung der Plattform)."""
    cases = sweep.cases()
    picks = [next(k for k, c in enumerate(cases) if c["sweep"] == name) for name in ("power", "wind", "vehicle", "fix", "height")]
    picks += [next(k for k, c in enumerate(cases) if c["sweep"] == "power" and c["s"]["tv"] == C.DEFAULT_TV), next(k for k, c in enumerate(cases) if c["sweep"] == "vehicle" and c["s"]["tv"] == 5)]
    for i in picks:
        fresh, stored = sweep.row_of(cases[i]), real["rows"][i]
        for key in ("t_rule", "t_const_max", "t_const_best", "t_opt", "e_rule", "e_opt", "j_rule", "j_opt", "j_const_best"):
            assert fresh[key] == pytest.approx(stored[key], rel=1e-4), (cases[i]["sweep"], cases[i]["s"]["tv"], key)
