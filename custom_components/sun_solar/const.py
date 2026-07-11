"""Constants for the Sun Solar integration."""
from __future__ import annotations

DOMAIN = "sun_solar"
DEFAULT_NAME = "Sun Solar"

CONF_POWER_ENTITY = "power_entity"
CONF_BATTERY_SOC_ENTITY = "battery_soc_entity"
CONF_BATTERY_REMAINING_ENTITY = "battery_remaining_entity"

# Rolling window used to average charging power, mirrors the 15-minute
# window used in the original Lovelace card.
AVERAGE_WINDOW_MINUTES = 15

# Below this average charging power (in Watt) an ETA is considered
# unreliable and is not reported.
MIN_POWER_FOR_ETA_W = 50

# SOC (%) at/above which the battery is treated as "full".
SOC_FULL_THRESHOLD = 99.5

# How often the coordinator samples the power entity and recalculates.
UPDATE_INTERVAL_SECONDS = 30

ATTR_AVERAGE_POWER_W = "average_power_w"
ATTR_REMAINING_TO_CHARGE_KWH = "remaining_to_charge_kwh"
ATTR_STATUS = "status"

STATUS_FULL = "full"
STATUS_CHARGING = "charging"
STATUS_NO_PRODUCTION = "no_production"
STATUS_UNAVAILABLE = "unavailable"
