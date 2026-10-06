"""Messreihe der Demo: rechnet alle Fälle der Sweeps (Ladeleistung × Tempolimit × Zeitwert, Wind × Profil, Fahrzeug × Länge × Zeitwert, Stoppfixzeit, Höhenunterschied) und schreibt data/rtp_results.json.
Alle Sweeps außer `power` und `vehicle` laufen mit „Zeit allein“ (C.TV_FAST); `power` mit „Zeit allein“ und dem Standard-Zeitwert, `vehicle` über die ganze Spanne der Zeitwerte.

    python tools/sweep.py                 # alle Sweeps, 4 Prozesse
    python tools/sweep.py --workers 2     # weniger Prozesse
    python tools/sweep.py --only power    # nur ein Sweep (power, wind, vehicle, fix, height) (schreibt in tools/sweep_<name>.json)

Live-Rechnung und Messreihe benutzen dieselben Funktionen (rtp_evaluation.run_live); die App rechnet die Messreihe nie live."""
from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import rtp_algorithm as A  # noqa: E402
import rtp_constants as C  # noqa: E402
import rtp_evaluation as E  # noqa: E402

SEEDS = tuple(range(100, 110))
SEEDS_SMALL = tuple(range(100, 105))
PEAKS = (50.0, 100.0, 150.0, 250.0, 350.0)
VMAXES = (110, 130, 160, 180)
TVS = C.TV_OPTIONS
POWER_TVS = (C.TV_FAST, C.DEFAULT_TV)
LENGTHS = (300, 600, 1000)
WINDS = (-30, -15, 0, 15, 30)
PROFILES = ("flach", "huegelig", "mittelgebirge", "pass")
STOPS = (1.0, 5.0, 15.0, 30.0)
RISES = (-500, 0, 500, 1000)


def scenario(**over) -> dict:
    """Szenario der Messreihe: Standardwerte mit „Zeit allein“, außer der Fall nennt einen Zeitwert."""
    return {**C.BASE_SCENARIO, "tv": C.TV_FAST, **over}


def cases() -> list[dict]:
    out = []
    for peak, vmax, tv, seed in itertools.product(PEAKS, VMAXES, POWER_TVS, SEEDS):
        out.append({"sweep": "power", "s": scenario(peak=peak, vmax=vmax, tv=tv, seed=seed)})
    for peak, profile, wind, seed in itertools.product((50.0, 150.0), PROFILES, WINDS, SEEDS_SMALL):
        out.append({"sweep": "wind", "s": scenario(peak=peak, profile=profile, headwind=wind, vmax=160, seed=seed)})
    for veh, length, tv, seed in itertools.product(C.VEHICLE_ORDER, LENGTHS, TVS, SEEDS_SMALL):
        out.append({"sweep": "vehicle", "s": scenario(**C.vehicle_scenario(veh), length=length, tv=tv, seed=seed)})
    for peak, stop, seed in itertools.product((50.0, 150.0, 350.0), STOPS, SEEDS_SMALL):
        out.append({"sweep": "fix", "s": scenario(peak=peak, stop_min=stop, seed=seed)})
    for veh, profile, rise, seed in itertools.product(("Pkw", "Elektro-Lkw"), ("flach", "pass"), RISES, SEEDS_SMALL):
        out.append({"sweep": "height", "s": scenario(**C.vehicle_scenario(veh), profile=profile, rise=rise, length=600, seed=seed)})
    return out


def row_of(case: dict) -> dict:
    s = case["s"]
    run = E.run_live(s)
    pl = run["plans"]
    row = {"sweep": case["sweep"], **{k: s[k] for k in C.SCENARIO_KEYS}}
    for key in C.METHODS:
        p = pl[key]
        row[f"t_{key}"] = p.time_min if p.feasible else None
        row[f"stops_{key}"] = len(p.stops) if p.feasible else None
        row[f"e_{key}"] = p.used_kwh if p.feasible else None
        row[f"j_{key}"] = A.plan_cost(run["trip"], p) if p.feasible else None
    opt, best = pl["opt"], pl["const_best"]
    row["v_best"] = best.mean_speed if best.feasible else None
    row["v_opt"] = opt.mean_speed if opt.feasible else None
    row["v_opt_min"] = float(opt.v.min()) if opt.feasible else None
    row["v_opt_max"] = float(opt.v.max()) if opt.feasible else None
    row["tgt_opt"] = E.mean_target_soc(opt) if opt.feasible and opt.stops else None
    row["value_opt"] = opt.value if opt.feasible else None
    row["cons_opt"] = 100.0 * opt.used_kwh / run["trip"].route.length if opt.feasible else None
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--only", help="nur diesen Sweep rechnen (power, wind, vehicle, fix, height)")
    args = ap.parse_args()
    cs = [c for c in cases() if not args.only or c["sweep"] == args.only]
    t0 = time.time()
    with Pool(args.workers) as pool:
        rows = pool.map(row_of, cs, chunksize=4)
    meta = {"seeds": [SEEDS[0], SEEDS[-1] + 1], "seeds_small": [SEEDS_SMALL[0], SEEDS_SMALL[-1] + 1], "peaks": list(PEAKS), "vmaxes": list(VMAXES), "tvs": list(TVS), "power_tvs": list(POWER_TVS), "lengths": list(LENGTHS),
            "winds": list(WINDS), "profiles": list(PROFILES), "stops": list(STOPS), "rises": list(RISES), "vehicles": list(C.VEHICLE_ORDER), "cases": len(rows), "seconds": round(time.time() - t0)}
    root = Path(__file__).resolve().parent.parent
    out = root / (f"tools/sweep_{args.only}.json" if args.only else C.RESULTS_FILE)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"meta": meta, "rows": rows}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(rows)} Fälle in {time.time() - t0:.0f} s nach {out}")


if __name__ == "__main__":
    main()
