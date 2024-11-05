from typing import Dict, List
from StratDaemon.integration.broker.base import BaseBroker
from StratDaemon.integration.confirmation.base import BaseConfirmation
from StratDaemon.integration.notification.base import BaseNotification
from StratDaemon.models.crypto import CryptoHistorical, CryptoLimitOrder, CryptoOrder
from pandera.typing import DataFrame, Series
from devtools import pprint
import time
from StratDaemon.utils.constants import (
    BUY_POWER,
    HISTORICAL_INTERVAL,
    HISTORICAL_SPAN,
    MAX_POLL_COUNT,
    POLL_INTERVAL_SEC,
    RISK_FACTOR,
)


class BaseStrategy:
    def __init__(
        self,
        name: str,
        broker: BaseBroker,
        notif: BaseNotification,
        conf: BaseConfirmation,
        currency_codes: List[str] = None,
        auto_generate_orders: bool = False,
        max_amount_per_order: float = 0.0,
        paper_trade: bool = False,
        confirm_before_trade: bool = False,
        risk_factor: float = RISK_FACTOR,
        buy_power: float = BUY_POWER,
    ) -> None:
        self.name = name
        self.broker = broker
        self.notif = notif
        self.conf = conf
        self.limit_orders: List[CryptoLimitOrder] = []
        self.currency_codes = currency_codes or []
        self.auto_generate_orders = auto_generate_orders
        self.max_amount_per_order = max_amount_per_order
        self.paper_trade = paper_trade
        self.confirm_before_trade = confirm_before_trade
        self.risk_factor = risk_factor
        self.buy_power = self.initial_buy_power = buy_power

    def add_limit_order(self, order: CryptoLimitOrder):
        if self.auto_generate_orders:
            print(
                "Auto-generating orders is enabled. It is recommended not to add limit orders manually."
            )
        self.limit_orders.append(order)

    def construct_dt_df(
        self, dt_dfs_input: Dict[str, DataFrame[CryptoHistorical]] | None
    ) -> Dict[str, DataFrame[CryptoHistorical]]:
        currency_codes = {order.currency_code for order in self.limit_orders}
        currency_codes.update(self.currency_codes)
        dt_dfs = dict()
        for currency_code in currency_codes:
            if dt_dfs_input is not None and currency_code in dt_dfs_input:
                df = dt_dfs_input[currency_code]
            else:
                df = self.broker.get_crypto_historical(
                    currency_code, HISTORICAL_INTERVAL, HISTORICAL_SPAN
                )
            df = self.transform_df(df)
            dt_dfs[currency_code] = df
        return dt_dfs

    def execute(
        self,
        dt_dfs_input: Dict[str, DataFrame[CryptoHistorical]] | None = None,
        print_orders: bool = True,
    ) -> List[CryptoOrder]:
        dt_dfs = self.construct_dt_df(dt_dfs_input)
        processed_orders = []

        orders_to_process = self.limit_orders.copy()

        if self.auto_generate_orders is True:
            for currency_code in self.currency_codes:
                orders_to_process.extend(
                    self.get_auto_generated_orders(currency_code, dt_dfs[currency_code])
                )

        for order in orders_to_process:
            df = dt_dfs[order.currency_code]
            most_recent_data: Series[CryptoHistorical] = df.iloc[-1]

            order = CryptoOrder(
                side=order.side,
                currency_code=order.currency_code,
                asset_price=most_recent_data.close,
                amount=order.amount,
                limit_price=order.limit_price,
                quantity=order.amount / most_recent_data.close,
                timestamp=most_recent_data.timestamp,
            )

            if getattr(self, f"execute_{order.side}_condition")(df, order):
                if self.confirm_before_trade:
                    if not self.send_notif_wait_for_conf(order):
                        print("Confirmation failed, skipping order.")
                        continue
                    print("Confirmation received, proceeding with order.")

                if (order.side == "buy" and self.buy_power >= order.amount) or (
                    order.side == "sell" and self.initial_buy_power > self.buy_power
                ):
                    self.buy_power += order.amount * (-1 if order.side == "buy" else 1)
                else:
                    # if print_orders:
                    print(f"Insufficient funds to execute {order.side} order.")
                    continue

                # if print_orders:
                print(f"Remaining buy power: {self.buy_power}")
                if self.paper_trade:
                    if print_orders:
                        print(f"Paper trading {order.side} order:")
                else:
                    if print_orders:
                        print(f"Executing live {order.side} order:")

                    processed_orders.append(
                        getattr(self.broker, f"{order.side}_crypto_market")(
                            order.currency_code, order.amount, most_recent_data
                        )
                    )
                if print_orders:
                    pprint(order)

        return processed_orders

    def send_notif_wait_for_conf(self, order: CryptoOrder) -> None:
        uid = self.notif.notify_order(order)
        is_confirmed = False

        try:
            self.conf.init_confirmation(uid)
            print(f"Waiting for confirmation for order with uid={uid}...")
            for _ in range(MAX_POLL_COUNT):
                time.sleep(POLL_INTERVAL_SEC)

                if is_confirmed := self.conf.check_confirmation(uid):
                    break
            self.conf.delete_confirmation(uid)
        except Exception as e:
            print(f"Error during confirmation: {e}")

        return is_confirmed

    def execute_buy_condition(
        self, df: DataFrame[CryptoHistorical], order: CryptoLimitOrder
    ) -> bool:
        raise NotImplementedError("This method should be overridden by subclasses")

    def execute_sell_condition(
        self, df: DataFrame[CryptoHistorical], order: CryptoLimitOrder
    ) -> bool:
        raise NotImplementedError("This method should be overridden by subclasses")

    def transform_df(
        self, df: DataFrame[CryptoHistorical]
    ) -> DataFrame[CryptoHistorical]:
        return df

    def get_auto_generated_orders(
        self, currency_code: str, df: DataFrame[CryptoHistorical]
    ) -> List[CryptoLimitOrder]:
        return []
