"""End-to-end-Rauchtest über Streamlits AppTest: lädt app.py mit den Standardeinstellungen, klickt jeden Button, fährt jeden Regler an seine Grenzen, wählt jede Option jeder Auswahl und prüft,
dass kein Python-Fehler auftritt (insbesondere `StreamlitDuplicateElementId` bei Diagrammen mit gleichem Inhalt und `StreamlitAPIException` bei Reglern mit berechneten Grenzen).
Dazu: Presets setzen alle Widgets, Fahrzeugwahl setzt die Fahrzeugparameter, der Zeitwert wählt den Punkt der Spanne, Permalink-Rundlauf, nicht erreichbares Ziel zeigt eine Warnung statt eines Fehlers."""
import os

import pytest
from streamlit.testing.v1 import AppTest

import rtp_constants as C
from rtp_presets import PRESET_KEYS

APP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")
TIMEOUT = 180


def _fresh_app() -> AppTest:
    at = AppTest.from_file(APP_PATH, default_timeout=TIMEOUT)
    at.run(timeout=TIMEOUT)
    assert not at.exception, [str(e) for e in at.exception]
    return at


def test_app_loads_and_shows_four_methods_and_the_sweep_summary():
    at = _fresh_app()
    labels = [m.label for m in at.metric]
    for key in C.METHODS:
        assert C.METHOD_LABELS[key] in labels
    assert "Freie gegen konstante" in labels


def test_every_preset_button_loads_its_scenario_and_renders():
    for name in C.PRESET_ORDER:
        at = _fresh_app()
        at.button(key=f"preset_{name}").click().run(timeout=TIMEOUT)
        assert not at.exception, (name, [str(e) for e in at.exception])
        for key, state_key in PRESET_KEYS.items():
            assert at.session_state[state_key] == C.PRESETS[name][key], (name, key)


def test_every_button_click_does_not_raise():
    labels = [b.label for b in _fresh_app().button]
    assert labels, "keine Buttons gefunden"
    for index, label in enumerate(labels):
        at = _fresh_app()
        at.button[index].click().run(timeout=TIMEOUT)
        assert not at.exception, (label, [str(e) for e in at.exception])


def test_every_slider_at_its_min_and_max_does_not_raise():
    labels = [s.label for s in _fresh_app().slider]
    assert labels, "keine Slider gefunden"
    for index, label in enumerate(labels):
        for edge in ("min", "max"):
            at = _fresh_app()
            slider = at.slider[index]
            value = slider.min if edge == "min" else slider.max
            if isinstance(slider.value, int):
                value = int(value)
            slider.set_value(value).run(timeout=TIMEOUT)
            assert not at.exception, (label, edge, [str(e) for e in at.exception])


@pytest.mark.parametrize("key,options", [("vehicle_select", C.VEHICLE_ORDER), ("curve_select", C.CURVE_NAMES)])
def test_every_selectbox_option_does_not_raise(key, options):
    for option in options:
        at = _fresh_app()
        at.selectbox(key=key).select(option).run(timeout=TIMEOUT)
        assert not at.exception, (key, option, [str(e) for e in at.exception])


@pytest.mark.parametrize("key,options", [("profile_select", C.PROFILE_TYPES), ("windmode_select", C.WIND_MODES)])
def test_every_select_slider_option_does_not_raise(key, options):
    for option in options:
        at = _fresh_app()
        at.select_slider(key=key).set_value(option).run(timeout=TIMEOUT)
        assert not at.exception, (key, option, [str(e) for e in at.exception])


@pytest.mark.parametrize("key,options", [("view_select", C.VIEW_OPTIONS), ("sweeptv_select", (C.DEFAULT_TV, C.TV_FAST))])
def test_every_radio_option_does_not_raise(key, options):
    for option in options:
        at = _fresh_app()
        at.radio(key=key).set_value(option).run(timeout=TIMEOUT)
        assert not at.exception, (key, option, [str(e) for e in at.exception])


def test_every_time_value_does_not_raise_and_changes_the_metrics():
    shown = {}
    for tv in C.TV_OPTIONS:
        at = _fresh_app()
        at.select_slider(key="tv_select").set_value(tv).run(timeout=TIMEOUT)
        assert not at.exception, (tv, [str(e) for e in at.exception])
        shown[tv] = {m.label: m.value for m in at.metric}[C.METHOD_LABELS["opt"]]
    assert shown[C.TV_FAST].endswith("min") and all(v.endswith("€") for tv, v in shown.items() if tv != C.TV_FAST)          # Zeit allein: Reisezeit, sonst Kosten in Euro
    assert len(set(shown.values())) == len(C.TV_OPTIONS)


def test_the_time_value_drives_the_optimum_from_economical_to_fast():
    speeds = {}
    for tv in (min(C.TV_OPTIONS), C.DEFAULT_TV, C.TV_FAST):
        at = _fresh_app()
        at.select_slider(key="tv_select").set_value(tv).run(timeout=TIMEOUT)
        assert not at.exception
        table = next(df for df in at.dataframe if "Verfahren" in df.value.columns and "Ø km/h" in df.value.columns).value
        speeds[tv] = float(table.loc[table["Verfahren"] == C.METHOD_LABELS["opt"], "Ø km/h"].iloc[0])
    assert speeds[min(C.TV_OPTIONS)] < 65.0 < speeds[C.DEFAULT_TV] < speeds[C.TV_FAST] and speeds[C.TV_FAST] > 125.0


def test_vehicle_selection_applies_the_vehicle_parameters():
    for name in C.VEHICLE_ORDER:
        at = _fresh_app()
        at.selectbox(key="vehicle_select").select(name).run(timeout=TIMEOUT)
        v = C.VEHICLES[name]
        assert at.session_state["cap_slider"] == v["cap"]
        assert at.session_state["mass_slider"] == v["mass"]
        assert at.session_state["peak_slider"] == v["peak"]
        assert at.session_state["vmax_slider"] == v["vmax"]
        assert at.session_state["curve_select"] == v["curve"]


def test_permalink_roundtrip_snaps_and_clips_values():
    at = AppTest.from_file(APP_PATH, default_timeout=TIMEOUT)
    at.query_params["len"] = "720"        # liegt zwischen den Rasterstufen 700 und 750: rastet auf 700 ein
    at.query_params["peak"] = "5000"      # über der Grenze: wird auf 800 begrenzt
    at.query_params["prof"] = "pass"
    at.query_params["wmode"] = "unsinn"   # ungültige Option: Standard bleibt
    at.query_params["cda"] = "abc"        # nicht lesbar: Standard bleibt
    at.query_params["tv"] = "7"           # gibt es nicht als Zeitwert: Standard bleibt
    at.run(timeout=TIMEOUT)
    assert not at.exception, [str(e) for e in at.exception]
    assert at.session_state["length_slider"] == 700
    assert at.session_state["peak_slider"] == C.PEAK_MAX
    assert at.session_state["profile_select"] == "pass"
    assert at.session_state["windmode_select"] == C.DEFAULT_WIND_MODE
    assert at.session_state["cda_slider"] == C.BASE_SCENARIO["cda"] and at.session_state["tv_select"] == C.DEFAULT_TV


def test_permalink_roundtrip_restores_the_time_value_and_the_price():
    at = AppTest.from_file(APP_PATH, default_timeout=TIMEOUT)
    at.query_params["tv"] = "5"
    at.query_params["price"] = "0.75"
    at.run(timeout=TIMEOUT)
    assert not at.exception, [str(e) for e in at.exception]
    assert at.session_state["tv_select"] == 5 and at.session_state["price_slider"] == pytest.approx(0.75)
    qp = at.query_params
    assert str(qp["tv"]) in ("5", "['5']") and "0.75" in str(qp["price"])


def test_unreachable_trip_shows_a_warning_and_no_exception():
    at = _fresh_app()
    at.slider(key="cap_slider").set_value(C.CAP_MIN)
    at.slider(key="soc0_slider").set_value(C.SOC0_MIN)
    at.slider(key="smindest_slider").set_value(C.SMIN_DEST_MAX)
    at.slider(key="length_slider").set_value(C.LENGTH_MAX)
    at.run(timeout=TIMEOUT)
    assert not at.exception, [str(e) for e in at.exception]
