"""Permalink-Einrasten, Fahrzeug- und Szenario-Presets, Regler-Spezifikationen und Konstanten-Konsistenz (ersetzt das Gerüst)."""
import random
from types import SimpleNamespace

import pytest

import rtp_constants as C
import rtp_presets as PR

DASHES = ("—", "–")


@pytest.fixture
def fake_st(monkeypatch):
    """Ersatz für streamlit in rtp_presets: Sitzungszustand und Adressparameter als gewöhnliche Wörterbücher."""
    fake = SimpleNamespace(session_state={}, query_params={})
    monkeypatch.setattr(PR, "st", fake)
    return fake


# ------------------------------------------------------------------ snap
def test_snap_rounds_to_the_grid_with_ties_going_to_the_smaller_value():
    assert PR.snap(12.4, 0, 100, 5) == 10 and PR.snap(12.5, 0, 100, 5) == 10 and PR.snap(12.6, 0, 100, 5) == 15 and PR.snap(15.0, 0, 100, 5) == 15
    assert PR.snap(50, -1000, 1000, 100) == 0 and PR.snap(51, -1000, 1000, 100) == 100                      # Gleichstand bei −950: der kleinere, −1000 + 10 · 100
    assert PR.snap(620, 100, 1500, 50) == 600 and PR.snap(625, 100, 1500, 50) == 600 and PR.snap(626, 100, 1500, 50) == 650


def test_snap_clamps_to_the_bounds():
    assert PR.snap(-5, 0, 100, 5) == 0 and PR.snap(105, 0, 100, 5) == 100 and PR.snap(1e9, 20.0, 700.0, 1.0) == 700.0 and PR.snap(-1e9, 20.0, 700.0, 1.0) == 20.0
    assert PR.snap(100, 0, 100, 60) == 100                                                                     # Rundung nach oben würde 120 ergeben: auf die Grenze begrenzt


def test_snap_with_float_steps_is_free_of_rounding_noise():
    assert PR.snap(0.62, 0.40, 8.00, 0.05) == 0.6 and PR.snap(0.675, 0.40, 8.00, 0.05) == 0.65 and PR.snap(0.676, 0.40, 8.00, 0.05) == 0.7       # Gleichstand bei 5,5 Schritten
    assert PR.snap(0.0102, 0.004, 0.015, 0.0005) == 0.01 and PR.snap(0.0138, 0.004, 0.015, 0.0005) == 0.014
    assert PR.snap(2.0000001, 0.3, 10.0, 0.1) == 2.0 and PR.snap(77.4, 20.0, 700.0, 1.0) == 77.0


def test_snap_leaves_grid_values_unchanged():
    for lo, hi, step in ((C.CAP_MIN, C.CAP_MAX, C.CAP_STEP), (C.CDA_MIN, C.CDA_MAX, C.CDA_STEP), (C.CR_MIN, C.CR_MAX, C.CR_STEP), (C.AUX_MIN, C.AUX_MAX, C.AUX_STEP),
                         (C.LENGTH_MIN, C.LENGTH_MAX, C.LENGTH_STEP), (C.TEMP_MIN, C.TEMP_MAX, C.TEMP_STEP)):
        for k in range(int(round((hi - lo) / step)) + 1):
            v = round(lo + k * step, 6)
            assert PR.snap(v, lo, hi, step) == v, (lo, step, k)


# ------------------------------------------------------------------ Regler-Spezifikationen
def test_setting_specs_cover_every_scenario_key_and_the_view():
    assert set(PR.PRESET_KEYS) == set(C.SCENARIO_KEYS)
    assert set(PR.PRESET_KEYS.values()) | {"view_select"} == set(PR.SETTING_SPECS) and len(PR.PRESET_KEYS) == len(set(PR.PRESET_KEYS.values()))
    assert len({s.url_param for s in PR.SETTING_SPECS.values()}) == len(PR.SETTING_SPECS)                    # Adressparameter eindeutig


def test_setting_defaults_are_the_base_scenario_inside_their_bounds():
    for key, state_key in PR.PRESET_KEYS.items():
        spec = PR.SETTING_SPECS[state_key]
        assert spec.default == C.BASE_SCENARIO[key], key
        check_value(spec, spec.default, key)
    assert PR.SETTING_SPECS["view_select"].default == C.DEFAULT_VIEW and C.DEFAULT_VIEW in PR.SETTING_SPECS["view_select"].options


def check_value(spec, value, label):
    if spec.options is not None:
        assert value in spec.options, label
    else:
        assert spec.lo <= value <= spec.hi, label
        assert type(spec.caster(value)) is spec.caster


def test_bounds_come_from_the_spec():
    assert PR.bounds("cap_slider") == (C.CAP_MIN, C.CAP_MAX) and PR.bounds("seed_input") == (C.SEED_MIN, C.SEED_MAX) and PR.bounds("vehicle_select") == (None, None)


# ------------------------------------------------------------------ Presets
def test_every_preset_is_complete_and_inside_the_bounds():
    assert set(C.PRESET_ORDER) == set(C.PRESETS) == set(C.PRESET_HELP) and len(C.PRESET_ORDER) == 7
    for name, p in C.PRESETS.items():
        assert set(p) == set(C.SCENARIO_KEYS), name
        for key, state_key in PR.PRESET_KEYS.items():
            check_value(PR.SETTING_SPECS[state_key], p[key], (name, key))
        assert p["curve"] in C.CURVES and p["vehicle"] in C.VEHICLES and C.SEED_MIN <= p["seed"] <= C.SEED_MAX


def test_every_vehicle_preset_is_inside_the_bounds():
    assert set(C.VEHICLES) == set(C.VEHICLE_ORDER) == set(C.VEHICLE_HELP)
    for name in C.VEHICLE_ORDER:
        v = C.vehicle_scenario(name)
        assert set(v) == {"vehicle", "cap", "mass", "cda", "cr", "peak", "aux", "curve", "vmax"} and v["vehicle"] == name
        for key in PR.VEHICLE_KEYS:
            check_value(PR.SETTING_SPECS[PR.PRESET_KEYS[key]], v[key], (name, key))
        assert v["vmax"] % C.V_STEP == 0 and v["curve"] in C.CURVES


def test_every_preset_and_vehicle_value_lies_on_the_slider_grid():
    """Ein Wert zwischen zwei Rasterstellen würde vom Regler beim ersten Bedienen verschoben; die Voreinstellung muss auf dem Raster liegen."""
    off = []
    scenarios = [(n, p) for n, p in C.PRESETS.items()] + [(n, C.vehicle_scenario(n)) for n in C.VEHICLE_ORDER]
    for name, p in scenarios:
        for key, value in p.items():
            spec = PR.SETTING_SPECS[PR.PRESET_KEYS[key]]
            if spec.options is None and PR.snap(value, spec.lo, spec.hi, spec.step) != pytest.approx(value, abs=1e-9):
                off.append((name, key, value))
    assert off == []


def test_preset_seed_lies_outside_the_measurement_seeds():
    assert {p["seed"] for p in C.PRESETS.values()} == {500} and C.DEFAULT_SEED == 500 and not any(100 <= p["seed"] < 110 for p in C.PRESETS.values())


def test_standard_preset_is_the_base_scenario_and_the_others_change_what_they_are_named_for():
    std = C.PRESETS["Standard"]
    assert std == C.BASE_SCENARIO and std["vehicle"] == C.DEFAULT_VEHICLE
    changed = {n: sorted(k for k in std if C.PRESETS[n][k] != std[k]) for n in C.PRESET_ORDER if n != "Standard"}
    assert changed["Langsamer Lader"] == ["peak", "vmax"] and changed["Kälte"] == ["temp"] and changed["Gegenwind"] == ["headwind", "peak", "vmax"] and changed["Alpenpass"] == ["profile"]
    assert changed["Ohne Tempolimit"] == ["vmax"]
    assert set(changed["Elektro-Lkw"]) == {"vehicle", "cap", "mass", "cda", "cr", "peak", "aux", "vmax", "length"}
    assert C.PRESETS["Langsamer Lader"]["peak"] == 50.0 and C.PRESETS["Kälte"]["temp"] == -10 and C.PRESETS["Gegenwind"]["headwind"] == 25 and C.PRESETS["Alpenpass"]["profile"] == "pass"
    assert C.PRESETS["Ohne Tempolimit"]["vmax"] == 180 and C.PRESETS["Elektro-Lkw"]["length"] == 1000 and C.PRESETS["Elektro-Lkw"]["vmax"] == 90


def test_apply_preset_writes_every_widget_key(fake_st):
    for name in C.PRESET_ORDER:
        fake_st.session_state.clear()
        PR.apply_preset(name)
        assert set(fake_st.session_state) == set(PR.PRESET_KEYS.values()), name
        assert all(fake_st.session_state[sk] == C.PRESETS[name][key] for key, sk in PR.PRESET_KEYS.items()), name


def test_apply_preset_overwrites_earlier_values(fake_st):
    PR.apply_preset("Kälte")
    PR.apply_preset("Standard")
    assert fake_st.session_state["temp_slider"] == 20 and fake_st.session_state["peak_slider"] == 150.0


def test_apply_vehicle_sets_only_the_vehicle_parameters(fake_st):
    fake_st.session_state.update({"vehicle_select": "Elektro-Lkw", "length_slider": 333, "temp_slider": -5, "peak_slider": 1.0})
    PR.apply_vehicle()
    s = fake_st.session_state
    assert (s["cap_slider"], s["mass_slider"], s["cda_slider"], s["cr_slider"], s["peak_slider"], s["aux_slider"], s["curve_select"], s["vmax_slider"]) == (600.0, 24000.0, 5.5, 0.006, 350.0, 5.0, "Standard", 90)
    assert s["length_slider"] == 333 and s["temp_slider"] == -5 and set(s) == {"vehicle_select", "length_slider", "temp_slider", "peak_slider", "cap_slider", "mass_slider", "cda_slider", "cr_slider",
                                                                              "aux_slider", "curve_select", "vmax_slider"}


def test_init_session_state_defaults_does_not_overwrite(fake_st):
    fake_st.session_state["cap_slider"] = 99.0
    PR.init_session_state_defaults()
    assert fake_st.session_state["cap_slider"] == 99.0 and fake_st.session_state["peak_slider"] == 150.0 and set(fake_st.session_state) == set(PR.SETTING_SPECS)


def test_randomize_seed_draws_from_the_seed_range(fake_st, monkeypatch):
    seen = []
    monkeypatch.setattr(PR.random, "randint", lambda a, b: seen.append((a, b)) or 4321)
    PR.randomize_seed()
    assert fake_st.session_state["seed_input"] == 4321 and seen == [(C.SEED_MIN, C.SEED_MAX)]
    monkeypatch.undo()
    random.seed(1)
    PR.st = fake_st
    PR.randomize_seed()
    assert C.SEED_MIN <= fake_st.session_state["seed_input"] <= C.SEED_MAX


def test_settings_from_state_has_the_scenario_keys_and_the_types():
    values = {sk: C.BASE_SCENARIO[key] for key, sk in PR.PRESET_KEYS.items()}
    values.update({"cap_slider": 77, "length_slider": 600.0, "vmax_slider": 130.0, "wind_slider": 15.0, "seed_input": 500.0, "stop_slider": 5, "profile_select": "pass"})
    out = PR.settings_from_state(values)
    assert set(out) == set(C.SCENARIO_KEYS)
    for key in ("cap", "mass", "cda", "cr", "peak", "aux", "loss", "stop_min"):
        assert type(out[key]) is float, key
    for key in ("length", "rise", "seed", "headwind", "temp", "soc0", "smin_stop", "smin_dest", "vmax"):
        assert type(out[key]) is int, key
    assert out["cap"] == 77.0 and out["length"] == 600 and out["headwind"] == 15 and out["stop_min"] == 5.0 and out["profile"] == "pass" and out["vehicle"] == "Pkw"


# ------------------------------------------------------------------ Permalink
def test_permalink_values_are_snapped_and_invalid_ones_ignored(fake_st):
    fake_st.query_params.update({"len": "620", "veh": "Pkw", "prof": "unbekannt", "cap": "abc", "peak": "55", "temp": "-100", "seed": "500.0", "wmode": "wechselnd", "cda": "0.624"})
    PR.load_permalink_settings()
    s = fake_st.session_state
    assert s["length_slider"] == 600 and s["vehicle_select"] == "Pkw" and "profile_select" not in s and "cap_slider" not in s
    assert s["peak_slider"] == 50.0 and s["temp_slider"] == C.TEMP_MIN and "seed_input" not in s and s["windmode_select"] == "wechselnd" and s["cda_slider"] == pytest.approx(0.62)
    assert type(s["length_slider"]) is int and type(s["peak_slider"]) is float and s["permalink_loaded"] is True


def test_permalink_is_read_only_once_per_session(fake_st):
    fake_st.query_params.update({"len": "300"})
    PR.load_permalink_settings()
    fake_st.query_params.update({"len": "900"})
    PR.load_permalink_settings()
    assert fake_st.session_state["length_slider"] == 300


def test_sync_query_params_mirrors_the_values_and_swallows_errors(fake_st):
    PR.sync_query_params({"length_slider": 600, "profile_select": "pass", "cap_slider": 77.5})
    assert fake_st.query_params == {"len": "600", "prof": "pass", "cap": "77.5"}

    class Broken(dict):
        def __setitem__(self, k, v):
            raise RuntimeError("nicht verfügbar")

    fake_st.query_params = Broken()
    PR.sync_query_params({"length_slider": 600})                                               # kein Fehler


# ------------------------------------------------------------------ Konstanten
def test_curves_start_at_zero_end_at_full_and_have_a_peak_of_one():
    assert C.DEFAULT_CURVE in C.CURVES and C.CURVE_NAMES == tuple(C.CURVES)
    for name, pts in C.CURVES.items():
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        assert xs[0] == 0.0 and xs[-1] == 1.0 and all(b > a for a, b in zip(xs, xs[1:])) and max(ys) == 1.0 and all(0 < y <= 1.0 for y in ys), name
        assert ys[-1] < 0.2 and ys[-1] == min(ys), name                                         # am Ende der Kurve fast keine Leistung mehr


def test_labels_colors_and_options_are_complete():
    assert set(C.METHOD_LABELS) == set(C.METHODS) == set(C.METHOD_COLORS) and set(C.VIEW_OPTIONS) <= set(C.METHODS) and C.DEFAULT_VIEW in C.VIEW_OPTIONS
    assert set(C.PROFILE_LABELS) == set(C.PROFILE_TYPES) and C.DEFAULT_PROFILE in C.PROFILE_TYPES and C.DEFAULT_WIND_MODE in C.WIND_MODES and C.DEFAULT_VEHICLE in C.VEHICLES
    assert C.V_MIN % C.V_STEP == 0 and C.VMAX_MIN % C.V_STEP == 0 and C.VMAX_STEP % C.V_STEP == 0 and C.RULE_CHARGE_TO == 80.0


def test_visible_texts_have_no_dashes_and_no_banned_words():
    texts = list(C.PRESET_HELP.values()) + list(C.VEHICLE_HELP.values()) + list(C.PROFILE_LABELS.values()) + list(C.METHOD_LABELS.values()) + list(C.PRESET_ORDER) + list(C.VEHICLE_ORDER)
    for t in texts:
        assert not any(d in t for d in DASHES), t
        assert "Saatwert" not in t and "Gedankenstrich" not in t, t
    assert all(C.PRESET_HELP[n] for n in C.PRESET_ORDER)


def test_format_helpers():
    assert C.fmt_hm(312) == "5 h 12 min" and C.fmt_hm(65.4) == "1 h 05 min" and C.fmt_hm(59.6) == "1 h 00 min" and C.fmt_hm(0) == "0 h 00 min"
    assert C.fmt_min(12.345) == "12 min" and C.fmt_min(12.345, 1) == "12.3 min"
