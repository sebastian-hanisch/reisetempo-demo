"""Abnahmekriterien der Presets: jedes Preset erzählt eine Geschichte, die am gezeigten Lauf UND an der Messreihe überprüfbar ist.

Reine Funktionen einfacher Zahlen (`check`), damit Tests sie mit künstlichen Werten einzeln an ihrer Schwelle kippen können; `facts_for` baut die Zahlen aus einer Live-Rechnung, einer
Vergleichsrechnung (`ref`) und der Ergebnisdatei. `tools/preset_search.py` sucht damit einen Seed außerhalb der Messreihen-Seeds, bei dem alle Kriterien aller Presets gelten.
Lücken (`gap_*`) sind Prozent der Zielfunktion (Kosten; bei „Zeit allein“ die Reisezeit)."""
from __future__ import annotations

import rtp_constants as C
import rtp_evaluation as E
import rtp_results as R

NAN = float("nan")

# Vergleichsrechnung je Preset: dieselben Einstellungen mit diesen Änderungen (ohne Eintrag: der Lauf selbst)
REF_OVERRIDES = {"Möglichst sparsam": {"tv": C.TV_FAST}, "Gegenwind": {"headwind": 0}, "Alpenpass": {"profile": "flach"}}

CRITERIA = {
    "Standard": [
        ("rule_costly", "Die Praxisregel kostet mindestens 2 % mehr als das Optimum", lambda f: f["gap_rule"] >= 2.0),
        ("rule_faster", "Die Praxisregel ist mindestens 2 % schneller als das Optimum", lambda f: f["tgap_rule"] <= -2.0),
        ("rule_thirsty", "Die Praxisregel verbraucht mindestens 10 % mehr Energie als das Optimum", lambda f: f["cons_rule"] >= 1.10 * f["cons_opt"]),
        ("v_below", "Die beste konstante Geschwindigkeit liegt mindestens 10 km/h unter dem Tempolimit", lambda f: f["v_best"] <= f["top"] - 10.0),
        ("free_small", "Eine freie Geschwindigkeit je Abschnitt bringt höchstens 0,6 % gegenüber der besten konstanten", lambda f: f["gap_free"] <= 0.6),
        ("tgt_low", "Die Stopps des Optimums laden im Mittel auf höchstens 70 %", lambda f: f["tgt"] <= 70.0),
        ("sweep_rule", "Messreihe: die Praxisregel kostet im Mittel mindestens 2 % mehr als das Optimum", lambda f: f["sweep_gap_rule"] >= 2.0),
        ("sweep_free", "Messreihe: eine freie Geschwindigkeit bringt im Mittel höchstens 0,5 % gegenüber der besten konstanten", lambda f: f["sweep_free_mean"] <= 0.5),
    ],
    "Möglichst schnell": [
        ("rule_slow", "Die Praxisregel braucht mindestens 2 % länger als das Optimum", lambda f: f["gap_rule"] >= 2.0),
        ("v_limit", "Die beste konstante Geschwindigkeit ist das Tempolimit", lambda f: f["v_best"] >= f["top"] - 1e-9),
        ("cmax_close", "Das Tempolimit mit optimalem Laden liegt höchstens 0,6 % über dem Optimum", lambda f: f["gap_cmax"] <= 0.6),
        ("sweep_rule", "Messreihe: die Praxisregel braucht im Mittel mindestens 2 % länger als das Optimum", lambda f: f["sweep_gap_rule"] >= 2.0),
    ],
    "Möglichst sparsam": [
        ("v_min", "Die beste konstante Geschwindigkeit liegt höchstens 5 km/h über der Mindestgeschwindigkeit", lambda f: f["v_best"] <= C.V_MIN + 5.0),
        ("saves", "Das Optimum verbraucht höchstens 60 % der Energie von „Zeit allein“", lambda f: f["cons_opt"] <= 0.60 * f["cons_ref"]),
        ("slower", "Das Optimum braucht mindestens 50 % länger als bei „Zeit allein“", lambda f: f["t_opt"] >= 1.5 * f["t_ref"]),
        ("sweep_saves", "Messreihe: der Pkw verbraucht bei 1 € je Stunde im Mittel höchstens 60 % der Energie von „Zeit allein“ (600 km)", lambda f: f["sweep_cons_ratio"] <= 0.60),
        ("sweep_slower", "Messreihe: der Pkw braucht bei 1 € je Stunde im Mittel mindestens 50 % länger als bei „Zeit allein“ (600 km)", lambda f: f["sweep_time_ratio"] >= 1.5),
    ],
    "Langsamer Lader": [
        ("rule_slow", "Die Praxisregel braucht mindestens 5 % länger als das Optimum", lambda f: f["gap_rule"] >= 5.0),
        ("v_below", "Die beste konstante Geschwindigkeit liegt mindestens 5 km/h unter dem Tempolimit", lambda f: f["v_best"] <= f["top"] - 5.0),
        ("cmax_loses", "Das Tempolimit mit optimalem Laden liegt mindestens 0,2 % über dem Optimum", lambda f: f["gap_cmax"] >= 0.2),
        ("sweep_rule", "Messreihe: die Praxisregel braucht im Mittel mindestens 5 % länger als das Optimum", lambda f: f["sweep_gap_rule"] >= 5.0),
        ("sweep_v", "Messreihe: die beste konstante Geschwindigkeit liegt im Mittel mindestens 2 km/h unter dem Tempolimit", lambda f: f["sweep_v_best"] <= f["top"] - 2.0),
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
        ("v_below", "Die beste konstante Geschwindigkeit liegt mindestens 50 km/h unter 180 km/h", lambda f: f["v_best"] <= f["top"] - 50.0),
        ("rule_costly", "Die Praxisregel (180 km/h) kostet mindestens 15 % mehr als das Optimum", lambda f: f["gap_rule"] >= 15.0),
        ("rule_thirsty", "Die Praxisregel verbraucht mindestens 50 % mehr Energie als das Optimum", lambda f: f["cons_rule"] >= 1.5 * f["cons_opt"]),
        ("sweep_rule", "Messreihe: die Praxisregel kostet im Mittel mindestens 15 % mehr als das Optimum", lambda f: f["sweep_gap_rule"] >= 15.0),
        ("sweep_v", "Messreihe: die beste konstante Geschwindigkeit liegt im Mittel mindestens 50 km/h unter 180 km/h", lambda f: f["sweep_v_best"] <= f["top"] - 50.0),
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
    opt, ropt = run["plans"]["opt"], ref["plans"]["opt"]
    f = {"gap_rule": E.gap_pct(run, "rule"), "tgap_rule": E.time_gap_pct(run, "rule"), "gap_cmax": E.gap_pct(run, "const_max"), "gap_free": E.gap_pct(run, "const_best"),
         "v_best": E.best_speed(run), "v_best_ref": E.best_speed(ref), "top": float(top), "stops_opt": len(opt.stops), "stops_ref": len(ropt.stops), "t_opt": opt.time_min, "t_ref": ropt.time_min,
         "tgt": E.mean_target_soc(opt), "cons_opt": E.consumption(run, "opt"), "cons_rule": E.consumption(run, "rule"), "cons_ref": E.consumption(ref, "opt")}
    peak = R.nearest((50.0, 100.0, 150.0, 250.0, 350.0), s["peak"])
    vmax = R.nearest((110, 130, 160, 180), s["vmax"])
    tv_cell = C.TV_FAST if s["tv"] >= C.TV_FAST else C.DEFAULT_TV           # Zeitwerte der Ladeleistung-×-Tempolimit-Messreihe
    ps = R.power_summary(res, peak, vmax, tv_cell)
    f["sweep_gap_rule"], f["sweep_v_best"] = ps["gap_rule"], ps["v_best"]
    f["sweep_free_mean"] = R.free_vs_const(res)["mean"]
    f["sweep_v_wind"] = R.wind_summary(res, 50.0, "huegelig", 15)["v_best"]
    f["sweep_v_nowind"] = R.wind_summary(res, 50.0, "huegelig", 0)["v_best"]
    f["sweep_pass_ratio"] = R.height_summary(res, "Pkw", "pass", 0)["t_opt"] / R.height_summary(res, "Pkw", "flach", 0)["t_opt"]
    slow, fast = R.vehicle_summary(res, "Pkw", 600, 1), R.vehicle_summary(res, "Pkw", 600, C.TV_FAST)
    f["sweep_cons_ratio"], f["sweep_time_ratio"] = slow["cons_opt"] / fast["cons_opt"], slow["t_opt"] / fast["t_opt"]
    if preset == "Elektro-Lkw":
        f["sweep_gap_rule"] = R.vehicle_summary(res, "Elektro-Lkw", 1000, C.TV_FAST)["gap_rule"]
    return f


def check(preset: str, facts: dict) -> list:
    """Liste (Kennung, Text, erfüllt) der Kriterien eines Presets."""
    return [(cid, text, bool(fn(facts))) for cid, text, fn in CRITERIA[preset]]
