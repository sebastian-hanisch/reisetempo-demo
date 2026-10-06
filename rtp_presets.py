"""SETTING_SPECS-Permalink-Muster, Fahrzeug- und Szenario-Presets und Zufalls-Seed-Button (Standardmuster aus dem Demo-Portfolio).
Alle Regler sind immer sichtbar mit festen Grenzen: kein ausblendbarer Regler."""
from __future__ import annotations

import random
from dataclasses import dataclass

import streamlit as st

import rtp_constants as C


@dataclass(frozen=True)
class SettingSpec:
    url_param: str
    caster: type
    default: object
    options: tuple | None = None
    lo: float | None = None
    hi: float | None = None
    step: float | None = None


B = C.BASE_SCENARIO
SETTING_SPECS = {
    "vehicle_select": SettingSpec("veh", str, B["vehicle"], C.VEHICLE_ORDER),
    "cap_slider": SettingSpec("cap", float, B["cap"], None, C.CAP_MIN, C.CAP_MAX, C.CAP_STEP),
    "mass_slider": SettingSpec("mass", float, B["mass"], None, C.MASS_MIN, C.MASS_MAX, C.MASS_STEP),
    "cda_slider": SettingSpec("cda", float, B["cda"], None, C.CDA_MIN, C.CDA_MAX, C.CDA_STEP),
    "cr_slider": SettingSpec("cr", float, B["cr"], None, C.CR_MIN, C.CR_MAX, C.CR_STEP),
    "peak_slider": SettingSpec("peak", float, B["peak"], None, C.PEAK_MIN, C.PEAK_MAX, C.PEAK_STEP),
    "aux_slider": SettingSpec("aux", float, B["aux"], None, C.AUX_MIN, C.AUX_MAX, C.AUX_STEP),
    "curve_select": SettingSpec("curve", str, B["curve"], C.CURVE_NAMES),
    "loss_slider": SettingSpec("loss", float, B["loss"], None, C.LOSS_MIN, C.LOSS_MAX, C.LOSS_STEP),
    "stop_slider": SettingSpec("stop", float, B["stop_min"], None, C.STOP_MIN, C.STOP_MAX, C.STOP_STEP),
    "length_slider": SettingSpec("len", int, B["length"], None, C.LENGTH_MIN, C.LENGTH_MAX, C.LENGTH_STEP),
    "profile_select": SettingSpec("prof", str, B["profile"], C.PROFILE_TYPES),
    "rise_slider": SettingSpec("rise", int, B["rise"], None, C.RISE_MIN, C.RISE_MAX, C.RISE_STEP),
    "wind_slider": SettingSpec("wind", int, B["headwind"], None, C.WIND_MIN, C.WIND_MAX, C.WIND_STEP),
    "windmode_select": SettingSpec("wmode", str, B["wind_mode"], C.WIND_MODES),
    "seed_input": SettingSpec("seed", int, B["seed"], None, C.SEED_MIN, C.SEED_MAX, 1),
    "tv_select": SettingSpec("tv", int, B["tv"], C.TV_OPTIONS),
    "price_slider": SettingSpec("price", float, B["price"], None, C.PRICE_MIN, C.PRICE_MAX, C.PRICE_STEP),
    "soc0_slider": SettingSpec("soc0", int, B["soc0"], None, C.SOC0_MIN, C.SOC0_MAX, C.SOC0_STEP),
    "sminstop_slider": SettingSpec("smins", int, B["smin_stop"], None, C.SMIN_STOP_MIN, C.SMIN_STOP_MAX, 1),
    "smindest_slider": SettingSpec("smind", int, B["smin_dest"], None, C.SMIN_DEST_MIN, C.SMIN_DEST_MAX, 1),
    "vmax_slider": SettingSpec("vmax", int, B["vmax"], None, C.VMAX_MIN, C.VMAX_MAX, C.VMAX_STEP),
    "view_select": SettingSpec("view", str, C.DEFAULT_VIEW, C.VIEW_OPTIONS),
    "sweeptv_select": SettingSpec("stv", int, C.DEFAULT_TV, (C.DEFAULT_TV, C.TV_FAST)),
}
# Szenario-Schlüssel -> Widget-Schlüssel (view_select und sweeptv_select sind reine Anzeigewahl und gehören nicht zum Szenario)
PRESET_KEYS = {"vehicle": "vehicle_select", "cap": "cap_slider", "mass": "mass_slider", "cda": "cda_slider", "cr": "cr_slider", "peak": "peak_slider", "aux": "aux_slider", "curve": "curve_select",
               "loss": "loss_slider", "stop_min": "stop_slider", "length": "length_slider", "profile": "profile_select", "rise": "rise_slider", "seed": "seed_input", "headwind": "wind_slider",
               "wind_mode": "windmode_select", "tv": "tv_select", "price": "price_slider", "soc0": "soc0_slider", "smin_stop": "sminstop_slider", "smin_dest": "smindest_slider", "vmax": "vmax_slider"}
VEHICLE_KEYS = ("cap", "mass", "cda", "cr", "peak", "aux", "curve", "vmax")


def snap(value, lo, hi, step):
    """Auf das Reglerraster einrasten (Gleichstand: der kleinere Wert) und auf die Grenzen begrenzen; Rundung auf 6 Stellen gegen Gleitkomma-Rauschen."""
    v = max(lo, min(hi, value))
    q, r = divmod(round((v - lo) / step * 1e6), 1_000_000)
    k = q + (1 if 2 * r > 1_000_000 else 0)
    return round(min(hi, lo + k * step), 6)


def init_session_state_defaults():
    for state_key, spec in SETTING_SPECS.items():
        if state_key not in st.session_state:
            st.session_state[state_key] = spec.default


def bounds(state_key):
    spec = SETTING_SPECS[state_key]
    return spec.lo, spec.hi


def _coerce(spec: SettingSpec, raw):
    value = spec.caster(raw)
    if spec.options is not None:
        return value if value in spec.options else None
    value = snap(value, spec.lo, spec.hi, spec.step)
    return spec.caster(value) if spec.caster is int else value


def load_permalink_settings():
    """Einmal je Sitzung: Werte aus der Adresszeile übernehmen, auf Grenzen und Raster begrenzt."""
    if "permalink_loaded" in st.session_state:
        return
    qp = st.query_params
    for state_key, spec in SETTING_SPECS.items():
        if spec.url_param in qp:
            try:
                value = _coerce(spec, qp[spec.url_param])
            except (ValueError, TypeError):
                continue
            if value is not None:
                st.session_state[state_key] = value
    st.session_state["permalink_loaded"] = True


def sync_query_params(values):
    """`values`: {Widget-Schlüssel: aktueller Wert}; die Adresszeile spiegelt die Konfiguration."""
    try:
        for state_key, value in values.items():
            st.query_params[SETTING_SPECS[state_key].url_param] = str(value)
    except Exception:
        pass


def apply_preset(name):
    for key, state_key in PRESET_KEYS.items():
        st.session_state[state_key] = C.PRESETS[name][key]


def apply_vehicle():
    """Rückruf der Fahrzeugwahl: setzt die Fahrzeugparameter (und das Tempolimit) auf die Werte des gewählten Presets; alle bleiben danach einzeln einstellbar."""
    v = C.vehicle_scenario(st.session_state["vehicle_select"])
    for key in VEHICLE_KEYS:
        st.session_state[PRESET_KEYS[key]] = v[key]


def randomize_seed():
    st.session_state["seed_input"] = random.randint(C.SEED_MIN, C.SEED_MAX)


def settings_from_state(values: dict) -> dict:
    """Szenario-Wörterbuch (Schlüssel C.SCENARIO_KEYS) aus den Widget-Werten."""
    out = {key: values[state_key] for key, state_key in PRESET_KEYS.items()}
    for key in ("cap", "mass", "cda", "cr", "peak", "aux", "loss", "stop_min", "price"):
        out[key] = float(out[key])
    for key in ("length", "rise", "seed", "headwind", "tv", "soc0", "smin_stop", "smin_dest", "vmax"):
        out[key] = int(out[key])
    out["curve"], out["profile"], out["wind_mode"], out["vehicle"] = str(out["curve"]), str(out["profile"]), str(out["wind_mode"]), str(out["vehicle"])
    return out
