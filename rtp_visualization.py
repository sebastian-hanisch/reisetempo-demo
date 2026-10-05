"""Plotly-Figuren der Demo „Reisegeschwindigkeit“. Alle Achsen fest (fixedrange), damit Touch-Scrollen nicht am Chart hängen bleibt.
Beschriftungen mit Zahlen stehen als Text, damit Plotly keine lineare Achse anlegt."""
from __future__ import annotations

import plotly.graph_objects as go
from plotly.subplots import make_subplots

import rtp_constants as C
import rtp_results as R


def _lock(fig, height=360, **layout):
    fig.update_layout(height=height, margin=dict(l=55, r=20, t=40, b=55), font=dict(size=12), legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0), **layout)
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def speed_steps(plan, dx=C.DX_KM):
    """Treppenlinie der Geschwindigkeit je Zelle: (x in km, y in km/h)."""
    xs, ys = [], []
    for i, v in enumerate(plan.v):
        xs += [i * dx, (i + 1) * dx]
        ys += [float(v), float(v)]
    return xs, ys


def build_trip(run: dict, key: str) -> go.Figure:
    """Drei Reihen über dem Weg: Geschwindigkeit der gewählten Fahrweise (Tempolimit gestrichelt), Ladestand in Prozent (gewählte Fahrweise gegen die Praxisregel, Ladestopps schattiert),
    Höhenprofil (Fläche) und Gegenwind."""
    trip = run["trip"]
    plan, rule = run["plans"][key], run["plans"]["rule"]
    route, cap = trip.route, trip.vehicle.cap
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.34, 0.40, 0.26], vertical_spacing=0.06, specs=[[{}], [{}], [{"secondary_y": True}]])
    xs, ys = speed_steps(plan)
    fig.add_trace(go.Scatter(x=[0, route.length], y=[run["speeds"][-1]] * 2, mode="lines", name="Tempolimit", line=dict(color="#555", width=1.5, dash="dash"), hoverinfo="skip"), row=1, col=1)
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name="Geschwindigkeit", line=dict(color=C.METHOD_COLORS[key], width=3),
                             hovertemplate="%{x:.0f} km: %{y:.0f} km/h<extra></extra>"), row=1, col=1)
    if rule.feasible and key != "rule":
        fig.add_trace(go.Scatter(x=[p[0] for p in rule.trace], y=[100.0 * p[1] / cap for p in rule.trace], mode="lines", name="Ladestand Praxisregel", line=dict(color=C.METHOD_COLORS["rule"], width=2, dash="dot"),
                                 hovertemplate="%{x:.0f} km: %{y:.0f} %<extra>Praxisregel</extra>"), row=2, col=1)
    fig.add_trace(go.Scatter(x=[p[0] for p in plan.trace], y=[100.0 * p[1] / cap for p in plan.trace], mode="lines", name="Ladestand", line=dict(color=C.METHOD_COLORS[key], width=3),
                             hovertemplate="%{x:.0f} km: %{y:.0f} %<extra></extra>"), row=2, col=1)
    for st in plan.stops:
        fig.add_vrect(x0=st.km - 3.0, x1=st.km + 3.0, fillcolor=C.COLOR_CHARGE, opacity=0.18, line_width=0, row=2, col=1)
    fig.add_hline(y=100.0 * trip.smin_stop / cap, line=dict(color="#999", width=1, dash="dash"), row=2, col=1)
    fig.add_trace(go.Scatter(x=[i * C.DX_KM for i in range(route.n + 1)], y=list(route.height), mode="lines", name="Höhe", fill="tozeroy", line=dict(color="#9aa5b1", width=1.5),
                             fillcolor="rgba(154,165,177,0.35)", hovertemplate="%{x:.0f} km: %{y:.0f} m<extra>Höhe</extra>"), row=3, col=1)
    wx, wy = [], []
    for i, w in enumerate(route.wind):
        wx += [i * C.DX_KM, (i + 1) * C.DX_KM]
        wy += [float(w), float(w)]
    fig.add_trace(go.Scatter(x=wx, y=wy, mode="lines", name="Gegenwind", line=dict(color="#2e7d4f", width=2), hovertemplate="%{x:.0f} km: %{y:.0f} km/h<extra>Gegenwind</extra>"), row=3, col=1, secondary_y=True)
    fig.update_yaxes(title_text="km/h", rangemode="tozero", row=1, col=1)
    fig.update_yaxes(title_text="Ladestand (%)", range=[0, 105], row=2, col=1)
    fig.update_yaxes(title_text="Höhe (m)", row=3, col=1, secondary_y=False)
    fig.update_yaxes(title_text="Gegenwind (km/h)", range=[C.WIND_MIN - 15, C.WIND_MAX + 15], row=3, col=1, secondary_y=True, showgrid=False)
    fig.update_xaxes(title_text="Weg (km)", row=3, col=1)
    return _lock(fig, 640)


def build_time_bars(run: dict) -> go.Figure:
    """Reisezeit je Verfahren in Minuten, gestapelt nach Fahren, Laden und Fixzeit der Stopps; darüber Gesamtzeit und Abstand zum Optimum."""
    fig = go.Figure()
    keys = [k for k in C.METHODS if run["plans"][k].feasible]
    labels = [C.METHOD_LABELS[k] for k in keys]
    for name, attr, color in (("Fahren", "drive_h", C.COLOR_DRIVE), ("Laden", "charge_h", C.COLOR_CHARGE), ("Fixzeit der Stopps", "fix_h", C.COLOR_FIX)):
        fig.add_trace(go.Bar(x=labels, y=[60.0 * getattr(run["plans"][k], attr) for k in keys], name=name, marker_color=color, hovertemplate="%{x}: %{y:.0f} min<extra>" + name + "</extra>"))
    opt = run["plans"]["opt"]
    texts = []
    for k in keys:
        p = run["plans"][k]
        suffix = "" if k == "opt" or not opt.feasible else f" (+{100.0 * (p.time_h / opt.time_h - 1.0):.1f} %)"
        texts.append(f"{p.time_min:.0f} min" + suffix)
    fig.add_trace(go.Scatter(x=labels, y=[run["plans"][k].time_min for k in keys], mode="text", text=texts, textposition="top center", showlegend=False, hoverinfo="skip"))
    fig.update_layout(barmode="stack")
    fig.update_yaxes(title_text="Reisezeit (min)", rangemode="tozero")
    return _lock(fig, 380)


def _line(fig, xs, ys, name, color, dash=None):
    fig.add_trace(go.Scatter(x=[str(x) for x in xs], y=ys, mode="lines+markers", name=name, line=dict(color=color, width=3, dash=dash), hovertemplate="%{x}: %{y:.1f}<extra>" + name + "</extra>"))


def build_power_gap(res: dict, vmax: int) -> go.Figure:
    """Messreihe: wie viel Prozent länger als das Optimum brauchen Praxisregel, Tempolimit mit optimalem Laden und beste konstante Geschwindigkeit, über der Ladeleistung (Tempolimit fest)."""
    peaks = res["meta"]["peaks"]
    fig = go.Figure()
    for key in ("rule", "const_max", "const_best"):
        _line(fig, [int(p) for p in peaks], [R.power_summary(res, p, vmax)[f"gap_{key}"] for p in peaks], C.METHOD_LABELS[key], C.METHOD_COLORS[key])
    fig.update_xaxes(title_text="Spitzenladeleistung (kW)", type="category")
    fig.update_yaxes(title_text="Reisezeit über dem Optimum (%)", rangemode="tozero")
    return _lock(fig, 360)


def build_best_speed(res: dict) -> go.Figure:
    """Messreihe: beste konstante Geschwindigkeit über der Ladeleistung, eine Linie je Tempolimit."""
    peaks = res["meta"]["peaks"]
    fig = go.Figure()
    shades = ("#9ecae1", "#6baed6", "#3182bd", "#08519c")
    for vmax, color in zip(res["meta"]["vmaxes"], shades):
        _line(fig, [int(p) for p in peaks], [R.power_summary(res, p, vmax)["v_best"] for p in peaks], f"Tempolimit {vmax} km/h", color)
    fig.update_xaxes(title_text="Spitzenladeleistung (kW)", type="category")
    fig.update_yaxes(title_text="Beste konstante Geschwindigkeit (km/h)", rangemode="tozero")
    return _lock(fig, 360)


def build_temp(res: dict) -> go.Figure:
    """Messreihe: Reisezeit des Optimums über der Außentemperatur, bezogen auf 20 °C (Prozent), eine Linie je Streckenlänge."""
    fig = go.Figure()
    colors = ("#9ecae1", "#3182bd", "#08519c")
    for length, color in zip(res["meta"]["lengths"], colors):
        ref = R.temp_summary(res, 20, length)["t_opt"]
        _line(fig, res["meta"]["temps"], [100.0 * (R.temp_summary(res, t, length)["t_opt"] / ref - 1.0) for t in res["meta"]["temps"]], f"{length} km", color)
    fig.update_xaxes(title_text="Außentemperatur (°C)", type="category")
    fig.update_yaxes(title_text="Mehr Reisezeit gegenüber 20 °C (%)", rangemode="tozero")
    return _lock(fig, 360)


def build_wind(res: dict) -> go.Figure:
    """Messreihe: beste konstante Geschwindigkeit über dem Gegenwind (Mittel über die vier Profiltypen), für 50 kW und 150 kW Ladeleistung bei Tempolimit 160."""
    fig = go.Figure()
    winds = res["meta"]["winds"]
    for peak, color in ((50.0, C.METHOD_COLORS["const_best"]), (150.0, C.METHOD_COLORS["const_max"])):
        ys = [sum(R.wind_summary(res, peak, p, w)["v_best"] for p in res["meta"]["profiles"]) / len(res["meta"]["profiles"]) for w in winds]
        _line(fig, winds, ys, f"{int(peak)} kW", color)
    fig.update_xaxes(title_text="Gegenwind (km/h, negativ = Rückenwind)", type="category")
    fig.update_yaxes(title_text="Beste konstante Geschwindigkeit (km/h)", rangemode="tozero")
    return _lock(fig, 360)


def build_vehicles(res: dict, length: int) -> go.Figure:
    """Messreihe: wie viel länger die Praxisregel gegenüber dem Optimum braucht, je Fahrzeug-Preset."""
    names = res["meta"]["vehicles"]
    fig = go.Figure(go.Bar(x=names, y=[R.vehicle_summary(res, v, length)["gap_rule"] for v in names], marker_color=C.METHOD_COLORS["rule"],
                           error_y=dict(type="data", array=[R.vehicle_summary(res, v, length)["gap_rule_se"] for v in names]), hovertemplate="%{x}: %{y:.1f} %<extra></extra>"))
    fig.update_yaxes(title_text="Praxisregel über dem Optimum (%)")
    return _lock(fig, 340)
