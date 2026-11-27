# Sun Solar Battery ETA

Sun Solar estimates when solar-charged batteries will reach their full threshold. It uses a rolling linear regression of state of charge (SOC), sampled every 30 seconds by default. Forecasts require daylight and a valid upcoming sunset from `sun.sun`. An estimate later than sunset is suppressed. Batteries already at their threshold report full at any time.

Use an SOC sensor that reports 0–100, with a percent unit or no unit. SOC alone cannot establish the charging source. Use this integration for batteries configured to charge exclusively from solar power. It does not read or control grid charging, tariffs, PV power or capacity. Changes in solar production and charging taper can affect the estimate.

## Install a released version

1. Open **Settings → Marketplace** in Home Assistant 2026.11 and connect GitHub if prompted.
2. Add `https://github.com/jaal2001/sun_solar` as a custom repository. The repository uses the HACS integration format.
3. Download **Sun Solar Battery ETA**, then restart Home Assistant.
4. Under **Settings → Devices & services → Add integration**, select **Sun Solar Battery ETA** and enter a battery name and its SOC sensor. One battery is enough. To add another, repeat this step with a different SOC sensor. Home Assistant groups battery entries under the same Sun Solar integration card.
5. Open the **Sun Solar Battery ETA** card under **Settings → Devices & services → Integrations**. On the battery entry, use **Reconfigure** to change the name or input sensor. Use **Configure** to set the rolling window (default 15 minutes), full threshold (default 99.5%), and optional Recorder history. Existing batteries keep their settings and entity IDs when upgrading from the Helpers view. History is off by default. If it is unavailable or excluded, live samples are collected automatically.

## Entities

- Each battery has a timestamp sensor with status, observed SOC rate and sample count. Existing per-battery entity IDs survive a v0.3 upgrade, and reconfiguring a battery preserves its registry identity.
- `sensor.sun_solar_all_batteries_eta` is the latest valid completion estimate across batteries below their threshold. Its ETA is unknown if any enabled battery has an unknown SOC or any unfinished battery has no forecast. If all are full, the timestamp is the latest observed full time.
- `binary_sensor.sun_solar_all_batteries_full` is on only when every enabled battery is confirmed full. When an enabled entry is unavailable, the binary sensor is off.
- The timestamp sensors expose `eta_display`: local `HH:MM`, `voll` when full, or `--:--` without an estimate. This fixed format is independent of the UI language.

Entity IDs shown here are defaults. Use the IDs in **Settings → Devices & services → Entities** if Home Assistant resolves a name collision or you rename an entity.

For an ESPHome display, import the aggregate attribute through the Home Assistant API:

```yaml
text_sensor:
  - platform: homeassistant
    id: solar_eta_display
    entity_id: sensor.sun_solar_all_batteries_eta
    attribute: eta_display
    internal: true
```

## Dashboard card

Sun Solar automatically registers its bundled **Sun Solar Dashboard** card when the Home Assistant frontend loads. Restart Home Assistant after updating the integration and reload the browser. Open a dashboard in edit mode, add **Sun Solar Dashboard**, and select the PV power sensor. The daily energy and battery SOC sensors are optional. The default forecast sensor is the combined Sun Solar ETA, which also works with just one battery. Select a specific battery's ETA entity to show that battery's forecast instead.

### Migrate from a locally installed card

1. Change the existing card's type from `custom:sun-solar-card` to `custom:sun-solar-dashboard-card`. Keep its `power_entity`, `energy_entity`, `battery_soc_entity`, `title`, `start_hour`, `end_hour`, and `max_power` settings if present.
2. Remove `battery_remaining_entity` from the card configuration. For the ETA and its graph marker, the card uses the Sun Solar integration's forecast. The PV history is used for the production curve.
3. After confirming all migrated cards work, remove the old `/local/sun-solar-card.js` dashboard resource. You can then delete the old file from `config/www`. The two card types can coexist during migration.

## Test the draft in parallel with an existing dashboard

For a draft build, use a separate Home Assistant 2026.11 test instance with its own configuration directory. Use test SOC sensors or simulated values, and configure the location and Sun integration in that instance. Copy the entire `custom_components/sun_solar` directory from a specific commit of `feature/v0.4.0` into the test instance's `config/custom_components/` directory, then restart. Use the GUI to add test batteries and verify the entity states. Avoid having Marketplace manage the same domain in that test instance while using the draft files.

Keep the production dashboard and its local card in place while installing the draft in the separate instance. The draft and published builds share the `sun_solar` domain.

## Development

Use Python 3.14.2 or newer. Install `requirements-test.txt` into a virtual environment and run `python -m pytest -q`. Run `node --test tests/frontend/*.test.cjs` for the card tests. CI runs the tests against Home Assistant 2026.11.3 and checks both the HACS packaging and Home Assistant metadata. Publishing uses the manually dispatched **Release** workflow on `main` and requires passing validation and a matching manifest version.
