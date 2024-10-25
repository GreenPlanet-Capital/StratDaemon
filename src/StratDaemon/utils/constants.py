import configparser
import os

CONFIG_FILE = "config.ini" if os.getenv("ENV") != "dev" else "config_dev.ini"
cfg_parser = configparser.ConfigParser()
cfg_parser.read(CONFIG_FILE)

ROBINHOOD_EMAIL = cfg_parser.get("robinhood", "email")
ROBINHOOD_PASSWORD = cfg_parser.get("robinhood", "password")

HISTORICAL_INTERVAL = cfg_parser.get("general", "historical_interval")
HISTORICAL_SPAN = cfg_parser.get("general", "historical_span")
