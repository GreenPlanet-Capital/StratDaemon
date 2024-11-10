from typing import List
from StratDaemon.integration.broker.base import BaseBroker
from StratDaemon.integration.confirmation.base import BaseConfirmation
from StratDaemon.integration.notification.base import BaseNotification
from StratDaemon.strats.base import BaseStrategy
from StratDaemon.models.crypto import CryptoHistorical, CryptoLimitOrder
from pandera.typing import DataFrame
from StratDaemon.utils.constants import (
    BUY_POWER,
    DEFAULT_INDICATOR_LENGTH,
    MAX_HOLDING_PER_CURRENCY,
    PERCENT_DIFF_THRESHOLD,
    RISK_FACTOR,
    VOL_WINDOW_SIZE,
)
import random
import pandas as pd
from StratDaemon.utils.funcs import percent_difference
from StratDaemon.utils.indicators import (
    add_boll_diff,
    add_fib_ret_lvls,
    add_trends_upwards,
)

pd.options.mode.chained_assignment = None


class FibVolStrategy(BaseStrategy):
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
        name_override: str = None,
        **kwargs,
    ) -> None:
        super().__init__(
            name_override or "fib_retracements_volatility",
            broker,
            notif,
            conf,
            currency_codes,
            auto_generate_orders,
            max_amount_per_order,
            paper_trade,
            confirm_before_trade,
            risk_factor,
            buy_power,
            max_holding_per_currency,
        )
        self.percent_diff_threshold = percent_diff_threshold
        self.vol_window_size = vol_window_size
        self.indicator_length = indicator_length
        self.random_number = None

    def update_random_number(self):
        self.random_number = random.random()

    def is_within_p_thres(
        self,
        df: DataFrame[CryptoHistorical],
        order: CryptoLimitOrder,
        percent_diff_threshold: float,
    ) -> bool:
        return (
            abs(percent_difference(df.iloc[-1].close, order.limit_price))
            <= percent_diff_threshold
        )

    def is_vol_increasing(self, df: DataFrame[CryptoHistorical]) -> bool:
        return (
            df["boll_diff"].rolling(window=self.vol_window_size).mean().iloc[-1]
            > df["boll_diff"].rolling(window=self.vol_window_size).mean().iloc[-2]
        )

    def execute_buy_condition(
        self, df: DataFrame[CryptoHistorical], order: CryptoLimitOrder
    ) -> bool:
        confident_signal = self.is_within_p_thres(
            df, order, self.percent_diff_threshold
        ) and not self.is_vol_increasing(df)
        # if vol is increasing, it's risky to buy since it could be either resistance or breakthrough
        risk_signal = (
            self.random_number <= self.risk_factor
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
        # so randomly decide to take the risk and hold
        return confident_signal and self.random_number > self.risk_factor

    def transform_df(
        self, df: DataFrame[CryptoHistorical]
    ) -> DataFrame[CryptoHistorical]:
        df = add_boll_diff(df, self.indicator_length)
        df = add_trends_upwards(df)
        df = add_fib_ret_lvls(df, df["trends_upwards"].iloc[-1])
        return df

    def get_auto_generated_orders(
        self, currency_code: str, df: DataFrame[CryptoHistorical]
    ) -> List[CryptoLimitOrder]:
        self.update_random_number()
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

        return orders
