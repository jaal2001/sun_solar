"""Exercise Sun Solar against the Home Assistant Core test harness."""

from datetime import datetime, timedelta, timezone

from homeassistant import config_entries
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.loader import async_get_integration
from homeassistant.util import dt as dt_util
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.recorder.common import async_wait_recording_done

from custom_components.sun_solar.const import CONF_BATTERY_SOC_ENTITY, DOMAIN

NOW = datetime(2026, 11, 27, 12, tzinfo=timezone.utc)
ETA = "sensor.sun_solar_all_batteries_eta"
FULL = "binary_sensor.sun_solar_all_batteries_full"
EAST = "sensor.east_soc"
WEST = "sensor.west_soc"


def sun(hass, sunset=NOW + timedelta(hours=3), state="above_horizon"):
    """Set the Sun entity to a deterministic daylight state."""
    attributes = {
        "next_setting": sunset.isoformat() if isinstance(sunset, datetime) else sunset
    }
    hass.states.async_set("sun.sun", state, attributes)


def soc(hass, entity_id, value):
    """Set a battery SOC sensor."""
    hass.states.async_set(entity_id, value, {"unit_of_measurement": "%"})


async def setup_battery(hass, source, name, **kwargs):
    """Load a battery through Home Assistant's config-entry manager."""
    entry = MockConfigEntry(
        domain=DOMAIN, title=name, data={CONF_BATTERY_SOC_ENTITY: source}, **kwargs
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def display(hass, entity_id=ETA):
    """Read the ESPHome display attribute."""
    return hass.states.get(entity_id).attributes["eta_display"]


async def test_forecasts_and_owner_removal(hass, freezer):
    """Check independent samples, the forecast gate and stable aggregate IDs."""
    freezer.move_to(NOW)
    sun(hass)
    soc(hass, EAST, 70)
    soc(hass, WEST, 50)
    east = await setup_battery(hass, EAST, "East")
    west = await setup_battery(hass, WEST, "West")
    registry = er.async_get(hass)
    individual = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{east.entry_id}_battery_full_eta"
    )
    assert hass.states.get(ETA).state == STATE_UNKNOWN
    assert display(hass) == "--:--"
    assert hass.states.get(FULL).state == "off"

    freezer.tick(timedelta(minutes=5))
    soc(hass, EAST, 75)
    soc(hass, WEST, 55)
    await hass.async_block_till_done()
    # Feed an uninterrupted pair of samples within the live sampling cadence.
    freezer.tick(timedelta(seconds=30))
    soc(hass, EAST, 76)
    soc(hass, WEST, 56)
    await hass.async_block_till_done()
    assert hass.states.get(ETA).state == "2026-11-27T12:27:15+00:00"
    assert hass.states.get(individual).state == "2026-11-27T12:17:15+00:00"
    expected = dt_util.as_local(NOW + timedelta(minutes=27, seconds=15))
    assert display(hass) == expected.strftime("%H:%M")

    soc(hass, EAST, "unavailable")
    await hass.async_block_till_done()
    assert hass.states.get(ETA).state == STATE_UNKNOWN

    soc(hass, EAST, 100)
    sun(hass, NOW + timedelta(minutes=10))
    await hass.async_block_till_done()
    assert display(hass) == "--:--"
    assert hass.states.get(ETA).attributes["status"] == "charging_past_sunset"

    sun(hass, "invalid")
    await hass.async_block_till_done()
    assert hass.states.get(ETA).attributes["status"] == "unavailable"

    sun(hass, state="below_horizon")
    await hass.async_block_till_done()
    assert display(hass) == "--:--"
    assert hass.states.get(ETA).attributes["status"] == "not_charging"
    soc(hass, WEST, 99.5)
    await hass.async_block_till_done()
    assert display(hass) == "voll"
    assert hass.states.get(FULL).state == "on"

    registry.async_update_entity(ETA, new_entity_id="sensor.custom_solar_eta")
    await hass.async_block_till_done()
    assert await hass.config_entries.async_remove(east.entry_id) == {
        "require_restart": False
    }
    await hass.async_block_till_done()
    assert (
        registry.async_get("sensor.custom_solar_eta").config_entry_id == west.entry_id
    )
    assert display(hass, "sensor.custom_solar_eta") == "voll"
    assert hass.states.get(FULL).state == "on"

    coordinator = west.runtime_data
    assert await hass.config_entries.async_unload(west.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.custom_solar_eta").state == STATE_UNAVAILABLE
    assert hass.states.get(FULL).state == STATE_UNAVAILABLE
    assert not coordinator._listeners
    assert not coordinator._unsub_refresh
    assert DOMAIN not in hass.data


async def test_config_reconfigure_options_and_legacy_identity(hass):
    """Verify GUI flows and retain v0.3 options and registry identity."""
    soc(hass, EAST, 100)
    soc(hass, WEST, 100)
    hass.states.async_set("sensor.power", "50", {"unit_of_measurement": "W"})
    legacy = await setup_battery(
        hass, EAST, "Legacy", options={CONF_BATTERY_SOC_ENTITY: WEST}
    )
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{legacy.entry_id}_battery_full_eta"
    )
    flow = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    for name, source, errors in (
        ("  ", EAST, {"name": "empty_name"}),
        ("West", WEST, {CONF_BATTERY_SOC_ENTITY: "duplicate_source"}),
        ("Power", "sensor.power", {CONF_BATTERY_SOC_ENTITY: "invalid_source"}),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], {"name": name, CONF_BATTERY_SOC_ENTITY: source}
        )
        assert result["errors"] == errors
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"name": " East ", CONF_BATTERY_SOC_ENTITY: EAST}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "East"
    await hass.async_block_till_done()

    flow = await hass.config_entries.options.async_init(legacy.entry_id)
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"],
        {"window_minutes": 2.5, "full_threshold": 100, "use_recorder": True},
    )
    assert result["errors"] == {"window_minutes": "invalid_window"}
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"],
        {"window_minutes": 20, "full_threshold": 100, "use_recorder": True},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert legacy.runtime_data.settings.entity_id == WEST
    assert legacy.runtime_data.settings.window_minutes == 20
    assert legacy.runtime_data.settings.full_threshold == 100

    soc(hass, "sensor.replacement", 99.5)
    flow = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": legacy.entry_id,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"name": "Renamed", CONF_BATTERY_SOC_ENTITY: EAST}
    )
    assert result["errors"] == {CONF_BATTERY_SOC_ENTITY: "duplicate_source"}
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        {"name": "Renamed", CONF_BATTERY_SOC_ENTITY: "sensor.replacement"},
    )
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert legacy.title == "Renamed"
    assert legacy.runtime_data.settings.entity_id == "sensor.replacement"
    assert legacy.runtime_data.settings.use_recorder
    assert (
        registry.async_get_entity_id(
            "sensor", DOMAIN, f"{legacy.entry_id}_battery_full_eta"
        )
        == entity_id
    )
    assert hass.states.get(entity_id).state == STATE_UNKNOWN
    assert hass.states.get(FULL).state == "off"


async def test_recorder_history_and_query_failure(
    async_test_recorder, hass, freezer, monkeypatch
):
    """Seed real Recorder data and fall back to live data on query failure."""
    freezer.move_to(NOW)
    async with async_test_recorder(hass):
        monkeypatch.setattr(
            "custom_components.sun_solar.coordinator.get_astral_event_date",
            lambda *_: NOW - timedelta(hours=2),
        )
        sun(hass)
        soc(hass, EAST, 60)
        soc(hass, WEST, 60)
        await async_wait_recording_done(hass)
        freezer.tick(timedelta(minutes=5))
        soc(hass, EAST, 70)
        soc(hass, WEST, 70)
        await async_wait_recording_done(hass)
        freezer.tick(timedelta(minutes=2))
        entry = await setup_battery(
            hass, EAST, "Recorder battery", options={"use_recorder": True}
        )
        assert entry.runtime_data.data.samples_in_window > 2
        assert entry.runtime_data.data.forecast.eta is not None

        def unavailable(*_args, **_kwargs):
            raise RuntimeError("Recorder query failed")

        monkeypatch.setattr(
            "homeassistant.components.recorder.history.get_significant_states",
            unavailable,
        )
        entry = await setup_battery(
            hass, WEST, "Fallback battery", options={"use_recorder": True}
        )
        assert entry.runtime_data.data.samples_in_window == 1
        assert display(hass) == "--:--"
        freezer.tick(timedelta(seconds=30))
        soc(hass, WEST, 71)
        await hass.async_block_till_done()
        assert entry.runtime_data.data.forecast.eta is not None


async def test_invalid_settings_block_aggregate(hass, freezer):
    """An enabled entry that cannot load prevents a misleading shared ETA."""
    freezer.move_to(NOW)
    sun(hass)
    soc(hass, EAST, 100)
    broken = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_BATTERY_SOC_ENTITY: WEST},
        options={"window_minutes": "nan"},
    )
    broken.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(broken.entry_id)
    await setup_battery(hass, EAST, "East")
    assert display(hass) == "--:--"
    assert hass.states.get(FULL).state == "off"
    await hass.config_entries.async_remove(broken.entry_id)
    await hass.async_block_till_done()
    assert display(hass) == "voll"


async def test_recorder_disabled_or_unavailable(hass, freezer):
    """Fall back to one live sample when Recorder is not installed."""
    freezer.move_to(NOW)
    sun(hass)
    soc(hass, EAST, 60)
    entry = await setup_battery(hass, EAST, "East", options={"use_recorder": True})
    assert entry.runtime_data.data.samples_in_window == 1
    assert display(hass) == "--:--"
    freezer.tick(timedelta(seconds=30))
    soc(hass, EAST, 61)
    await hass.async_block_till_done()
    assert entry.runtime_data.data.forecast.eta is not None


async def test_service_card_with_one_battery(hass, freezer):
    """Expose the configuration as a service and forecast with one battery."""
    freezer.move_to(NOW)
    sun(hass)
    soc(hass, EAST, 60)
    entry = await setup_battery(hass, EAST, "East")
    integration = await async_get_integration(hass, DOMAIN)
    assert integration.integration_type == "service"
    assert hass.config_entries.async_entries(DOMAIN) == [entry]

    freezer.tick(timedelta(seconds=30))
    soc(hass, EAST, 61)
    await hass.async_block_till_done()
    assert hass.states.get(ETA).state == "2026-11-27T12:19:45+00:00"
    assert hass.states.get(FULL).state == "off"

    soc(hass, EAST, 99.5)
    await hass.async_block_till_done()
    assert display(hass) == "voll"
    assert hass.states.get(FULL).state == "on"
