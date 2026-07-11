# Sun Solar Battery ETA

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/jaal2001/sun_solar.svg)](https://github.com/jaal2001/sun_solar/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Home Assistant Integration, HACS-installierbar. Ersetzt die frühere
`sun-solar-card.js`-Lovelace-Karte vollständig durch eine echte Integration
mit GUI-Konfiguration (Config Flow) und einer wiederverwendbaren Entity.

## Was es macht

Erzeugt genau eine Entity: `sensor.sun_solar_battery_full_eta`
(`device_class: timestamp`). Der Wert ist der voraussichtliche Zeitpunkt,
zu dem der Akku voll geladen ist, berechnet aus dem 15-Minuten-Ø der
Ladeleistung – gleiche Kernlogik wie vorher im JS, nur jetzt serverseitig
in Python und als echte, in Automationen nutzbare Entity statt als
String in einer Karte.

Zusatz-Attribute der Entity:
- `status`: `full` | `charging` | `no_production` | `unavailable`
- `average_power_w`: aktuell verwendeter 15-Min-Leistungsdurchschnitt
- `remaining_to_charge_kwh`: noch zu ladende Energiemenge

## Installation über HACS

1. HACS → Integrationen → Menü (⋮) → Benutzerdefinierte Repositories
2. Repository-URL `https://github.com/jaal2001/sun_solar` eintragen, Kategorie **Integration** wählen
3. "Sun Solar Battery ETA" installieren, Home Assistant neu starten
4. Einstellungen → Geräte & Dienste → Integration hinzufügen → "Sun Solar Battery ETA"
5. Im Dialog eintragen:
   - PV-/Ladeleistung-Sensor (W oder kW)
   - Akku-Ladestand-Sensor (%)
   - Nutzbare Akku-Kapazität in kWh (fester Zahlenwert, keine Entity - der
     SOC deines BMS berücksichtigt SoH-Alterung bereits selbst, deshalb
     reicht hier ein einmalig eingetragener Kapazitätswert)

Über den "Konfigurieren"-Button auf der Integrationskachel lassen sich die
Werte jederzeit ohne YAML nachträglich ändern.

## Anzeige im Dashboard

Es gibt keine eigene Karte mehr. Die Entity lässt sich wie jede andere
Timestamp-Entity mit Standard-Lovelace-Karten anzeigen, z. B. einer
Entities-Karte oder einem Markdown-Template.

## Nicht von diesem Repo getestet

Dieser Code wurde ausschließlich auf Python-Syntax geprüft
(`py_compile`), nicht gegen eine laufende Home-Assistant-Instanz. Vor dem
produktiven Einsatz: in einer Test-Instanz installieren und die
Config-Flow-Dialoge sowie das Verhalten bei "unavailable"-Quell-Entities
durchspielen.
