from StratDaemon.integration.broker.alpaca import AlpacaBroker
from StratDaemon.integration.broker.crypto_compare import CryptoCompareBroker
from StratDaemon.integration.broker.robinhood import RobinhoodBroker
from StratDaemon.utils.constants import CRYPTO_CURRENCY_CODES
import time

broker = AlpacaBroker()

for crypto in CRYPTO_CURRENCY_CODES:
    print(f"Pulling historical data for {crypto}...")
    df = broker.get_crypto_historical(
        crypto, "minute", pull_from_api=True, is_backtest=True
    )
    df = df.sort_values("timestamp", ascending=True)
    df.to_json(f"alpaca_{crypto}_historical_data.json")

    # time.sleep(30)
