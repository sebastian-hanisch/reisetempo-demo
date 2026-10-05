# Reisegeschwindigkeit: Wie schnell fahren, wenn man laden muss? (Streamlit-Demo)

**[→ Demo live ausprobieren](https://sebastianhanisch-reisetempo-demo.streamlit.app/)**

Interaktive **Fall-Demo** zur zeitminimalen Reiseplanung eines Elektrofahrzeugs im Portfolio von [Sebastian Hanisch](https://sebastianhanisch.net) (Operations Research und Machine Learning), Gruppe Transport & Tourenplanung.
Gegenstück zur [Ladestrategie](https://github.com/sebastian-hanisch/ladestrategie-demo): Dort wird bei fester Geschwindigkeit und festen Ladesäulen die **Energie** minimiert und das Batterieheizen gewählt; hier wird die
**Reisezeit** minimiert, und die **Reisegeschwindigkeit je Abschnitt** und der **Ladeplan** (wo laden, von wie viel auf wie viel Prozent) sind die Entscheidungen. Strecke mit **Höhenprofil** und **Wind**.

Gegeben sind Nettokapazität, Anfangsladestand, Mindestladestand am Ladestopp und am Ziel, Außentemperatur und Streckenlänge. Implizit steckt ein temperatur- und geschwindigkeitsabhängiger Verbrauch (aus der Physik),
eine Ladekurve (Ladeleistung über dem Ladestand) und ein Ladeverlust darin. Schnellladen ist an jeder Zellgrenze der Strecke möglich. Es gibt fünf Musterfahrzeuge und sieben Beispielszenarien; jeder Wert bleibt einstellbar.

## Kernfrage

Schneller fahren verbraucht mehr Energie und kostet damit Ladezeit; langsamer fahren spart Ladezeit, kostet aber Fahrzeit. **Wie schnell sollte man fahren, wenn man laden muss, und wie viel verschenkt die einfache Regel
„Tempolimit fahren, bei Bedarf bis 80 % laden“?** Die Demo vergleicht diese **Praxisregel** mit dem **Tempolimit bei optimalem Laden**, der **besten konstanten Geschwindigkeit** und dem **Optimum** (Geschwindigkeit je 5-km-Zelle frei,
dynamische Programmierung über Ort und Ladestand).

## Literatur und Abgrenzung

Das Problem ist aus der Literatur bekannt, die Demo erfindet es nicht neu. Zeitoptimale Planung mit nichtlinearer Ladekurve: Montoya, Guéret, Mendoza und Villegas, *The electric vehicle routing problem with nonlinear charging function*,
Transportation Research Part B 103 (2017). Energie- und zeitoptimale Wege mit Ladestopps: Baum et al., *Energy-Optimal Routes for Battery Electric Vehicles*, Algorithmica (2019). Planung von Fernfahrten mit Geschwindigkeit und
Ladeentscheidungen: *Planning Ahead for EV: Total Travel Time Optimization for Electric Vehicles*, IEEE ITSC 2019 (DOI 10.1109/ITSC.2019.8917335); dynamische Programmierung über Geschwindigkeit und Laden mit Höhenprofil:
*An All-Electric Alpine Crossing: Time-Optimal Strategy Calculation via Fleet-Based Vehicle Data*, IEEE Open Journal of ITS 2020 (DOI 10.1109/OJITS.2020.3019599). Zum Ladefenster auf Langstrecken: Clar-Garcia et al.,
*Optimal DC Fast-Charging Strategies for Battery Electric Vehicles During Long-Distance Trips*, Batteries 11(11), 2025 (DOI 10.3390/batteries11110394): Die optimale Ladegrenze liegt dort bei etwa 59 % Ladestand (±10), unabhängig
von der Außentemperatur, mit mehr, dafür kürzeren Stopps. Das passt zu dem, was hier gemessen wird (Ladeziel im Mittel um 50 %). Die Zusammenfassungen der Artikel wurden im Web gelesen, die Volltexte nicht ausgewertet;
Zahlen daraus stehen nur, wo sie in einer Zusammenfassung standen. Diese Demo ist keine Nachbildung der Studien, sondern rechnet das Problem mit eigenen, stilisierten Annahmen nach.

Verwandte Demos des Portfolios, die dasselbe nicht tun: die [Ladestrategie](https://github.com/sebastian-hanisch/ladestrategie-demo) (Energie bei fester Geschwindigkeit, Batterieheizen, keine Ladekurve), die
[Geschwindigkeitsoptimierung](https://github.com/sebastian-hanisch/slow-steaming-demo) im Seeverkehr (Geschwindigkeit gegen Zeitfenster, kein Laden), der [Fernverkehr](https://github.com/sebastian-hanisch/fernverkehr-demo)
mit Fahrerregeln und Elektro-Lkw (Touren mehrerer Fahrzeuge, Laden proportional zur Energie) und die [Energieoptimale Fahrweise](https://github.com/sebastian-hanisch/energiefahrweise-demo) eines Zuges (Dynamik und Rollen).

## Befunde und Korrekturen gegenüber dem Plan

- **Ein Vorab-Befund hielt nur teilweise.** Die erste Vorab-Messreihe nannte 4,5 % als mittlere Lücke der Praxisregel (Tempolimit 130 km/h); in dieser Fassung sind es für den Standardfall (Pkw, 150 kW) 3,4 %, für 50 kW 9,0 %.
  Die Größenordnung blieb, der Betrag hängt stark von der Ladeleistung ab.
- **Ein Messfehler der ersten Fassung:** Das Nachspielen eines DP-Plans auf dem Ladestandsraster schwankte um ±3 % und ließ das Optimum scheinbar schlechter aussehen als eine konstante Fahrt (unmöglich, da jede konstante Fahrt eine
  zulässige Wahl des Optimums ist). Der DP-Wert selbst war über alle Raster stabil. Die Demo fährt den Plan deshalb mit dem **stetigen** Ladestand nach (die Wertfunktion wird am echten Ladestand ausgewertet) und zeigt den DP-Wert daneben.
- **Das Höhenprofil ändert wenig.** Zur Erwartung „Steigungen machen die Geschwindigkeit je Abschnitt interessant“: Hangabtrieb und Rollwiderstand addieren je Kilometer eine feste Energie, die nicht von der Geschwindigkeit abhängt;
  nur der Luftwiderstand (und damit der Wind) und die Nebenverbraucher tun es. Gemessen: Eine Geschwindigkeit je Abschnitt zu wählen bringt über alle 795 Fälle im Mittel 0,17 % (95. Perzentil rund 0,4 %, Maximum 0,83 %) gegenüber der
  besten **konstanten** Geschwindigkeit, auch mit Hügeln und Wind. Das ist ein Negativbefund und steht deshalb vorn.
- **Das Ladefenster ist der große Hebel, nicht das Tempo.** Das Tempolimit mit optimalem Laden liegt bei 150 kW nur 0,13 % über dem Optimum, die Praxisregel (jeweils bis 80 % laden) 3,4 %.
- **Fixzeit je Stopp ist eine Annahme, die das Ergebnis mitbestimmt.** Sie war im Auftrag nicht genannt; ohne sie gäbe es beliebig viele Mikro-Stopps. Bei 5 min lädt das Optimum im Mittel auf etwa 50 %, bei 30 min je nach Ladeleistung auf 61 bis 89 %.

## Modell

- **Strecke:** Zellen zu 5 km (bis 1500 km). Je Zelle eine Steigung, ein Gegenwind und eine gewählte Geschwindigkeit. Höhenprofil aus vier Typen (flach, hügelig mit Höhenunterschied null, Mittelgebirge bis 5 %, Alpenpass mit einem Anstieg
  von 4 bis 5 % über 30 bis 50 km und gleich hohem Abstieg), zufällig mit SplitMix64 (Ganzzahl-Arithmetik, plattformstabil), dazu ein einstellbarer Höhenunterschied Start bis Ziel. Wind konstant oder je 20 bis 50 km um bis zu ±15 km/h schwankend.
- **Verbrauch:** Kraft am Rad = Rollwiderstand + Hangabtrieb + Luftwiderstand mit der Relativgeschwindigkeit zum Wind (0,5·ρ·c_w·A·(v+w)·|v+w|). Antrieb mit Wirkungsgrad 0,90, Rekuperation mit 0,65, Nebenverbraucher als Leistung mal Zeit.
  Kälte erhöht den Verbrauch linear unter 20 °C (+35,6 % bei −6,6 °C nach dem AAA-Wintertest 2025, wie in der Ladestrategie-Demo) und senkt den Ladewirkungsgrad.
- **Laden:** Ladeleistung = Spitzenleistung · Kurve(Ladestand) · Ladewirkungsgrad. Drei stilisierte Kurvenformen (Standard, Lange Spitze, Früh abfallend); die Ladezeit ist das Integral dE/P, auf dem Raster als Trapezregel und in geschlossener Form
  für die Nachrechnung. Ladeverlust bei 20 °C einstellbar (Standard 10 %), bei −20 °C 15 Punkte mehr. Ein Stopp kostet zusätzlich eine feste Zeit (Standard 5 min). Laden ist an jeder Zellgrenze möglich, wenn bei Ankunft der Mindestladestand am
  Stopp erreicht ist (am Start ohne Einschränkung).
- **Fahrzeuge:** Kompaktwagen (50 kWh, 100 kW), Pkw (77 kWh, 150 kW, Standard), Großer Pkw (100 kWh, 250 kW), Lieferwagen (80 kWh, 120 kW, Tempolimit 110), Elektro-Lkw (600 kWh, 350 kW, 24 t, Tempolimit 90). Alle Werte sind
  Größenordnungen, keine Herstellerangaben, und im Regler einstellbar.

## Methodik

- **Praxisregel:** konstant mit dem Tempolimit fahren; ein Stopp, sobald die nächste Zelle den Ladestand unter den Mindestladestand am Stopp drücken würde; Laden bis 80 %, am letzten Stopp nur so viel, wie das Ziel braucht (stetig simuliert).
- **Tempolimit, optimal laden:** dieselbe Geschwindigkeit, Ort und Menge der Stopps aus der DP.
- **Beste konstante Geschwindigkeit:** je Geschwindigkeit im Raster von 5 km/h ein DP, gewählt wird der kleinste DP-Wert.
- **Optimum:** Rückwärts-DP über (Ort, Ladestand) mit 500 Ladestandsstufen: f_i(s) = min_v dx/v + g_(i+1)(s − e_i(v)) mit linearer Interpolation der Wertfunktion, g_i(s) = min(f_i(s), min_(s'>s) t_fix + Tch(s') − Tch(s) + f_i(s')).
  Danach wird der Plan mit dem stetigen Ladestand nachgefahren. Rechenzeit der Live-Rechnung etwa 0,2 bis 1 s.

## Befunde (gemessen, keine Behauptungen)

Alle Zahlen stammen aus `data/rtp_results.json` (795 Fälle, `tools/sweep.py`, 5 bis 10 Zufallsstrecken je Zelle, Seeds ab 100) und werden in `tests/test_claims.py` über dieselben Auswertungsfunktionen wie in der App nachgerechnet.
Standardfall der Messreihe: Pkw (77 kWh), hügelige Strecke von 600 km, 20 °C, 5 min Fixzeit, wenn nichts anderes steht.

| Frage | Befund |
|---|---|
| Wie viel verschenkt die Praxisregel? | Bei 150 kW und Tempolimit 130: **3,4 %** Reisezeit über dem Optimum; bei 50 kW **9,0 %**; bei 350 kW 1,5 %. |
| Spielt das Tempolimit eine Rolle? | Bei 50 kW und Tempolimit 160 liegt die Praxisregel **21,3 %**, bei 180 **30,8 %** über dem Optimum; bei 150 kW sind es 5,1 % und 5,4 %. |
| Reicht das Tempolimit mit optimalem Laden? | Bei 150 kW und Tempolimit 130 liegt es **0,13 %** über dem Optimum: Das Ladefenster, nicht das Tempo, macht den Unterschied. Bei 50 kW und Limit 160 sind es 5,2 %, bei 180 13,5 %. |
| Wie schnell sollte man fahren? | Beste konstante Geschwindigkeit: bei 50 kW **126** (Limit 130) bzw. **134** km/h (Limit 160 und 180); bei 150 kW das Limit 130 bzw. 160, bei Limit 180 etwa **173,5** km/h. |
| Bringt eine Geschwindigkeit je Abschnitt etwas? | **Fast nichts:** im Mittel 0,17 % gegenüber der besten konstanten Geschwindigkeit (95. Perzentil rund 0,4 %, Maximum 0,83 %, 795 Fälle). |
| Auf wie viel Prozent laden die Stopps? | Im Mittel auf etwa **50 %** bei 5 min Fixzeit und Tempolimit 130 (46 bis 50 % je Ladeleistung); bei 30 min Fixzeit auf 61 bis 89 % je Ladeleistung. |
| Was kostet Kälte? | Pkw, 150 kW, Limit 130: bei −10 °C **13,0 %** mehr Reisezeit als bei 20 °C (600 km), bei −20 °C 17,9 %; bei 1000 km 8 statt 5 Stopps bei −10 °C. |
| Was macht Wind? | Beste konstante Geschwindigkeit bei 50 kW und Limit 160: 145 km/h bei 30 km/h Rückenwind, 133 ohne Wind, 124 bei 30 km/h Gegenwind. Bei 150 kW fährt man in allen Fällen das Limit. |
| Was kostet ein Höhenunterschied? | Optimum, 600 km: Pkw +1000 m: **+1,2 %** Reisezeit (21,6 auf 22,7 kWh/100 km); Elektro-Lkw: **+3,5 %** Reisezeit und +10,7 % Verbrauch (112,8 auf 124,9 kWh/100 km). Der Alpenpass (Anstieg und Abstieg gleich hoch) kostet dem Pkw 0,2 %. |
| Wie unterscheiden sich die Fahrzeuge? | Praxisregel über dem Optimum bei 600 km: Kompaktwagen 4,5 %, Pkw 3,4 %, Großer Pkw 0,3 %, Lieferwagen **10,4 %**, Elektro-Lkw 0,0 % (ein Stopp, kein Unterschied). |

## Ehrliche Grenzen

- **Stilisierte Annahmen:** Fahrzeugwerte und Ladekurven sind Größenordnungen, keine Herstellerangaben; die Ladeleistung hängt nicht von der Temperatur ab (die Ladestrategie-Demo untersucht Batterieheizen).
- **Keine Wirklichkeit des Ladens:** keine Auslastung der Säulen, keine Wartezeit, keine festen Säulenorte (Schnellladen überall), keine Beschleunigungsvorgänge, kein Verkehr, keine Fahrerpausen.
- **Fixzeit:** 5 min je Stopp ist eine Annahme und bestimmt das Ladefenster mit (siehe oben).
- **Rechenfehler:** Die DP rechnet auf einem Raster (500 Ladestandsstufen, 5-km-Zellen, 5 km/h). Unterschiede unter etwa 0,2 % sind nicht belastbar; in einzelnen Fällen liegt die Praxisregel um bis zu 0,08 % unter dem DP-Optimum.
- **Messreihe:** Standardfall ist ein Pkw; die Zellen anderer Fahrzeuge, Längen und Temperaturen stehen in den Tabellen, aber nicht alle Kombinationen sind gerechnet.
- **Literatur:** Die Studien wurden über ihre Zusammenfassungen gelesen, nicht im Volltext nachgerechnet; diese Demo reproduziert keine ihrer Zahlen.

## Verifikation

- **Kern:** Verbrauch, Ladezeit (Tabelle gegen geschlossene Formel), DP und Praxisregel gegen Handrechnungen auf Mini-Strecken; DP gegen eine **Vollaufzählung** aller Entscheidungsfolgen auf kleinen Strecken und gegen eine geschlossene Formel für einen
  einzelnen Stopp (`tests/test_oracle_reisetempo.py`); jeder Plan wird unabhängig nachgerechnet (`check_plan`).
- **Fehler-Einbau:** `tools/mutation_check.py` baut einzeln Fehler in die Rechenkerne ein; die Ergebnisse stehen im Abschnitt Tests.
- **Messreihe:** Zahlen dieser README in `tests/test_claims.py`; Presets mit Abnahmekriterien an Lauf und Messreihe (`tests/test_stories.py`, Suche mit `tools/preset_search.py`, Seed 500).
- **Oberfläche:** AppTest-Rauchtest (jeder Button, jeder Regler am Minimum und Maximum, Presets, Permalink) und Footer-Test.

## Tests

424 Tests; der Lauf unter Linux mit frisch installierten, ungepinnten Paketen (wie die CI) ist grün (`python tools/demo_linux_check.py reisetempo-demo`, 50 s), unter Windows dauern die AppTests länger.

- **Mini-Instanzen je Einheit** mit von Hand gerechneten Erwartungen: Verbrauch, Ladeleistung und Ladezeit (Tabelle gegen geschlossene Formel), Szenario und Höhenprofil, Interpolation, Laden, Wertfunktion auf einer Strecke aus zwei Zellen, Praxisregel, Meldungen und Presets.
- **Orakel (45 Tests):** Vollaufzählung aller Entscheidungsfolgen auf sieben Mini-Szenarien (eben, Gefälle mit Rekuperation, Gegenwind, Kälte, gemischt, kleiner Akku): Das DP liegt höchstens 0,7 % über der Aufzählung und nie darunter (Rasterfehler);
  geschlossene Formel für einen einzelnen Stopp; Ladezeit gegen numerische Quadratur; Energie gegen eine eigene Leistungsbilanz; jeder Plan gegen die unabhängige Nachrechnung.
- **Messreihe und Presets:** jede Zahl der Befunde-Tabelle (30 Tests); Abnahmekriterien aller sieben Presets an Lauf und Messreihe, jedes Kriterium kippt einzeln an seiner Schwelle.
- **Oberfläche:** 12 AppTests (jeder Button und Preset, jeder Regler am Minimum und Maximum, jede Option jeder Auswahl, Fahrzeugwahl, Permalink mit Einrasten und Begrenzen, nicht erreichbares Ziel) und der Footer-Test.
- **Fehler-Einbau** (`tools/mutation_check.py`): 56 Fehler in Physik, DP, Praxisregel und Szenario, einzeln in einer Kopie eingebaut; 55 werden von den Tests gefunden, einer ist gleichwertig (das Suffix-Minimum ohne Verschiebung ist bei positiver Fixzeit wirkungslos, und die Fixzeit ist per Regler mindestens 1 min).
- **Zwei Fehler, die erst die Tests fanden:** Das Ladestandsraster war bei großen Akkus zu grob (Elektro-Lkw: DP-Wert und Nachfahrt wichen bis zu 3,6 % ab, jetzt höchstens 0,25 kWh je Stufe); der Gerüst-Test importierte eine nicht mehr vorhandene Klasse.

## Dateistruktur

| Datei | Zweck |
|---|---|
| `app.py` | Streamlit-App |
| `rtp_constants.py` | Regler-Grenzen, feste Annahmen, Fahrzeuge, Ladekurven, Presets |
| `rtp_rng.py` | SplitMix64 (Ganzzahl-Arithmetik) |
| `rtp_scenario.py` | Fahrzeug, Strecke mit Höhenprofil und Wind, Fahrt |
| `rtp_physics.py` | Energie je Zelle, Ladeleistung, Ladezeit (Tabelle und geschlossene Form) |
| `rtp_algorithm.py` | DP über (Ort, Ladestand), stetige Nachfahrt, beste konstante Geschwindigkeit, Plan-Nachrechnung |
| `rtp_strategies.py` | Praxisregel (stetig simuliert) und die vier Verfahren |
| `rtp_evaluation.py` | Live-Lauf, Kennzahlen, Meldungen |
| `rtp_results.py` | Auswertung der vorgerechneten Messreihe |
| `rtp_stories.py` | Abnahmekriterien der Presets |
| `rtp_presets.py` | Permalink, Fahrzeug- und Szenario-Presets, Zufalls-Seed-Button |
| `rtp_visualization.py` | Plotly-Abbildungen (Achsen gesperrt) |
| `rtp_pdf_export.py` | Ladeplan als PDF |
| `data/rtp_results.json` | Messreihe (erzeugt mit `tools/sweep.py`) |
| `tools/sweep.py`, `tools/preset_search.py`, `tools/mutation_check.py` | Messreihe, Preset-Suche, Fehler-Einbau |
| `tests/` | Mini-Instanzen, Orakel, Messreihen-Zahlen, Presets, AppTests, Footer |

## Bewusst nicht umgesetzt

- **Echte Ladesäulen und Routenwahl** (feste Orte, Auslastung, Wartezeit, mehrere Wege): das ist die Ladestrategie- und Netzwerkseite, hier ist Schnellladen überall möglich.
- **Temperaturabhängige Ladeleistung und Batterieheizen:** siehe Ladestrategie-Demo.
- **Beschleunigung, Verkehr, Geschwindigkeitsbegrenzungen je Abschnitt:** das Tempolimit gilt überall; Zellen mit eigenem Limit wären eine Erweiterung.
- **Unsicherheit** (Wind, Verbrauch, Ladeleistung): alle Eingaben sind bekannt, die Planung ist deterministisch.
- **Reale Messdaten** (OBD-Daten, Flottendaten) als Verbrauchsmodell: hier eine Physikformel mit einstellbaren Parametern.

## Lokal ausführen

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
streamlit run app.py
```

## Tests ausführen

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Gebaut mit Streamlit, Plotly, NumPy, pandas und fpdf2.

---

Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). Mehr zum Thema: [Tourenplanung optimieren](https://sebastianhanisch.net/tourenplanung-optimierung.html).
