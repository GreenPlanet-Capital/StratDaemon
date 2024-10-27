from StratDaemon.integration.broker.robinhood import RobinhoodBroker
from StratDaemon.models.crypto import CryptoLimitOrder
from StratDaemon.strats.naive import NaiveStrategy
from StratDaemon.integration.notification.sms import SMSNotification
from StratDaemon.integration.confirmation.crypto_db import CryptoDBConfirmation


rh_integration = RobinhoodBroker()
notif = SMSNotification()
conf = CryptoDBConfirmation()
strat = NaiveStrategy(
    rh_integration, notif, conf, paper_trade=True, confirm_before_trade=True
)
strat.add_limit_order(
    CryptoLimitOrder(
        side="buy",
        currency_code="BTC",
        limit_price=70000,
        amount=1,
    )
)
orders = strat.execute()
