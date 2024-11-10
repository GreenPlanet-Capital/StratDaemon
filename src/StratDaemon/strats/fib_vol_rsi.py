from typing import List
from StratDaemon.integration.broker.base import BaseBroker
from StratDaemon.integration.confirmation.base import BaseConfirmation
from StratDaemon.integration.notification.base import BaseNotification
from StratDaemon.strats.fib_vol import FibVolStrategy
from StratDaemon.models.crypto import CryptoHistorical, CryptoLimitOrder
from pandera.typing import DataFrame
from StratDaemon.utils.constants import (
    BUY_POWER,
    DEFAULT_INDICATOR_LENGTH,
    MAX_HOLDING_PER_CURRENCY,
    PERCENT_DIFF_THRESHOLD,
    RISK_FACTOR,
    RSI_BUY_THRESHOLD,
    RSI_SELL_THRESHOLD,
    VOL_WINDOW_SIZE,
)
import pandas as pd
from StratDaemon.utils.indicators import (
    add_rsi,
)

pd.options.mode.chained_assignment = None


class FibVolRsiStrategy(FibVolStrategy):
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
        percent_diff_threshold: float = PERCENT_DIFF_THRESHOLD,
        vol_window_size: int = VOL_WINDOW_SIZE,
        risk_factor: float = RISK_FACTOR,
        buy_power: float = BUY_POWER,
        max_holding_per_currency: float = MAX_HOLDING_PER_CURRENCY,
        rsi_buy_threshold: float = RSI_BUY_THRESHOLD,
        rsi_sell_threshold: float = RSI_SELL_THRESHOLD,
    ) -> None:
        super().__init__(
            broker,
            notif,
            conf,
            currency_codes,
            auto_generate_orders,
            max_amount_per_order,
            paper_trade,
            confirm_before_trade,
            percent_diff_threshold,
            vol_window_size,
            risk_factor,
            buy_power,
            max_holding_per_currency,
            "fib_retracements_volatility_rsi",
        )
        self.percent_diff_threshold = percent_diff_threshold
        self.vol_window_size = vol_window_size
        self.rsi_buy_threshold = rsi_buy_threshold
        self.rsi_sell_threshold = rsi_sell_threshold

    def execute_buy_condition(
        self, df: DataFrame[CryptoHistorical], order: CryptoLimitOrder
    ) -> bool:
        confident_signal = self.is_within_p_thres(
            df, order, self.percent_diff_threshold
        ) and not self.is_vol_increasing(df)
        # if vol is increasing, it's risky to buy since it could be either resistance or breakthrough
        risk_signal = (
            df.iloc[-1].rsi
            > self.rsi_buy_threshold  # RSI above 50 indicates bullish trend
            and self.is_within_p_thres(df, order, self.percent_diff_threshold)
            and self.is_vol_increasing(df)
        )
        return confident_signal or risk_signal

    def execute_sell_condition(
        self, df: DataFrame[CryptoHistorical], order: CryptoLimitOrder
    ) -> bool:
        confident_signal = self.is_within_p_thres(
            df, order, self.percent_diff_threshold
        ) and self.is_vol_increasing(df)
        # if vol increasing, it's safe to sell but misses out on some opportunities
        # so use rsi to decide to take the risk and hold
        return (
            confident_signal and df.iloc[-1].rsi < self.rsi_sell_threshold
        )  # RSI below 50 indicates bearish trend

    def transform_df(
        self, df: DataFrame[CryptoHistorical]
    ) -> DataFrame[CryptoHistorical]:
        df = super().transform_df(df)
        df = add_rsi(df, DEFAULT_INDICATOR_LENGTH)
        return df
