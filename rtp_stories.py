"""Abnahmekriterien der Presets: jedes Preset erzählt eine Geschichte, die am gezeigten Lauf UND an der Messreihe überprüfbar ist.

Reine Funktionen einfacher Zahlen (`check`), damit Tests sie mit künstlichen Werten einzeln an ihrer Schwelle kippen können; `facts_for` baut die Zahlen aus einer Live-Rechnung, einer
Vergleichsrechnung (`ref`) und der Ergebnisdatei. `tools/preset_search.py` sucht damit einen Seed außerhalb der Messreihen-Seeds, bei dem alle Kriterien aller Presets gelten."""
from __future__ import annotations

import rtp_evaluation as E
import rtp_results as R

NAN = float("nan")

# Vergleichsrechnung je Preset: dieselben Einstellungen mit diesen Änderungen (ohne Eintrag: der Lauf selbst)
REF_OVERRIDES = {"Kälte": {"temp": 20}, "Gegenwind": {"headwind": 0}, "Alpenpass": {"profile": "flach"}}

CRITERIA = {
    "Standard": [
        ("rule_slow", "Die Praxisregel braucht mindestens 2 % länger als das Optimum", lambda f: f["gap_rule"] >= 2.0),
        ("cmax_close", "Das Tempolimit mit optimalem Laden liegt höchstens 0,6 % über dem Optimum", lambda f: f["gap_cmax"] <= 0.6),
        ("free_small", "Eine freie Geschwindigkeit je Abschnitt bringt höchstens 0,6 % gegenüber der besten konstanten", lambda f: f["gap_free"] <= 0.6),
        ("tgt_low", "Die Stopps des Optimums laden im Mittel auf höchstens 60 %", lambda f: f["tgt"] <= 60.0),
        ("sweep_rule", "Messreihe: die Praxisregel braucht im Mittel mindestens 2 % länger als das Optimum", lambda f: f["sweep_gap_rule"] >= 2.0),
        ("sweep_free", "Messreihe: eine freie Geschwindigkeit bringt im Mittel höchstens 0,5 % gegenüber der besten konstanten", lambda f: f["sweep_free_mean"] <= 0.5),
    ],
    "Langsamer Lader": [
        ("rule_slow", "Die Praxisregel braucht mindestens 5 % länger als das Optimum", lambda f: f["gap_rule"] >= 5.0),
        ("v_below", "Die beste konstante Geschwindigkeit liegt mindestens 5 km/h unter dem Tempolimit", lambda f: f["v_best"] <= f["top"] - 5.0),
        ("cmax_loses", "Das Tempolimit mit optimalem Laden liegt mindestens 0,2 % über dem Optimum", lambda f: f["gap_cmax"] >= 0.2),
        ("sweep_rule", "Messreihe: die Praxisregel braucht im Mittel mindestens 5 % länger als das Optimum", lambda f: f["sweep_gap_rule"] >= 5.0),
        ("sweep_v", "Messreihe: die beste konstante Geschwindigkeit liegt im Mittel mindestens 2 km/h unter dem Tempolimit", lambda f: f["sweep_v_best"] <= f["top"] - 2.0),
    ],
    "Kälte": [
        ("slower", "Das Optimum braucht mindestens 8 % länger als bei 20 °C", lambda f: f["t_opt"] >= 1.08 * f["t_ref"]),
        ("more_stops", "Das Optimum macht mindestens einen Stopp mehr als bei 20 °C", lambda f: f["stops_opt"] >= f["stops_ref"] + 1),
        ("rule_slow", "Die Praxisregel braucht mindestens 2 % länger als das Optimum", lambda f: f["gap_rule"] >= 2.0),
        ("sweep_slower", "Messreihe: bei −10 °C braucht das Optimum im Mittel mindestens 8 % länger als bei 20 °C (600 km)", lambda f: f["sweep_cold_ratio"] >= 1.08),
    ],
    "Gegenwind": [
        ("v_lower", "Die beste konstante Geschwindigkeit liegt mindestens 5 km/h unter der ohne Wind", lambda f: f["v_best"] <= f["v_best_ref"] - 5.0),
        ("slower", "Das Optimum braucht mindestens 5 % länger als ohne Wind", lambda f: f["t_opt"] >= 1.05 * f["t_ref"]),
        ("rule_slow", "Die Praxisregel braucht mindestens 5 % länger als das Optimum", lambda f: f["gap_rule"] >= 5.0),
        ("sweep_v", "Messreihe: bei 15 km/h Gegenwind liegt die beste Geschwindigkeit im Mittel mindestens 5 km/h unter der ohne Wind", lambda f: f["sweep_v_wind"] <= f["sweep_v_nowind"] - 5.0),
    ],
    "Alpenpass": [
        ("time_close", "Der Pass kostet das Optimum höchstens 1 % Zeit gegenüber der flachen Strecke", lambda f: f["t_opt"] <= 1.01 * f["t_ref"]),
        ("v_same", "Die beste konstante Geschwindigkeit weicht höchstens 5 km/h von der auf flacher Strecke ab", lambda f: abs(f["v_best"] - f["v_best_ref"]) <= 5.0),
        ("free_small", "Eine freie Geschwindigkeit je Abschnitt bringt höchstens 0,6 % gegenüber der besten konstanten", lambda f: f["gap_free"] <= 0.6),
        ("sweep_time", "Messreihe: der Pass kostet den Pkw im Mittel höchstens 1 % Zeit", lambda f: f["sweep_pass_ratio"] <= 1.01),
    ],
    "Ohne Tempolimit": [
        ("v_below", "Die beste konstante Geschwindigkeit liegt mindestens 5 km/h unter 180 km/h", lambda f: f["v_best"] <= f["top"] - 5.0),
        ("rule_slow", "Die Praxisregel (180 km/h) braucht mindestens 4 % länger als das Optimum", lambda f: f["gap_rule"] >= 4.0),
        ("v_high", "Die beste konstante Geschwindigkeit liegt trotzdem über 150 km/h", lambda f: f["v_best"] >= 150.0),
        ("sweep_rule", "Messreihe: die Praxisregel braucht im Mittel mindestens 4 % länger als das Optimum", lambda f: f["sweep_gap_rule"] >= 4.0),
    ],
    "Elektro-Lkw": [
        ("v_limit", "Die beste konstante Geschwindigkeit ist das Tempolimit", lambda f: f["v_best"] >= f["top"] - 1e-9),
        ("rule_slow", "Die Praxisregel braucht mindestens 3 % länger als das Optimum", lambda f: f["gap_rule"] >= 3.0),
        ("free_small", "Eine freie Geschwindigkeit je Abschnitt bringt höchstens 0,6 % gegenüber der besten konstanten", lambda f: f["gap_free"] <= 0.6),
        ("sweep_rule", "Messreihe: die Praxisregel braucht für den Lkw bei 1000 km im Mittel mindestens 3 % länger als das Optimum", lambda f: f["sweep_gap_rule"] >= 3.0),
    ],
}


def ref_settings(preset: str, settings: dict) -> dict:
    return {**settings, **REF_OVERRIDES.get(preset, {})}


def facts_for(preset: str, run: dict, ref: dict, res: dict) -> dict:
    """Die Zahlen für die Kriterien. `ref` ist die Vergleichsrechnung (für Presets ohne Eintrag in REF_OVERRIDES der Lauf selbst)."""
    s = run["settings"]
    top = run["speeds"][-1]
    f = {"gap_rule": E.gap_pct(run, "rule"), "gap_cmax": E.gap_pct(run, "const_max"), "gap_free": E.gap_pct(run, "const_best"), "v_best": E.best_speed(run), "v_best_ref": E.best_speed(ref),
         "top": float(top), "stops_opt": len(run["plans"]["opt"].stops), "stops_ref": len(ref["plans"]["opt"].stops), "t_opt": run["plans"]["opt"].time_min, "t_ref": ref["plans"]["opt"].time_min,
         "tgt": E.mean_target_soc(run["plans"]["opt"])}
    peak = R.nearest((50.0, 100.0, 150.0, 250.0, 350.0), s["peak"])
    vmax = R.nearest((110, 130, 160, 180), s["vmax"])
    ps = R.power_summary(res, peak, vmax)
    f["sweep_gap_rule"], f["sweep_v_best"] = ps["gap_rule"], ps["v_best"]
    f["sweep_free_mean"] = R.free_vs_const(res)["mean"]
    f["sweep_cold_ratio"] = R.temp_summary(res, -10, 600)["t_opt"] / R.temp_summary(res, 20, 600)["t_opt"]
    f["sweep_v_wind"] = R.wind_summary(res, 50.0, "huegelig", 15)["v_best"]
    f["sweep_v_nowind"] = R.wind_summary(res, 50.0, "huegelig", 0)["v_best"]
    f["sweep_pass_ratio"] = R.height_summary(res, "Pkw", "pass", 0)["t_opt"] / R.height_summary(res, "Pkw", "flach", 0)["t_opt"]
    if preset == "Elektro-Lkw":
        f["sweep_gap_rule"] = R.vehicle_summary(res, "Elektro-Lkw", 1000)["gap_rule"]
    return f


def check(preset: str, facts: dict) -> list:
    """Liste (Kennung, Text, erfüllt) der Kriterien eines Presets."""
    return [(cid, text, bool(fn(facts))) for cid, text, fn in CRITERIA[preset]]
