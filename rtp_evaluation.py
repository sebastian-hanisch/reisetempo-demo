"""Auswertung eines Laufs: Kennzahlen je Verfahren, Vergleich und Meldungen (Live-Rechnung und Messreihe benutzen dieselben Funktionen).

Zielfunktion J = w_time · Reisezeit (h) + w_energy · entnommene Energie (kWh); bei „Zeit allein“ (w_energy = 0, w_time = 1) ist J die Reisezeit in Stunden."""
from __future__ import annotations

import time

import numpy as np

import rtp_algorithm as A
import rtp_constants as C
import rtp_scenario as S
import rtp_strategies as ST

TIE_PCT = 0.5          # Unterschiede unter 0,5 % der Zielfunktion gelten als gleichwertig (DP-Raster und Nachfahrt)
RULE_GAP_MIN_PCT = 1.0


def run_live(settings: dict) -> dict:
    """Rechnet alle vier Verfahren für ein Einstellungs-Wörterbuch."""
    t0 = time.time()
    trip = S.make_trip(settings)
    plans = ST.run_all(trip)
    return {"settings": dict(settings), "trip": trip, "plans": plans, "seconds": time.time() - t0, "speeds": S.speed_grid(trip.vmax)}


def feasible(run: dict, key: str) -> bool:
    return run["plans"][key].feasible


def time_only(run: dict) -> bool:
    """Ist die Zielfunktion die reine Reisezeit („Zeit allein“, Energie kostet nichts)?"""
    return run["trip"].w_energy == 0.0


def objective(run: dict, key: str) -> float:
    """Zielfunktionswert des Plans von `key` (Euro, bei „Zeit allein“ Stunden)."""
    return A.plan_cost(run["trip"], run["plans"][key])


def gap_pct(run: dict, key: str, ref: str = "opt") -> float:
    """Um wie viel Prozent die Zielfunktion (Kosten, bei „Zeit allein“ die Reisezeit) von `key` über der von `ref` liegt (Basis: ref)."""
    a, b = run["plans"][key], run["plans"][ref]
    if not (a.feasible and b.feasible):
        return float("nan")
    return 100.0 * (objective(run, key) / objective(run, ref) - 1.0)


def time_gap_pct(run: dict, key: str, ref: str = "opt") -> float:
    """Um wie viel Prozent die Reisezeit von `key` über der von `ref` liegt (negativ: schneller)."""
    a, b = run["plans"][key], run["plans"][ref]
    if not (a.feasible and b.feasible):
        return float("nan")
    return 100.0 * (a.time_h / b.time_h - 1.0)


def consumption(run: dict, key: str) -> float:
    """Der Batterie entnommene Energie in kWh je 100 km."""
    return 100.0 * run["plans"][key].used_kwh / run["trip"].route.length


def energy_cost(run: dict, key: str) -> float:
    """Energiekosten der Fahrt in Euro: Strompreis geteilt durch den Ladewirkungsgrad mal entnommene Energie (unabhängig vom gewählten Zeitwert)."""
    s = run["settings"]
    return float(s["price"]) / (1.0 - float(s["loss"]) / 100.0) * run["plans"][key].used_kwh


def total_cost(run: dict, key: str) -> float:
    """Gesamtkosten in Euro (Zeitwert mal Reisezeit plus Energiekosten); bei „Zeit allein“ gibt es keinen Zeitwert in Euro: NaN."""
    if time_only(run):
        return float("nan")
    return objective(run, key)


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
    """Eine Zeile je Verfahren: Kosten, Reisezeit, Zeitanteile, Stopps, mittlere Geschwindigkeit, Verbrauch."""
    rows = []
    ref = run["plans"]["opt"]
    for key in C.METHODS:
        p = run["plans"][key]
        if not p.feasible:
            rows.append({"key": key, "feasible": False, "note": p.note})
            continue
        rows.append({"key": key, "feasible": True, "time_min": p.time_min, "drive_min": 60 * p.drive_h, "charge_min": 60 * p.charge_h, "fix_min": 60 * p.fix_h, "stops": len(p.stops),
                     "mean_speed": p.mean_speed, "consumption": consumption(run, key), "charged_kwh": p.charged_kwh, "energy_cost": energy_cost(run, key), "total_cost": total_cost(run, key),
                     "gap_opt_pct": gap_pct(run, key) if ref.feasible else float("nan"), "time_gap_pct": time_gap_pct(run, key) if ref.feasible else float("nan")})
    return rows


def frontier(settings: dict, options=C.TV_OPTIONS) -> list[dict]:
    """Die Spanne zwischen „möglichst sparsam“ und „möglichst schnell“: der Optimalplan (Geschwindigkeit frei) je Zeitwert der Auswahl.
    Je Punkt Reisezeit, entnommene Energie, Energiekosten, mittlere Geschwindigkeit und Stopps; nicht erreichbare Fälle fehlen."""
    out = []
    for tv in options:
        trip = S.make_trip({**settings, "tv": tv})
        p = A.solve(trip, S.speed_grid(trip.vmax), "opt")
        if p.feasible:
            out.append({"tv": tv, "time_min": p.time_min, "used_kwh": p.used_kwh, "consumption": 100.0 * p.used_kwh / trip.route.length, "mean_speed": p.mean_speed, "stops": len(p.stops),
                        "energy_cost": float(settings["price"]) / (1.0 - float(settings["loss"]) / 100.0) * p.used_kwh})
    return out


def speed_curve(settings: dict) -> list[dict]:
    """Konstante Geschwindigkeiten (Raster von V_MIN bis zum Tempolimit), jeweils mit zeitoptimalem Laden: Reisezeit und Energiekosten je Geschwindigkeit. Die entnommene Energie hängt nicht
    vom Laden ab, nur die Reisezeit; deshalb wird hier die reine Reisezeit minimiert („Zeit allein“)."""
    trip = S.make_trip({**settings, "tv": C.TV_FAST})
    out = []
    for v in S.speed_grid(trip.vmax):
        p = A.solve(trip, [v], "const")
        if p.feasible:
            out.append({"v": v, "time_min": p.time_min, "used_kwh": p.used_kwh, "consumption": 100.0 * p.used_kwh / trip.route.length, "stops": len(p.stops),
                        "energy_cost": float(settings["price"]) / (1.0 - float(settings["loss"]) / 100.0) * p.used_kwh})
    return out


def _eur(x: float) -> str:
    return f"{x:.0f} €" if abs(x) >= 100 else f"{x:.1f} €"


def messages(run: dict) -> list[tuple[str, str]]:
    """Meldungen (Zustand, Text) zu einem Lauf; jede Aussage nennt ihre Zahlen und gilt nur für diesen Lauf."""
    out = []
    plans = run["plans"]
    fast = time_only(run)
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
            if fast:
                out.append(("success", f"Die Praxisregel (Tempolimit {top} km/h, jeweils bis {C.RULE_CHARGE_TO:.0f} % laden) braucht {d_min:.0f} min ({gap:.1f} %) länger als das Optimum. {opt_txt}"))
            else:
                d_cons = consumption(run, "rule") - consumption(run, "opt")
                t_txt = f"{abs(d_min):.0f} min {'schneller' if d_min < 0 else 'langsamer'}"
                e_txt = f"{abs(d_cons):.1f} kWh/100 km {'mehr' if d_cons > 0 else 'weniger'}"
                d_eur = objective(run, "rule") - objective(run, "opt")
                out.append(("success", f"Die Praxisregel (Tempolimit {top} km/h, jeweils bis {C.RULE_CHARGE_TO:.0f} % laden) kostet {_eur(d_eur)} ({gap:.1f} %) mehr als das Optimum: sie ist {t_txt}, "
                                       f"verbraucht aber {e_txt}. {opt_txt}"))
        else:
            if fast:
                out.append(("info", f"Die Praxisregel liegt nur {abs(d_min):.1f} min ({abs(gap):.1f} %) neben dem Optimum: Bei dieser Ladeleistung und Strecke genügt sie praktisch."))
            else:
                out.append(("info", f"Die Praxisregel liegt bei den Kosten nur {abs(gap):.1f} % neben dem Optimum: Bei diesem Zeitwert und dieser Strecke genügt sie praktisch."))
    best = plans["const_best"]
    if best.feasible:
        v = best.mean_speed
        cmax = plans["const_max"]
        if v < top - C.V_STEP / 2:
            extra = ""
            if cmax.feasible:
                extra = (f" Mit Tempolimit {top} km/h und optimalem Laden wären es {cmax.time_min - best.time_min:.0f} min mehr." if fast
                         else f" Mit Tempolimit {top} km/h und optimalem Laden kostet es {gap_pct(run, 'const_max', 'const_best'):.1f} % mehr.")
            out.append(("info", f"Die beste konstante Geschwindigkeit liegt bei {v:.0f} km/h, also {top - v:.0f} km/h unter dem Tempolimit.{extra}"))
        else:
            out.append(("info", f"Die beste konstante Geschwindigkeit ist das Tempolimit von {top} km/h: Hier lohnt sich das Ausfahren."))
        g = gap_pct(run, "const_best")
        d_best = best.time_min - opt.time_min
        unit = f"{d_best:.1f} min ({g:.2f} %)" if fast else f"{g:.2f} % der Kosten"
        if g < TIE_PCT:
            out.append(("info", f"Eine Geschwindigkeit je Abschnitt zu wählen bringt gegenüber der besten konstanten nur {unit}."))
        else:
            unit = f"{d_best:.1f} min ({g:.1f} %)" if fast else f"{g:.1f} % der Kosten"
            out.append(("success", f"Eine freie Geschwindigkeit je Abschnitt spart gegenüber der besten konstanten {unit}."))
    return out
