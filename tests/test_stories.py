"""Preset-Kriterien: jedes Kriterium kippt einzeln an seiner Schwelle (künstliche Zahlen), `facts_for` liest die richtigen Größen aus einem echten Lauf und der echten Messreihe,
und bei Seed 500 erfüllen alle Presets alle Kriterien (Abnahme; Suche nach einem solchen Seed: tools/preset_search.py)."""
import math
import statistics as st

import numpy as np
import pytest

import rtp_constants as C
import rtp_evaluation as E
import rtp_results as R
import rtp_stories as S

NEUTRAL = dict(gap_rule=6.0, gap_cmax=0.3, gap_free=0.2, v_best=100.0, v_best_ref=100.0, top=130.0, stops_opt=3, stops_ref=3, t_opt=600.0, t_ref=600.0, tgt=50.0, sweep_gap_rule=6.0,
               sweep_v_best=100.0, sweep_free_mean=0.2, sweep_cold_ratio=1.0, sweep_v_wind=100.0, sweep_v_nowind=100.0, sweep_pass_ratio=1.0)

# je Preset: Zahlen, bei denen alle Kriterien erfüllt sind
GOOD = {
    "Standard": {},
    "Langsamer Lader": {},
    "Kälte": dict(t_opt=700.0, stops_opt=5, sweep_cold_ratio=1.2),
    "Gegenwind": dict(v_best=90.0, t_opt=650.0, sweep_v_wind=90.0),
    "Alpenpass": dict(t_opt=603.0, sweep_pass_ratio=1.005),
    "Ohne Tempolimit": dict(top=180.0, v_best=160.0),
    "Elektro-Lkw": dict(top=90.0, v_best=90.0),
}

# (Preset, Kriterium, Größe, Wert genau an der Schwelle (erfüllt), Wert knapp dahinter (verletzt), Zahl im Kriterientext)
THRESHOLDS = [
    ("Standard", "rule_slow", "gap_rule", 2.0, 1.99, "2 %"), ("Standard", "cmax_close", "gap_cmax", 0.6, 0.61, "0,6 %"), ("Standard", "free_small", "gap_free", 0.6, 0.61, "0,6 %"),
    ("Standard", "tgt_low", "tgt", 60.0, 60.1, "60 %"), ("Standard", "sweep_rule", "sweep_gap_rule", 2.0, 1.99, "2 %"), ("Standard", "sweep_free", "sweep_free_mean", 0.5, 0.51, "0,5 %"),
    ("Langsamer Lader", "rule_slow", "gap_rule", 5.0, 4.99, "5 %"), ("Langsamer Lader", "v_below", "v_best", 125.0, 125.1, "5 km/h"), ("Langsamer Lader", "cmax_loses", "gap_cmax", 0.2, 0.19, "0,2 %"),
    ("Langsamer Lader", "sweep_rule", "sweep_gap_rule", 5.0, 4.99, "5 %"), ("Langsamer Lader", "sweep_v", "sweep_v_best", 128.0, 128.1, "2 km/h"),
    ("Kälte", "slower", "t_opt", 649.0, 647.0, "8 %"), ("Kälte", "more_stops", "stops_opt", 4, 3, "einen Stopp mehr"), ("Kälte", "rule_slow", "gap_rule", 2.0, 1.99, "2 %"),
    ("Kälte", "sweep_slower", "sweep_cold_ratio", 1.08, 1.079, "8 %"),
    ("Gegenwind", "v_lower", "v_best", 95.0, 95.1, "5 km/h"), ("Gegenwind", "slower", "t_opt", 631.0, 629.0, "5 %"), ("Gegenwind", "rule_slow", "gap_rule", 5.0, 4.99, "5 %"),
    ("Gegenwind", "sweep_v", "sweep_v_wind", 95.0, 95.1, "5 km/h"),
    ("Alpenpass", "time_close", "t_opt", 605.0, 607.0, "1 %"), ("Alpenpass", "v_same", "v_best", 105.0, 105.1, "5 km/h"), ("Alpenpass", "v_same", "v_best", 95.0, 94.9, "5 km/h"),
    ("Alpenpass", "free_small", "gap_free", 0.6, 0.61, "0,6 %"), ("Alpenpass", "sweep_time", "sweep_pass_ratio", 1.01, 1.011, "1 %"),
    ("Ohne Tempolimit", "v_below", "v_best", 175.0, 175.1, "5 km/h"), ("Ohne Tempolimit", "rule_slow", "gap_rule", 4.0, 3.99, "4 %"), ("Ohne Tempolimit", "v_high", "v_best", 150.0, 149.9, "150 km/h"),
    ("Ohne Tempolimit", "sweep_rule", "sweep_gap_rule", 4.0, 3.99, "4 %"),
    ("Elektro-Lkw", "v_limit", "v_best", 90.0, 89.9, "Tempolimit"), ("Elektro-Lkw", "rule_slow", "gap_rule", 3.0, 2.99, "3 %"), ("Elektro-Lkw", "free_small", "gap_free", 0.6, 0.61, "0,6 %"),
    ("Elektro-Lkw", "sweep_rule", "sweep_gap_rule", 3.0, 2.99, "3 %"),
]


def facts(preset, **over):
    return {**NEUTRAL, **GOOD[preset], **over}


def failing(preset, **over):
    return [cid for cid, _, ok in S.check(preset, facts(preset, **over)) if not ok]


def text_of(preset, cid):
    return next(t for c, t, _ in S.CRITERIA[preset] if c == cid)


# ------------------------------------------------------------------ Aufbau
def test_every_preset_has_criteria_and_every_criterion_has_a_threshold_test():
    assert set(S.CRITERIA) == set(C.PRESET_ORDER) == set(GOOD)
    for name in C.PRESET_ORDER:
        ids = [cid for cid, _, _ in S.CRITERIA[name]]
        assert len(ids) == len(set(ids)) >= 4 and set(ids) == {c for p, c, *_ in THRESHOLDS if p == name}, name


def test_criteria_texts_are_present_german_and_free_of_dashes():
    for name, items in S.CRITERIA.items():
        for cid, text, fn in items:
            assert text and callable(fn) and not any(d in text for d in ("—", "–")) and "Saatwert" not in text, (name, cid)
            assert text.startswith("Messreihe:") == cid.startswith("sweep"), (name, cid)


@pytest.mark.parametrize("preset", C.PRESET_ORDER)
def test_good_facts_pass_every_criterion(preset):
    assert failing(preset) == []


def test_check_returns_id_text_and_a_real_bool():
    out = S.check("Standard", {**NEUTRAL, "gap_rule": np.float64(3.0), "tgt": np.float64(40.0)})
    assert [c for c, _, _ in out] == [c for c, _, _ in S.CRITERIA["Standard"]] and all(type(ok) is bool for _, _, ok in out) and all(isinstance(t, str) for _, t, _ in out)


# ------------------------------------------------------------------ Schwellen
@pytest.mark.parametrize("preset,cid,key,ok,bad,snippet", THRESHOLDS)
def test_each_criterion_flips_alone_at_its_threshold(preset, cid, key, ok, bad, snippet):
    assert failing(preset, **{key: ok}) == [], (preset, cid, "an der Schwelle erfüllt")
    assert failing(preset, **{key: bad}) == [cid], (preset, cid, "knapp dahinter verletzt, alle anderen weiter erfüllt")
    assert snippet in text_of(preset, cid), (preset, cid, "die Schwelle im Text")


def test_ratio_criteria_use_the_reference_run():
    assert failing("Kälte", t_opt=1.08 * 500 + 1.0, t_ref=500.0) == [] and failing("Kälte", t_opt=1.08 * 500 - 1.0, t_ref=500.0) == ["slower"]
    assert failing("Gegenwind", t_opt=1.05 * 800 + 1.0, t_ref=800.0) == [] and failing("Gegenwind", t_opt=1.05 * 800 - 1.0, t_ref=800.0) == ["slower"]
    assert failing("Alpenpass", t_opt=1.01 * 800 - 1.0, t_ref=800.0) == [] and failing("Alpenpass", t_opt=1.01 * 800 + 1.0, t_ref=800.0) == ["time_close"]
    assert failing("Kälte", stops_opt=8, stops_ref=7) == [] and failing("Kälte", stops_opt=7, stops_ref=7) == ["more_stops"] and failing("Kälte", stops_opt=2, stops_ref=3) == ["more_stops"]


def test_relative_speed_criteria_use_the_reference_speed_and_the_limit():
    assert failing("Gegenwind", v_best=75.0, v_best_ref=80.0) == [] and failing("Gegenwind", v_best=76.0, v_best_ref=80.0) == ["v_lower"]
    assert failing("Alpenpass", v_best=85.0, v_best_ref=80.0) == [] and failing("Alpenpass", v_best=86.0, v_best_ref=80.0) == ["v_same"] and failing("Alpenpass", v_best=74.0, v_best_ref=80.0) == ["v_same"]
    assert failing("Gegenwind", sweep_v_wind=70.0, sweep_v_nowind=75.0) == [] and failing("Gegenwind", sweep_v_wind=71.0, sweep_v_nowind=75.0) == ["sweep_v"]
    assert failing("Langsamer Lader", v_best=105.0, top=110.0) == [] and failing("Langsamer Lader", v_best=106.0, top=110.0) == ["v_below"]
    assert failing("Elektro-Lkw", v_best=110.0, top=110.0) == [] and failing("Elektro-Lkw", v_best=109.0, top=110.0) == ["v_limit"]


def test_missing_values_fail_their_criteria():
    nan = float("nan")
    for preset in C.PRESET_ORDER:
        everything_nan = {k: nan for k in NEUTRAL}
        assert [cid for cid, _, ok in S.check(preset, everything_nan) if ok] == [], preset              # ein Vergleich mit NaN ist nie wahr: fehlende Daten erfüllen kein Kriterium
    assert failing("Standard", tgt=nan) == ["tgt_low"] and failing("Langsamer Lader", sweep_v_best=nan) == ["sweep_v"]


# ------------------------------------------------------------------ facts_for gegen echte Läufe
@pytest.fixture(scope="module")
def res():
    return R.load_results()


def mean_gap(rows, key):
    return st.mean(100.0 * (r[f"t_{key}"] / r["t_opt"] - 1.0) for r in rows)


def rows_where(res, sweep, **kw):
    return [r for r in res["rows"] if r["sweep"] == sweep and all(r[k] == v for k, v in kw.items())]


def test_ref_settings_change_only_the_named_levers():
    s = C.PRESETS["Standard"]
    assert S.ref_settings("Kälte", {**s, "temp": -10})["temp"] == 20 and S.ref_settings("Gegenwind", {**s, "headwind": 25})["headwind"] == 0
    assert S.ref_settings("Alpenpass", {**s, "profile": "pass"})["profile"] == "flach"
    assert S.ref_settings("Standard", s) == s and S.ref_settings("Elektro-Lkw", s) == s and set(S.REF_OVERRIDES) == {"Kälte", "Gegenwind", "Alpenpass"}
    k = S.ref_settings("Kälte", {**s, "temp": -10})
    assert {key: v for key, v in k.items() if key != "temp"} == {key: v for key, v in s.items() if key != "temp"}


def test_facts_for_reads_the_live_run_and_the_reference_run(res):
    settings = C.PRESETS["Kälte"]
    run = E.run_live(settings)
    ref = E.run_live(S.ref_settings("Kälte", settings))
    f = S.facts_for("Kälte", run, ref, res)
    p, q = run["plans"], ref["plans"]
    assert f["gap_rule"] == pytest.approx(100 * (p["rule"].time_h / p["opt"].time_h - 1)) and f["gap_cmax"] == pytest.approx(100 * (p["const_max"].time_h / p["opt"].time_h - 1))
    assert f["gap_free"] == pytest.approx(100 * (p["const_best"].time_h / p["opt"].time_h - 1)) and f["top"] == 130.0
    assert f["v_best"] == pytest.approx(float(np.mean(p["const_best"].v))) and f["v_best_ref"] == pytest.approx(float(np.mean(q["const_best"].v)))
    assert f["stops_opt"] == len(p["opt"].stops) and f["stops_ref"] == len(q["opt"].stops)
    assert f["t_opt"] == pytest.approx(60 * p["opt"].time_h) and f["t_ref"] == pytest.approx(60 * q["opt"].time_h) and f["t_opt"] > f["t_ref"]
    tail = p["opt"].stops[1:] or p["opt"].stops
    assert f["tgt"] == pytest.approx(st.mean(s.soc_to for s in tail))


def test_facts_for_reads_the_sweep_independently_of_the_summary_functions(res):
    settings = C.PRESETS["Standard"]                                                     # 150 kW, Tempolimit 130
    run = E.run_live(settings)
    f = S.facts_for("Standard", run, run, res)
    cell = rows_where(res, "power", peak=150.0, vmax=130)
    assert len(cell) == 10 and f["sweep_gap_rule"] == pytest.approx(mean_gap(cell, "rule")) and f["sweep_v_best"] == pytest.approx(st.mean(r["v_best"] for r in cell))
    assert f["sweep_free_mean"] == pytest.approx(st.mean(100.0 * (r["t_const_best"] / r["t_opt"] - 1.0) for r in res["rows"]))
    cold, warm = rows_where(res, "temp", temp=-10, length=600), rows_where(res, "temp", temp=20, length=600)
    assert f["sweep_cold_ratio"] == pytest.approx(st.mean(r["t_opt"] for r in cold) / st.mean(r["t_opt"] for r in warm))
    assert f["sweep_v_wind"] == pytest.approx(st.mean(r["v_best"] for r in rows_where(res, "wind", peak=50.0, profile="huegelig", headwind=15)))
    assert f["sweep_v_nowind"] == pytest.approx(st.mean(r["v_best"] for r in rows_where(res, "wind", peak=50.0, profile="huegelig", headwind=0)))
    assert f["sweep_pass_ratio"] == pytest.approx(st.mean(r["t_opt"] for r in rows_where(res, "height", vehicle="Pkw", profile="pass", rise=0))
                                                  / st.mean(r["t_opt"] for r in rows_where(res, "height", vehicle="Pkw", profile="flach", rise=0)))


def test_facts_for_picks_the_nearest_sweep_cell_for_other_settings(res):
    settings = {**C.PRESETS["Standard"], "peak": 120.0, "vmax": 140}                       # 120 kW liegt näher an 100 als an 150 kW, 140 näher an 130 als an 160 km/h
    run = E.run_live(settings)
    f = S.facts_for("Standard", run, run, res)
    assert f["sweep_gap_rule"] == pytest.approx(mean_gap(rows_where(res, "power", peak=100.0, vmax=130), "rule"))
    tie = {**settings, "peak": 125.0}                                                      # genau in der Mitte zwischen 100 und 150 kW: die kleinere Zelle
    assert S.facts_for("Standard", E.run_live(tie), E.run_live(tie), res)["sweep_gap_rule"] == pytest.approx(mean_gap(rows_where(res, "power", peak=100.0, vmax=130), "rule"))


def test_facts_for_the_truck_uses_the_vehicle_sweep_at_1000_km(res):
    settings = C.PRESETS["Elektro-Lkw"]
    run = E.run_live(settings)
    f = S.facts_for("Elektro-Lkw", run, run, res)
    assert f["sweep_gap_rule"] == pytest.approx(mean_gap(rows_where(res, "vehicle", vehicle="Elektro-Lkw", length=1000), "rule")) and f["top"] == 90.0
    assert f["sweep_gap_rule"] != pytest.approx(S.facts_for("Standard", E.run_live(C.PRESETS["Standard"]), E.run_live(C.PRESETS["Standard"]), res)["sweep_gap_rule"])


def test_facts_for_without_stops_gives_a_nan_target(res):
    settings = {**C.PRESETS["Standard"], "length": 100}
    run = E.run_live(settings)
    assert not run["plans"]["opt"].stops and math.isnan(S.facts_for("Standard", run, run, res)["tgt"])


# ------------------------------------------------------------------ Abnahme: alle Presets bei Seed 500
@pytest.mark.parametrize("preset", C.PRESET_ORDER)
def test_every_preset_meets_every_criterion_at_the_preset_seed(preset, res):
    settings = C.PRESETS[preset]
    assert settings["seed"] == 500
    run = E.run_live(settings)
    ref = E.run_live(S.ref_settings(preset, settings)) if preset in S.REF_OVERRIDES else run
    verdict = S.check(preset, S.facts_for(preset, run, ref, res))
    assert [cid for cid, _, ok in verdict if not ok] == [], [t for _, t, ok in verdict if not ok]
