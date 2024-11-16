from typing import List, Tuple
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
    RSI_PERCENT_INCR_THRESHOLD,
    RSI_SELL_THRESHOLD,
    RSI_TREND_SPAN,
    VOL_WINDOW_SIZE,
)
import pandas as pd
from StratDaemon.utils.funcs import percent_difference
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
        indicator_length: int = DEFAULT_INDICATOR_LENGTH,
        rsi_buy_threshold: float = RSI_BUY_THRESHOLD,
        rsi_sell_threshold: float = RSI_SELL_THRESHOLD,
        rsi_percent_incr_threshold: float = RSI_PERCENT_INCR_THRESHOLD,
        rsi_trend_span: int = RSI_TREND_SPAN,
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
            indicator_length,
            "fib_retracements_volatility_rsi",
        )
        self.percent_diff_threshold = percent_diff_threshold
        self.vol_window_size = vol_window_size
        self.rsi_buy_threshold = rsi_buy_threshold
        self.rsi_sell_threshold = rsi_sell_threshold
        self.rsi_percent_incr_threshold = rsi_percent_incr_threshold
        self.rsi_trend_span = rsi_trend_span

    def rsi_percent_change(self, df: DataFrame[CryptoHistorical]) -> float:
        assert df.index[0] == 0, "Index must be 0-based"
        rsi = df.rsi
        rsi_prev_idx = max(rsi.first_valid_index(), len(rsi) - self.rsi_trend_span)
        rsi_cur, rsi_prev = rsi.iloc[-1], rsi.loc[rsi_prev_idx]
        return percent_difference(rsi_cur, rsi_prev)

    def is_rsi_increasing(self, df: DataFrame[CryptoHistorical]) -> bool:
        return self.rsi_percent_change(df) >= self.rsi_percent_incr_threshold

    def is_rsi_decreasing(self, df: DataFrame[CryptoHistorical]) -> bool:
        return self.rsi_percent_change(df) <= -self.rsi_percent_incr_threshold

    def execute_buy_condition(
        self, df: DataFrame[CryptoHistorical], order: CryptoLimitOrder
    ) -> Tuple[bool, bool]:
        is_within_fib_lvl = self.is_within_p_thres(
            df, order.limit_price, self.percent_diff_threshold, "close"
        )
        is_vol_increasing = self.is_indicator_increasing(df, "boll_diff")

        confident_signal = (
            is_within_fib_lvl and not is_vol_increasing
        )  # stabilizing at support

        # if vol is increasing, it's risky to buy since it could be either resistance or breakthrough
        is_within_rsi_lvl = df.iloc[-1].rsi < self.rsi_buy_threshold
        risk_signal = (
            is_within_fib_lvl and is_vol_increasing and is_within_rsi_lvl
        )  # or is_rsi_increasing
        return confident_signal or self.is_rsi_increasing(df), risk_signal

    def execute_sell_condition(
        self, df: DataFrame[CryptoHistorical], order: CryptoLimitOrder
    ) -> Tuple[bool, bool]:
        is_within_fib_lvl = self.is_within_p_thres(
            df, order.limit_price, self.percent_diff_threshold, "close"
        )
        is_vol_increasing = self.is_indicator_increasing(df, "boll_diff")
        confident_signal = (
            is_within_fib_lvl and is_vol_increasing
        )  # trying to break resistance

        is_within_rsi_lvl = df.iloc[-1].rsi > self.rsi_sell_threshold
        is_rsi_increasing = self.is_indicator_increasing(df, "rsi")
        risk_signal = is_within_rsi_lvl and not is_rsi_increasing

        # if vol increasing, it's safe to sell but misses out on some opportunities
        # so use rsi to decide to take the risk and hold
        return confident_signal and self.is_rsi_decreasing(df), risk_signal

    def get_score(
        self, df: DataFrame[CryptoHistorical], order: CryptoLimitOrder
    ) -> float:
        sr = df.iloc[-1]
        return (1 - percent_difference(sr.close, order.limit_price)) + (
            1
            - abs(
                sr.rsi
                - (
                    self.rsi_buy_threshold
                    if order.side == "buy"
                    else self.rsi_sell_threshold
                )
            )
        )

    def transform_df(
        self, df: DataFrame[CryptoHistorical]
    ) -> DataFrame[CryptoHistorical]:
        df = super().transform_df(df)
        df = add_rsi(df, self.indicator_length)
        return df
