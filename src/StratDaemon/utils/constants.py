import configparser
import os

CONFIG_FILE = "config.ini" if os.getenv("ENV") != "dev" else "config_dev.ini"
cfg_parser = configparser.ConfigParser()
cfg_parser.read(CONFIG_FILE)

ROBINHOOD_EMAIL = cfg_parser.get("robinhood", "email")
ROBINHOOD_PASSWORD = cfg_parser.get("robinhood", "password")

HISTORICAL_INTERVAL = cfg_parser.get("broker", "historical_interval")
HISTORICAL_SPAN = cfg_parser.get("broker", "historical_span")

CARRIER_MAP = {
    "verizon": "vtext.com",
    "tmobile": "tmomail.net",
    "sprint": "messaging.sprintpcs.com",
    "at&t": "txt.att.net",
    "boost": "smsmyboostmobile.com",
    "cricket": "sms.cricketwireless.net",
    "uscellular": "email.uscc.net",
}
PHONE_NUMBER = cfg_parser.get("sms", "phone_number")
CARRIER = cfg_parser.get("sms", "carrier").lower()

EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
GMAIL_EMAIL = cfg_parser.get("gmail", "email")
GMAIL_PASSWORD = cfg_parser.get("gmail", "password")

CRYPTO_COMPARE_API_KEY = cfg_parser.get("tests", "crypto_compare_api_key")

CRYPTO_DB_URL = "https://comerciohub.tech/api/crypto"

POLL_INTERVAL_SEC = cfg_parser.getint("confirmation", "polling_interval_sec")
MAX_POLL_COUNT = cfg_parser.getint("confirmation", "max_poll_count")

DEFAULT_INDICATOR_LENGTH = 14
FIB_VALUES = [2.168, 2, 1.618, 1.382, 1, 0.618]
PERCENT_DIFF_THRESHOLD = 0.05
VOL_WINDOW_SIZE = 5
