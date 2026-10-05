"""Physik von Hand gerechnet: Kältefaktor, Radkraft, Zellenergie, Ladewirkungsgrad, Ladeleistung und Ladezeit (Tabelle gegen geschlossene Form und gegen Handrechnung).

Mini-Fahrzeug: 50 kWh, 1000 kg, c_w·A = 0,5 m², c_r = 0,01, 100 kW Spitze, 1 kW Nebenverbraucher, Ladekurve „Standard“.
Alle Erwartungen sind mit einem unabhängigen Python-Einzeiler (math statt rtp_physics) nachgerechnet."""
import numpy as np
import pytest

import rtp_constants as C
import rtp_physics as P
from rtp_scenario import Vehicle

VEH = Vehicle(cap=50.0, mass=1000.0, cda=0.5, cr=0.01, peak=100.0, aux=1.0, curve="Standard")


# ------------------------------------------------------------------ Kältefaktor
def test_cold_factor_is_one_from_the_reference_temperature_upwards():
    assert P.cold_factor(20.0) == pytest.approx(1.0) and P.cold_factor(35.0) == pytest.approx(1.0) and P.cold_factor(20.0001) == pytest.approx(1.0)


def test_cold_factor_rises_linearly_below_the_reference():
    assert P.cold_factor(-6.6) == pytest.approx(1.356)                      # 26,6 K unter 20 °C: der AAA-Wert von +35,6 %
    assert P.cold_factor(0.0) == pytest.approx(1 + 20 * 0.356 / 26.6)       # 1,26767
    assert P.cold_factor(-10.0) == pytest.approx(1.4015038, abs=1e-6)       # 30 K unter 20 °C: 1 + 30 · 0,356 / 26,6
    assert P.cold_factor(10.0) - 1 == pytest.approx((P.cold_factor(0.0) - 1) / 2)


# ------------------------------------------------------------------ Radkraft
def test_wheel_force_flat_without_wind():
    # 36 km/h = 10 m/s: Rollen 0,01 · 1000 · 9,81 = 98,1 N, Luft 0,5 · 1,2 · 0,5 · 10² = 30 N
    assert P.wheel_force(VEH, 36.0, 0.0, 0.0) == pytest.approx(128.1)


def test_wheel_force_on_a_climb_adds_the_hill_force():
    # Steigung 10 %: cosθ = 1/√1,01 = 0,995037, sinθ = 0,0995037; Rollen 98,1 · 0,995037 = 97,613 N, Hang 9810 · 0,0995037 = 976,13 N, Luft 30 N
    assert P.wheel_force(VEH, 36.0, 0.1, 0.0) == pytest.approx(1103.7446, abs=1e-3)


def test_wheel_force_downhill_is_negative_when_the_hill_force_wins():
    assert P.wheel_force(VEH, 36.0, -0.1, 0.0) == pytest.approx(-848.5183, abs=1e-3)        # 97,613 − 976,13 + 30
    assert P.wheel_force(VEH, 36.0, -0.1, 0.0) < 0 < P.wheel_force(VEH, 36.0, 0.1, 0.0)


def test_wheel_force_air_uses_the_relative_speed():
    # Gegenwind 36 km/h: Relativgeschwindigkeit 72 km/h = 20 m/s, Luft 0,5 · 1,2 · 0,5 · 400 = 120 N, dazu Rollen 98,1 N
    assert P.wheel_force(VEH, 36.0, 0.0, 36.0) == pytest.approx(218.1)
    assert P.wheel_force(VEH, 36.0, 0.0, 36.0) > P.wheel_force(VEH, 36.0, 0.0, 0.0) > P.wheel_force(VEH, 36.0, 0.0, -18.0)


def test_a_tailwind_larger_than_the_speed_pushes_the_vehicle():
    # Rückenwind 72 km/h bei 36 km/h: Relativgeschwindigkeit −36 km/h = −10 m/s, Luft −30 N (Vorzeichen bleibt erhalten, nicht +30 N): 98,1 − 30
    assert P.wheel_force(VEH, 36.0, 0.0, -72.0) == pytest.approx(68.1)
    assert P.wheel_force(VEH, 36.0, 0.0, -36.0) == pytest.approx(98.1)                       # Relativgeschwindigkeit null: nur Rollen


# ------------------------------------------------------------------ Zellenergie
def test_cell_energy_flat_by_hand():
    # Kraft 128,1 N auf 5 km: 128,1 · 5000 / 3,6e6 = 0,177917 kWh; geteilt durch 0,9 = 0,197685; Nebenverbraucher 1 kW · 5/36 h = 0,138889 kWh
    assert P.cell_energy(VEH, 36.0, 20.0, 0.0, 0.0) == pytest.approx(0.197685 + 0.138889, abs=1e-5)


def test_cell_energy_uphill_is_the_drive_work_over_the_efficiency_plus_the_auxiliaries():
    # Kraft 1103,7446 N: Arbeit 1,532979 kWh, geteilt durch 0,9 = 1,703310; dazu 0,138889
    assert P.cell_energy(VEH, 36.0, 20.0, 0.1, 0.0) == pytest.approx(1.703310 + 0.138889, abs=1e-5)


def test_cell_energy_downhill_recovers_65_percent_of_the_work_without_cold_factor():
    # Kraft −848,5183 N: Arbeit −1,178498 kWh, mal 0,65 = −0,766023; Nebenverbraucher 0,138889 (bei 20 °C)
    assert P.cell_energy(VEH, 36.0, 20.0, -0.1, 0.0) == pytest.approx(-0.766023 + 0.138889, abs=1e-5)
    # bei −10 °C (Faktor 1,4015038): die Rekuperation bleibt gleich, nur der Nebenverbraucher wird mit dem Faktor mehr: 0,138889 · 1,4015038 = 0,194653
    assert P.cell_energy(VEH, 36.0, -10.0, -0.1, 0.0) == pytest.approx(-0.766023 + 0.194653, abs=1e-5)


def test_cold_factor_scales_the_drive_part_and_the_auxiliaries_of_a_flat_cell():
    # 0,197685 · 1,4015038 = 0,277057 und 0,138889 · 1,4015038 = 0,194653
    assert P.cell_energy(VEH, 36.0, -10.0, 0.0, 0.0) == pytest.approx(0.277057 + 0.194653, abs=1e-5)
    assert P.cell_energy(VEH, 36.0, -10.0, 0.0, 0.0) == pytest.approx(P.cell_energy(VEH, 36.0, 20.0, 0.0, 0.0) * P.cold_factor(-10.0))


def test_auxiliaries_scale_with_the_time_in_the_cell():
    only_aux = Vehicle(cap=50.0, mass=1000.0, cda=0.5, cr=0.0, peak=100.0, aux=2.0, curve="Standard")
    still = Vehicle(cap=50.0, mass=1.0, cda=1e-9, cr=0.0, peak=100.0, aux=2.0, curve="Standard")        # praktisch kein Fahrwiderstand
    assert P.cell_energy(still, 50.0, 20.0, 0.0, 0.0) == pytest.approx(2.0 * 5.0 / 50.0, abs=1e-6)       # 2 kW · 0,1 h
    assert P.cell_energy(still, 100.0, 20.0, 0.0, 0.0) == pytest.approx(2.0 * 5.0 / 100.0, abs=1e-6)     # halbe Zeit, halber Verbrauch
    assert P.cell_energy(only_aux, 50.0, 20.0, 0.0, 0.0, dx=10.0) > P.cell_energy(only_aux, 50.0, 20.0, 0.0, 0.0, dx=5.0)


def test_cell_energy_is_linear_in_the_cell_length():
    assert P.cell_energy(VEH, 36.0, 20.0, 0.02, 10.0, dx=10.0) == pytest.approx(2 * P.cell_energy(VEH, 36.0, 20.0, 0.02, 10.0, dx=5.0))


def test_consumption_flat_by_hand():
    # je km: 128,1 · 1000 / 3,6e6 / 0,9 = 0,039537 kWh plus 1/36 = 0,027778 kWh, in kWh/100 km: 6,7315
    assert P.consumption_flat(VEH, 36.0, 20.0) == pytest.approx(6.7315, abs=1e-3)
    assert P.consumption_flat(VEH, 36.0, 20.0, wind=36.0) > P.consumption_flat(VEH, 36.0, 20.0)


# ------------------------------------------------------------------ Ladewirkungsgrad und Ladeleistung
def test_eta_charge_reference_cold_and_floor():
    assert P.eta_charge(20.0, 10.0) == pytest.approx(0.9) and P.eta_charge(30.0, 10.0) == pytest.approx(0.9)
    assert P.eta_charge(0.0, 10.0) == pytest.approx(0.9 - 20 * 0.15 / 40)                   # 0,825: 20 K unter 20 °C kosten 7,5 Punkte
    assert P.eta_charge(-20.0, 10.0) == pytest.approx(0.75)                                 # 40 K: 15 Punkte
    assert P.eta_charge(20.0, 0.0) == pytest.approx(1.0)
    assert P.eta_charge(-20.0, 30.0) == pytest.approx(0.6)                                  # 1 − 0,3 − 0,15 = 0,55, der Boden hebt auf 0,6
    assert P.eta_charge(-25.0, 30.0) == pytest.approx(0.6)


def test_charge_power_follows_the_curve_times_peak_times_efficiency():
    eta = 0.9
    assert float(P.charge_power(VEH, 0.0, 20.0, 10.0)) == pytest.approx(0.75 * 100 * eta)       # 67,5 kW am Anfang der Kurve
    assert float(P.charge_power(VEH, 0.05, 20.0, 10.0)) == pytest.approx(0.875 * 100 * eta)     # Mitte zwischen 0,75 und 1,0: 78,75 kW
    assert float(P.charge_power(VEH, 0.2, 20.0, 10.0)) == pytest.approx(90.0)                   # Plateau
    assert float(P.charge_power(VEH, 0.475, 20.0, 10.0)) == pytest.approx(0.775 * 90.0)         # Mitte zwischen (0,35; 1,0) und (0,6; 0,55)
    assert float(P.charge_power(VEH, 1.0, 20.0, 10.0)) == pytest.approx(0.08 * 90.0)            # 7,2 kW bei voller Batterie
    assert float(P.charge_power(VEH, 0.2, -20.0, 10.0)) == pytest.approx(75.0)                  # Kälte: Wirkungsgrad 0,75


def test_charge_power_accepts_arrays():
    out = P.charge_power(VEH, np.array([0.0, 0.2, 1.0]), 20.0, 10.0)
    assert out.shape == (3,) and out == pytest.approx([67.5, 90.0, 7.2])


# ------------------------------------------------------------------ Ladezeit
GRID = np.linspace(0.0, 50.0, 501)         # Schrittweite 0,1 kWh


def test_charge_time_exact_on_the_constant_part_of_the_curve():
    # 5 bis 17,5 kWh (Anteil 0,1 bis 0,35): konstant 90 kW, 12,5 kWh / 90 kW = 0,138889 h
    assert P.charge_time_exact(VEH, 20.0, 10.0, 5.0, 17.5) == pytest.approx(12.5 / 90.0)


def test_charge_time_exact_on_the_linear_rise_gives_a_logarithm():
    # 0 bis 5 kWh: P(s) = 90 · (0,75 + 0,05 s) kW, Zeit = ln(1,0 / 0,75) / (90 · 0,05) = ln(4/3) / 4,5 = 0,0639293 h
    assert P.charge_time_exact(VEH, 20.0, 10.0, 0.0, 5.0) == pytest.approx(0.0639293, abs=1e-7)


def test_charge_time_exact_is_additive_and_zero_for_an_empty_interval():
    whole = P.charge_time_exact(VEH, 20.0, 10.0, 3.0, 47.0)
    for cut in (4.0, 10.0, 17.5, 31.0, 45.5):
        assert whole == pytest.approx(P.charge_time_exact(VEH, 20.0, 10.0, 3.0, cut) + P.charge_time_exact(VEH, 20.0, 10.0, cut, 47.0))
    assert P.charge_time_exact(VEH, 20.0, 10.0, 30.0, 30.0) == 0.0 and P.charge_time_exact(VEH, 20.0, 10.0, 30.0, 20.0) == 0.0


def test_charge_time_exact_grows_with_cold_and_with_a_smaller_peak():
    warm = P.charge_time_exact(VEH, 20.0, 10.0, 5.0, 40.0)
    assert P.charge_time_exact(VEH, -10.0, 10.0, 5.0, 40.0) > warm
    slow = Vehicle(cap=50.0, mass=1000.0, cda=0.5, cr=0.01, peak=50.0, aux=1.0, curve="Standard")
    assert P.charge_time_exact(slow, 20.0, 10.0, 5.0, 40.0) == pytest.approx(2 * warm)


def test_charge_time_table_on_the_constant_part_equals_the_hand_value():
    tab = P.charge_time_table(VEH, 20.0, 10.0, GRID)
    assert tab[175] - tab[50] == pytest.approx(12.5 / 90.0, rel=1e-9)                       # Trapezregel ist auf einem Plateau exakt


def test_charge_time_table_starts_at_zero_and_increases():
    tab = P.charge_time_table(VEH, 20.0, 10.0, GRID)
    assert len(tab) == len(GRID) and tab[0] == pytest.approx(0.0, abs=1e-15) and bool(np.all(np.diff(tab) > 0))


def test_charge_time_table_agrees_with_the_closed_form():
    tab = P.charge_time_table(VEH, 20.0, 10.0, GRID)
    for i, j in ((0, 500), (0, 50), (100, 400), (300, 500), (450, 500)):
        exact = P.charge_time_exact(VEH, 20.0, 10.0, GRID[i], GRID[j])
        assert tab[j] - tab[i] == pytest.approx(exact, rel=1e-3), (i, j)                    # gemessene Abweichung der Trapezregel etwa 3e-5
    cold = P.charge_time_table(VEH, -10.0, 15.0, GRID)
    assert cold[500] == pytest.approx(P.charge_time_exact(VEH, -10.0, 15.0, 0.0, 50.0), rel=1e-3)
