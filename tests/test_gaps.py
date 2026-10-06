"""Figuren: Zahl und Namen der Spuren, Werte aus den Daten, feste Achsen (fixedrange) für Touch-Scrollen."""
import statistics as st
from types import SimpleNamespace

import numpy as np
import pytest

import rtp_constants as C
import rtp_evaluation as E
import rtp_results as R
import rtp_visualization as V
from rtp_scenario import make_route
from helpers_fake import plan, stop, unreachable

TRACE_NAMES = ["Tempolimit", "Geschwindigkeit", "Ladestand Praxisregel", "Ladestand", "Höhe", "Gegenwind"]


def fake_trip_run(rule_ok=True):
    """Strecke von 20 km (vier Zellen), Batterie 100 kWh; alle Zahlen von Hand gewählt."""
    route = SimpleNamespace(length=20.0, n=4, height=np.array([0.0, 10.0, 30.0, 20.0, 20.0]), wind=np.array([0.0, 10.0, 10.0, -5.0]))
    trip = SimpleNamespace(route=route, vehicle=SimpleNamespace(cap=100.0), smin_stop=10.0)
    opt = plan("opt", 0.5, charge_h=0.1, fix_h=0.05, v=[100, 110, 110, 90], stops=[stop(km=10.0)])
    opt.trace = [(0.0, 100.0), (5.0, 80.0), (10.0, 60.0), (10.0, 90.0), (15.0, 70.0), (20.0, 50.0)]
    rule = plan("rule", 0.6, v=[130] * 4) if rule_ok else unreachable("rule")
    if rule_ok:
        rule.trace = [(0.0, 100.0), (5.0, 70.0), (10.0, 40.0), (15.0, 10.0), (20.0, 0.0)]
    return {"plans": {"rule": rule, "const_max": plan("const_max", 0.6, v=[130] * 4), "const_best": plan("const_best", 0.55, v=[110] * 4), "opt": opt}, "speeds": [40, 130], "trip": trip}


def all_axes(fig):
    return list(fig.select_xaxes()) + list(fig.select_yaxes())


def trace(fig, name):
    return next(t for t in fig.data if t.name == name)


# ------------------------------------------------------------------ Fahrtbild
def test_speed_steps_form_a_staircase():
    xs, ys = V.speed_steps(plan("opt", 1.0, v=[100, 120]), 5.0)
    assert xs == [0.0, 5.0, 5.0, 10.0] and ys == [100.0, 100.0, 120.0, 120.0]
    xs, ys = V.speed_steps(plan("opt", 1.0, v=[90]), 2.5)
    assert xs == [0.0, 2.5] and ys == [90.0, 90.0] and V.speed_steps(plan("opt", 1.0, v=[]), 5.0) == ([], [])


def test_trip_figure_has_the_named_traces_for_a_chosen_method():
    fig = V.build_trip(fake_trip_run(), "opt")
    assert [t.name for t in fig.data] == TRACE_NAMES and len(fig.data) == 6


def test_trip_figure_omits_the_rule_trace_for_the_rule_itself_and_if_the_rule_is_unreachable():
    assert [t.name for t in V.build_trip(fake_trip_run(), "rule").data] == [n for n in TRACE_NAMES if n != "Ladestand Praxisregel"]
    assert [t.name for t in V.build_trip(fake_trip_run(rule_ok=False), "opt").data] == [n for n in TRACE_NAMES if n != "Ladestand Praxisregel"]
    assert [t.name for t in V.build_trip(fake_trip_run(), "const_best").data] == TRACE_NAMES


def test_trip_figure_values_come_from_the_plan_and_the_route():
    fig = V.build_trip(fake_trip_run(), "opt")
    lim = trace(fig, "Tempolimit")
    assert list(lim.x) == [0, 20.0] and list(lim.y) == [130, 130]
    v = trace(fig, "Geschwindigkeit")
    assert list(v.x) == [0.0, 5.0, 5.0, 10.0, 10.0, 15.0, 15.0, 20.0] and list(v.y) == [100.0, 100.0, 110.0, 110.0, 110.0, 110.0, 90.0, 90.0]
    soc, rule = trace(fig, "Ladestand"), trace(fig, "Ladestand Praxisregel")
    assert list(soc.x) == [0.0, 5.0, 10.0, 10.0, 15.0, 20.0] and list(soc.y) == pytest.approx([100.0, 80.0, 60.0, 90.0, 70.0, 50.0])         # kWh in Prozent der 100 kWh
    assert list(rule.x) == [0.0, 5.0, 10.0, 15.0, 20.0] and list(rule.y) == pytest.approx([100.0, 70.0, 40.0, 10.0, 0.0])
    h, w = trace(fig, "Höhe"), trace(fig, "Gegenwind")
    assert list(h.x) == [0.0, 5.0, 10.0, 15.0, 20.0] and list(h.y) == [0.0, 10.0, 30.0, 20.0, 20.0]
    assert list(w.x) == [0.0, 5.0, 5.0, 10.0, 10.0, 15.0, 15.0, 20.0] and list(w.y) == [0.0, 0.0, 10.0, 10.0, 10.0, 10.0, -5.0, -5.0]


def test_trip_figure_uses_method_colors_and_other_chosen_methods():
    for key in ("opt", "rule", "const_max", "const_best"):
        fig = V.build_trip(fake_trip_run(), key)
        assert trace(fig, "Geschwindigkeit").line.color == C.METHOD_COLORS[key] and trace(fig, "Ladestand").line.color == C.METHOD_COLORS[key]
    const = V.build_trip(fake_trip_run(), "const_best")
    assert set(trace(const, "Geschwindigkeit").y) == {110.0}


def test_trip_figure_shades_each_stop_and_marks_the_minimum_stop_level():
    fig = V.build_trip(fake_trip_run(), "opt")
    rects = [s for s in fig.layout.shapes if s.type == "rect"]
    lines = [s for s in fig.layout.shapes if s.type == "line"]
    assert len(rects) == 1 and rects[0].x0 == 7.0 and rects[0].x1 == 13.0                     # Stopp bei km 10, 3 km nach beiden Seiten
    assert len(lines) == 1 and lines[0].y0 == pytest.approx(10.0)                              # Mindestladestand am Stopp: 10 kWh von 100 kWh
    assert [s for s in V.build_trip(fake_trip_run(), "rule").layout.shapes if s.type == "rect"] == []
    run = fake_trip_run()
    run["plans"]["opt"].stops = [stop(km=5.0), stop(km=10.0)]
    assert len([s for s in V.build_trip(run, "opt").layout.shapes if s.type == "rect"]) == 2


def test_trip_figure_axes_titles_ranges_and_fixed_axes():
    fig = V.build_trip(fake_trip_run(), "opt")
    ys = {ax.title.text: ax for ax in fig.select_yaxes()}
    assert set(ys) == {"km/h", "Ladestand (%)", "Höhe (m)", "Gegenwind (km/h)"}
    assert tuple(ys["Ladestand (%)"].range) == (0, 105) and tuple(ys["Gegenwind (km/h)"].range) == (C.WIND_MIN - 15, C.WIND_MAX + 15) == (-55, 55)
    assert [ax.title.text for ax in fig.select_xaxes() if ax.title.text] == ["Weg (km)"]
    axes = all_axes(fig)
    assert len(axes) == 7 and all(ax.fixedrange is True for ax in axes)                         # drei x-Achsen, vier y-Achsen (Wind rechts)


def test_the_wind_axis_covers_every_wind_the_sliders_allow():
    lo, hi = C.WIND_MIN - 15, C.WIND_MAX + 15
    for seed in range(40):
        for head in (C.WIND_MIN, C.WIND_MAX):
            w = make_route(600.0, "flach", seed, head, "wechselnd").wind
            assert lo <= w.min() and w.max() <= hi


# ------------------------------------------------------------------ Zeitbalken
def test_time_bars_stack_drive_charge_and_fix_with_labels():
    run = fake_trip_run()
    run["plans"]["rule"] = plan("rule", 1.75, charge_h=0.5, fix_h=0.25, v=[130] * 4)
    run["plans"]["opt"] = plan("opt", 1.5, charge_h=0.25, fix_h=0.25, v=[100] * 4)
    run["plans"]["const_max"] = unreachable("const_max")
    fig = V.build_time_bars(run)
    assert [t.name for t in fig.data[:3]] == ["Fahren", "Laden", "Fixzeit der Stopps"] and fig.layout.barmode == "stack"
    labels = [C.METHOD_LABELS[k] for k in ("rule", "const_best", "opt")]                      # nicht erreichbare Verfahren fehlen
    assert list(fig.data[0].x) == labels
    assert list(fig.data[0].y) == pytest.approx([60 * 1.0, 60 * (0.55 - 0), 60 * 1.0])          # Fahrzeit: 1,75 − 0,5 − 0,25 = 1 h; Bestwert 0,55 h; Optimum 1,5 − 0,25 − 0,25 = 1 h
    assert list(fig.data[1].y) == pytest.approx([30.0, 0.0, 15.0]) and list(fig.data[2].y) == pytest.approx([15.0, 0.0, 15.0])
    total = fig.data[3]
    assert total.mode == "text" and list(total.y) == pytest.approx([105.0, 33.0, 90.0])
    assert list(total.text) == ["105 min (+16.7 %)", "33 min (+" + f"{100 * (0.55 / 1.5 - 1):.1f}" + " %)", "90 min"]       # Abstand zum Optimum: 1,75 / 1,5 − 1 = 16,7 %; beim Optimum keiner
    assert [ax.fixedrange for ax in all_axes(fig)] == [True, True]


# ------------------------------------------------------------------ echter Lauf
@pytest.fixture(scope="module")
def real_run():
    return E.run_live(C.PRESETS["Standard"])


@pytest.mark.parametrize("key", C.VIEW_OPTIONS)
def test_trip_figure_of_a_real_run_matches_the_plan(real_run, key):
    fig = V.build_trip(real_run, key)
    p, route = real_run["plans"][key], real_run["trip"].route
    assert [t.name for t in fig.data] == [n for n in TRACE_NAMES if n != "Ladestand Praxisregel" or key != "rule"]
    assert list(trace(fig, "Geschwindigkeit").y)[::2] == [float(x) for x in p.v] and list(trace(fig, "Höhe").y) == pytest.approx(list(route.height))
    soc = list(trace(fig, "Ladestand").y)
    assert min(soc) >= -1e-6 and max(soc) <= 100 + 1e-6                                          # Ladestand in Prozent der Kapazität
    assert len([s for s in fig.layout.shapes if s.type == "rect"]) == len(p.stops) and all(ax.fixedrange is True for ax in all_axes(fig))


def test_time_bars_of_a_real_run_have_one_bar_per_reachable_method(real_run):
    fig = V.build_time_bars(real_run)
    assert list(fig.data[0].x) == [C.METHOD_LABELS[k] for k in C.METHODS] and list(fig.data[3].y) == pytest.approx([real_run["plans"][k].time_min for k in C.METHODS])
    stacked = np.array([fig.data[i].y for i in range(3)]).sum(axis=0)
    assert stacked == pytest.approx(list(fig.data[3].y))                                        # Fahren + Laden + Fixzeit = Reisezeit


# ------------------------------------------------------------------ Messreihen-Figuren
@pytest.fixture(scope="module")
def res():
    return R.load_results()


def rows_where(res, sweep, **kw):
    return [r for r in res["rows"] if r["sweep"] == sweep and all(r[k] == v for k, v in kw.items())]


def test_power_gap_has_one_line_per_comparison_method_with_the_summary_values(res):
    fig = V.build_power_gap(res, 160)
    assert [t.name for t in fig.data] == [C.METHOD_LABELS[k] for k in ("rule", "const_max", "const_best")]
    assert list(fig.data[0].x) == ["50", "100", "150", "250", "350"] and fig.layout.xaxis.type == "category"
    for t, key in zip(fig.data, ("rule", "const_max", "const_best")):
        assert list(t.y) == [R.power_summary(res, p, 160)[f"gap_{key}"] for p in res["meta"]["peaks"]] and t.line.color == C.METHOD_COLORS[key]
    rows = rows_where(res, "power", peak=50.0, vmax=160, tv=C.TV_FAST)
    assert fig.data[0].y[0] == pytest.approx(st.mean(100 * (r["t_rule"] / r["t_opt"] - 1) for r in rows))          # Gegenprobe direkt aus den Zeilen
    assert all(ax.fixedrange is True for ax in all_axes(fig))


def test_power_gap_of_the_priced_cell_uses_the_cost_and_labels_the_axis_accordingly(res):
    fig = V.build_power_gap(res, 160, 20)
    for t, key in zip(fig.data, ("rule", "const_max", "const_best")):
        assert list(t.y) == [R.power_summary(res, p, 160, 20)[f"gap_{key}"] for p in res["meta"]["peaks"]]
    rows = rows_where(res, "power", peak=50.0, vmax=160, tv=20)
    assert fig.data[0].y[0] == pytest.approx(st.mean(100 * (r["j_rule"] / r["j_opt"] - 1) for r in rows))
    assert fig.layout.yaxis.title.text == "Kosten über dem Optimum (%)" and V.build_power_gap(res, 160).layout.yaxis.title.text == "Reisezeit über dem Optimum (%)"
    assert fig.data[0].y[0] > V.build_power_gap(res, 160).data[0].y[0]                                  # bei 20 €/h verschenkt das Tempolimit mehr (Energie) als bei Zeit allein


def test_best_speed_has_one_line_per_speed_limit_and_stays_below_the_limit(res):
    fig = V.build_best_speed(res)
    assert [t.name for t in fig.data] == [f"Tempolimit {v} km/h" for v in (110, 130, 160, 180)]
    for t, vmax in zip(fig.data, (110, 130, 160, 180)):
        assert list(t.x) == ["50", "100", "150", "250", "350"] and all(C.V_MIN <= y <= vmax for y in t.y), vmax
        assert list(t.y) == [R.power_summary(res, p, vmax)["v_best"] for p in res["meta"]["peaks"]]
    assert all(ax.fixedrange is True for ax in all_axes(fig))
    priced = V.build_best_speed(res, 20)
    assert list(priced.data[3].y) == [R.power_summary(res, p, 180, 20)["v_best"] for p in res["meta"]["peaks"]] and max(priced.data[3].y) < 130          # bei 20 €/h fährt niemand 180


def test_wind_lines_average_the_four_profiles_and_fall_with_headwind(res):
    fig = V.build_wind(res)
    assert [t.name for t in fig.data] == ["50 kW", "150 kW"] and list(fig.data[0].x) == ["-30", "-15", "0", "15", "30"]
    for t, peak in zip(fig.data, (50.0, 150.0)):
        want = [st.mean(r["v_best"] for r in rows_where(res, "wind", peak=peak, headwind=w)) for w in (-30, -15, 0, 15, 30)]
        assert list(t.y) == pytest.approx(want)
        assert t.y[0] >= t.y[-1] - 1e-9, peak                                                    # Rückenwind erlaubt mindestens so viel Tempo wie Gegenwind (bei 150 kW stößt beides ans Tempolimit)
    assert fig.data[0].y[0] > fig.data[0].y[-1] + 5                                              # bei 50 kW deutlich mehr
    assert all(ax.fixedrange is True for ax in all_axes(fig))


def test_vehicle_bars_show_the_rule_gap_with_error_bars(res):
    fig = V.build_vehicles(res, 600)
    names = list(res["meta"]["vehicles"])
    assert list(fig.data[0].x) == names and list(fig.data[0].y) == [R.vehicle_summary(res, v, 600)["gap_rule"] for v in names]
    assert list(fig.data[0].error_y.array) == [R.vehicle_summary(res, v, 600)["gap_rule_se"] for v in names] and fig.data[0].marker.color == C.METHOD_COLORS["rule"]
    assert fig.data[0].y[1] == pytest.approx(st.mean(100 * (r["t_rule"] / r["t_opt"] - 1) for r in rows_where(res, "vehicle", vehicle="Pkw", length=600, tv=C.TV_FAST)))
    assert all(ax.fixedrange is True for ax in all_axes(fig))
    priced = V.build_vehicles(res, 600, 20)
    assert list(priced.data[0].y) == [R.vehicle_summary(res, v, 600, 20)["gap_rule"] for v in names]
    assert priced.data[0].y[1] == pytest.approx(st.mean(100 * (r["j_rule"] / r["j_opt"] - 1) for r in rows_where(res, "vehicle", vehicle="Pkw", length=600, tv=20)))


def test_spectrum_sweep_has_one_line_per_vehicle_normalised_to_time_alone(res):
    fig = V.build_spectrum_sweep(res, 600)
    names = list(res["meta"]["vehicles"])
    assert [t.name for t in fig.data] == names and all(len(t.x) == len(C.TV_OPTIONS) for t in fig.data)
    for t, name in zip(fig.data, names):
        pts = R.spectrum(res, name, 600)
        assert t.x[-1] == pytest.approx(100.0) and t.y[-1] == pytest.approx(100.0)                      # „Zeit allein“ ist die Bezugsgröße
        assert list(t.x) == pytest.approx([100.0 * p["t_opt"] / pts[-1]["t_opt"] for p in pts]) and list(t.y) == pytest.approx([100.0 * p["cons_opt"] / pts[-1]["cons_opt"] for p in pts])
        assert t.x[0] > 120 and t.y[0] < 80, name                                                         # sparsam: deutlich langsamer, deutlich weniger Verbrauch
        assert list(t.text) == [C.tv_label(tv) for tv in C.TV_OPTIONS]
    assert all(ax.fixedrange is True for ax in all_axes(fig))


def test_energy_bars_show_the_consumption_of_every_reachable_method(real_run):
    fig = V.build_energy_bars(real_run)
    assert list(fig.data[0].x) == [C.METHOD_LABELS[k] for k in C.METHODS] and list(fig.data[0].y) == pytest.approx([E.consumption(real_run, k) for k in C.METHODS])
    assert list(fig.data[0].marker.color) == [C.METHOD_COLORS[k] for k in C.METHODS] and all(ax.fixedrange is True for ax in all_axes(fig))
    run = fake_trip_run()
    run["plans"]["const_max"] = unreachable("const_max")
    assert list(V.build_energy_bars(run).data[0].x) == [C.METHOD_LABELS[k] for k in ("rule", "const_best", "opt")]


def spectrum_inputs(settings=None):
    s = settings or C.PRESETS["Standard"]
    return E.run_live(s), E.frontier(s), E.speed_curve(s)


def test_spectrum_figure_has_frontier_speed_curve_cost_line_and_four_method_points():
    run, front, curve = spectrum_inputs()
    fig = V.build_spectrum(run, front, curve)
    assert [t.name for t in fig.data] == ["Konstante Geschwindigkeit", "Optimum je Zeitwert", "Gleiche Kosten"] + [C.METHOD_LABELS[k] for k in C.METHODS]
    cur, fr = fig.data[0], fig.data[1]
    assert list(cur.x) == pytest.approx([c["time_min"] / 60 for c in curve]) and list(cur.y) == pytest.approx([c["energy_cost"] for c in curve]) and list(cur.customdata) == [f"{c['v']} km/h" for c in curve]
    assert list(fr.x) == pytest.approx([f["time_min"] / 60 for f in front]) and list(fr.y) == pytest.approx([f["energy_cost"] for f in front]) and list(fr.customdata) == [C.tv_label(f["tv"]) for f in front]
    assert [t for t in fr.text if t] == [C.tv_label(tv) for tv in V.SPECTRUM_LABELLED] and all(t == (C.tv_label(f["tv"]) if f["tv"] in V.SPECTRUM_LABELLED else "") for t, f in zip(fr.text, front))
    for t, key in zip(fig.data[3:], C.METHODS):
        p = run["plans"][key]
        assert list(t.x) == [p.time_h] and list(t.y) == [E.energy_cost(run, key)] and t.marker.color == C.METHOD_COLORS[key] and t.marker.symbol == "diamond"
    assert fig.layout.xaxis.title.text == "Reisezeit (h)" and fig.layout.yaxis.title.text == "Energiekosten (€)" and all(ax.fixedrange is True for ax in all_axes(fig))


def test_spectrum_axes_cover_exactly_the_points_and_cut_the_cost_line():
    run, front, curve = spectrum_inputs()
    fig = V.build_spectrum(run, front, curve)
    xs = [c["time_min"] / 60 for c in curve] + [f["time_min"] / 60 for f in front] + [run["plans"][k].time_h for k in C.METHODS]
    ys = [c["energy_cost"] for c in curve] + [f["energy_cost"] for f in front] + [E.energy_cost(run, k) for k in C.METHODS]
    (x0, x1), (y0, y1) = fig.layout.xaxis.range, fig.layout.yaxis.range
    assert x0 < min(xs) and x1 > max(xs) and y0 < min(ys) and y1 > max(ys) and x1 - x0 < 1.2 * (max(xs) - min(xs)) and y1 - y0 < 1.3 * (max(ys) - min(ys))
    line = fig.data[2]
    assert min(line.y) < y0                                                                      # die Gerade reicht über den sichtbaren Bereich hinaus und wird abgeschnitten
    assert V.build_spectrum(run, [], []).layout.yaxis.range is not None


def test_spectrum_cost_line_has_the_slope_minus_time_value_and_touches_the_optimum():
    run, front, curve = spectrum_inputs()
    line = V.build_spectrum(run, front, curve).data[2]
    (x0, x1), (y0, y1) = line.x, line.y
    assert (y1 - y0) / (x1 - x0) == pytest.approx(-run["trip"].w_time)                                    # Steigung = −Zeitwert (€ je Stunde, Zeit in Stunden)
    opt = run["plans"]["opt"]
    assert y0 + (opt.time_h - x0) * (y1 - y0) / (x1 - x0) == pytest.approx(E.energy_cost(run, "opt"))        # die Gerade geht durch das gewählte Optimum
    # Gewichtssummen-Eigenschaft: kein Punkt der Spanne und keine konstante Geschwindigkeit liegt unterhalb der Geraden (Rasterrauschen 0,5 %)
    def below(x, y):
        return y + run["trip"].w_time * x < E.energy_cost(run, "opt") + run["trip"].w_time * opt.time_h - 0.005 * (E.energy_cost(run, "opt") + run["trip"].w_time * opt.time_h)
    assert not any(below(f["time_min"] / 60, f["energy_cost"]) for f in front) and not any(below(c["time_min"] / 60, c["energy_cost"]) for c in curve)


def test_spectrum_figure_without_a_cost_line_for_time_alone_and_without_unreachable_methods():
    s = C.PRESETS["Möglichst schnell"]
    run, front, curve = spectrum_inputs(s)
    fig = V.build_spectrum(run, front, curve)
    assert [t.name for t in fig.data] == ["Konstante Geschwindigkeit", "Optimum je Zeitwert"] + [C.METHOD_LABELS[k] for k in C.METHODS]            # bei „Zeit allein“ gibt es keine Kostengerade
    run["plans"]["rule"] = unreachable("rule")
    assert "Praxisregel" not in [t.name for t in V.build_spectrum(run, front, curve).data]
    assert [t.name for t in V.build_spectrum(run, [], []).data][:2] == ["Konstante Geschwindigkeit", "Optimum je Zeitwert"]


def test_all_figures_have_a_fixed_layout_height(res, real_run):
    for fig in (V.build_trip(real_run, "opt"), V.build_time_bars(real_run), V.build_energy_bars(real_run), V.build_power_gap(res, 130), V.build_best_speed(res), V.build_wind(res), V.build_vehicles(res, 600),
                V.build_spectrum_sweep(res, 600), V.build_spectrum(real_run, E.frontier(real_run["settings"]), E.speed_curve(real_run["settings"]))):
        assert fig.layout.height is not None and fig.layout.height >= 340
