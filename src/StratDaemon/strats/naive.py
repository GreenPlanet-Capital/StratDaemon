from typing import List
from StratDaemon.integration.broker.base import BaseBroker
from StratDaemon.integration.confirmation.base import BaseConfirmation
from StratDaemon.integration.notification.base import BaseNotification
from StratDaemon.strats.base import BaseStrategy
from StratDaemon.models.crypto import CryptoHistorical, CryptoLimitOrder, CryptoOrder
from pandera.typing import DataFrame, Series


class NaiveStrategy(BaseStrategy):
    def __init__(
        self,
        broker: BaseBroker,
        notif: BaseNotification,
        conf: BaseConfirmation,
        paper_trade: bool = False,
        confirm_before_trade: bool = False,
    ) -> None:
        super().__init__(
            "naivety", broker, notif, conf, paper_trade, confirm_before_trade
        )

    def execute_buy_condition(
        self, df: DataFrame[CryptoHistorical], order: CryptoLimitOrder
    ) -> bool:
        return df.iloc[-1].close < order.limit_price

    def execute_sell_condition(
        self, df: DataFrame[CryptoHistorical], order: CryptoLimitOrder
    ) -> bool:
        return df.iloc[-1].close > order.limit_price
