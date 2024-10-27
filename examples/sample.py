from StratDaemon.integration.broker.robinhood import RobinhoodBroker
from StratDaemon.strats.fib_vol import FibVolStrategy
from StratDaemon.integration.notification.sms import SMSNotification
from StratDaemon.integration.confirmation.crypto_db import CryptoDBConfirmation


integration = RobinhoodBroker()
notif = SMSNotification()
conf = CryptoDBConfirmation()

strat = FibVolStrategy(
    integration,
    notif,
    conf,
    currency_codes=["DOGE"],
    auto_generate_orders=True,
    max_amount_per_order=100,
    paper_trade=True,
    confirm_before_trade=False,
)
# strat.add_limit_order(
#     CryptoLimitOrder(
#         side="buy",
#         currency_code="BTC",
#         limit_price=60_000,
#         amount=1,
#     )
# )
orders = strat.execute()
