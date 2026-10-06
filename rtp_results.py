"""Vorgerechnete Messreihe (data/rtp_results.json, erzeugt mit tools/sweep.py): Auswertung je Sweep. Die App rechnet sie nie live.

Jede Zeile gehört zu einem Zeitwert `tv` (C.TV_FAST = „Zeit allein“). `gap` ist der Abstand der Reisezeit, `gap_obj` der Abstand der Zielfunktion (bei „Zeit allein“ gleich dem der Reisezeit)."""
from __future__ import annotations

import json
import statistics as st
from pathlib import Path

import rtp_constants as C

ROOT = Path(__file__).resolve().parent


def load_results(path=None) -> dict:
    return json.loads(Path(path or ROOT / C.RESULTS_FILE).read_text(encoding="utf-8"))


def mean_se(xs) -> tuple:
    xs = [x for x in xs if x is not None]
    if not xs:
        return float("nan"), float("nan")
    return st.mean(xs), (st.stdev(xs) / len(xs) ** 0.5 if len(xs) > 1 else float("nan"))


def rows_of(res: dict, sweep: str, **kw) -> list:
    """Zeilen eines Sweeps, die alle Bedingungen kw (Spalte = Wert) erfüllen."""
    return [r for r in res["rows"] if r["sweep"] == sweep and all(r[k] == v for k, v in kw.items())]


def gap(row: dict, key: str, ref: str = "opt") -> float:
    """Um wie viel Prozent die Reisezeit von `key` über der von `ref` liegt (Basis: ref)."""
    return 100.0 * (row[f"t_{key}"] / row[f"t_{ref}"] - 1.0)


def gap_obj(row: dict, key: str, ref: str = "opt") -> float:
    """Um wie viel Prozent die Zielfunktion (Kosten; bei „Zeit allein“ die Reisezeit) von `key` über der von `ref` liegt (Basis: ref)."""
    return 100.0 * (row[f"j_{key}"] / row[f"j_{ref}"] - 1.0)


def cons(row: dict, key: str) -> float:
    """Der Batterie entnommene Energie des Verfahrens `key` in kWh je 100 km."""
    return 100.0 * row[f"e_{key}"] / row["length"]


def nearest(values, x):
    """Der Wert aus `values`, der x am nächsten liegt (bei Gleichstand der kleinere)."""
    return min(sorted(values), key=lambda v: abs(v - x))


def power_summary(res: dict, peak: float, vmax: int, tv: int = C.TV_FAST) -> dict:
    """Ladeleistung × Tempolimit bei einem Zeitwert: mittlere Lücken der Zielfunktion der drei Vergleichsverfahren zum Optimum, beste konstante Geschwindigkeit, mittleres Ladeziel, Reisezeit
    und Verbrauch von Optimum und Praxisregel."""
    rows = rows_of(res, "power", peak=peak, vmax=vmax, tv=tv)
    out = {"n": len(rows), "peak": peak, "vmax": vmax, "tv": tv}
    for key in ("rule", "const_max", "const_best"):
        out[f"gap_{key}"], out[f"gap_{key}_se"] = mean_se(gap_obj(r, key) for r in rows)
    out["tgap_rule"], _ = mean_se(gap(r, "rule") for r in rows)
    out["v_best"], out["v_best_se"] = mean_se(r["v_best"] for r in rows)
    out["v_opt"], _ = mean_se(r["v_opt"] for r in rows)
    out["tgt_opt"], _ = mean_se(r["tgt_opt"] for r in rows)
    out["t_opt"], _ = mean_se(r["t_opt"] for r in rows)
    out["t_rule"], _ = mean_se(r["t_rule"] for r in rows)
    out["cons_opt"], _ = mean_se(cons(r, "opt") for r in rows)
    out["cons_rule"], _ = mean_se(cons(r, "rule") for r in rows)
    out["stops_opt"], _ = mean_se(r["stops_opt"] for r in rows)
    return out


def wind_summary(res: dict, peak: float, profile: str, wind: float) -> dict:
    rows = rows_of(res, "wind", peak=peak, profile=profile, headwind=wind)
    out = {"n": len(rows), "peak": peak, "profile": profile, "wind": wind}
    out["v_best"], out["v_best_se"] = mean_se(r["v_best"] for r in rows)
    out["gap_const_best"], out["gap_const_best_se"] = mean_se(gap_obj(r, "const_best") for r in rows)
    out["t_opt"], _ = mean_se(r["t_opt"] for r in rows)
    return out


def vehicle_summary(res: dict, vehicle: str, length: float, tv: int = C.TV_FAST) -> dict:
    """Fahrzeug × Streckenlänge × Zeitwert: Reisezeit, Verbrauch, Geschwindigkeit und Stopps des Optimums, Lücken der Zielfunktion von Praxisregel und bester konstanter Fahrt."""
    rows = rows_of(res, "vehicle", vehicle=vehicle, length=length, tv=tv)
    out = {"n": len(rows), "vehicle": vehicle, "length": length, "tv": tv}
    out["t_opt"], _ = mean_se(r["t_opt"] for r in rows)
    out["t_rule"], _ = mean_se(r["t_rule"] for r in rows)
    out["cons_opt"], _ = mean_se(cons(r, "opt") for r in rows)
    out["cons_rule"], _ = mean_se(cons(r, "rule") for r in rows)
    out["v_opt"], _ = mean_se(r["v_opt"] for r in rows)
    out["stops_opt"], _ = mean_se(r["stops_opt"] for r in rows)
    out["gap_rule"], out["gap_rule_se"] = mean_se(gap_obj(r, "rule") for r in rows)
    out["gap_const_best"], _ = mean_se(gap_obj(r, "const_best") for r in rows)
    out["v_best"], _ = mean_se(r["v_best"] for r in rows)
    return out


def spectrum(res: dict, vehicle: str, length: float) -> list[dict]:
    """Die Spanne eines Fahrzeugs: je Zeitwert der Messreihe die Zusammenfassung von `vehicle_summary` (aufsteigend nach Zeitwert, „Zeit allein“ zuletzt)."""
    return [vehicle_summary(res, vehicle, length, tv) for tv in res["meta"]["tvs"]]


def fix_summary(res: dict, peak: float, stop_min: float) -> dict:
    rows = rows_of(res, "fix", peak=peak, stop_min=stop_min)
    out = {"n": len(rows), "peak": peak, "stop_min": stop_min}
    out["gap_rule"], out["gap_rule_se"] = mean_se(gap_obj(r, "rule") for r in rows)
    out["stops_opt"], _ = mean_se(r["stops_opt"] for r in rows)
    out["tgt_opt"], _ = mean_se(r["tgt_opt"] for r in rows)
    return out


def height_summary(res: dict, vehicle: str, profile: str, rise: float) -> dict:
    rows = rows_of(res, "height", vehicle=vehicle, profile=profile, rise=rise)
    out = {"n": len(rows), "vehicle": vehicle, "profile": profile, "rise": rise}
    out["t_opt"], _ = mean_se(r["t_opt"] for r in rows)
    out["cons_opt"], _ = mean_se(r["cons_opt"] for r in rows)
    return out


def free_vs_const(res: dict) -> dict:
    """Über alle Fälle: wie viel bringt eine freie Geschwindigkeit je Abschnitt gegenüber der besten konstanten? (Mittel, 95. Perzentil, Maximum in Prozent der Zielfunktion)"""
    gaps = sorted(gap_obj(r, "const_best") for r in res["rows"] if r["t_const_best"] is not None)
    return {"n": len(gaps), "mean": st.mean(gaps), "p95": gaps[int(0.95 * (len(gaps) - 1))], "max": gaps[-1]}


def cell_exists(settings: dict) -> bool:
    """Gibt es zu den Einstellungen eine Zelle der Ladeleistung × Tempolimit-Messreihe (Fahrzeug Pkw)? Der Seed gehört nicht dazu."""
    return settings["peak"] in (50.0, 100.0, 150.0, 250.0, 350.0) and settings["vmax"] in (110, 130, 160, 180)
