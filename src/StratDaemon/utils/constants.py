import configparser
import os

CONFIG_FILE = "config.ini" if os.getenv("ENV") != "dev" else "config_dev.ini"
cfg_parser = configparser.ConfigParser()
cfg_parser.read(CONFIG_FILE)

ROBINHOOD_EMAIL = cfg_parser.get("robinhood", "email")
ROBINHOOD_PASSWORD = cfg_parser.get("robinhood", "password")


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

POLL_INTERVAL_SEC = cfg_parser.getint(
    "confirmation", "polling_interval_sec", fallback=5
)
MAX_POLL_COUNT = cfg_parser.getint("confirmation", "max_poll_count", fallback=10)

RH_HISTORICAL_INTERVAL = "15second"
RH_HISTORICAL_SPAN = "hour"
RISK_FACTOR = 0.10

CRYPTO_CURRENCY_CODES = ["SHIB", "DOGE"]
CRYPTO_COMPARE_HISTORICAL_INTERVAL = "minute"
FIB_VALUES = [2.168, 2, 1.618, 1.382, 1, 0.618]
NUMERICAL_SPAN = 60 # number of data points to consider for the trend (use - RSI and Bollinger Bands for MA)
BUY_POWER = 250.0
WAIT_TIME = 30

DEFAULT_INDICATOR_LENGTH = 14 # RSI Window size for Moving average
PERCENT_DIFF_THRESHOLD = 0.01 # Threshold for percent difference between the current price and the Fib level
VOL_WINDOW_SIZE = 10 # Bollinger Bands window size for Moving average

RSI_BUY_THRESHOLD = 40
RSI_SELL_THRESHOLD = 60
RSI_PERCENT_INCR_THRESHOLD = 0.3
RSI_TREND_SPAN = 6 # Number of minutes window to check difference between RSI Values

MAX_HOLDING_PER_CURRENCY = 100.0

