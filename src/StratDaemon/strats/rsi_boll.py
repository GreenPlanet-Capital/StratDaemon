from StratDaemon.integration.broker.base import BaseBroker
from StratDaemon.integration.confirmation.base import BaseConfirmation
from StratDaemon.integration.notification.base import BaseNotification
from StratDaemon.strats.base import BaseStrategy
from StratDaemon.models.crypto import CryptoHistorical, CryptoLimitOrder
from pandera.typing import DataFrame
import pandas_ta as ta
from StratDaemon.utils.constants import DEFAULT_INDICATOR_LENGTH
from StratDaemon.utils.funcs import normalize_values
import pandas as pd

pd.options.mode.chained_assignment = None


class RsiBollStrategy(BaseStrategy):
    def __init__(
        self,
        broker: BaseBroker,
        notif: BaseNotification,
        conf: BaseConfirmation,
        paper_trade: bool = False,
        confirm_before_trade: bool = False,
    ) -> None:
        super().__init__(
            "rsi_bollinger", broker, notif, conf, paper_trade, confirm_before_trade
        )

    def execute_buy_condition(
        self, df: DataFrame[CryptoHistorical], order: CryptoLimitOrder
    ) -> bool:
        return (
            df.iloc[-1].close < order.limit_price
            and df.iloc[-1].rsi <= 30
            and df.iloc[-1].boll_diff <= 0.5
        )

    def execute_sell_condition(
        self, df: DataFrame[CryptoHistorical], order: CryptoLimitOrder
    ) -> bool:
        return (
            df.iloc[-1].close > order.limit_price
            and df.iloc[-1].rsi >= 70
            and df.iloc[-1].boll_diff <= 0.5
        )

    def transform_df(
        self, df: DataFrame[CryptoHistorical]
    ) -> DataFrame[CryptoHistorical]:
        df["rsi"] = ta.rsi(df["close"], length=DEFAULT_INDICATOR_LENGTH)
        boll = ta.bbands(df["close"], length=DEFAULT_INDICATOR_LENGTH)

        df["boll_diff"] = boll[f"BBU_14_2.0"] - boll["BBL_14_2.0"]
        df = df.dropna()
        df["boll_diff"] = normalize_values(df["boll_diff"], 0, 1)

        return df
