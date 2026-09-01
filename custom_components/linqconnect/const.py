"""Constants for the LINQ Connect Menus integration."""

from datetime import timedelta

DOMAIN = "linqconnect"

API_BASE = "https://api.linqconnect.com/api"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

CONF_SHARE_CODE = "share_code"
CONF_DISTRICT_NAME = "district_name"
CONF_DISTRICT_ID = "district_id"
CONF_IDENTIFIER = "identifier"
CONF_BUILDINGS = "buildings"
CONF_SESSIONS = "sessions"
CONF_ROLLOVER_TIME = "rollover_time"

DEFAULT_ROLLOVER_TIME = "13:00:00"
DEFAULT_SESSIONS = ["Lunch"]
SESSION_CHOICES = ["Breakfast", "Lunch", "Snack", "Dinner"]

UPDATE_INTERVAL = timedelta(hours=6)
FETCH_WINDOW_DAYS = 42

MANUFACTURER = "LINQ"
MODEL = "School menu"
