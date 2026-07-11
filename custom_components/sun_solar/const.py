"""Constants for the Sun Solar integration."""
from __future__ import annotations

DOMAIN = "sun_solar"
DEFAULT_NAME = "Sun Solar"

CONF_BATTERY_SOC_ENTITY = "battery_soc_entity"

# Window over which the SOC slope (%/Minute) is computed via lineare
# Regression, um einzelne verrauschte/quantisierte SOC-Sprünge zu glätten.
SOC_RATE_WINDOW_MINUTES = 15

# SOC (%) at/above which the battery is treated as "full".
SOC_FULL_THRESHOLD = 99.5

# Unterhalb dieser Steigung (%/Minute) gilt der Akku als "lädt nicht" -
# reine Rausch-/Mess-Jitter-Schwelle, kein physikalischer Wert.
# [Vermutung] Startwert, ggf. anpassen falls SOC-Sensor grob aufgelöst ist.
MIN_SOC_RATE_PERCENT_PER_MIN = 0.01

# How often the coordinator samples the SOC entity and recalculates.
UPDATE_INTERVAL_SECONDS = 30

ATTR_STATUS = "status"
ATTR_SOC_RATE_PERCENT_PER_HOUR = "soc_rate_percent_per_hour"
ATTR_SAMPLES_IN_WINDOW = "samples_in_window"

STATUS_FULL = "full"
STATUS_CHARGING = "charging"
STATUS_NOT_CHARGING = "not_charging"
STATUS_UNAVAILABLE = "unavailable"
