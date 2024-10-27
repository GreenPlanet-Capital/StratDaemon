from typing import List
from StratDaemon.integration.broker.base import BaseBroker
from StratDaemon.integration.confirmation.base import BaseConfirmation
from StratDaemon.integration.notification.base import BaseNotification
from StratDaemon.strats.base import BaseStrategy
from StratDaemon.models.crypto import CryptoHistorical, CryptoLimitOrder
from pandera.typing import DataFrame
from StratDaemon.utils.constants import DEFAULT_INDICATOR_LENGTH
import pandas as pd
from StratDaemon.utils.indicators import add_boll_diff, add_rsi

pd.options.mode.chained_assignment = None


class RsiBollStrategy(BaseStrategy):
    def __init__(
        self,
        broker: BaseBroker,
        notif: BaseNotification,
        conf: BaseConfirmation,
        currency_codes: List[str] = None,
        auto_generate_orders: bool = False,
        max_amount_per_order: float = 0.0,
        paper_trade: bool = False,
        confirm_before_trade: bool = False,
    ) -> None:
        super().__init__(
            "rsi_bollinger",
            broker,
            notif,
            conf,
            currency_codes,
            auto_generate_orders,
            max_amount_per_order,
            paper_trade,
            confirm_before_trade,
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
        df = add_boll_diff(df, DEFAULT_INDICATOR_LENGTH)
        df = add_rsi(df, DEFAULT_INDICATOR_LENGTH)
        return df
