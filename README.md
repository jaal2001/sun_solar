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
zu dem der Akku voll geladen ist, berechnet per linearer Regression über
die SOC-Änderung (%/Minute) der letzten 15 Minuten, linear auf 100%
hochgerechnet. Keine Leistungs- oder Kapazitätsangabe nötig – nur der
SOC-Sensor.

**Bekannte Einschränkung:** Ladekurven sind in der CV-Phase (letzte
~5-10% vor voll) nicht mehr linear, der Ladestrom tapert ab. Die lineare
Hochrechnung wird in diesem Bereich tendenziell zu optimistisch sein.

Zusatz-Attribute der Entity:
- `status`: `full` | `charging` | `not_charging` | `unavailable`
- `soc_rate_percent_per_hour`: aktuell gemessene SOC-Änderungsrate
- `samples_in_window`: Anzahl der SOC-Messpunkte im 15-Minuten-Fenster
  (niedrige Werte deuten auf einen grob auflösenden/selten aktualisierenden
  SOC-Sensor hin, was die ETA wackeliger macht)

## Installation über HACS

1. HACS → Integrationen → Menü (⋮) → Benutzerdefinierte Repositories
2. Repository-URL `https://github.com/jaal2001/sun_solar` eintragen, Kategorie **Integration** wählen
3. "Sun Solar Battery ETA" installieren, Home Assistant neu starten
4. Einstellungen → Geräte & Dienste → Integration hinzufügen → "Sun Solar Battery ETA"
5. Im Dialog den Akku-Ladestand-Sensor (%) auswählen

Über den "Konfigurieren"-Button auf der Integrationskachel lässt sich der
Sensor jederzeit ohne YAML nachträglich ändern.

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
