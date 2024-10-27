from StratDaemon.integration.broker.base import BaseBroker
from StratDaemon.integration.confirmation.base import BaseConfirmation
from StratDaemon.integration.notification.base import BaseNotification
from StratDaemon.strats.base import BaseStrategy
from StratDaemon.models.crypto import CryptoHistorical, CryptoLimitOrder
from pandera.typing import DataFrame
import pandas_ta as ta
from StratDaemon.utils.constants import DEFAULT_INDICATOR_LENGTH


class RsiStrategy(BaseStrategy):
    def __init__(
        self,
        broker: BaseBroker,
        notif: BaseNotification,
        conf: BaseConfirmation,
        paper_trade: bool = False,
        confirm_before_trade: bool = False,
    ) -> None:
        super().__init__("rsi", broker, notif, conf, paper_trade, confirm_before_trade)

    def execute_buy_condition(
        self, df: DataFrame[CryptoHistorical], order: CryptoLimitOrder
    ) -> bool:
        return df.iloc[-1].close < order.limit_price and df.iloc[-1].rsi <= 30

    def execute_sell_condition(
        self, df: DataFrame[CryptoHistorical], order: CryptoLimitOrder
    ) -> bool:
        return df.iloc[-1].close > order.limit_price and df.iloc[-1].rsi >= 70

    def transform_df(
        self, df: DataFrame[CryptoHistorical]
    ) -> DataFrame[CryptoHistorical]:
        df["rsi"] = ta.rsi(df["close"], length=DEFAULT_INDICATOR_LENGTH)
        return df
