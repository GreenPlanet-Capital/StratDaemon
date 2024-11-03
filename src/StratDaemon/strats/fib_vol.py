from typing import List
from StratDaemon.integration.broker.base import BaseBroker
from StratDaemon.integration.confirmation.base import BaseConfirmation
from StratDaemon.integration.notification.base import BaseNotification
from StratDaemon.strats.base import BaseStrategy
from StratDaemon.models.crypto import CryptoHistorical, CryptoLimitOrder
from pandera.typing import DataFrame
from StratDaemon.utils.constants import (
    DEFAULT_INDICATOR_LENGTH,
    PERCENT_DIFF_THRESHOLD,
    VOL_WINDOW_SIZE,
)
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
    ) -> None:
        super().__init__(
            "fib_retracements_volatility",
            broker,
            notif,
            conf,
            currency_codes,
            auto_generate_orders,
            max_amount_per_order,
            paper_trade,
            confirm_before_trade,
        )

    def is_within_p_thres(
        self, df: DataFrame[CryptoHistorical], order: CryptoLimitOrder
    ) -> bool:
        return (
            abs(percent_difference(df.iloc[-1].close, order.limit_price))
            <= PERCENT_DIFF_THRESHOLD
        )

    def is_vol_increasing(self, df: DataFrame[CryptoHistorical]) -> bool:
        return (
            df["close"].rolling(window=VOL_WINDOW_SIZE).mean().iloc[-1]
            > df["close"].rolling(window=VOL_WINDOW_SIZE).mean().iloc[-2]
        )

    def execute_buy_condition(
        self, df: DataFrame[CryptoHistorical], order: CryptoLimitOrder
    ) -> bool:
        return self.is_within_p_thres(df, order) and not self.is_vol_increasing(df)

    def execute_sell_condition(
        self, df: DataFrame[CryptoHistorical], order: CryptoLimitOrder
    ) -> bool:
        return self.is_within_p_thres(df, order) and self.is_vol_increasing(df)

    def transform_df(
        self, df: DataFrame[CryptoHistorical]
    ) -> DataFrame[CryptoHistorical]:
        df = add_boll_diff(df, DEFAULT_INDICATOR_LENGTH)
        df = add_trends_upwards(df)
        df = add_fib_ret_lvls(df, df["trends_upwards"].iloc[-1])
        return df

    def get_auto_generated_orders(
        self, currency_code: str, df: DataFrame[CryptoHistorical]
    ) -> List[CryptoLimitOrder]:
        sr = df.iloc[-1]

        fib_vals = sorted(sr.filter(like="fib_").values)
        n = len(fib_vals)
        closest_idx = (fib_vals - sr.close).argmin()

        orders = []
        if sr.trends_upwards:
            orders.append(
                CryptoLimitOrder(
                    side="sell",
                    currency_code=currency_code,
                    limit_price=fib_vals[min(closest_idx + 1, n - 1)],
                    amount=self.max_amount_per_order,
                )
            )
        else:
            orders.append(
                CryptoLimitOrder(
                    side="buy",
                    currency_code=currency_code,
                    limit_price=fib_vals[max(closest_idx - 1, 0)],
                    amount=self.max_amount_per_order,
                )
            )

        return orders
