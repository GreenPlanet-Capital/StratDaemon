import configparser
import os

CONFIG_FILE = "config_dev.ini"
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

DB_USER = cfg_parser.get("db", "user")
DB_PASSWORD = cfg_parser.get("db", "password")
OPTUNA_DB_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@localhost:5432/optuna"

RH_HISTORICAL_INTERVAL = "15second"
RH_HISTORICAL_SPAN = "hour"
CRYPTO_COMPARE_HISTORICAL_INTERVAL = "minute"

RESTART_WAIT_TIME = 45 * 60  # Time to wait before restarting the daemon (in seconds)

CRYPTO_CURRENCY_CODES = ["SHIB", "DOGE"]
FIB_VALUES = [2.168, 2, 1.618, 1.382, 1, 0.618]

BUY_POWER = 250.0
MAX_HOLDING_PER_CURRENCY = 100.0

NUMERICAL_SPAN = 50  # number of data points to consider for the trend (use - RSI and Bollinger Bands for MA)
WAIT_TIME = 45  # Time to wait before next iteration (in minutes)
HEALTH_CHECK_WAIT_TIME = 5  # Time to wait before health check (in minutes)

DEFAULT_INDICATOR_LENGTH = 20  # RSI Window size for Moving average
VOL_WINDOW_SIZE = 18  # Bollinger Bands window size for Moving average
PERCENT_DIFF_THRESHOLD = 0.02  # Threshold for percent difference between the current price and the closest Fib level

RSI_BUY_THRESHOLD = 55
RSI_SELL_THRESHOLD = 80
RSI_PERCENT_INCR_THRESHOLD = 0.1
RSI_TREND_SPAN = 5  # Number of minutes window to check difference between RSI Values

TRAILING_STOP_LOSS = 0.05
TRAILING_TAKE_PROFIT = 0.10
