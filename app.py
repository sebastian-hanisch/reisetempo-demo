"""Reisegeschwindigkeit: Wie schnell fahren, wenn man laden muss? - interaktive Fall-Demo
Sebastian Hanisch - Operations Research und Machine Learning

Ein Elektrofahrzeug soll eine Strecke mit Höhenprofil und Wind so schnell wie möglich fahren. Entschieden werden die Reisegeschwindigkeit je Abschnitt und die Ladestopps (wo, von wie viel auf wie
viel Prozent). Die Demo vergleicht die Praxisregel (Tempolimit, immer bis 80 % laden) mit dem Tempolimit bei optimalem Laden, der besten konstanten Geschwindigkeit und dem Optimum
(dynamische Programmierung über Ort und Ladestand).

Lauffähig mit: streamlit run app.py
"""

import pandas as pd
import streamlit as st

import rtp_algorithm as A
import rtp_constants as C
import rtp_evaluation as E
import rtp_physics as P
import rtp_results as R
from rtp_pdf_export import generate_plan_pdf, table_rows
from rtp_presets import (apply_preset, apply_vehicle, bounds, init_session_state_defaults, load_permalink_settings, randomize_seed, settings_from_state, sync_query_params)
from rtp_presets import SETTING_SPECS
from rtp_visualization import build_best_speed, build_power_gap, build_temp, build_time_bars, build_trip, build_vehicles, build_wind

st.set_page_config(page_title="Reisegeschwindigkeit – Sebastian Hanisch", layout="wide")


@st.cache_data(show_spinner=False)
def _results():
    return R.load_results()


@st.cache_data(show_spinner=False)
def _live(key):
    return E.run_live(dict(key))


st.title("🔋 Reisegeschwindigkeit: Wie schnell fahren, wenn man laden muss?")
st.markdown(
    """
Ein Elektrofahrzeug soll eine **Strecke mit Höhenprofil und Wind** so **schnell wie möglich** fahren. Schneller fahren verbraucht mehr Energie und kostet damit Ladezeit; langsamer fahren spart
Ladezeit, kostet aber Fahrzeit. Gesucht sind die **Reisegeschwindigkeit je Abschnitt** und der **Ladeplan** (wo laden, von wie viel auf wie viel Prozent). Die Demo vergleicht die
**Praxisregel** (Tempolimit fahren, bei Bedarf bis 80 % laden) mit dem **Tempolimit bei optimalem Laden**, der **besten konstanten Geschwindigkeit** und dem **Optimum** (dynamische
Programmierung über Ort und Ladestand) und zeigt, **wie viel die Regel verschenkt** und **ob sich eine wechselnde Geschwindigkeit überhaupt lohnt**.
"""
)
st.caption(
    "Gegenstück zur [Ladestrategie](https://sebastianhanisch-ladestrategie-demo.streamlit.app/) (dort wird Energie bei fester Geschwindigkeit minimiert und zusätzlich Batterieheizen gewählt; "
    "hier die Reisezeit mit freier Geschwindigkeit und Ladekurve), verwandt mit der [Geschwindigkeitsoptimierung](https://sebastianhanisch-slow-steaming-demo.streamlit.app/) im Seeverkehr "
    "und dem [Fernverkehr mit Elektro-Lkw](https://sebastianhanisch-fernverkehr-demo.streamlit.app/). Das Problem ist aus der Literatur bekannt, die Demo rechnet es mit stilisierten Annahmen nach."
)

st.caption("🎯 Schnellstart – ein Beispielszenario laden:")
preset_cols = st.columns(4)
for i, name in enumerate(C.PRESET_ORDER):
    with preset_cols[i % 4]:
        st.button(name, key=f"preset_{name}", width="stretch", on_click=apply_preset, args=(name,), help=C.PRESET_HELP[name])

st.caption("🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, um ein Szenario zu teilen.")

load_permalink_settings()
init_session_state_defaults()


def _slider(label, key, help_text, fmt=None):
    lo, hi = bounds(key)
    kw = {"format": fmt} if fmt else {}
    return st.slider(label, lo, hi, step=SETTING_SPECS[key].step, key=key, help=help_text, **kw)


with st.sidebar:
    st.header("⚙️ Einstellungen")
    st.markdown("**Fahrzeug**")
    st.selectbox("Musterfahrzeug", C.VEHICLE_ORDER, key="vehicle_select", on_change=apply_vehicle,
                 help="Setzt die Fahrzeugparameter unten und das Tempolimit auf Werte in der Größenordnung des Fahrzeugtyps (stilisiert, keine Herstellerangaben). Jeder Wert bleibt danach einzeln einstellbar.")
    _slider("Nettokapazität (kWh)", "cap_slider", "Nutzbare Batteriekapazität.", "%.0f")
    _slider("Spitzenladeleistung (kW)", "peak_slider", "Höchste Ladeleistung am Anschluss; die tatsächliche Leistung folgt der Ladekurve über dem Ladestand.", "%.0f")
    st.selectbox("Ladekurve", C.CURVE_NAMES, key="curve_select",
                 help="Form der Ladekurve: wie lange die Spitzenleistung gehalten wird und wie stark die Leistung bei hohem Ladestand abfällt.")
    _slider("Masse (kg)", "mass_slider", "Gesamtmasse mit Beladung.", "%.0f")
    _slider("Luftwiderstandsfläche c_w·A (m²)", "cda_slider", "Produkt aus Luftwiderstandsbeiwert und Stirnfläche.", "%.2f")
    with st.expander("Weitere Fahrzeugparameter"):
        _slider("Rollwiderstandsbeiwert", "cr_slider", "Typisch 0,006 (Lkw-Reifen) bis 0,011.", "%.4f")
        _slider("Nebenverbraucher (kW)", "aux_slider", "Elektronik, Gebläse und Pumpen; wird mit der Fahrzeit multipliziert und vom Kältefaktor mitgetragen.", "%.1f")
        _slider("Ladeverlust (%)", "loss_slider", f"Verlust beim Laden bei {C.T_REF:.0f} °C; bei Kälte wächst er (bis +15 Punkte bei −20 °C).", "%.0f")
        _slider("Fixzeit je Ladestopp (min)", "stop_slider", "Anfahrt, Anstecken und Bezahlen. Ohne Fixzeit gäbe es beliebig viele Mikro-Stopps.", "%.0f")
    st.markdown("**Fahrt**")
    _slider("Streckenlänge (km)", "length_slider", "Die Strecke besteht aus Zellen zu 5 km; je Zelle gelten Steigung, Wind und eine Geschwindigkeit.")
    _slider("Außentemperatur (°C)", "temp_slider", "Unter 20 °C steigt der Verbrauch (35,6 % mehr bei −6,6 °C, linear) und der Ladewirkungsgrad sinkt.")
    _slider("Anfangsladestand (%)", "soc0_slider", "Ladestand beim Start. Am Start darf ohne Einschränkung geladen werden.")
    _slider("Mindestladestand am Ladestopp (%)", "sminstop_slider", "So viel muss bei Ankunft an einem Ladestopp mindestens noch im Akku sein.")
    _slider("Mindestladestand am Ziel (%)", "smindest_slider", "So viel muss bei Ankunft im Ziel mindestens noch im Akku sein.")
    _slider("Tempolimit (km/h)", "vmax_slider", "Höchste erlaubte Reisegeschwindigkeit; gewählt wird im Raster von 5 km/h ab 40 km/h.")
    st.markdown("**Strecke und Wind**")
    st.select_slider("Höhenprofil", options=C.PROFILE_TYPES, key="profile_select", format_func=lambda t: C.PROFILE_LABELS[t],
                     help="Steigungsprofil je 5-km-Zelle, zufällig erzeugt. Hügelig und Mittelgebirge haben Höhenunterschied null, der Alpenpass einen Anstieg und einen gleich hohen Abstieg.")
    _slider("Zusätzlicher Höhenunterschied Start bis Ziel (m)", "rise_slider", "Gleichmäßig über die Strecke verteilt, zusätzlich zum Profil (negativ = Ziel liegt tiefer).")
    _slider("Gegenwind (km/h)", "wind_slider", "Komponente des Windes in Fahrtrichtung; negativ ist Rückenwind. Der Luftwiderstand folgt der Relativgeschwindigkeit.")
    st.select_slider("Windverlauf", options=C.WIND_MODES, key="windmode_select", help="Konstant, oder je Abschnitt von 20 bis 50 km um bis zu ±15 km/h schwankend.")
    st.number_input("Zufalls-Seed", min_value=bounds("seed_input")[0], max_value=bounds("seed_input")[1], step=1, key="seed_input", help="Bestimmt Höhenprofil und Windschwankung.")
    st.button("🎲 Neue Strecke würfeln", on_click=randomize_seed)

values = {k: st.session_state[k] for k in SETTING_SPECS}
sync_query_params(values)
settings = settings_from_state(values)
res = _results()

with st.spinner("Rechne die vier Verfahren …"):
    run = _live(tuple(sorted(settings.items())))
trip, plans = run["trip"], run["plans"]
route = trip.route
st.caption(
    f"Strecke: {route.length:.0f} km, Höhenunterschied Start bis Ziel {round(route.height[-1]) + 0:+d} m, steilste Zelle {100 * max(abs(route.grade)):.1f} %, Gegenwind {settings['headwind']:+d} km/h ({settings['wind_mode']}). "
    f"Verbrauch des Fahrzeugs auf ebener Strecke bei {settings['temp']} °C: {P.consumption_flat(trip.vehicle, 100, trip.temp):.1f} kWh/100 km bei 100 km/h, "
    f"{P.consumption_flat(trip.vehicle, 130, trip.temp):.1f} bei 130 km/h. Rechenzeit dieses Laufs {run['seconds']:.1f} s."
)

# ------------------------------------------------------------------ Ergebnis
st.markdown("---")
st.markdown("## 🔋 Was kostet die Regel?")
opt = plans["opt"]
cols = st.columns(4)
for col, key in zip(cols, C.METHODS):
    p = plans[key]
    if not p.feasible:
        col.metric(C.METHOD_LABELS[key], "nicht erreichbar", help=p.note)
        continue
    diff = 0.0 if key == "opt" or not opt.feasible else p.time_min - opt.time_min
    delta = "Referenz" if key == "opt" or not opt.feasible else "praktisch gleich" if abs(diff) < 0.5 else f"{diff:+.0f} min gegen das Optimum"
    col.metric(C.METHOD_LABELS[key], C.fmt_hm(p.time_min), delta=delta, delta_color="off" if key == "opt" or abs(diff) < 0.5 else "inverse",
               help="Reisezeit: Fahren, Laden und Fixzeit der Stopps. Delta = diese Reisezeit minus die des Optimums.")
for state, text in E.messages(run):
    (st.success if state == "success" else st.warning if state == "warning" else st.info)(f"💡 {text}")

rows = []
for r in E.summary_rows(run):
    if not r["feasible"]:
        rows.append({"Verfahren": C.METHOD_LABELS[r["key"]], "Reisezeit": "nicht erreichbar"})
        continue
    rows.append({"Verfahren": C.METHOD_LABELS[r["key"]], "Reisezeit (min)": round(r["time_min"], 1), "Fahren (min)": round(r["drive_min"], 1), "Laden (min)": round(r["charge_min"], 1),
                 "Fixzeit (min)": round(r["fix_min"], 1), "Ladestopps": r["stops"], "Ø km/h": round(r["mean_speed"], 1), "Verbrauch (kWh/100 km)": round(r["consumption"], 1),
                 "Über dem Optimum": "–" if r["key"] == "opt" else f"{r['gap_opt_pct']:+.1f} %"})
st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
st.caption("Die Reisezeit kommt aus der stetigen Nachfahrt jedes Plans (kein Rundungsfehler durch das Ladestandsraster). Unterschiede unter etwa 0,2 % liegen im Rechenfehler der dynamischen Programmierung und sind nicht belastbar.")
st.plotly_chart(build_time_bars(run), width="stretch", key=f"time_{tuple(sorted(settings.items()))}")

st.markdown("### Die Fahrt im Detail")
view = st.radio("Verfahren anzeigen", C.VIEW_OPTIONS, key="view_select", horizontal=True, format_func=lambda k: C.METHOD_LABELS[k],
                help="Reine Anzeigewahl: welches Verfahren in den Diagrammen und im Ladeplan gezeigt wird (keine Einstellung der Rechnung).")
if plans[view].feasible:
    st.plotly_chart(build_trip(run, view), width="stretch", key=f"trip_{tuple(sorted(settings.items()))}_{view}")
    st.caption("Oben die Reisegeschwindigkeit je Abschnitt (gestrichelt das Tempolimit), in der Mitte der Ladestand (orange hinterlegt die Ladestopps, gestrichelt der Mindestladestand am Stopp, "
               "gepunktet die Praxisregel), unten das Höhenprofil und der Gegenwind je Abschnitt.")
    stops, sections = table_rows(plans[view], C.DX_KM)
    t1, t2 = st.columns(2)
    with t1:
        st.markdown("**Ladeplan**")
        if stops:
            st.dataframe(pd.DataFrame([{"bei km": f"{km:.0f}", "Ladestand bei Ankunft": f"{a:.0f} %", "Ladestand danach": f"{b:.0f} %", "Ladezeit (min)": round(ch), "Stopp gesamt (min)": round(tot)}
                                       for km, a, b, ch, tot in stops]), width="stretch", hide_index=True)
        else:
            st.info("Kein Ladestopp nötig.")
    with t2:
        st.markdown("**Reisegeschwindigkeit**")
        st.dataframe(pd.DataFrame([{"von km": f"{a:.0f}", "bis km": f"{b:.0f}", "km/h": f"{v:.0f}"} for a, b, v in sections]), width="stretch", hide_index=True)
    summary_lines = [f"{C.METHOD_LABELS[view]}: Reisezeit {C.fmt_hm(plans[view].time_min)} für {route.length:.0f} km, {len(plans[view].stops)} Ladestopps.",
                     f"Fahrzeug: {settings['cap']:.0f} kWh, {settings['peak']:.0f} kW, {settings['mass']:.0f} kg; Außentemperatur {settings['temp']} °C, Gegenwind {settings['headwind']:+d} km/h; Tempolimit {settings['vmax']} km/h."]
    st.download_button("📄 Ladeplan als PDF herunterladen", data=generate_plan_pdf(plans[view], "Ladeplan", summary_lines, C.DX_KM), file_name="ladeplan.pdf", mime="application/pdf", key="pdf_download")
else:
    st.warning(plans[view].note)

# ------------------------------------------------------------------ Kernabschnitt: Messreihe
st.markdown("---")
st.subheader("📐 Was die Messreihe zeigt")
fv = R.free_vs_const(res)
peak_cell, vmax_cell = R.nearest(res["meta"]["peaks"], settings["peak"]), R.nearest(res["meta"]["vmaxes"], settings["vmax"])
ps = R.power_summary(res, peak_cell, vmax_cell)
st.caption(f"Vorgerechnet (tools/sweep.py): {res['meta']['cases']} Fälle, je Zelle 5 bis 10 Zufallsstrecken (Seeds ab {res['meta']['seeds'][0]}), Mittel ± Standardfehler. Standardfall der Messreihe: Pkw mit 77 kWh, "
           f"hügelige Strecke von 600 km, 20 °C, Tempolimit 130 km/h, wenn nichts anderes steht. Gezeigt ist die Zelle, die Ihren Einstellungen am nächsten liegt: {peak_cell:.0f} kW und Tempolimit {vmax_cell} km/h "
           f"(Fahrzeug, Strecke und Temperatur der Zelle können von Ihren Einstellungen abweichen).")
d1, d2, d3, d4 = st.columns(4)
d1.metric("Praxisregel", f"+{ps['gap_rule']:.1f} ± {ps['gap_rule_se']:.1f} %", help="Reisezeit über dem Optimum (Praxisregel: Tempolimit, jeweils bis 80 % laden).")
d2.metric("Tempolimit, optimal laden", f"+{ps['gap_const_max']:.1f} ± {ps['gap_const_max_se']:.1f} %")
d3.metric("Beste konstante Geschwindigkeit", f"{ps['v_best']:.0f} ± {ps['v_best_se']:.0f} km/h", help="Mittlere beste konstante Geschwindigkeit dieser Zelle.")
d4.metric("Freie gegen konstante", f"{fv['mean']:.2f} %", help=f"Wie viel eine freie Geschwindigkeit je Abschnitt gegenüber der besten konstanten spart: Mittel über alle {fv['n']} Fälle; 95. Perzentil {fv['p95']:.2f} %, Maximum {fv['max']:.2f} %.")
st.markdown("**Wie viel länger braucht die Praxisregel, je nach Ladeleistung?**")
st.plotly_chart(build_power_gap(res, vmax_cell), width="stretch", key=f"sweep_gap_{vmax_cell}")
st.caption(f"Tempolimit {vmax_cell} km/h. Das Ladefenster macht den Unterschied: Das Tempolimit mit optimalem Laden liegt fast immer nahe am Optimum, die Praxisregel nicht. Je langsamer der Lader und je höher das Tempolimit, desto mehr verschenkt die Regel.")
c1, c2 = st.columns(2)
with c1:
    st.markdown("**Beste konstante Geschwindigkeit**")
    st.plotly_chart(build_best_speed(res), width="stretch", key="sweep_best_speed")
    st.caption("Mit langsamem Lader liegt die beste Geschwindigkeit deutlich unter dem Tempolimit; ab etwa 150 kW fährt man bei Tempolimit 130 das Limit aus.")
with c2:
    st.markdown("**Kälte kostet Reisezeit**")
    st.plotly_chart(build_temp(res), width="stretch", key="sweep_temp")
    st.caption("Mehr Reisezeit des Optimums gegenüber 20 °C (Pkw, 150 kW, Tempolimit 130): Der Verbrauch steigt, der Ladewirkungsgrad sinkt, es braucht mehr Stopps.")
c3, c4 = st.columns(2)
with c3:
    st.markdown("**Wind verschiebt die beste Geschwindigkeit**")
    st.plotly_chart(build_wind(res), width="stretch", key="sweep_wind")
    st.caption("Mittel über die vier Höhenprofile bei Tempolimit 160. Gegenwind drückt die beste Geschwindigkeit nach unten, Rückenwind nach oben, solange der Lader langsam genug ist, dass das Limit nicht ohnehin gilt (150 kW fährt hier das Limit).")
with c4:
    st.markdown("**Fahrzeug-Presets (600 km)**")
    st.plotly_chart(build_vehicles(res, 600), width="stretch", key="sweep_vehicles")
    st.caption("Wie viel länger die Praxisregel gegenüber dem Optimum braucht. Beim Lieferwagen mit früh abfallender Ladekurve ist es am meisten, beim Lkw mit nur einem Stopp nichts.")
hs = {v: (R.height_summary(res, v, "flach", 0), R.height_summary(res, v, "flach", 1000)) for v in ("Pkw", "Elektro-Lkw")}
st.markdown("**Was kostet ein Höhenunterschied?**")
st.dataframe(pd.DataFrame([{"Fahrzeug": v, "Reisezeit eben (min)": round(a["t_opt"], 1), "Reisezeit mit +1000 m (min)": round(b["t_opt"], 1), "Mehr Reisezeit": f"{100 * (b['t_opt'] / a['t_opt'] - 1):.1f} %",
                            "Verbrauch eben (kWh/100 km)": round(a["cons_opt"], 1), "Verbrauch mit +1000 m": round(b["cons_opt"], 1)} for v, (a, b) in hs.items()]), width="stretch", hide_index=True)
st.caption("Optimum, flaches Profil, Anstieg von 1000 m über 600 km. Hügel mit Höhenunterschied null kosten beim Pkw bei hohem Tempo fast nichts; der schwere, langsame Lkw spürt jeden Höhenmeter.")

# ------------------------------------------------------------------ Methodenvergleich
st.markdown("---")
with st.expander("🔧 Wie wir das erreichen – vollständiger Methodenvergleich", expanded=False):
    tabs = st.tabs(["🚗 Verfahren", "🧪 Plan nachrechnen", "📈 Messreihe"])

    with tabs[0]:
        st.markdown(
            f"**Praxisregel:** konstant mit dem Tempolimit fahren; ein Ladestopp wird eingelegt, sobald die nächste Zelle den Ladestand unter den Mindestladestand am Stopp drücken würde; "
            f"geladen wird bis {C.RULE_CHARGE_TO:.0f} %, am letzten Stopp nur so weit, wie das Ziel braucht. **Tempolimit, optimal laden:** dasselbe Tempo, aber Ort und Menge der Stopps kommen aus der "
            f"dynamischen Programmierung. **Beste konstante Geschwindigkeit:** ein solches DP je Geschwindigkeit im Raster von {C.V_STEP} km/h, gewählt wird die kleinste Reisezeit. **Optimum:** die "
            f"Geschwindigkeit darf je 5-km-Zelle wechseln. Die DP läuft rückwärts über (Ort, Ladestand) mit mindestens {C.N_SOC} Ladestandsstufen (höchstens {C.DS_MAX} kWh je Stufe); Laden ist an jeder Zellgrenze möglich, wenn bei Ankunft der "
            f"Mindestladestand erreicht ist. Der Plan wird danach mit dem stetigen Ladestand nachgefahren."
        )
        st.dataframe(pd.DataFrame([{"Verfahren": C.METHOD_LABELS[k], "DP-Wert (min)": "–" if plans[k].value_h is None else f"{60 * plans[k].value_h:.1f}", "Nachfahrt (min)": f"{plans[k].time_min:.1f}"}
                                   for k in C.METHODS if plans[k].feasible]), width="stretch", hide_index=True)

    with tabs[1]:
        st.caption("Jeder Plan wird unabhängig von der DP nachgerechnet: Zelle für Zelle Energie aus der Physik, Ladezeit in geschlossener Form (Integral der stückweise linearen Ladekurve) statt aus der "
                   "Tabelle. Zeit und Endladestand müssen mit dem Plan übereinstimmen, der Ladestand darf nie unter null und bei Ankunft an einem Stopp nie unter den Mindestladestand fallen.")
        key = tuple(sorted(settings.items()))
        if st.button("🧪 Pläne nachrechnen", key="check_button"):
            st.session_state["check_result"] = {"key": key, "rows": [{"Verfahren": C.METHOD_LABELS[k], "Plan (min)": round(plans[k].time_min, 2), "Nachgerechnet (min)": round(60 * (c := A.check_plan(trip, plans[k]))["time_h"], 2),
                                                                     "Endladestand (%)": round(100 * c["soc_end"] / trip.vehicle.cap, 1), "Zulässig": "ja" if c["ok"] else "nein"}
                                                                    for k in C.METHODS if plans[k].feasible]}
        cr = st.session_state.get("check_result")
        if cr and cr["key"] == key:
            st.dataframe(pd.DataFrame(cr["rows"]), width="stretch", hide_index=True)
        elif cr:
            st.caption("Die Einstellungen haben sich seit dem letzten Lauf geändert, bitte erneut nachrechnen.")

    with tabs[2]:
        st.caption("Ladeleistung × Tempolimit (Pkw, 600 km, hügelig, 20 °C): mittlere Reisezeit über dem Optimum in Prozent.")
        out = []
        for pk in res["meta"]["peaks"]:
            for vm in res["meta"]["vmaxes"]:
                s = R.power_summary(res, pk, vm)
                out.append({"Ladeleistung": f"{pk:.0f} kW", "Tempolimit": f"{vm} km/h", "Praxisregel": round(s["gap_rule"], 1), "Tempolimit, optimal laden": round(s["gap_const_max"], 1),
                            "Beste konstante": round(s["gap_const_best"], 2), "beste Geschwindigkeit": round(s["v_best"]), "Ladeziel Optimum (%)": round(s["tgt_opt"]), "Stopps Optimum": round(s["stops_opt"], 1)})
        st.dataframe(pd.DataFrame(out), width="stretch", hide_index=True)
        st.caption("Fixzeit je Stopp (Praxisregel über dem Optimum, in Prozent): Ladeleistung × Fixzeit.")
        st.dataframe(pd.DataFrame([{"Ladeleistung": f"{pk:.0f} kW", **{f"{st_:.0f} min": f"{R.fix_summary(res, pk, st_)['gap_rule']:.1f} % ({R.fix_summary(res, pk, st_)['stops_opt']:.1f} Stopps)" for st_ in (1.0, 5.0, 15.0, 30.0)}}
                                   for pk in (50.0, 150.0, 350.0)]), width="stretch", hide_index=True)

with st.expander("Wie funktioniert diese Demo?"):
    st.markdown(
        f"""
**Fahrzeug.** Verbrauch aus der Physik: Rollwiderstand und Hangabtrieb (konstant je Kilometer), Luftwiderstand mit der Relativgeschwindigkeit zum Wind (wächst mit dem Quadrat), Wirkungsgrad {C.ETA_DRIVE:.2f} beim Antreiben,
Rekuperation {C.ETA_REGEN:.2f} bei negativer Radarbeit, Nebenverbraucher als Leistung mal Zeit. Kälte erhöht den Verbrauch linear unter {C.T_REF:.0f} °C (AAA-Wintertest: +35,6 % bei −6,6 °C, wie in der
Ladestrategie-Demo) und senkt den Ladewirkungsgrad. **Ladekurve:** Anteil der Spitzenleistung über dem Ladestand, stilisiert (drei Formen); die Leistung hängt nicht von der Temperatur ab. Alle Fahrzeugwerte
und Kurven sind Größenordnungen, keine Herstellerangaben.

**Strecke.** Zellen zu {C.DX_KM:.0f} km mit Steigung und Gegenwind; das Höhenprofil wird mit SplitMix64 zufällig erzeugt (vier Typen), dazu ein einstellbarer Höhenunterschied Start bis Ziel. Geschwindigkeit
und Ladeentscheidung gelten je Zelle. **Entscheidungen:** Reisegeschwindigkeit je Zelle ({C.V_MIN} km/h bis zum Tempolimit im Raster von {C.V_STEP} km/h) und Laden an jeder Zellgrenze (von x % auf y %).

**Annahmen und Grenzen.** Schnellladen ist überall möglich; ein Stopp kostet eine feste Zeit (Standard {C.DEFAULT_STOP:.0f} min), sonst gäbe es beliebig viele Mikro-Stopps. Es gibt keine Ladesäulen-Auslastung, keine
Wartezeit, keinen Verkehr, keine Fahrerpausen und keine Beschleunigungsvorgänge. Die Ladeleistung hängt nicht von der Temperatur ab (die Ladestrategie-Demo untersucht Batterieheizen). Die DP hat einen
Fehlerboden von etwa 0,1 %; Unterschiede darunter sind nicht belastbar. Die Praxisregel ist eine einfache Regel, das Optimum eine Schranke dessen, was Planung gegenüber ihr bringt.
"""
    )

with st.expander("📐 Mathematische Formulierung"):
    st.markdown(
        r"""
**Zeit.** $T = \sum_i \frac{\Delta x}{v_i} + \sum_{\text{Stopps}} \big(t_\mathrm{fix} + T_\mathrm{ch}(s'_k) - T_\mathrm{ch}(s_k)\big)$ mit der Ladezeitfunktion $T_\mathrm{ch}(s) = \int_0^s \frac{dE}{\eta\, P(E/C)}$.

**Energie je Zelle.** $e_i(v) = \frac{F_i(v)\,\Delta x}{\eta_\mathrm{antr}}\,k_T + P_\mathrm{aux} \frac{\Delta x}{v}\,k_T$ für $F_i > 0$, sonst $\eta_\mathrm{rek}\,F_i\,\Delta x$ (Rekuperation), mit
$F_i(v) = c_r m g \cos\theta_i + m g \sin\theta_i + \tfrac12 \rho\, c_w A\,(v + w_i)\,|v + w_i|$ und dem Kältefaktor $k_T$.

**Bellman-Rückwärtsrechnung.** $f_i(s) = \min_v \big[\Delta x / v + g_{i+1}(s - e_i(v))\big]$, $g_i(s) = \min\big(f_i(s),\ \min_{s' > s} [t_\mathrm{fix} + T_\mathrm{ch}(s') - T_\mathrm{ch}(s) + f_i(s')]\big)$ für $s \ge s_\mathrm{min,Stopp}$,
$f_n(s) = 0$ für $s \ge s_\mathrm{min,Ziel}$. Warum die Steigung die beste Geschwindigkeit kaum ändert: $\sin\theta$ und der Rollwiderstand addieren je Kilometer eine feste Energie, unabhängig von $v$; nur der Luftwiderstandsterm
(und damit der Wind) und die Nebenverbraucher hängen von $v$ ab.
"""
    )

st.markdown("---")
st.caption(
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). "
    "Mehr zum Thema: [Tourenplanung optimieren](https://sebastianhanisch.net/tourenplanung-optimierung.html)."
)
