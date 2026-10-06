"""Künstliche Pläne und Läufe für die Tests von Auswertung, Meldungen, Geschichten, PDF und Figuren (ohne DP-Rechnung, mit handgerechneten Zahlen)."""
from types import SimpleNamespace

import numpy as np

import rtp_algorithm as A
import rtp_constants as C


def stop(km=100.0, soc_from=10.0, soc_to=60.0, charge_min=20.0, total_min=25.0):
    return A.Stop(km, soc_from, soc_to, charge_min, total_min)


def plan(method, time_h, *, charge_h=0.0, fix_h=0.0, v=None, stops=None, energy=None, charged_kwh=0.0, used_kwh=None):
    """Erreichbarer Plan mit der Gesamtzeit time_h (Stunden); die Fahrzeit ist der Rest nach Laden und Fixzeit. Die entnommene Energie ist die Summe der Energie je Zelle, wenn nichts anderes steht."""
    n = 0 if v is None else len(v)
    e = np.array(energy if energy is not None else [0.0] * n, dtype=float)
    return A.Plan(method, True, time_h=time_h, drive_h=time_h - charge_h - fix_h, charge_h=charge_h, fix_h=fix_h, stops=list(stops or []), v=np.array(v if v is not None else [], dtype=float),
                  energy=e, charged_kwh=charged_kwh, used_kwh=float(e.sum()) if used_kwh is None else float(used_kwh))


def unreachable(method, note="Mit diesen Einstellungen ist das Ziel nicht erreichbar."):
    return A.Plan(method, False, note=note)


def fake_run(opt=10.0, rule=10.2, cmax=10.1, cbest=10.05, *, v_best=120.0, top=130, opt_stops=None, length=100.0, w_time=1.0, w_energy=0.0, used=None, price=0.5, loss=10.0):
    """Lauf aus den Gesamtzeiten (Stunden) der vier Verfahren; None heißt nicht erreichbar. Die beste konstante Fahrt hat die Geschwindigkeit v_best auf allen Zellen.
    Zielfunktion: Zeitwert w_time und Energiegewicht w_energy (Standard: Zeit allein); `used` = {Verfahren: der Batterie entnommene Energie in kWh}."""
    n = int(length / C.DX_KM)
    used = used or {}
    plans = {"rule": plan("rule", rule, v=[top] * n, used_kwh=used.get("rule", 0.0)) if rule is not None else unreachable("rule", "Die Praxisregel erreicht das Ziel nicht."),
             "const_max": plan("const_max", cmax, v=[top] * n, used_kwh=used.get("const_max", 0.0)) if cmax is not None else unreachable("const_max"),
             "const_best": plan("const_best", cbest, v=[v_best] * n, used_kwh=used.get("const_best", 0.0)) if cbest is not None else unreachable("const_best"),
             "opt": plan("opt", opt, v=[top] * n, stops=opt_stops, used_kwh=used.get("opt", 0.0)) if opt is not None else unreachable("opt")}
    route = SimpleNamespace(length=length, n=n)
    return {"plans": plans, "speeds": list(range(C.V_MIN, top + 1, C.V_STEP)), "trip": SimpleNamespace(route=route, w_time=w_time, w_energy=w_energy),
            "settings": {"price": price, "loss": loss}}
