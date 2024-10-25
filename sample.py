from typing import List
from StratDaemon.integration.robinhood import RobinhoodIntegration
from StratDaemon.models.crypto import CryptoAsset, CryptoHistorical
from StratDaemon.utils.constants import HISTORICAL_INTERVAL, HISTORICAL_SPAN

SAMPLE_CURRENCY_CODE = "BTC"

rh_integration = RobinhoodIntegration()
# positions: List[CryptoAsset] = rh_integration.get_crypto_positions()

historical_data: CryptoHistorical = rh_integration.get_crypto_historical(
    SAMPLE_CURRENCY_CODE, HISTORICAL_INTERVAL, HISTORICAL_SPAN
)

# order_buy = rh_integration.buy_crypto_market(SAMPLE_CURRENCY_CODE, 1)
# order_sell = rh_integration.sell_crypto_market(SAMPLE_CURRENCY_CODE, 1)
