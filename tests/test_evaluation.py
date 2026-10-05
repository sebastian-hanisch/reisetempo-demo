"""Auswertung: Lücken, Ladeziel, Kennzahlenzeilen und jede Meldungsverzweigung an ihrer Schwelle (künstliche Pläne), dazu die Live-Rechnung und nicht erreichbare Ziele."""
import math

import pytest

import rtp_constants as C
import rtp_evaluation as E
from helpers_fake import fake_run, plan, stop, unreachable

SHORT = {**C.BASE_SCENARIO, "length": 100}


def msgs(**kw):
    return E.messages(fake_run(**kw))


def gap_run(g_rule=None, g_best=None, **kw):
    """Lauf mit Optimum 10 h; die Praxisregel bzw. die beste konstante Fahrt liegen g Prozent darüber."""
    opt = 10.0
    return fake_run(opt=opt, rule=opt * (1 + g_rule / 100.0) if g_rule is not None else 10.5, cbest=opt * (1 + g_best / 100.0) if g_best is not None else 10.05, **kw)


# ------------------------------------------------------------------ gap_pct, mean_target_soc, best_speed
def test_gap_pct_is_relative_to_the_reference():
    run = fake_run(opt=2.0, rule=2.1, cmax=2.5, cbest=2.0)
    assert E.gap_pct(run, "rule") == pytest.approx(5.0) and E.gap_pct(run, "const_max") == pytest.approx(25.0) and E.gap_pct(run, "const_best") == pytest.approx(0.0, abs=1e-12)
    assert E.gap_pct(run, "opt", ref="rule") == pytest.approx(100 * (2.0 / 2.1 - 1))              # Basis ist die Referenz: das Optimum liegt 4,76 % unter der Regel
    assert E.gap_pct(run, "opt") == pytest.approx(0.0, abs=1e-12)


def test_gap_pct_is_nan_if_one_side_is_unreachable():
    assert math.isnan(E.gap_pct(fake_run(rule=None), "rule")) and math.isnan(E.gap_pct(fake_run(opt=None), "rule")) and math.isnan(E.gap_pct(fake_run(cbest=None), "const_best"))


def test_feasible_reads_the_plan_flag():
    run = fake_run(cmax=None)
    assert E.feasible(run, "rule") and not E.feasible(run, "const_max")


def test_mean_target_soc_skips_the_first_stop():
    p = plan("opt", 1.0, stops=[stop(soc_to=90.0), stop(soc_to=50.0), stop(soc_to=60.0)])
    assert E.mean_target_soc(p) == pytest.approx(55.0)                                              # Mittel von 50 und 60, der erste Stopp (90 %) zählt nicht
    assert E.mean_target_soc(plan("opt", 1.0, stops=[stop(soc_to=90.0), stop(soc_to=40.0)])) == pytest.approx(40.0)
    assert E.mean_target_soc(plan("opt", 1.0, stops=[stop(soc_to=72.0)])) == pytest.approx(72.0)     # ein einziger Stopp: sein Ladeziel
    assert math.isnan(E.mean_target_soc(plan("opt", 1.0)))


def test_best_speed_is_the_speed_of_the_best_constant_plan():
    assert E.best_speed(fake_run(v_best=115.0)) == pytest.approx(115.0)
    assert math.isnan(E.best_speed(fake_run(cbest=None)))


# ------------------------------------------------------------------ summary_rows
def test_summary_rows_by_hand():
    opt = plan("opt", 1.75, charge_h=0.5, fix_h=0.25, v=[100.0, 120.0], energy=[10.0, 14.0], stops=[stop(), stop()], charged_kwh=30.0)
    rule = plan("rule", 1.925, charge_h=0.6, fix_h=0.125, v=[130.0, 130.0], energy=[20.0, 20.0], stops=[stop()], charged_kwh=20.0)
    run = {"plans": {"rule": rule, "const_max": unreachable("const_max", "nicht erreichbar"), "const_best": plan("const_best", 1.75, v=[110.0, 110.0], energy=[12.0, 12.0]), "opt": opt},
           "trip": type("T", (), {"route": type("R", (), {"length": 100.0})()})()}
    rows = E.summary_rows(run)
    assert [r["key"] for r in rows] == list(C.METHODS)
    o = rows[3]
    assert o["feasible"] and o["time_min"] == pytest.approx(105.0) and o["charge_min"] == pytest.approx(30.0) and o["fix_min"] == pytest.approx(15.0) and o["drive_min"] == pytest.approx(60.0)
    assert o["stops"] == 2 and o["mean_speed"] == pytest.approx(110.0) and o["charged_kwh"] == pytest.approx(30.0)
    assert o["consumption"] == pytest.approx(24.0) and o["gap_opt_pct"] == pytest.approx(0.0, abs=1e-9)              # 24 kWh auf 100 km
    r = rows[0]
    assert r["gap_opt_pct"] == pytest.approx(10.0) and r["consumption"] == pytest.approx(40.0) and r["stops"] == 1 and r["drive_min"] == pytest.approx(60 * (1.925 - 0.6 - 0.125))
    assert rows[1] == {"key": "const_max", "feasible": False, "note": "nicht erreichbar"}
    assert rows[2]["gap_opt_pct"] == pytest.approx(0.0, abs=1e-9) and rows[2]["stops"] == 0


def test_summary_rows_without_a_reachable_optimum_give_nan_gaps():
    run = fake_run(opt=None, rule=10.0)
    run["plans"]["rule"].energy = run["plans"]["rule"].energy + 1.0
    rows = E.summary_rows(run)
    assert rows[3]["feasible"] is False and math.isnan(rows[0]["gap_opt_pct"])


# ------------------------------------------------------------------ Meldungen: Praxisregel
def test_rule_message_flips_at_one_percent_gap():
    assert E.RULE_GAP_MIN_PCT == 1.0
    first = lambda r: r[0]
    assert first(E.messages(gap_run(g_rule=1.01)))[0] == "success" and first(E.messages(gap_run(g_rule=0.99)))[0] == "info"
    assert first(E.messages(gap_run(g_rule=1.5)))[0] == "success"


def test_rule_success_message_names_numbers_and_the_target_soc():
    stops = [stop(soc_to=90.0), stop(soc_to=50.0), stop(soc_to=60.0)]
    state, text = E.messages(gap_run(g_rule=2.0, opt_stops=stops, top=130))[0]
    assert state == "success" and "Tempolimit 130 km/h" in text and "bis 80 % laden" in text
    assert "12 min (2.0 %) länger" in text                                                      # 2 % von 600 min
    assert "Das Optimum macht 3 Ladestopps mit einem mittleren Ladeziel von 55 %, die Praxisregel 0." in text


def test_rule_success_message_without_stops_of_the_optimum_has_a_fallback_text():
    text = E.messages(gap_run(g_rule=2.0, opt_stops=[]))[0][1]
    assert "Das Optimum kommt ohne Ladestopp aus, die Praxisregel macht 0." in text and "Ladeziel" not in text


def test_rule_info_message_uses_the_absolute_difference_even_if_the_rule_is_faster():
    state, text = E.messages(gap_run(g_rule=0.5))[0]
    assert state == "info" and "nur 3.0 min (0.5 %) neben dem Optimum" in text and "genügt sie praktisch" in text
    state, text = E.messages(gap_run(g_rule=-0.2))[0]
    assert state == "info" and "nur 1.2 min (0.2 %)" in text                                    # Rasterrauschen: die Regel kann knapp schneller sein


# ------------------------------------------------------------------ Meldungen: beste konstante Geschwindigkeit
def test_best_speed_message_flips_at_half_a_step_below_the_limit():
    below = [t for s, t in msgs(v_best=127.4, top=130) if "beste konstante Geschwindigkeit" in t][0]
    at = [t for s, t in msgs(v_best=127.5, top=130) if "beste konstante Geschwindigkeit" in t][0]
    assert "liegt bei 127 km/h, also 3 km/h unter dem Tempolimit" in below and "ist das Tempolimit von 130 km/h" in at and "lohnt sich das Ausfahren" in at


def test_best_speed_below_the_limit_names_the_time_cost_of_the_limit():
    run = fake_run(opt=10.0, rule=10.5, cmax=10.1, cbest=10.05, v_best=100.0, top=130)
    text = [t for s, t in E.messages(run) if "unter dem Tempolimit" in t][0]
    assert "liegt bei 100 km/h, also 30 km/h unter dem Tempolimit" in text
    assert "Mit Tempolimit 130 km/h und optimalem Laden wären es 3 min mehr" in text                # 606 − 603 min
    run["plans"]["const_max"] = unreachable("const_max")
    assert "optimalem Laden wären es" not in [t for s, t in E.messages(run) if "unter dem Tempolimit" in t][0]


def test_free_speed_message_flips_at_half_a_percent():
    assert E.TIE_PCT == 0.5
    low = E.messages(gap_run(g_best=0.49))[-1]
    high = E.messages(gap_run(g_best=0.51))[-1]
    assert low[0] == "info" and "bringt gegenüber der besten konstanten nur 2.9 min (0.49 %)" in low[1]        # 0,49 % von 600 min
    assert high[0] == "success" and "spart gegenüber der besten konstanten 3.1 min (0.5 %)" in high[1]


def test_all_reachable_gives_three_messages_in_a_fixed_order():
    out = E.messages(fake_run())
    assert len(out) == 3 and [s for s, _ in out] == ["success", "info", "success"] and "Praxisregel" in out[0][1] and "konstante Geschwindigkeit" in out[1][1] and "freie Geschwindigkeit" in out[2][1]


# ------------------------------------------------------------------ Meldungen: nicht erreichbare Verfahren
def test_unreachable_methods_each_get_a_warning_with_label_and_note():
    out = E.messages(fake_run(rule=None, cmax=None))
    warns = [t for s, t in out if s == "warning"]
    assert warns == ["Praxisregel: Die Praxisregel erreicht das Ziel nicht.", "Tempolimit, optimal laden: Mit diesen Einstellungen ist das Ziel nicht erreichbar."]
    assert [s for s, _ in out[:2]] == ["warning", "warning"] and len(out) == 4                      # danach noch die Meldungen zur besten konstanten Fahrt


def test_unreachable_optimum_returns_only_the_warnings():
    out = E.messages(fake_run(opt=None))
    assert out == [("warning", "Optimum (Geschwindigkeit frei): Mit diesen Einstellungen ist das Ziel nicht erreichbar.")]
    assert E.messages(fake_run(opt=None, rule=None, cmax=None, cbest=None)) and all(s == "warning" for s, _ in E.messages(fake_run(opt=None, rule=None, cmax=None, cbest=None)))
    assert len(E.messages(fake_run(opt=None, rule=None, cmax=None, cbest=None))) == 4


def test_unreachable_rule_still_reports_the_constant_speed_messages():
    out = E.messages(fake_run(rule=None))
    assert out[0][0] == "warning" and len(out) == 3 and not any("Praxisregel (Tempolimit" in t for _, t in out)


def test_unreachable_best_constant_gives_a_warning_and_only_the_rule_message():
    out = E.messages(fake_run(cbest=None))
    assert [s for s, _ in out] == ["warning", "success"] and "Beste konstante Geschwindigkeit" in out[0][1]


# ------------------------------------------------------------------ Live-Rechnung
def test_run_live_runs_all_four_methods_on_the_speed_grid():
    run = E.run_live(SHORT)
    assert set(run) == {"settings", "trip", "plans", "seconds", "speeds"} and list(run["plans"]) == list(C.METHODS)
    assert run["settings"] == SHORT and run["settings"] is not SHORT and run["speeds"][0] == 40 and run["speeds"][-1] == 130 and run["seconds"] >= 0
    assert all(E.feasible(run, k) for k in C.METHODS) and run["trip"].route.n == 20


def test_run_live_values_are_ordered_by_the_choice_they_have():
    p = E.run_live(SHORT)["plans"]
    tol = 1e-9
    assert p["opt"].value_h <= p["const_best"].value_h + tol and p["const_best"].value_h <= p["const_max"].value_h + tol         # mehr Wahlmöglichkeiten, nie schlechter
    assert all(p[k].time_h > 0 for k in C.METHODS) and all(p[k].time_min == pytest.approx(60 * p[k].time_h) for k in C.METHODS)


def test_run_live_changes_with_the_settings():
    a, b = E.run_live(SHORT), E.run_live({**SHORT, "headwind": 25})
    assert b["plans"]["opt"].energy.sum() > a["plans"]["opt"].energy.sum()                  # auf 100 km ohne Stopp bleibt die Zeit gleich, der Verbrauch steigt
    assert E.run_live({**SHORT, "vmax": 110})["speeds"][-1] == 110


def test_a_target_below_the_start_charge_is_reachable_by_charging_at_the_start():
    run = E.run_live({**SHORT, "soc0": 10, "smin_dest": 30})
    for key in C.METHODS:
        p = run["plans"][key]
        assert p.feasible and len(p.stops) >= 1 and p.stops[0].km == 0.0 and p.stops[0].soc_from == pytest.approx(10.0), key
        assert p.soc_end >= run["trip"].smin_dest - 1e-6


@pytest.mark.parametrize("soc0", [100, 10])
def test_a_tiny_battery_gives_unreachable_plans_with_notes_and_no_exception(soc0):
    run = E.run_live({**SHORT, "cap": 0.2, "soc0": soc0})
    for key in C.METHODS:
        p = run["plans"][key]
        assert p.feasible is False and p.note, key
        assert math.isnan(p.time_h) and p.mean_speed != p.mean_speed                          # keine Zeit, keine Geschwindigkeit
    assert [s for s, _ in E.messages(run)] == ["warning"] * 4
    rows = E.summary_rows(run)
    assert all(r["feasible"] is False and r["note"] for r in rows) and math.isnan(E.gap_pct(run, "rule")) and math.isnan(E.best_speed(run))


def test_a_small_battery_makes_the_fast_methods_unreachable_but_the_flags_match_the_warnings():
    run = E.run_live({**SHORT, "cap": 1.0})
    out = E.messages(run)
    unreachable_keys = [k for k in C.METHODS if not E.feasible(run, k)]
    assert unreachable_keys, "bei 1 kWh Batterie muss mindestens ein Verfahren das Ziel verfehlen"
    assert [t.split(":")[0] for s, t in out if s == "warning"] == [C.METHOD_LABELS[k] for k in unreachable_keys]
