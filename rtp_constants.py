"""Feste Annahmen, Regler-Grenzen, Fahrzeug-Presets und Farben der Demo „Reisegeschwindigkeit“ (eine Wahrheitsquelle).

Alle Fahrzeugwerte und Ladekurven sind stilisierte Annahmen in der Größenordnung heutiger Fahrzeuge, keine Herstellerangaben."""

# ------------------------------------------------------------------ Physik (feste Annahmen)
RHO = 1.2                    # Luftdichte (kg/m³)
G_ACC = 9.81                 # Erdbeschleunigung (m/s²)
ETA_DRIVE = 0.90             # Wirkungsgrad Batterie bis Rad beim Antreiben
ETA_REGEN = 0.65             # Anteil der Hangabtriebs- und Bremsarbeit, der bei Rekuperation in die Batterie zurückfließt
T_REF = 20.0                 # Referenztemperatur (°C): darüber kein Kälteeffekt
COLD_PER_K = 0.356 / 26.6    # Mehrverbrauch je Kelvin unter T_REF (AAA-Wintertest 2025: +35,6 % bei −6,6 °C, linear angesetzt)
CHARGE_LOSS_COLD_PER_K = 0.15 / 40.0   # zusätzlicher Ladeverlust je Kelvin unter T_REF (15 Punkte bei −20 °C)
ETA_CHARGE_FLOOR = 0.60      # unterer Anschlag des Ladewirkungsgrads

# ------------------------------------------------------------------ Rechenraster (Live und Messreihe identisch)
DX_KM = 5.0                  # Zellenlänge der Strecke (km): Steigung, Wind und Geschwindigkeit gelten je Zelle
N_SOC = 500                  # Ladestandsraster: mindestens N_SOC Stufen ...
DS_MAX = 0.25                # ... und höchstens DS_MAX kWh je Stufe (große Akkus bekommen mehr Stufen; sonst weichen DP-Wert und Nachfahrt auseinander)
V_MIN = 40                   # kleinste wählbare Reisegeschwindigkeit (km/h)
V_STEP = 5                   # Geschwindigkeitsraster (km/h)
SOC_EPS = 1e-9

# ------------------------------------------------------------------ Praxisregel
RULE_CHARGE_TO = 80.0        # Ladeziel der Praxisregel (Prozent der Kapazität)

# ------------------------------------------------------------------ Ladekurven (Anteil der Spitzenleistung über dem Ladestand), stilisiert
CURVES = {
    "Standard": ((0.0, 0.75), (0.1, 1.0), (0.35, 1.0), (0.6, 0.55), (0.8, 0.30), (0.9, 0.15), (1.0, 0.08)),
    "Lange Spitze": ((0.0, 0.80), (0.1, 1.0), (0.55, 1.0), (0.7, 0.70), (0.8, 0.40), (0.9, 0.20), (1.0, 0.10)),
    "Früh abfallend": ((0.0, 0.70), (0.1, 1.0), (0.2, 0.85), (0.4, 0.55), (0.6, 0.35), (0.8, 0.20), (1.0, 0.10)),
}
CURVE_NAMES = tuple(CURVES)
DEFAULT_CURVE = "Standard"

# ------------------------------------------------------------------ Fahrzeug-Presets (alle Werte im Regler einstellbar)
VEHICLE_ORDER = ("Kompaktwagen", "Pkw", "Großer Pkw", "Lieferwagen", "Elektro-Lkw")
VEHICLES = {
    "Kompaktwagen": {"cap": 50.0, "mass": 1700.0, "cda": 0.62, "cr": 0.010, "peak": 100.0, "aux": 0.8, "curve": "Standard", "vmax": 130},
    "Pkw": {"cap": 77.0, "mass": 2000.0, "cda": 0.62, "cr": 0.010, "peak": 150.0, "aux": 0.8, "curve": "Standard", "vmax": 130},
    "Großer Pkw": {"cap": 100.0, "mass": 2500.0, "cda": 0.75, "cr": 0.010, "peak": 250.0, "aux": 1.0, "curve": "Lange Spitze", "vmax": 130},
    "Lieferwagen": {"cap": 80.0, "mass": 3200.0, "cda": 1.30, "cr": 0.011, "peak": 120.0, "aux": 1.5, "curve": "Früh abfallend", "vmax": 110},
    "Elektro-Lkw": {"cap": 600.0, "mass": 24000.0, "cda": 5.50, "cr": 0.006, "peak": 350.0, "aux": 5.0, "curve": "Standard", "vmax": 90},
}
VEHICLE_HELP = {
    "Kompaktwagen": "Kleiner Akku, mäßige Ladeleistung: viele Stopps, jede Minute Ladezeit zählt.",
    "Pkw": "Mittelklasse mit 77 kWh und 150 kW Spitzenleistung: der Standardfall.",
    "Großer Pkw": "Großer Akku und 250 kW: wenige, kurze Stopps, die Geschwindigkeit wird fast nur vom Tempolimit begrenzt.",
    "Lieferwagen": "Hoher Luftwiderstand, früh abfallende Ladekurve, Tempolimit 110: Geschwindigkeit kostet viel Energie.",
    "Elektro-Lkw": "600 kWh, 24 t, Tempolimit 90: wenige, aber lange Ladestopps.",
}
DEFAULT_VEHICLE = "Pkw"

# ------------------------------------------------------------------ Regler: Fahrzeug
CAP_MIN, CAP_MAX, CAP_STEP = 20.0, 700.0, 1.0
MASS_MIN, MASS_MAX, MASS_STEP = 800.0, 40000.0, 100.0
CDA_MIN, CDA_MAX, CDA_STEP = 0.40, 8.00, 0.01
CR_MIN, CR_MAX, CR_STEP = 0.004, 0.015, 0.0005
PEAK_MIN, PEAK_MAX, PEAK_STEP = 30.0, 800.0, 10.0
AUX_MIN, AUX_MAX, AUX_STEP = 0.3, 10.0, 0.1
LOSS_MIN, LOSS_MAX, LOSS_STEP = 0.0, 30.0, 1.0       # Ladeverlust bei Referenztemperatur (Prozent)
DEFAULT_LOSS = 10.0
STOP_MIN, STOP_MAX, STOP_STEP = 1.0, 30.0, 1.0        # Fixzeit je Ladestopp (Minuten); ohne Fixzeit gäbe es beliebig viele Mikro-Stopps
DEFAULT_STOP = 5.0

# ------------------------------------------------------------------ Regler: Fahrt
LENGTH_MIN, LENGTH_MAX, LENGTH_STEP, DEFAULT_LENGTH = 100, 1500, 50, 600
TEMP_MIN, TEMP_MAX, TEMP_STEP, DEFAULT_TEMP = -25, 40, 5, 20
SOC0_MIN, SOC0_MAX, SOC0_STEP, DEFAULT_SOC0 = 10, 100, 5, 100
SMIN_STOP_MIN, SMIN_STOP_MAX, DEFAULT_SMIN_STOP = 0, 30, 10     # Mindestladestand bei Ankunft an einem Ladestopp (Prozent)
SMIN_DEST_MIN, SMIN_DEST_MAX, DEFAULT_SMIN_DEST = 0, 30, 10     # Mindestladestand am Ziel (Prozent)
VMAX_MIN, VMAX_MAX, VMAX_STEP = 80, 180, 10

# ------------------------------------------------------------------ Regler: Höhenprofil und Wind
PROFILE_TYPES = ("flach", "huegelig", "mittelgebirge", "pass")
PROFILE_LABELS = {"flach": "flach", "huegelig": "hügelig (±2 %)", "mittelgebirge": "Mittelgebirge (bis 5 %)", "pass": "Alpenpass (4 bis 5 % über rund 40 km)"}
DEFAULT_PROFILE = "huegelig"
RISE_MIN, RISE_MAX, RISE_STEP, DEFAULT_RISE = -1000, 1000, 100, 0   # Höhenunterschied Start bis Ziel (m), gleichmäßig auf die Strecke verteilt, zusätzlich zum Profil
WIND_MIN, WIND_MAX, WIND_STEP, DEFAULT_WIND = -40, 40, 5, 0       # Gegenwind in km/h (negativ = Rückenwind)
WIND_MODES = ("konstant", "wechselnd")
DEFAULT_WIND_MODE = "konstant"
SEED_MIN, SEED_MAX, DEFAULT_SEED = 0, 9999, 500

# ------------------------------------------------------------------ Verfahren
METHODS = ("rule", "const_max", "const_best", "opt")
METHOD_LABELS = {
    "rule": "Praxisregel",
    "const_max": "Tempolimit, optimal laden",
    "const_best": "Beste konstante Geschwindigkeit",
    "opt": "Optimum (Geschwindigkeit frei)",
}
METHOD_COLORS = {"rule": "#c0392b", "const_max": "#c77700", "const_best": "#2e7d4f", "opt": "#2a6fb0"}
VIEW_OPTIONS = ("rule", "const_max", "const_best", "opt")
DEFAULT_VIEW = "opt"
COLOR_DRIVE, COLOR_CHARGE, COLOR_FIX = "#2a6fb0", "#c77700", "#7d8898"
COLOR_UP, COLOR_DOWN = "#c77700", "#2a6fb0"

# ------------------------------------------------------------------ Messreihe
RESULTS_FILE = "data/rtp_results.json"

# ------------------------------------------------------------------ Szenarien (Seeds liegen außerhalb der Messreihen-Seeds)
PRESET_ORDER = ["Standard", "Langsamer Lader", "Kälte", "Gegenwind", "Alpenpass", "Ohne Tempolimit", "Elektro-Lkw"]
SCENARIO_KEYS = ("vehicle", "cap", "mass", "cda", "cr", "peak", "aux", "curve", "loss", "stop_min", "length", "profile", "rise", "seed", "headwind", "wind_mode", "temp", "soc0", "smin_stop", "smin_dest", "vmax")


def vehicle_scenario(name: str) -> dict:
    v = VEHICLES[name]
    return {"vehicle": name, "cap": v["cap"], "mass": v["mass"], "cda": v["cda"], "cr": v["cr"], "peak": v["peak"], "aux": v["aux"], "curve": v["curve"], "vmax": v["vmax"]}


BASE_SCENARIO = {**vehicle_scenario(DEFAULT_VEHICLE), "loss": DEFAULT_LOSS, "stop_min": DEFAULT_STOP, "length": DEFAULT_LENGTH, "profile": DEFAULT_PROFILE, "rise": DEFAULT_RISE, "seed": DEFAULT_SEED,
                 "headwind": DEFAULT_WIND, "wind_mode": DEFAULT_WIND_MODE, "temp": DEFAULT_TEMP, "soc0": DEFAULT_SOC0, "smin_stop": DEFAULT_SMIN_STOP, "smin_dest": DEFAULT_SMIN_DEST}

PRESETS = {
    "Standard": dict(BASE_SCENARIO),
    "Langsamer Lader": {**BASE_SCENARIO, "peak": 50.0, "vmax": 160},
    "Kälte": {**BASE_SCENARIO, "temp": -10},
    "Gegenwind": {**BASE_SCENARIO, "peak": 50.0, "headwind": 25, "vmax": 160},
    "Alpenpass": {**BASE_SCENARIO, "profile": "pass"},
    "Ohne Tempolimit": {**BASE_SCENARIO, "vmax": 180},
    "Elektro-Lkw": {**BASE_SCENARIO, **vehicle_scenario("Elektro-Lkw"), "length": 1000},
}
PRESET_HELP = {
    "Standard": "Pkw mit 150 kW, 600 km, 20 °C, hügelige Strecke: Die Praxisregel (Tempolimit, immer bis 80 % laden) verschenkt Zeit beim Laden.",
    "Langsamer Lader": "Mit nur 50 kW lohnt es sich, deutlich unter dem Tempolimit von 160 km/h zu fahren: Jede Minute am Lader ist teuer.",
    "Kälte": "Bei −10 °C steigt der Verbrauch und der Ladewirkungsgrad sinkt: mehr Stopps, deutlich längere Reisezeit.",
    "Gegenwind": "Gegenwind verschiebt die beste Geschwindigkeit nach unten: Der Luftwiderstand wächst mit dem Quadrat der Relativgeschwindigkeit.",
    "Alpenpass": "Anstieg und Abstieg über einen Pass: Die Steigung kostet Energie, ändert aber die beste Geschwindigkeit kaum.",
    "Ohne Tempolimit": "Bis 180 km/h erlaubt: Wie schnell sollte man mit 150 kW überhaupt fahren?",
    "Elektro-Lkw": "600 kWh, 24 t, Tempolimit 90 und 1000 km: Die Geschwindigkeit ist nie die Frage, aber das Ladefenster zählt auch hier.",
}


def fmt_min(x, digits=0):
    return f"{x:.{digits}f} min"


def fmt_hm(minutes: float) -> str:
    """Minuten als „5 h 12 min“."""
    m = int(round(minutes))
    return f"{m // 60} h {m % 60:02d} min"
