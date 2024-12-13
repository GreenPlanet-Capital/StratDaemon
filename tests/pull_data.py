from StratDaemon.integration.broker.alpaca import AlpacaBroker
from StratDaemon.utils.constants import CRYPTO_CURRENCY_CODES


broker = AlpacaBroker()

for crypto in CRYPTO_CURRENCY_CODES:
    print(f"Pulling historical data for {crypto}...")
    broker.get_crypto_historical(crypto, "minute", pull_from_api=True, is_backtest=True)
