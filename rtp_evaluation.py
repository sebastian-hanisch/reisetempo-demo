"""Auswertung eines Laufs: Kennzahlen je Verfahren, Vergleich und Meldungen (Live-Rechnung und Messreihe benutzen dieselben Funktionen)."""
from __future__ import annotations

import time

import numpy as np

import rtp_algorithm as A
import rtp_constants as C
import rtp_scenario as S
import rtp_strategies as ST

TIE_PCT = 0.5          # Unterschiede unter 0,5 % der Reisezeit gelten als gleichwertig (DP-Raster und Nachfahrt)
RULE_GAP_MIN_PCT = 1.0


def run_live(settings: dict) -> dict:
    """Rechnet alle vier Verfahren für ein Einstellungs-Wörterbuch."""
    t0 = time.time()
    trip = S.make_trip(settings)
    plans = ST.run_all(trip)
    return {"settings": dict(settings), "trip": trip, "plans": plans, "seconds": time.time() - t0, "speeds": S.speed_grid(trip.vmax)}


def feasible(run: dict, key: str) -> bool:
    return run["plans"][key].feasible


def gap_pct(run: dict, key: str, ref: str = "opt") -> float:
    """Um wie viel Prozent die Reisezeit von `key` über der von `ref` liegt (Basis: ref)."""
    a, b = run["plans"][key], run["plans"][ref]
    if not (a.feasible and b.feasible):
        return float("nan")
    return 100.0 * (a.time_h / b.time_h - 1.0)


def mean_target_soc(plan: A.Plan) -> float:
    """Mittleres Ladeziel (Prozent) der Stopps nach dem ersten (der erste Stopp startet oft von einem hohen Ladestand); ohne Folgestopps das Ladeziel des einzigen Stopps."""
    if not plan.stops:
        return float("nan")
    tail = plan.stops[1:] or plan.stops
    return float(np.mean([s.soc_to for s in tail]))


def best_speed(run: dict) -> float:
    """Mittlere Geschwindigkeit der besten konstanten Fahrt (die Geschwindigkeit selbst, falls möglich)."""
    p = run["plans"]["const_best"]
    return p.mean_speed if p.feasible else float("nan")


def summary_rows(run: dict) -> list[dict]:
    """Eine Zeile je Verfahren: Reisezeit, Zeitanteile, Stopps, mittlere Geschwindigkeit, Verbrauch."""
    rows = []
    ref = run["plans"]["opt"]
    for key in C.METHODS:
        p = run["plans"][key]
        if not p.feasible:
            rows.append({"key": key, "feasible": False, "note": p.note})
            continue
        dist = run["trip"].route.length
        rows.append({"key": key, "feasible": True, "time_min": p.time_min, "drive_min": 60 * p.drive_h, "charge_min": 60 * p.charge_h, "fix_min": 60 * p.fix_h, "stops": len(p.stops),
                     "mean_speed": p.mean_speed, "consumption": 100.0 * float(np.sum(p.energy)) / dist, "charged_kwh": p.charged_kwh,
                     "gap_opt_pct": 100.0 * (p.time_h / ref.time_h - 1.0) if ref.feasible else float("nan")})
    return rows


def messages(run: dict) -> list[tuple[str, str]]:
    """Meldungen (Zustand, Text) zu einem Lauf; jede Aussage nennt ihre Zahlen und gilt nur für diesen Lauf."""
    out = []
    plans = run["plans"]
    for key in C.METHODS:
        if not plans[key].feasible:
            out.append(("warning", f"{C.METHOD_LABELS[key]}: {plans[key].note}"))
    opt = plans["opt"]
    if not opt.feasible:
        return out
    top = run["speeds"][-1]
    rule = plans["rule"]
    if rule.feasible:
        gap = gap_pct(run, "rule")
        d_min = rule.time_min - opt.time_min
        if gap >= RULE_GAP_MIN_PCT:
            tgt = mean_target_soc(opt)
            opt_txt = (f"Das Optimum macht {len(opt.stops)} Ladestopps mit einem mittleren Ladeziel von {tgt:.0f} %, die Praxisregel {len(rule.stops)}." if tgt == tgt
                       else f"Das Optimum kommt ohne Ladestopp aus, die Praxisregel macht {len(rule.stops)}.")
            out.append(("success", f"Die Praxisregel (Tempolimit {top} km/h, jeweils bis {C.RULE_CHARGE_TO:.0f} % laden) braucht {d_min:.0f} min ({gap:.1f} %) länger als das Optimum. {opt_txt}"))
        else:
            out.append(("info", f"Die Praxisregel liegt nur {abs(d_min):.1f} min ({abs(gap):.1f} %) neben dem Optimum: Bei dieser Ladeleistung und Strecke genügt sie praktisch."))
    best = plans["const_best"]
    if best.feasible:
        v = best.mean_speed
        cmax = plans["const_max"]
        if v < top - C.V_STEP / 2:
            extra = f" Mit Tempolimit {top} km/h und optimalem Laden wären es {cmax.time_min - best.time_min:.0f} min mehr." if cmax.feasible else ""
            out.append(("info", f"Die beste konstante Geschwindigkeit liegt bei {v:.0f} km/h, also {top - v:.0f} km/h unter dem Tempolimit.{extra}"))
        else:
            out.append(("info", f"Die beste konstante Geschwindigkeit ist das Tempolimit von {top} km/h: Hier lohnt sich das Ausfahren."))
        g = gap_pct(run, "const_best")
        if g < TIE_PCT:
            out.append(("info", f"Eine Geschwindigkeit je Abschnitt zu wählen bringt gegenüber der besten konstanten nur {best.time_min - opt.time_min:.1f} min ({g:.2f} %)."))
        else:
            out.append(("success", f"Eine freie Geschwindigkeit je Abschnitt spart gegenüber der besten konstanten {best.time_min - opt.time_min:.1f} min ({g:.1f} %)."))
    return out
