from typing import List
from StratDaemon.integration.robinhood import RobinhoodIntegration
from StratDaemon.models.crypto import CryptoLimitOrder
from StratDaemon.utils.constants import HISTORICAL_INTERVAL, HISTORICAL_SPAN
from StratDaemon.strats.naive import NaiveStrategy

SAMPLE_CURRENCY_CODE = "BTC"

rh_integration = RobinhoodIntegration()
historical_data = rh_integration.get_crypto_historical(
    SAMPLE_CURRENCY_CODE, HISTORICAL_INTERVAL, HISTORICAL_SPAN
)

strat = NaiveStrategy("naivety", rh_integration, paper_trade=True)
strat.add_limit_order(
    CryptoLimitOrder(
        side="buy",
        currency_code=SAMPLE_CURRENCY_CODE,
        limit_price=70000,
        amount=1,
    )
)
orders = strat.execute(historical_data)
