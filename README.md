# Reisegeschwindigkeit: Wie schnell fahren, wenn man laden muss? (Streamlit-Demo)

**[→ Demo live ausprobieren](https://sebastianhanisch-reisetempo-demo.streamlit.app/)**

Interaktive **Fall-Demo** zur Reiseplanung eines Elektrofahrzeugs zwischen **möglichst sparsam** und **möglichst schnell** im Portfolio von [Sebastian Hanisch](https://sebastianhanisch.net) (Operations Research und Machine Learning),
Gruppe Transport & Tourenplanung. Gegenstück zur [Ladestrategie](https://github.com/sebastian-hanisch/ladestrategie-demo): Dort wird bei fester Geschwindigkeit und festen Ladesäulen die **Energie** minimiert, und dort werden
Temperatur und Batterieheizen untersucht; hier wählt der **Zeitwert** (Euro je Stunde Reisezeit) den Punkt zwischen Energie und Zeit, und die **Reisegeschwindigkeit je Abschnitt** und der **Ladeplan** (wo laden, von wie viel auf wie viel
Prozent) sind die Entscheidungen. Strecke mit **Höhenprofil** und **Wind**; die Außentemperatur ist konstant und mild angenommen.

Gegeben sind Nettokapazität, Anfangsladestand, Mindestladestand am Ladestopp und am Ziel, Streckenlänge, Zeitwert und Strompreis. Implizit steckt ein geschwindigkeitsabhängiger Verbrauch (aus der Physik), eine Ladekurve
(Ladeleistung über dem Ladestand) und ein Ladeverlust darin. Schnellladen ist an jeder Zellgrenze der Strecke möglich. Es gibt fünf Musterfahrzeuge und acht Beispielszenarien; jeder Wert bleibt einstellbar.

## Kernfrage

Schneller fahren verbraucht mehr Energie und kostet damit Ladezeit; langsamer fahren spart Energie, kostet aber Fahrzeit. **Wie viel ist eine Stunde Reisezeit wert, und wie schnell sollte man dann fahren, wenn man laden muss? Und
wie viel verschenkt die einfache Regel „Tempolimit fahren, bei Bedarf bis 80 % laden“?** Die Demo vergleicht diese **Praxisregel** mit dem **Tempolimit bei optimalem Laden**, der **besten konstanten Geschwindigkeit** und dem **Optimum**
(Geschwindigkeit je 5-km-Zelle frei, dynamische Programmierung über Ort und Ladestand), alle bis auf die Regel für dieselbe Zielfunktion:

> Kosten = Zeitwert · Reisezeit + Strompreis / Ladewirkungsgrad · Energie, die die Fahrt der Batterie entnimmt.

Der Zeitwert wählt den Punkt der Spanne: bei **1 €/h** zählt fast nur die Energie („möglichst sparsam“), bei **„∞“** nur die Zeit („möglichst schnell“, die Energie kostet nichts). Das Optimum je Zeitwert bildet die Linie der
besten Kompromisse aus Reisezeit und Energie; jede Gerade gleicher Kosten (Steigung minus Zeitwert) berührt sie im gewählten Optimum.

## Literatur und Abgrenzung

Das Problem ist aus der Literatur bekannt, die Demo erfindet es nicht neu. Zeitoptimale Planung mit nichtlinearer Ladekurve: Montoya, Guéret, Mendoza und Villegas, *The electric vehicle routing problem with nonlinear charging function*,
Transportation Research Part B 103 (2017). Energie- und zeitoptimale Wege mit Ladestopps: Baum et al., *Energy-Optimal Routes for Battery Electric Vehicles*, Algorithmica (2019). Planung von Fernfahrten mit Geschwindigkeit und
Ladeentscheidungen: *Planning Ahead for EV: Total Travel Time Optimization for Electric Vehicles*, IEEE ITSC 2019 (DOI 10.1109/ITSC.2019.8917335); dynamische Programmierung über Geschwindigkeit und Laden mit Höhenprofil:
*An All-Electric Alpine Crossing: Time-Optimal Strategy Calculation via Fleet-Based Vehicle Data*, IEEE Open Journal of ITS 2020 (DOI 10.1109/OJITS.2020.3019599). Zum Ladefenster auf Langstrecken: Clar-Garcia et al.,
*Optimal DC Fast-Charging Strategies for Battery Electric Vehicles During Long-Distance Trips*, Batteries 11(11), 2025 (DOI 10.3390/batteries11110394): Die optimale Ladegrenze liegt dort bei etwa 59 % Ladestand (±10), unabhängig
von der Außentemperatur, mit mehr, dafür kürzeren Stopps. Das passt zu dem, was hier gemessen wird (Ladeziel im Mittel um 50 % bei Zeit allein). Die Zusammenfassungen der Artikel wurden im Web gelesen, die Volltexte nicht ausgewertet;
Zahlen daraus stehen nur, wo sie in einer Zusammenfassung standen. Diese Demo ist keine Nachbildung der Studien, sondern rechnet das Problem mit eigenen, stilisierten Annahmen nach. Dass sich Zeit und Energie gegeneinander
abwägen lassen (hier mit einem Zeitwert in Euro, einer Gewichtssumme), ist der übliche Weg, eine Kompromisslinie zu erzeugen; die Demo rechnet ihn für Fahrzeug, Strecke und Ladekurve nach.

Verwandte Demos des Portfolios, die dasselbe nicht tun: die [Ladestrategie](https://github.com/sebastian-hanisch/ladestrategie-demo) (Energie bei fester Geschwindigkeit, Temperatur und Batterieheizen, keine Ladekurve), die
[Geschwindigkeitsoptimierung](https://github.com/sebastian-hanisch/slow-steaming-demo) im Seeverkehr (Geschwindigkeit gegen Zeitfenster, kein Laden), der [Fernverkehr](https://github.com/sebastian-hanisch/fernverkehr-demo)
mit Fahrerregeln und Elektro-Lkw (Touren mehrerer Fahrzeuge, Laden proportional zur Energie) und die [Energieoptimale Fahrweise](https://github.com/sebastian-hanisch/energiefahrweise-demo) eines Zuges (Dynamik und Rollen).

## Befunde und Korrekturen gegenüber dem Plan

- **Die Demo wurde nach der ersten Fassung umgebaut.** Die erste Fassung minimierte nur die Reisezeit und hatte die Außentemperatur als Regler. Auf Anregung zeigt sie jetzt die ganze Spanne zwischen sparsam und schnell (Zeitwert und
  Strompreis als Regler), und die Temperatur ist konstant: Ihr Einfluss steht in der Ladestrategie-Demo. Die alten Befunde zu „Zeit allein“ gelten unverändert weiter (Messreihe `power`, `wind`, `fix`, `height` bei „Zeit allein“),
  die Kältebefunde sind entfallen. Neu ist die Mindestgeschwindigkeit von 60 km/h (Autobahn): Ohne sie liefe der sparsame Rand gegen beliebig kleine Geschwindigkeiten.
- **Ein Vorab-Befund hielt nur teilweise.** Die erste Vorab-Messreihe nannte 4,5 % als mittlere Lücke der Praxisregel (Tempolimit 130 km/h); in dieser Fassung sind es für den Standardfall (Pkw, 150 kW) 3,4 %, für 50 kW 9,0 %.
  Die Größenordnung blieb, der Betrag hängt stark von der Ladeleistung ab.
- **Ein Messfehler der ersten Fassung:** Das Nachspielen eines DP-Plans auf dem Ladestandsraster schwankte um ±3 % und ließ das Optimum scheinbar schlechter aussehen als eine konstante Fahrt (unmöglich, da jede konstante Fahrt eine
  zulässige Wahl des Optimums ist). Der DP-Wert selbst war über alle Raster stabil. Die Demo fährt den Plan deshalb mit dem **stetigen** Ladestand nach (die Wertfunktion wird am echten Ladestand ausgewertet) und zeigt den DP-Wert daneben.
- **Das Höhenprofil ändert wenig.** Zur Erwartung „Steigungen machen die Geschwindigkeit je Abschnitt interessant“: Hangabtrieb und Rollwiderstand addieren je Kilometer eine feste Energie, die nicht von der Geschwindigkeit abhängt;
  nur der Luftwiderstand (und damit der Wind) und die Nebenverbraucher tun es. Gemessen: Eine Geschwindigkeit je Abschnitt zu wählen bringt über alle 1415 Fälle im Mittel 0,14 % (95. Perzentil rund 0,4 %) gegenüber der
  besten **konstanten** Geschwindigkeit, auch mit Hügeln und Wind. Das ist ein Negativbefund und steht deshalb vorn. Das Maximum von 2,0 % liegt beim Elektro-Lkw mitten in der Spanne (20 €/h, 300 km); bei „Zeit allein“ sind es höchstens 0,83 %.
- **Das Ladefenster ist bei „Zeit allein“ der große Hebel, nicht das Tempo.** Das Tempolimit mit optimalem Laden liegt bei 150 kW nur 0,13 % über dem Optimum, die Praxisregel (jeweils bis 80 % laden) 3,4 %. Bei 20 €/h wächst der Anteil des Tempolimits selbst (Energie):
  bei 150 kW und Limit 160 liegt das Tempolimit mit optimalem Laden 11,6 % über dem Optimum, die Praxisregel 14,3 %.
- **Fixzeit je Stopp ist eine Annahme, die das Ergebnis mitbestimmt.** Sie war im Auftrag nicht genannt; ohne sie gäbe es beliebig viele Mikro-Stopps. Bei 5 min lädt das Optimum im Mittel auf etwa 50 %, bei 30 min je nach Ladeleistung auf 61 bis 89 %.
- **Zeitwert und Strompreis sind Annahmen, die das Ergebnis mitbestimmen,** und deshalb Regler. Der Standard von 20 €/h und 0,50 €/kWh ist stilisiert, nicht aus einer Quelle; der Strompreis verschiebt nur das Verhältnis von Zeit und Energie.

## Modell

- **Strecke:** Zellen zu 5 km (bis 1500 km). Je Zelle eine Steigung, ein Gegenwind und eine gewählte Geschwindigkeit. Höhenprofil aus vier Typen (flach, hügelig mit Höhenunterschied null, Mittelgebirge bis 5 %, Alpenpass mit einem Anstieg
  von 4 bis 5 % über 30 bis 50 km und gleich hohem Abstieg), zufällig mit SplitMix64 (Ganzzahl-Arithmetik, plattformstabil), dazu ein einstellbarer Höhenunterschied Start bis Ziel. Wind konstant oder je 20 bis 50 km um bis zu ±15 km/h schwankend.
- **Verbrauch:** Kraft am Rad = Rollwiderstand + Hangabtrieb + Luftwiderstand mit der Relativgeschwindigkeit zum Wind (0,5·ρ·c_w·A·(v+w)·|v+w|). Antrieb mit Wirkungsgrad 0,90, Rekuperation mit 0,65, Nebenverbraucher als Leistung mal Zeit.
  Die Temperatur ist konstant und mild; es gibt keinen Kälteeffekt (siehe Ladestrategie-Demo).
- **Laden:** Ladeleistung = Spitzenleistung · Kurve(Ladestand) · Ladewirkungsgrad. Drei stilisierte Kurvenformen (Standard, Lange Spitze, Früh abfallend); die Ladezeit ist das Integral dE/P, auf dem Raster als Trapezregel und in geschlossener Form
  für die Nachrechnung. Ladeverlust einstellbar (Standard 10 %). Ein Stopp kostet zusätzlich eine feste Zeit (Standard 5 min). Laden ist an jeder Zellgrenze möglich, wenn bei Ankunft der Mindestladestand am
  Stopp erreicht ist (am Start ohne Einschränkung).
- **Zielfunktion:** Kosten = Zeitwert · Reisezeit + Strompreis / Ladewirkungsgrad · entnommene Energie. Geladene Energie kostet nichts extra: Die Energie wird bei der Entnahme bewertet (Anfangsladestand zum selben Preis, damit kurze Fahrten ohne Laden
  nicht „gratis“ wären), Laden kostet nur Zeit. Rekuperation oberhalb der Kapazität wird nicht gutgeschrieben. „∞“ heißt: Zeitwert 1, Energiegewicht 0, die Zielfunktion ist die Reisezeit. Wählbare Zeitwerte: 1, 2, 5, 10, 20, 30, 50, 100 €/h und „∞“;
  Strompreis 0,20 bis 1,00 €/kWh (Standard 0,50).
- **Fahrzeuge:** Kompaktwagen (50 kWh, 100 kW), Pkw (77 kWh, 150 kW, Standard), Großer Pkw (100 kWh, 250 kW), Lieferwagen (80 kWh, 120 kW, Tempolimit 110), Elektro-Lkw (600 kWh, 350 kW, 24 t, Tempolimit 90). Alle Werte sind
  Größenordnungen, keine Herstellerangaben, und im Regler einstellbar.

## Methodik

- **Praxisregel:** konstant mit dem Tempolimit fahren; ein Stopp, sobald die nächste Zelle den Ladestand unter den Mindestladestand am Stopp drücken würde; Laden bis 80 %, am letzten Stopp nur so viel, wie das Ziel braucht (stetig simuliert).
  Sie hängt nicht vom Zeitwert ab; ihre Kosten werden mit derselben Zielfunktion bewertet.
- **Tempolimit, optimal laden:** dieselbe Geschwindigkeit, Ort und Menge der Stopps aus der DP (für die Zielfunktion).
- **Beste konstante Geschwindigkeit:** je Geschwindigkeit im Raster von 5 km/h (ab 60 km/h) ein DP, gewählt wird der kleinste DP-Wert.
- **Optimum:** Rückwärts-DP über (Ort, Ladestand) mit 500 Ladestandsstufen (höchstens 0,25 kWh je Stufe): f_i(s) = min_v w_t·dx/v + w_e·u_i(s,v) + g_(i+1)(s − e_i(v)) mit linearer Interpolation der Wertfunktion und der entnommenen Energie
  u = max(e, s − Kapazität), g_i(s) = min(f_i(s), min_(s'>s) w_t·(t_fix + Tch(s') − Tch(s)) + f_i(s')). Danach wird der Plan mit dem stetigen Ladestand nachgefahren. Rechenzeit der Live-Rechnung etwa 0,2 bis 1 s, die Spanne
  (neun Optimalpläne und je nach Tempolimit bis zu 25 konstante Geschwindigkeiten) kommt in der App dazu.
- **Spanne:** je wählbarem Zeitwert der Optimalplan; dazu die konstanten Geschwindigkeiten mit zeitoptimalem Laden (die entnommene Energie hängt bei einer festen Geschwindigkeit nicht vom Laden ab).

## Befunde (gemessen, keine Behauptungen)

Alle Zahlen stammen aus `data/rtp_results.json` (1415 Fälle, `tools/sweep.py`, 5 bis 10 Zufallsstrecken je Zelle, Seeds ab 100) und werden in `tests/test_claims.py` über dieselben Auswertungsfunktionen wie in der App nachgerechnet.
Standardfall der Messreihe: Pkw (77 kWh), hügelige Strecke von 600 km, 5 min Fixzeit, 0,50 €/kWh, wenn nichts anderes steht. „Zeit allein“ ist der Zeitwert „∞“. Prozentwerte der Spanne beziehen sich auf „Zeit allein“.

| Frage | Befund |
|---|---|
| Wie weit reicht die Spanne? | Pkw, 150 kW, Limit 130: Von „Zeit allein“ bis 1 €/h sinkt der Verbrauch von **21,6 auf 10,7 kWh/100 km** (−51 %), die Reisezeit steigt von 316 auf 596 min (+89 %); die Geschwindigkeit fällt von 130 km/h auf die Mindestgeschwindigkeit von 60. |
| Und der Mittelweg? | Bei 20 €/h: **+9,7 %** Reisezeit (346 min) für **−17,4 %** Verbrauch (17,9 kWh/100 km), Geschwindigkeit etwa 112 km/h; bei 10 €/h +20,1 % Reisezeit für −28,0 % Verbrauch. |
| Ab wann gibt es nichts mehr zu gewinnen? | Ab 100 €/h ist der Pkw (wie Kompaktwagen und Großer Pkw) nicht mehr von „Zeit allein“ zu unterscheiden. Lieferwagen und Elektro-Lkw brauchen mehr: Bei 50 €/h noch +2,3 % bzw. **+7,2 %** Reisezeit für −10,2 % bzw. −9,8 % Verbrauch. |
| Wie unterscheiden sich die Fahrzeuge in der Mitte der Spanne? | Bei 20 €/h gegen „Zeit allein“ (Reisezeit, Verbrauch): Kompaktwagen +7,2 % / −19,3 %, Pkw +9,7 % / −17,4 %, Großer Pkw +9,0 % / −14,5 %, Lieferwagen +9,3 % / −23,5 %, Elektro-Lkw **+25,5 % / −22,4 %**. |
| Wie viel verschenkt die Praxisregel bei „Zeit allein“? | Bei 150 kW und Tempolimit 130: **3,4 %** Reisezeit über dem Optimum; bei 50 kW **9,0 %**; bei 350 kW 1,5 %. |
| Und bei 20 €/h? | Bei 150 kW und Limit 130 kostet sie **3,4 %** mehr als das Optimum, ist aber **5,7 % schneller** und verbraucht 21,6 statt 17,9 kWh/100 km; bei 50 kW sind es 11,8 % Mehrkosten. |
| Spielt das Tempolimit eine Rolle? | „Zeit allein“, 50 kW: Praxisregel bei Limit 160 **21,3 %**, bei 180 **30,8 %** über dem Optimum; bei 150 kW 5,1 % und 5,4 %. Bei 20 €/h, 50 kW: 33,8 % und 50,9 % Mehrkosten; bei 150 kW 14,3 % und 25,3 % (Limit 180: 35,2 statt 17,9 kWh/100 km). |
| Reicht das Tempolimit mit optimalem Laden? | „Zeit allein“, 150 kW, Limit 130: **0,13 %** über dem Optimum (das Ladefenster, nicht das Tempo, macht den Unterschied); bei 50 kW und Limit 160 5,2 %, bei 180 13,5 %. Bei 20 €/h, 150 kW, Limit 130: 1,4 % Mehrkosten. |
| Wie schnell sollte man fahren? | Beste konstante Geschwindigkeit bei „Zeit allein“: bei 50 kW **126** (Limit 130) bzw. **134** km/h (Limit 160 und 180); bei 150 kW das Limit 130 bzw. 160, bei Limit 180 etwa **173,5** km/h. Bei 20 €/h fast unabhängig vom Tempolimit: **100** km/h bei 50 kW, **110** bei 150 kW, **120** bei 350 kW (Limit 130, 160 und 180). |
| Bringt eine Geschwindigkeit je Abschnitt etwas? | **Fast nichts:** im Mittel 0,14 % der Zielfunktion gegenüber der besten konstanten Geschwindigkeit (95. Perzentil rund 0,4 %, Maximum 2,0 % beim Elektro-Lkw, 1415 Fälle; bei „Zeit allein“ höchstens 0,83 %). |
| Auf wie viel Prozent laden die Stopps? | Bei „Zeit allein“ im Mittel auf etwa **50 %** bei 5 min Fixzeit und Tempolimit 130 (46 bis 50 % je Ladeleistung); bei 30 min Fixzeit auf 61 bis 89 %. Bei 20 €/h genügt ein Stopp, geladen wird auf 45 % (50 kW), 59 % (150 kW) und 71 % (350 kW). |
| Was macht Wind? | Beste konstante Geschwindigkeit bei 50 kW und Limit 160 („Zeit allein“): 145 km/h bei 30 km/h Rückenwind, 133 ohne Wind, 124 bei 30 km/h Gegenwind. Bei 150 kW fährt man in allen Fällen das Limit. |
| Was kostet ein Höhenunterschied? | Optimum, „Zeit allein“, 600 km: Pkw +1000 m: **+1,2 %** Reisezeit (21,6 auf 22,7 kWh/100 km); Elektro-Lkw: **+3,5 %** Reisezeit und +10,7 % Verbrauch (112,8 auf 124,9 kWh/100 km). Der Alpenpass (Anstieg und Abstieg gleich hoch) kostet dem Pkw 0,2 %. |
| Wie unterscheiden sich die Fahrzeuge bei der Praxisregel? | „Zeit allein“, 600 km, Praxisregel über dem Optimum: Kompaktwagen 4,5 %, Pkw 3,4 %, Großer Pkw 0,3 %, Lieferwagen **10,4 %**, Elektro-Lkw 0,0 % (ein Stopp, kein Unterschied). |

## Ehrliche Grenzen

- **Stilisierte Annahmen:** Fahrzeugwerte und Ladekurven sind Größenordnungen, keine Herstellerangaben. Zeitwert und Strompreis sind Annahmen, die das Ergebnis mitbestimmen; die Standardwerte (20 €/h, 0,50 €/kWh) sind nicht aus einer Quelle.
- **Konstante Temperatur:** kein Kälteeffekt auf Verbrauch und Ladung und keine Temperaturabhängigkeit der Ladeleistung (die Ladestrategie-Demo untersucht Temperatur und Batterieheizen). Im Winter lägen Verbrauch und Ladezeit höher.
- **Der sparsame Rand ist die Mindestgeschwindigkeit:** Bei 1 €/h fährt der Pkw im Mittel 60 km/h und braucht für 600 km fast zehn Stunden. Das ist das Ergebnis der Zielfunktion, kein realistischer Plan; die Spanne zeigt, wie weit Sparsamkeit führen würde.
- **Keine Wirklichkeit des Ladens:** keine Auslastung der Säulen, keine Wartezeit, keine festen Säulenorte (Schnellladen überall), keine Beschleunigungsvorgänge, kein Verkehr, keine Fahrerpausen.
- **Fixzeit:** 5 min je Stopp ist eine Annahme und bestimmt das Ladefenster mit (siehe oben).
- **Rechenfehler:** Die DP rechnet auf einem Raster (500 Ladestandsstufen, 5-km-Zellen, 5 km/h). Unterschiede unter etwa 0,2 % sind nicht belastbar; in einzelnen Fällen liegt die Praxisregel um bis zu 0,08 % unter dem DP-Optimum.
- **Messreihe:** Standardfall ist ein Pkw; die Zellen anderer Fahrzeuge und Längen stehen in den Tabellen, aber nicht alle Kombinationen sind gerechnet. Die Ladeleistung-×-Tempolimit-Messreihe gibt es nur für „Zeit allein“ und 20 €/h; Wind, Fixzeit und Höhe sind nur für „Zeit allein“ gerechnet.
- **Literatur:** Die Studien wurden über ihre Zusammenfassungen gelesen, nicht im Volltext nachgerechnet; diese Demo reproduziert keine ihrer Zahlen.

## Verifikation

- **Kern:** Verbrauch, Ladezeit (Tabelle gegen geschlossene Formel), DP und Praxisregel gegen Handrechnungen auf Mini-Strecken; DP gegen eine **Vollaufzählung** aller Entscheidungsfolgen auf kleinen Strecken, für „Zeit allein“ und für
  eine Zielfunktion mit Energiegewicht (die entnommene Energie dort aus der Energieerhaltung, unabhängig von der Zellrechnung der DP), gegen eine geschlossene Formel für einen einzelnen Stopp und gegen die Zerlegung in unabhängige Zellen ohne Laden
  (`tests/test_oracle_reisetempo.py`); jeder Plan wird unabhängig nachgerechnet (`check_plan`, Zeit, Energie und Kosten).
- **Fehler-Einbau:** `tools/mutation_check.py` baut einzeln Fehler in die Rechenkerne ein; die Ergebnisse stehen im Abschnitt Tests.
- **Messreihe:** Zahlen dieser README in `tests/test_claims.py`; Presets mit Abnahmekriterien an Lauf und Messreihe (`tests/test_stories.py`, Suche mit `tools/preset_search.py`, Seed 500).
- **Oberfläche:** AppTest-Rauchtest (jeder Button, jeder Regler am Minimum und Maximum, jeder Zeitwert, Presets, Permalink) und Footer-Test.

## Tests

510 Tests; der Lauf unter Linux mit frisch installierten, ungepinnten Paketen (wie die CI) ist grün (`python tools/demo_linux_check.py reisetempo-demo`, 118 s), unter Windows dauern die AppTests länger.

- **Mini-Instanzen je Einheit** mit von Hand gerechneten Erwartungen: Verbrauch, Ladeleistung und Ladezeit (Tabelle gegen geschlossene Formel), Szenario, Gewichte der Zielfunktion und Höhenprofil, Interpolation, Laden, Wertfunktion auf einer Strecke aus zwei Zellen, Praxisregel, Meldungen (mit und ohne bewertete Energie), Spanne und Presets.
- **Orakel (60 Tests):** Vollaufzählung aller Entscheidungsfolgen auf zwölf Mini-Szenarien (eben, Gefälle mit Rekuperation, Gegenwind, Ladeverlust, gemischt, kleiner Akku, jeweils für „Zeit allein“ und für eine Zielfunktion mit Energiegewicht): Das DP liegt höchstens 1 % über der Aufzählung und nie mehr als 0,2 % darunter (Rasterfehler der Interpolation);
  die entnommene Energie der Aufzählung kommt aus der Energieerhaltung, nicht aus der Zellrechnung; ohne Laden nimmt jede Zelle die Geschwindigkeit mit den kleinsten Zellkosten (eigene Leistungsbilanz); geschlossene Formel für einen einzelnen Stopp (Zeit und Kosten);
  Ladezeit gegen numerische Quadratur; Energie gegen eine eigene Leistungsbilanz; jeder Plan gegen die unabhängige Nachrechnung.
- **Messreihe und Presets:** jede Zahl der Befunde-Tabelle (51 Tests); Abnahmekriterien aller acht Presets an Lauf und Messreihe, jedes Kriterium kippt einzeln an seiner Schwelle.
- **Oberfläche:** 16 AppTests (jeder Button und Preset, jeder Regler am Minimum und Maximum, jede Option jeder Auswahl, jeder Zeitwert, Fahrzeugwahl, Permalink mit Einrasten und Begrenzen, nicht erreichbares Ziel) und der Footer-Test.
- **Fehler-Einbau** (`tools/mutation_check.py`): 84 Fehler in Physik, DP, Praxisregel, Szenario, Auswertung und Messreihe, einzeln in einer Kopie eingebaut; 81 werden von den Tests gefunden, drei sind gleichwertig (das Suffix-Minimum ohne Verschiebung ist bei positiver Fixzeit wirkungslos, die Fixzeit ist per Regler mindestens 1 min; die Geschwindigkeitskurve mit Zeitwert 1 statt „Zeit allein“ ergibt bei fester Geschwindigkeit denselben Plan; eine Lücke von genau 1,0 % tritt bei Gleitkommazahlen nicht auf).
- **Zwei Fehler, die erst die Tests fanden:** Das Ladestandsraster war bei großen Akkus zu grob (Elektro-Lkw: DP-Wert und Nachfahrt wichen bis zu 3,6 % ab, jetzt höchstens 0,25 kWh je Stufe); der Gerüst-Test importierte eine nicht mehr vorhandene Klasse.

## Dateistruktur

| Datei | Zweck |
|---|---|
| `app.py` | Streamlit-App |
| `rtp_constants.py` | Regler-Grenzen, feste Annahmen, Zeitwerte, Fahrzeuge, Ladekurven, Presets |
| `rtp_rng.py` | SplitMix64 (Ganzzahl-Arithmetik) |
| `rtp_scenario.py` | Fahrzeug, Strecke mit Höhenprofil und Wind, Fahrt, Gewichte der Zielfunktion |
| `rtp_physics.py` | Energie je Zelle, Ladeleistung, Ladezeit (Tabelle und geschlossene Form) |
| `rtp_algorithm.py` | DP über (Ort, Ladestand) für die Zielfunktion, stetige Nachfahrt, beste konstante Geschwindigkeit, Plan-Nachrechnung |
| `rtp_strategies.py` | Praxisregel (stetig simuliert) und die vier Verfahren |
| `rtp_evaluation.py` | Live-Lauf, Kennzahlen, Meldungen, Spanne und Geschwindigkeitskurve |
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
- **Temperatur, temperaturabhängige Ladeleistung und Batterieheizen:** siehe Ladestrategie-Demo.
- **Mehrere Ziele ohne Gewichtssumme** (Pareto-Punkte, die nicht auf der konvexen Hülle liegen): Die Gewichtssumme findet nur Punkte der konvexen Hülle; die Linie der Demo ist dieser Teil der Kompromisse.
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
