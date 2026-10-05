"""Fehler-Einbau-Test: baut einzelne Fehler in die Rechenmodule ein und prüft, ob die Tests (ohne AppTests) sie finden.

Aufruf (im Projektordner, mit dem Test-venv): python tools/mutation_check.py [Teilstring des Dateinamens] [--jobs N] [--indices 5,8-12] [--with-app] [--dry-run]
Jeder Mutant ersetzt genau eine Stelle in einer KOPIE des Projektordners (temporärer Ordner je Mutant, das Original bleibt unberührt); PYTHONDONTWRITEBYTECODE=1, damit veralteter
Bytecode keine Überlebenden vortäuscht; Quelltexte als LF. Vor den Mutanten läuft die unveränderte Kopie: Ist sie nicht grün, bricht das Werkzeug ab.
Ein Mutant kann in eine Endlosschleife laufen; nach TIMEOUT Sekunden gilt er als gefunden. Überlebende sind entweder gleichwertig (kein sichtbarer Unterschied, dann mit
Begründung als viertes Element des Eintrags markiert) oder eine Lücke der Tests. `--with-app` nimmt die AppTests hinzu, `--dry-run` prüft nur, ob jede Zeichenkette genau einmal vorkommt."""
import concurrent.futures
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable
WITH_APP = "--with-app" in sys.argv
TIMEOUT = 900
FIRST = ["test_algorithm.py", "test_strategies.py", "test_oracle_reisetempo.py", "test_physics.py", "test_scenario.py", "test_rng.py"]   # schnelle und trennscharfe Dateien zuerst (pytest -x)
SKIP = {"test_app.py", "test_footer.py"}                                                                                          # AppTests (Streamlit), nur mit --with-app

# (Datei, alter Text, neuer Text[, Begründung, warum der Mutant gleichwertig ist])
MUTANTS = [
    # ---------------------------------------------------------------- rtp_physics.py
    ('rtp_physics.py', '    theta = np.arctan(grade)\n', '    theta = grade\n'),                                                                                                   # Winkel = Steigung (kleine-Winkel-Näherung)
    ('rtp_physics.py', 'veh.cr * veh.mass * C.G_ACC * np.cos(theta) + veh.mass * C.G_ACC * np.sin(theta)', 'veh.cr * veh.mass * C.G_ACC * np.cos(theta) - veh.mass * C.G_ACC * np.sin(theta)'),   # Vorzeichen Hangabtrieb
    ('rtp_physics.py', '    rel = (v + wind) / 3.6', '    rel = (v - wind) / 3.6'),                                                                                                 # Wind mit falschem Vorzeichen
    ('rtp_physics.py', '0.5 * C.RHO * veh.cda * rel * abs(rel)', '0.5 * C.RHO * veh.cda * rel * rel'),                                                                       # Wind ohne Betrag (Rückenwind erzeugt Schub)
    ('rtp_physics.py', '    work = wheel_force(veh, v, grade, wind) * dx * 1000.0 / 3.6e6', '    work = wheel_force(veh, v, grade, wind) * dx * 1000.0 / 3.6e5'),                # falsche Einheitenumrechnung
    ('rtp_physics.py', '    drive = work / C.ETA_DRIVE * cold if work > 0 else work * C.ETA_REGEN', '    drive = work * C.ETA_DRIVE * cold if work > 0 else work * C.ETA_REGEN'),      # Antriebswirkungsgrad multipliziert statt geteilt
    ('rtp_physics.py', '    drive = work / C.ETA_DRIVE * cold if work > 0 else work * C.ETA_REGEN', '    drive = work / C.ETA_DRIVE * cold if work > 0 else work'),                      # Rekuperation ohne Wirkungsgrad
    ('rtp_physics.py', 'return float(max(C.ETA_CHARGE_FLOOR, 1.0 - loss / 100.0 - max(0.0, C.T_REF - temp) * C.CHARGE_LOSS_COLD_PER_K))', 'return float(min(C.ETA_CHARGE_FLOOR, 1.0 - loss / 100.0 - max(0.0, C.T_REF - temp) * C.CHARGE_LOSS_COLD_PER_K))'),   # Untergrenze wird zur Obergrenze
    ('rtp_physics.py', '    return np.interp(soc_frac, pts[:, 0], pts[:, 1]) * veh.peak * eta_charge(temp, loss)', '    return np.interp(soc_frac, pts[:, 0], pts[:, 1]) * veh.peak'),               # Ladewirkungsgrad fehlt
    ('rtp_physics.py', '    return np.concatenate([[0.0], np.cumsum(0.5 * (inv[1:] + inv[:-1]) * np.diff(grid))])', '    return np.concatenate([[0.0], np.cumsum(inv[1:] * np.diff(grid))])'),             # Trapezregel durch Rechteckregel ersetzt
    ('rtp_physics.py', '        total += (hi - lo) / (scale * pa) if abs(pb - pa) < 1e-12 else np.log(pb / pa) / (scale * slope)', '        total += (hi - lo) / (scale * pa) if abs(pb - pa) < 1e-12 else np.log(pb / pa) / scale'),   # Steigung fehlt im Logarithmusterm
    ('rtp_physics.py', '        pa = p0 + slope * (lo - x0 * veh.cap)                 # Leistungsanteil bei lo', '        pa = p0 + slope * lo                 # Leistungsanteil bei lo'),                  # Stückbeginn nicht abgezogen
    ('rtp_physics.py', '        lo, hi = max(s_from, x0 * veh.cap), min(s_to, x1 * veh.cap)', '        lo, hi = max(s_from, x0 * veh.cap), min(s_to, x1 * veh.cap * 0.999)'),         # Stückgrenze verschoben
    # ---------------------------------------------------------------- rtp_algorithm.py
    ('rtp_algorithm.py', '    ds = cap / n', '    ds = cap / (n + 1)'),                                                                                                                 # Rasterschritt falsch
    ('rtp_algorithm.py', 'int(np.ceil(cap / C.DS_MAX - 1e-9))', 'int(np.floor(cap / C.DS_MAX - 1e-9))'),                                                                  # Raster für große Akkus zu grob
    ('rtp_algorithm.py', '    ok = (x >= -C.SOC_EPS) & (a < INF / 2) & (b < INF / 2)', '    ok = (x >= -C.SOC_EPS) & (a < INF / 2)'),                                                         # unzulässiger rechter Nachbar ignoriert
    ('rtp_algorithm.py', '    ok = (x >= -C.SOC_EPS) & (a < INF / 2) & (b < INF / 2)', '    ok = (a < INF / 2) & (b < INF / 2)'),                                                             # negativer Ladestand zulässig
    ('rtp_algorithm.py', '    return np.where(ok, a * (1.0 - frac) + b * frac, INF)', '    return np.where(ok, a * frac + b * (1.0 - frac), INF)'),                                           # Interpolationsgewichte vertauscht
    ('rtp_algorithm.py', '    h = best + tch', '    h = best - tch'),                                                                                                                         # Ladezeit mit falschem Vorzeichen im Suffix-Minimum
    ('rtp_algorithm.py', '    suf = np.minimum.accumulate(h[::-1])[::-1]', '    suf = np.minimum.accumulate(h)'),                                                                    # Präfix- statt Suffix-Minimum
    ('rtp_algorithm.py', '    later = np.concatenate([suf[1:], [INF]])', '    later = suf',
     'Mit positiver Fixzeit lohnt „Laden auf dasselbe Niveau“ nie (Fixzeit + best(s) > best(s)); die strikte Verschiebung ändert den Wert nur bei Fixzeit ≤ 0, und die Regler lassen mindestens 1 min zu'),
    ('rtp_algorithm.py', '    return np.where(can_charge, np.minimum(best, fix_h - tch + later), best)', '    return np.where(can_charge, np.minimum(best, -tch + later), best)'),                              # Fixzeit weggelassen
    ('rtp_algorithm.py', '    return np.where(can_charge, np.minimum(best, fix_h - tch + later), best)', '    return np.where(can_charge, np.minimum(best, fix_h + tch + later), best)'),                        # Ladezeit mit falschem Vorzeichen
    ('rtp_algorithm.py', '    return np.where(can_charge, np.minimum(best, fix_h - tch + later), best)', '    return np.where(~can_charge, np.minimum(best, fix_h - tch + later), best)'),                       # Mindestladestand-Maske umgekehrt
    ('rtp_algorithm.py', '    can = grid >= trip.smin_stop - C.SOC_EPS', '    can = grid >= trip.smin_dest - C.SOC_EPS'),                                                         # falscher Mindestladestand für Stopps
    ('rtp_algorithm.py', '    can = grid >= trip.smin_stop - C.SOC_EPS', '    can = grid >= trip.smin_stop + C.SOC_EPS'),                                                         # Grenze < statt <= beim Mindestladestand am Stopp
    ('rtp_algorithm.py', '            best = np.minimum(best, t_cell[k] + interp_value(nxt, ds, grid - E[i, k]))', '            best = np.minimum(best, t_cell[k] + interp_value(nxt, ds, grid + E[i, k]))'),    # Energie mit falschem Vorzeichen
    ('rtp_algorithm.py', '    g0 = with_charging(f[0], tch, trip.stop_h, np.ones(len(grid), dtype=bool))', '    g0 = with_charging(f[0], tch, trip.stop_h, grid >= trip.smin_stop - C.SOC_EPS)'),          # Laden am Start nur oberhalb des Mindestladestands
    ('rtp_algorithm.py', '        if i == 0 or s >= trip.smin_stop - C.SOC_EPS:', '        if s >= trip.smin_stop - C.SOC_EPS:'),                                                       # kein Laden am Start unter dem Mindestladestand
    ('rtp_algorithm.py', '                if cand[j] < stay - 1e-9:', '                if cand[j] < stay + 10.0:'),                                                      # Stopp auch ohne Gewinn
    ('rtp_algorithm.py', '        vals = t_cell + np.array([float(interp_value(nxt, ds, s - E[i, k])) for k in range(len(speeds))])', '        vals = t_cell + np.array([float(interp_value(nxt, ds, s + E[i, k])) for k in range(len(speeds))])'),   # Nachfahrt mit falschem Vorzeichen
    ('rtp_algorithm.py', '        s = min(s - E[i, k], veh.cap)\n        p.trace', '        s = s - E[i, k]\n        p.trace'),                                                                        # Rekuperation oberhalb der Kapazität nicht verworfen
    ('rtp_algorithm.py', '    p.time_h = p.drive_h + p.charge_h + p.fix_h', '    p.time_h = p.drive_h + p.charge_h'),                                                                  # Fixzeit nicht in der Reisezeit
    ('rtp_algorithm.py', '        if p.feasible and (best is None or p.value_h < best.value_h):', '        if p.feasible and (best is None or p.value_h > best.value_h):'),                          # schlechteste konstante Geschwindigkeit gewählt
    ('rtp_algorithm.py', '            if i > 0:\n                min_stop_arrival', '            if i >= 0:\n                min_stop_arrival'),                                                          # Stopp am Start zählt als Ankunftsstopp
    ('rtp_algorithm.py', 'and min_stop_arrival >= trip.smin_stop - 1e-6}', 'and min_stop_arrival >= trip.smin_dest - 1e-6}'),                                                          # falscher Mindestladestand im Prüfer
    # ---------------------------------------------------------------- rtp_strategies.py
    ('rtp_strategies.py', '        s = min(s - e, cap)\n        low = min(low, s)', '        s = s - e\n        low = min(low, s)'),                                                                  # simulate_ahead ohne Kappung
    ('rtp_strategies.py', '        low = min(low, s)\n    return low, s', '        pass\n    return low, s'),                                                                               # kleinster Stand wird nicht verfolgt
    ('rtp_strategies.py', '    ceiling = veh.cap * C.RULE_CHARGE_TO / 100.0', '    ceiling = veh.cap * C.RULE_CHARGE_TO / 1000.0'),                                                     # Ladeziel 8 statt 80 %
    ('rtp_strategies.py', '        finish = low >= -C.SOC_EPS and end >= trip.smin_dest - C.SOC_EPS', '        finish = low >= -C.SOC_EPS or end >= trip.smin_dest - C.SOC_EPS'),                        # Zielprüfung mit „oder“
    ('rtp_strategies.py', '        finish = low >= -C.SOC_EPS and end >= trip.smin_dest - C.SOC_EPS', '        finish = low >= -C.SOC_EPS and end > trip.smin_dest + C.SOC_EPS'),                        # Zielprüfung strikt statt mit Gleichheit
    ('rtp_strategies.py', '        if not finish and s - E[i] < trip.smin_stop - C.SOC_EPS:', '        if not finish and s - E[i] < trip.smin_stop + C.SOC_EPS:'),                                # Stoppbedingung: Gleichheit löst einen Stopp aus (Grenze < gegen <=)
    ('rtp_strategies.py', '        if not finish and s - E[i] < trip.smin_stop - C.SOC_EPS:', '        if s - E[i] < trip.smin_stop - C.SOC_EPS:'),                                                  # Stopp auch wenn das Ziel erreichbar ist
    ('rtp_strategies.py', '            target = min(ceiling, need)', '            target = max(ceiling, need)'),                                                              # Ladeziel: Maximum statt Minimum
    ('rtp_strategies.py', '            target = min(ceiling, need)', '            target = ceiling'),                                                                           # immer bis zum Ladeziel laden
    ('rtp_strategies.py', '            p.fix_h += trip.stop_h\n            p.charged_kwh', '            p.charged_kwh'),                                                                      # Fixzeit der Regel nicht gezählt
    ('rtp_strategies.py', '"const_max": A.solve(trip, [top], "const_max")', '"const_max": A.solve(trip, speeds, "const_max")'),                                                       # Tempolimit-Verfahren mit freier Geschwindigkeit
    ('rtp_strategies.py', '"opt": A.solve(trip, speeds, "opt")', '"opt": A.solve(trip, [top], "opt")'),                                                                                         # Optimum ohne freie Geschwindigkeit
    # ---------------------------------------------------------------- rtp_scenario.py
    ('rtp_scenario.py', '    top = int(vmax // C.V_STEP) * C.V_STEP', '    top = int(-(-vmax // C.V_STEP)) * C.V_STEP'),                                                                        # Tempolimit auf das Raster aufgerundet
    ('rtp_scenario.py', '    return list(range(C.V_MIN, max(top, C.V_MIN) + 1, C.V_STEP))', '    return list(range(C.V_MIN, max(top, C.V_MIN), C.V_STEP))'),                                      # Tempolimit selbst fehlt
    ('rtp_scenario.py', '        return g - g.mean()\n    if profile == "mittelgebirge":', '        return g\n    if profile == "mittelgebirge":'),                                                  # hügeliges Profil nicht mittelwertfrei
    ('rtp_scenario.py', '    cap = veh.cap\n    return Trip(veh, route, float(s["temp"]), cap * float(s["soc0"]) / 100.0, cap * float(s["smin_stop"]) / 100.0, cap * float(s["smin_dest"]) / 100.0,', '    cap = veh.cap\n    return Trip(veh, route, float(s["temp"]), cap * float(s["soc0"]) / 100.0, cap * float(s["smin_dest"]) / 100.0, cap * float(s["smin_stop"]) / 100.0,'),   # Mindestladestände vertauscht
    ('rtp_scenario.py', 'float(s["loss"]), float(s["stop_min"]) / 60.0)', 'float(s["loss"]), float(s["stop_min"]) / 6.0)'),                                                                       # Fixzeit falsch umgerechnet
    ('rtp_scenario.py', '    z = (sum(rng.below(1000) for _ in range(12)) - 6000) / 1000.0', '    z = (sum(rng.below(1000) for _ in range(12)) - 5000) / 1000.0'),                                  # Irwin-Hall nicht mittelwertfrei
    ('rtp_scenario.py', '    g[s2:s2 + k] = -up', '    g[s2:s2 + k] = up'),                                                                                                                              # Abstieg des Passes wird Anstieg
    ('rtp_scenario.py', '        wind = wind + _pieces(rng, n, 4, 10, lambda: float(rng.between(-15, 15)))', '        wind = _pieces(rng, n, 4, 10, lambda: float(rng.between(-15, 15)))'),                         # Grundwind fehlt bei wechselndem Wind
]


def check_unique():
    bad = []
    for n, m in enumerate(MUTANTS, 1):
        name, old, new = m[:3]
        text = (ROOT / name).read_bytes().decode("utf-8").replace("\r\n", "\n")
        if text.count(old) != 1:
            bad.append((n, name, old[:70], text.count(old)))
        if old == new:
            bad.append((n, name, "alt == neu", 0))
    return bad


def test_files(base: pathlib.Path):
    names = sorted(f.name for f in (base / "tests").glob("test_*.py"))
    skip = set() if WITH_APP else SKIP
    ordered = [f for f in FIRST if f in names] + [f for f in names if f not in FIRST]
    return [f"tests/{f}" for f in ordered if f not in skip]


def run_tests(tmp: pathlib.Path):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *test_files(tmp)], cwd=tmp, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=TIMEOUT)


def run_one(args):
    n, name, old, new, base = args
    tmp = pathlib.Path(tempfile.mkdtemp(prefix=f"rtp_mut{n}_"))
    try:
        shutil.copytree(base, tmp, dirs_exist_ok=True)
        path = tmp / name
        original = path.read_bytes().decode("utf-8")
        path.write_bytes(original.replace(old, new).encode("utf-8"))
        try:
            r = run_tests(tmp)
            return n, name, old, new, r.returncode == 0, False
        except subprocess.TimeoutExpired:
            return n, name, old, new, False, True                 # Endlosschleife oder zu langsam: gilt als gefunden
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def make_base() -> pathlib.Path:
    base = pathlib.Path(tempfile.mkdtemp(prefix="rtp_mut_base_"))
    for f in ROOT.glob("*.py"):
        (base / f.name).write_bytes(f.read_bytes().replace(b"\r\n", b"\n"))
    shutil.copytree(ROOT / "tests", base / "tests", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "tools", base / "tools", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "data", base / "data")
    for extra in ("README.md", "requirements.txt", "requirements-dev.txt"):
        if (ROOT / extra).exists():
            shutil.copy(ROOT / extra, base / extra)
    if (ROOT / ".streamlit").exists():
        shutil.copytree(ROOT / ".streamlit", base / ".streamlit")
    for f in (base / "tests").glob("*.py"):
        f.write_bytes(f.read_bytes().replace(b"\r\n", b"\n"))
    return base


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")          # Windows-Konsole (cp1252) vertrüge Umlaute und Sonderzeichen sonst nicht
    args =[a for a in sys.argv[1:] if not a.startswith("--")]
    only = args[0] if args else ""
    jobs = 6
    if "--jobs" in sys.argv:
        jobs = int(sys.argv[sys.argv.index("--jobs") + 1])
        only = "" if only == str(jobs) else only
    wanted = None
    if "--indices" in sys.argv:
        spec = sys.argv[sys.argv.index("--indices") + 1]
        only = "" if only == spec else only
        wanted = set()
        for part in spec.split(","):
            lo, _, hi = part.partition("-")
            wanted.update(range(int(lo), int(hi or lo) + 1))
    bad = check_unique()
    for b in bad:
        print("FEHLER (Stelle nicht eindeutig gefunden):", b)
    if "--dry-run" in sys.argv:
        print(f"{len(MUTANTS)} Mutanten, {len(bad)} Fehler in der Mutantenliste")
        return
    base = make_base()
    try:
        r = run_tests(base)
        if r.returncode != 0:
            print("Die unveränderte Kopie besteht die Tests nicht; Abbruch.\n" + r.stdout[-3000:])
            sys.exit(2)
        bad_ids = {b[0] for b in bad}
        work = [(n, m[0], m[1], m[2], base) for n, m in enumerate(MUTANTS, 1) if n not in bad_ids and (not only or only in m[0]) and (wanted is None or n in wanted)]
        survivors, equivalent, killed = [], [], 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
            for n, name, old, new, survived, timeout in pool.map(run_one, work):
                reason = MUTANTS[n - 1][3] if len(MUTANTS[n - 1]) > 3 else ""
                if timeout:
                    print(f"[{n:3d}] Zeitüberschreitung (als gefunden gezählt)  {name}", flush=True)
                if survived and reason:
                    equivalent.append(n)
                    print(f"[{n:3d}] überlebt, gleichwertig  {name}: {old[:60]!r} -> {new[:60]!r}\n        Begründung: {reason}", flush=True)
                elif survived:
                    survivors.append(n)
                    print(f"[{n:3d}] ÜBERLEBT  {name}: {old[:70]!r} -> {new[:70]!r}", flush=True)
                else:
                    killed += 1
                    print(f"[{n:3d}] gefunden  {name}", flush=True)
        print(f"\n{killed} gefunden, {len(survivors)} überlebt (Lücken), {len(equivalent)} gleichwertig (begründet), {len(bad)} Fehler in der Mutantenliste")
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    main()
