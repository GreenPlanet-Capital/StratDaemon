from typing import List, Tuple
from StratDaemon.integration.broker.base import BaseBroker
from StratDaemon.integration.notification.base import BaseNotification
from StratDaemon.strats.base import BaseStrategy
from StratDaemon.models.crypto import CryptoHistorical, CryptoLimitOrder
from pandera.typing import DataFrame
from StratDaemon.utils.constants import (
    BUY_POWER,
    DEFAULT_INDICATOR_LENGTH,
    MAX_HOLDING_PER_CURRENCY,
    PERCENT_DIFF_THRESHOLD,
    RSI_BUY_THRESHOLD,
    RSI_PERCENT_INCR_THRESHOLD,
    RSI_SELL_THRESHOLD,
    RSI_TREND_SPAN,
    TRAILING_STOP_LOSS,
    TRAILING_TAKE_PROFIT,
    VOL_WINDOW_SIZE,
)
import pandas as pd
from StratDaemon.utils.funcs import percent_difference
from StratDaemon.utils.indicators import (
    add_boll_diff,
    add_fib_ret_lvls,
    add_rsi,
    add_super_trend,
    add_trends_upwards,
)

pd.options.mode.chained_assignment = None


class FibVolRsiStrategy(BaseStrategy):
    def __init__(
        self,
        broker: BaseBroker,
        notif: BaseNotification,
        currency_codes: List[str] = None,
        auto_generate_orders: bool = False,
        max_amount_per_order: float = 0.0,
        paper_trade: bool = False,
        percent_diff_threshold: float = PERCENT_DIFF_THRESHOLD,
        vol_window_size: int = VOL_WINDOW_SIZE,
        buy_power: float = BUY_POWER,
        max_holding_per_currency: float = MAX_HOLDING_PER_CURRENCY,
        indicator_length: int = DEFAULT_INDICATOR_LENGTH,
        rsi_buy_threshold: float = RSI_BUY_THRESHOLD,
        rsi_sell_threshold: float = RSI_SELL_THRESHOLD,
        rsi_percent_incr_threshold: float = RSI_PERCENT_INCR_THRESHOLD,
        rsi_trend_span: int = RSI_TREND_SPAN,
        trailing_stop_loss: float = TRAILING_STOP_LOSS,
        trailing_take_profit: float = TRAILING_TAKE_PROFIT,
    ) -> None:
        super().__init__(
            "fib_retracements_volatility_rsi",
            broker,
            notif,
            currency_codes,
            auto_generate_orders,
            max_amount_per_order,
            paper_trade,
            buy_power,
            trailing_stop_loss,
            trailing_take_profit,
            max_holding_per_currency,
        )
        self.percent_diff_threshold = percent_diff_threshold
        self.vol_window_size = vol_window_size
        self.rsi_buy_threshold = rsi_buy_threshold
        self.rsi_sell_threshold = rsi_sell_threshold
        self.rsi_percent_incr_threshold = rsi_percent_incr_threshold
        self.rsi_trend_span = rsi_trend_span
        self.percent_diff_threshold = percent_diff_threshold
        self.vol_window_size = vol_window_size
        self.indicator_length = indicator_length

    def is_within_p_thres(
        self,
        df: DataFrame[CryptoHistorical],
        indicator_value: float,
        percent_diff_threshold: float,
        indicator: str,
    ) -> bool:
        return (
            abs(percent_difference(df.iloc[-1][indicator], indicator_value))
            <= percent_diff_threshold
        )

    def is_indicator_increasing(
        self, df: DataFrame[CryptoHistorical], indicator: str
    ) -> bool:
        indicator_cur, indicator_prev = self.get_indicator_trend(df, indicator)
        return indicator_cur > indicator_prev

    def get_indicator_trend(
        self, df: DataFrame[CryptoHistorical], indicator: str
    ) -> Tuple[float, float]:
        assert (
            len(df) > self.vol_window_size
        ), f"Not enough data points to calculate indicator increase: DataFrame has {len(df)} but need more than {self.vol_window_size}"
        rolling_mean = df[indicator].rolling(window=self.vol_window_size).mean()
        return rolling_mean.iloc[-1], rolling_mean.iloc[-2]

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
        is_within_rsi_lvl = df.iloc[-1].rsi <= self.rsi_buy_threshold
        risk_signal = (
            is_within_fib_lvl and is_within_rsi_lvl and self.is_rsi_increasing(df)
        )
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

        is_within_rsi_lvl = df.iloc[-1].rsi >= self.rsi_sell_threshold
        risk_signal = is_within_rsi_lvl and self.is_rsi_decreasing(df)

        # if vol increasing, it's safe to sell but misses out on some opportunities
        # so use rsi to decide to take the risk and hold
        return confident_signal and self.is_rsi_decreasing(df), risk_signal

    def get_score(
        self, df: DataFrame[CryptoHistorical], order: CryptoLimitOrder
    ) -> float:
        sr = df.iloc[-1]
        return (
            (1 - abs(percent_difference(sr.close, order.limit_price)))
            + (
                1
                - abs(
                    percent_difference(
                        sr.rsi,
                        (
                            self.rsi_buy_threshold
                            if order.side == "buy"
                            else self.rsi_sell_threshold
                        ),
                    )
                )
            )
        ) / 2

    def transform_df(
        self, df: DataFrame[CryptoHistorical]
    ) -> DataFrame[CryptoHistorical]:
        df = add_boll_diff(df, self.indicator_length)
        df = add_super_trend(df, atr_length=14, multiplier=3)
        df = add_trends_upwards(df)
        df = add_fib_ret_lvls(df, df["trends_upwards"].iloc[-1])
        df = add_rsi(df, self.indicator_length)
        return df

    def get_auto_generated_orders(
        self, currency_code: str, df: DataFrame[CryptoHistorical]
    ) -> List[CryptoLimitOrder]:
        sr = df.iloc[-1]

        fib_vals = sorted(sr.filter(like="fib_").values)
        n = len(fib_vals)
        closest_idx = (fib_vals - sr.close).argmin()

        orders = [
            CryptoLimitOrder(
                side="sell",
                currency_code=currency_code,
                limit_price=fib_vals[min(closest_idx + 1, n - 1)],  # Resistance point
                amount=self.max_amount_per_order,
            ),
            CryptoLimitOrder(
                side="buy",
                currency_code=currency_code,
                limit_price=fib_vals[max(closest_idx - 1, 0)],  # Support point
                amount=self.max_amount_per_order,
            ),
        ]

        for order in orders:
            score = self.get_score(df, order)
            if str(score) == "nan":
                score = 0.5  # unsure of the score
            elif score < 0:
                score = 1e-6  # avoid negative scores
            order.amount *= score

        return orders
