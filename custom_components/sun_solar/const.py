"""Constants for the Sun Solar integration."""

DOMAIN = "sun_solar"
DEFAULT_NAME = "Sun Solar"

CONF_BATTERY_SOC_ENTITY = "battery_soc_entity"
CONF_WINDOW_MINUTES = "window_minutes"
CONF_FULL_THRESHOLD = "full_threshold"
CONF_USE_RECORDER = "use_recorder"

SUN_ENTITY_ID = "sun.sun"
SOC_RATE_WINDOW_MINUTES = 15
SOC_FULL_THRESHOLD = 99.5
UPDATE_INTERVAL_SECONDS = 30
MIN_WINDOW_MINUTES = 2
MAX_WINDOW_MINUTES = 120

ATTR_STATUS = "status"
ATTR_SOC_RATE_PERCENT_PER_HOUR = "soc_rate_percent_per_hour"
ATTR_SAMPLES_IN_WINDOW = "samples_in_window"
ATTR_ETA_DISPLAY = "eta_display"
DISPLAY_TEXT_FULL = "voll"
DISPLAY_TEXT_UNKNOWN = "--:--"
