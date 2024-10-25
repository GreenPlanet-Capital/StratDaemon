from typing import List
from StratDaemon.integration.base import BaseIntegration
from StratDaemon.strats.base import BaseStrategy
from StratDaemon.models.crypto import CryptoHistorical, CryptoLimitOrder, CryptoOrder
from pandera.typing import DataFrame, Series


class NaiveStrategy(BaseStrategy):
    def __init__(
        self, name: str, integration: BaseIntegration, paper_trade: bool = False
    ) -> None:
        super().__init__(name, integration, paper_trade)

    def execute_buy_condition(
        self, df: DataFrame[CryptoHistorical], order: CryptoLimitOrder
    ) -> bool:
        return df.iloc[-1].close < order.limit_price

    def execute_sell_condition(
        self, df: DataFrame[CryptoHistorical], order: CryptoLimitOrder
    ) -> bool:
        return df.iloc[-1].close > order.limit_price
