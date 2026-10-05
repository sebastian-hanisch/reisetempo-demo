"""Die vier Verfahren der Demo und die Praxisregel (stetig simuliert, ohne Wertfunktion).

Praxisregel: konstant mit dem Tempolimit fahren; ein Ladestopp wird eingelegt, sobald die nächste Zelle den Ladestand unter den Mindestladestand am Stopp drücken würde;
geladen wird bis 80 % der Kapazität, am letzten Stopp nur so weit, wie das Ziel braucht."""
from __future__ import annotations

import numpy as np

import rtp_algorithm as A
import rtp_constants as C
import rtp_physics as P
from rtp_scenario import Trip, speed_grid

MAX_STOPS = 200


def simulate_ahead(E: np.ndarray, cap: float, s: float, i: int) -> tuple[float, float]:
    """Fährt die Zellen i bis n−1 ohne weiteren Stopp (Energie E je Zelle): (kleinster Ladestand unterwegs, Ladestand am Ziel). Oberhalb der Kapazität geht Rekuperation verloren."""
    low = s
    for e in E[i:]:
        s = min(s - e, cap)
        low = min(low, s)
    return low, s


def needed_soc(E: np.ndarray, cap: float, i: int, smin_dest: float) -> float:
    """Kleinster Ladestand am Zellbeginn i, mit dem das Ziel ohne weiteren Stopp erreichbar ist (Bisektion; die Erreichbarkeit ist monoton im Ladestand)."""
    lo, hi = 0.0, cap
    low, end = simulate_ahead(E, cap, hi, i)
    if low < -C.SOC_EPS or end < smin_dest - C.SOC_EPS:
        return float("inf")
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        low, end = simulate_ahead(E, cap, mid, i)
        if low >= -C.SOC_EPS and end >= smin_dest - C.SOC_EPS:
            hi = mid
        else:
            lo = mid
    return hi


def rule_plan(trip: Trip, v: float) -> A.Plan:
    """Praxisregel mit konstanter Geschwindigkeit v (km/h)."""
    veh, rt = trip.vehicle, trip.route
    n = rt.n
    E = np.array([P.cell_energy(veh, v, trip.temp, rt.grade[i], rt.wind[i]) for i in range(n)])
    t_cell = C.DX_KM / v
    s = trip.soc0
    p = A.Plan("rule", True)
    p.v, p.energy = np.full(n, float(v)), E.copy()
    p.trace.append((0.0, s))
    ceiling = veh.cap * C.RULE_CHARGE_TO / 100.0
    for i in range(n):
        low, end = simulate_ahead(E, veh.cap, s, i)
        finish = low >= -C.SOC_EPS and end >= trip.smin_dest - C.SOC_EPS
        if not finish and s - E[i] < trip.smin_stop - C.SOC_EPS:
            if len(p.stops) >= MAX_STOPS:
                return A.Plan("rule", False, note="Zu viele Stopps.")
            need = needed_soc(E, veh.cap, i, trip.smin_dest)
            target = min(ceiling, need)
            if target <= s + 1e-9:
                return A.Plan("rule", False, note=f"Die Praxisregel (Laden bis {C.RULE_CHARGE_TO:.0f} %) kommt nicht ans Ziel.")
            ch = P.charge_time_exact(veh, trip.temp, trip.loss, s, target)
            p.stops.append(A.Stop(i * C.DX_KM, 100.0 * s / veh.cap, 100.0 * target / veh.cap, 60.0 * ch, 60.0 * (ch + trip.stop_h)))
            p.charge_h += ch
            p.fix_h += trip.stop_h
            p.charged_kwh += target - s
            p.trace.append((i * C.DX_KM, s))
            s = target
            p.trace.append((i * C.DX_KM, s))
        s = min(s - E[i], veh.cap)
        p.drive_h += t_cell
        p.trace.append(((i + 1) * C.DX_KM, s))
    if s < trip.smin_dest - C.SOC_EPS:
        return A.Plan("rule", False, note="Die Praxisregel erreicht das Ziel nicht.")
    p.soc_end = s
    p.time_h = p.drive_h + p.charge_h + p.fix_h
    return p


def run_all(trip: Trip) -> dict:
    """Alle vier Verfahren: Praxisregel, Tempolimit mit optimalem Laden, beste konstante Geschwindigkeit, Optimum mit freier Geschwindigkeit."""
    speeds = speed_grid(trip.vmax)
    top = speeds[-1]
    return {"rule": rule_plan(trip, top), "const_max": A.solve(trip, [top], "const_max"), "const_best": A.best_constant(trip, speeds), "opt": A.solve(trip, speeds, "opt")}
