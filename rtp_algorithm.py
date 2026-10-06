"""Kern der Demo: Reiseplanung eines Elektrofahrzeugs zwischen „möglichst schnell“ und „möglichst sparsam“ durch dynamische Programmierung über (Ort, Ladestand).

Zielfunktion: Kosten = w_time · Reisezeit (h) + w_energy · Energie, die die Fahrt der Batterie entnimmt (kWh). Mit w_time = 1 und w_energy = 0 ist das die reine Reisezeit.
Rückwärts-DP: f_i(s) = kleinste Restkosten ab dem Beginn der Zelle i mit Ladestand s (kWh).
  Fahren:  f_i(s) = min_v  w_time · dx/v + w_energy · u_i(s, v) + g_{i+1}(s − e_i(v))      (lineare Interpolation der Wertfunktion; u = entnommene Energie, ohne verworfene Rekuperation)
  Laden:   g_i(s) = min( f_i(s),  min_{s' > s}  w_time · (t_fix + Tch(s') − Tch(s)) + f_i(s') )   nur wenn s ≥ Mindestladestand am Stopp
  Ziel:    f_n(s) = 0, wenn s ≥ Mindestladestand am Ziel, sonst unendlich.
Geladene Energie kostet nichts extra: Die Energie wird bei der Entnahme bewertet (Strompreis geteilt durch den Ladewirkungsgrad), Laden kostet nur Zeit.
Der Plan wird danach mit dem stetigen Ladestand nachgefahren (die Wertfunktion wird am echten Ladestand ausgewertet, nicht auf das Raster gerundet);
`value` ist der DP-Wert, die Kosten und die Zeit der Nachfahrt stehen im Plan. Jede Regel ist eine eigene Funktion mit expliziten Ein- und Ausgaben (DEMO-PLAYBOOK §1b)."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

import rtp_constants as C
import rtp_physics as P
from rtp_scenario import Trip

INF = 1e9


@dataclass
class Stop:
    km: float
    soc_from: float        # Prozent der Kapazität bei Ankunft
    soc_to: float          # Prozent nach dem Laden
    charge_min: float      # reine Ladezeit
    total_min: float       # Ladezeit plus Fixzeit des Stopps


@dataclass
class Plan:
    method: str
    feasible: bool
    time_h: float = float("nan")
    value: float | None = None             # DP-Wert in der Einheit der Zielfunktion (nur für Verfahren, die per DP geplant sind)
    drive_h: float = 0.0
    charge_h: float = 0.0
    fix_h: float = 0.0
    stops: list = field(default_factory=list)
    v: np.ndarray = field(default_factory=lambda: np.zeros(0))          # Geschwindigkeit je Zelle (km/h)
    energy: np.ndarray = field(default_factory=lambda: np.zeros(0))     # Energie je Zelle (kWh, mit Nebenverbrauchern)
    trace: list = field(default_factory=list)                           # (km, Ladestand kWh): Zellgrenzen, an Stopps vor und nach dem Laden
    soc_end: float = float("nan")
    charged_kwh: float = 0.0
    used_kwh: float = 0.0                  # der Batterie entnommene Energie (kWh, ohne Rekuperation oberhalb der Kapazität)
    note: str = ""

    @property
    def time_min(self) -> float:
        return 60.0 * self.time_h

    @property
    def mean_speed(self) -> float:
        return float(np.mean(self.v)) if len(self.v) else float("nan")


def make_grid(cap: float) -> tuple[np.ndarray, float]:
    """Ladestandsraster 0 bis cap in gleichen Schritten: mindestens N_SOC Stufen und höchstens DS_MAX kWh je Stufe; gibt (Raster, Schrittweite) zurück."""
    n = max(C.N_SOC, int(np.ceil(cap / C.DS_MAX - 1e-9)))
    ds = cap / n
    return np.arange(n + 1) * ds, ds


def interp_value(arr: np.ndarray, ds: float, x) -> np.ndarray:
    """Wertfunktion `arr` (auf dem Raster mit Schritt ds) an den Stellen x: linear interpoliert; unzulässig (INF), wenn x < 0 oder einer der beiden Nachbarn unzulässig ist;
    oberhalb der Kapazität gilt der Wert bei voller Batterie."""
    x = np.asarray(x, dtype=float)
    top = len(arr) - 1
    pos = np.clip(x / ds, 0.0, float(top))
    lo = np.minimum(np.floor(pos).astype(int), top - 1)
    frac = pos - lo
    a, b = arr[lo], arr[lo + 1]
    ok = (x >= -C.SOC_EPS) & (a < INF / 2) & (b < INF / 2)
    return np.where(ok, a * (1.0 - frac) + b * frac, INF)


def with_charging(best: np.ndarray, tch: np.ndarray, fix_h: float, can_charge: np.ndarray) -> np.ndarray:
    """g(s) = min(best(s), Fixkosten + Tch(s') − Tch(s) + best(s')) über s' > s, wo Laden erlaubt ist (tch und fix_h in der Einheit der Zielfunktion: Kosten des Ladens)."""
    h = best + tch
    suf = np.minimum.accumulate(h[::-1])[::-1]
    later = np.concatenate([suf[1:], [INF]])
    return np.where(can_charge, np.minimum(best, fix_h - tch + later), best)


def cell_energies(trip: Trip, speeds) -> np.ndarray:
    """Energie (kWh) je Zelle und Geschwindigkeit: Matrix n × K."""
    veh, rt = trip.vehicle, trip.route
    return np.array([[P.cell_energy(veh, v, rt.grade[i], rt.wind[i]) for v in speeds] for i in range(rt.n)])


def plan_cost(trip: Trip, plan: Plan) -> float:
    """Zielfunktionswert eines Plans: w_time · Reisezeit + w_energy · entnommene Energie."""
    return trip.w_time * plan.time_h + trip.w_energy * plan.used_kwh


def value_functions(trip: Trip, speeds, E: np.ndarray, grid: np.ndarray, ds: float, tch: np.ndarray) -> tuple[list, list]:
    """Rückwärts-DP: Listen f (vor dem Laden) und g (nach möglichem Laden) je Zellbeginn; f[n] ist die Zielbedingung."""
    n, cap = trip.route.n, trip.vehicle.cap
    can = grid >= trip.smin_stop - C.SOC_EPS
    c_time = trip.w_time * np.array([C.DX_KM / v for v in speeds])
    f, g = [None] * (n + 1), [None] * (n + 1)
    f[n] = np.where(grid >= trip.smin_dest - C.SOC_EPS, 0.0, INF)
    for i in range(n - 1, -1, -1):
        nxt = f[n] if i == n - 1 else g[i + 1]
        best = np.full(len(grid), INF)
        for k in range(len(speeds)):
            used = np.maximum(E[i, k], grid - cap)                     # entnommene Energie: bei Rekuperation oberhalb der Kapazität nur bis „voll“
            best = np.minimum(best, c_time[k] + trip.w_energy * used + interp_value(nxt, ds, grid - E[i, k]))
        f[i] = best
        g[i] = with_charging(best, trip.w_time * tch, trip.w_time * trip.stop_h, can)
    return f, g


def solve(trip: Trip, speeds, method: str = "opt") -> Plan:
    """Kostenminimaler Plan mit den wählbaren Geschwindigkeiten `speeds` (eine einzige Geschwindigkeit = konstantes Tempo)."""
    veh, rt = trip.vehicle, trip.route
    grid, ds = make_grid(veh.cap)
    tch = P.charge_time_table(veh, trip.loss, grid)
    E = cell_energies(trip, speeds)
    f, g = value_functions(trip, speeds, E, grid, ds, tch)
    g0 = with_charging(f[0], trip.w_time * tch, trip.w_time * trip.stop_h, np.ones(len(grid), dtype=bool))      # am Start darf jederzeit geladen werden
    value = float(interp_value(g0, ds, trip.soc0))
    if value >= INF / 2:
        return Plan(method, False, note="Mit diesen Einstellungen ist das Ziel nicht erreichbar.")
    plan = replay(trip, speeds, E, f, g, tch, grid, ds, method)
    plan.value = value
    return plan


def replay(trip: Trip, speeds, E: np.ndarray, f: list, g: list, tch: np.ndarray, grid: np.ndarray, ds: float, method: str) -> Plan:
    """Fährt den DP-Plan mit stetigem Ladestand nach: Je Zelle wird zuerst über das Laden (Ziel auf dem Raster) und dann über die Geschwindigkeit entschieden,
    jeweils durch Auswertung der Wertfunktion am echten Ladestand."""
    veh, rt = trip.vehicle, trip.route
    n = rt.n
    t_cell = np.array([C.DX_KM / v for v in speeds])
    c_time = trip.w_time * t_cell
    s = trip.soc0
    p = Plan(method, True)
    p.v, p.energy = np.zeros(n), np.zeros(n)
    p.trace.append((0.0, s))
    for i in range(n):
        if i == 0 or s >= trip.smin_stop - C.SOC_EPS:
            stay = float(interp_value(f[i], ds, s))
            later = grid > s + 1e-9
            cand = trip.w_time * (trip.stop_h + tch[later] - float(np.interp(s, grid, tch))) + f[i][later]
            if cand.size:
                j = int(np.argmin(cand))
                if cand[j] < stay - 1e-9:
                    target = float(grid[later][j])
                    ch = P.charge_time_exact(veh, trip.loss, s, target)
                    p.stops.append(Stop(i * C.DX_KM, 100.0 * s / veh.cap, 100.0 * target / veh.cap, 60.0 * ch, 60.0 * (ch + trip.stop_h)))
                    p.charge_h += ch
                    p.fix_h += trip.stop_h
                    p.charged_kwh += target - s
                    p.trace.append((i * C.DX_KM, s))
                    s = target
                    p.trace.append((i * C.DX_KM, s))
        nxt = f[n] if i == n - 1 else g[i + 1]
        used = np.maximum(E[i], s - veh.cap)
        vals = c_time + trip.w_energy * used + np.array([float(interp_value(nxt, ds, s - E[i, k])) for k in range(len(speeds))])
        k = int(np.argmin(vals))
        p.v[i] = speeds[k]
        p.energy[i] = E[i, k]
        p.drive_h += t_cell[k]
        p.used_kwh += float(used[k])
        s = min(s - E[i, k], veh.cap)
        p.trace.append(((i + 1) * C.DX_KM, s))
    p.soc_end = s
    p.time_h = p.drive_h + p.charge_h + p.fix_h
    return p


def best_constant(trip: Trip, speeds) -> Plan:
    """Beste konstante Geschwindigkeit: je Geschwindigkeit ein DP mit festem Tempo (Laden bleibt frei), gewählt wird der kleinste DP-Wert (kleinste Kosten)."""
    best = None
    for v in speeds:
        p = solve(trip, [v], "const_best")
        if p.feasible and (best is None or p.value < best.value):
            best = p
    return best if best is not None else Plan("const_best", False, note="Mit diesen Einstellungen ist das Ziel nicht erreichbar.")


def check_plan(trip: Trip, plan: Plan) -> dict:
    """Unabhängige Nachrechnung eines Plans aus Geschwindigkeit je Zelle und Ladestopps (Zeit, entnommene Energie, Kosten, Endladestand, kleinster Ladestand bei Ankunft an einem Stopp,
    kleinster Ladestand überhaupt). Benutzt nur die Physik-Funktionen, nicht die DP-Tabellen (Ladezeit in geschlossener Form)."""
    veh, rt = trip.vehicle, trip.route
    stops = {int(round(st.km / C.DX_KM)): st for st in plan.stops}
    s, t, used = trip.soc0, 0.0, 0.0
    min_stop_arrival, min_soc = float("inf"), s
    for i in range(rt.n):
        if i in stops:
            st = stops[i]
            if i > 0:
                min_stop_arrival = min(min_stop_arrival, s)
            target = veh.cap * st.soc_to / 100.0
            t += P.charge_time_exact(veh, trip.loss, s, target) + trip.stop_h
            s = target
        v = float(plan.v[i])
        s_next = min(s - P.cell_energy(veh, v, rt.grade[i], rt.wind[i]), veh.cap)
        used += s - s_next
        s = s_next
        t += C.DX_KM / v
        min_soc = min(min_soc, s)
    return {"time_h": t, "used_kwh": used, "cost": trip.w_time * t + trip.w_energy * used, "soc_end": s, "min_stop_arrival": min_stop_arrival, "min_soc": min_soc,
            "ok": s >= trip.smin_dest - 1e-6 and min_soc >= -1e-6 and min_stop_arrival >= trip.smin_stop - 1e-6}
