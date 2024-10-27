from typing import Dict, List
from StratDaemon.integration.broker.base import BaseBroker
from StratDaemon.integration.confirmation.base import BaseConfirmation
from StratDaemon.integration.notification.base import BaseNotification
from StratDaemon.models.crypto import CryptoHistorical, CryptoLimitOrder, CryptoOrder
from pandera.typing import DataFrame, Series
from devtools import pprint
import time
from StratDaemon.utils.constants import (
    HISTORICAL_INTERVAL,
    HISTORICAL_SPAN,
    MAX_POLL_COUNT,
    POLL_INTERVAL_SEC,
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

    def add_limit_order(self, order: CryptoLimitOrder):
        if self.auto_generate_orders:
            print(
                "Auto-generating orders is enabled. It is recommended not to add limit orders manually."
            )
        self.limit_orders.append(order)

    def construct_dt_df(self) -> Dict[str, DataFrame[CryptoHistorical]]:
        currency_codes = {order.currency_code for order in self.limit_orders}
        currency_codes.update(self.currency_codes)
        dt_dfs = dict()
        for currency_code in currency_codes:
            df = self.broker.get_crypto_historical(
                currency_code, HISTORICAL_INTERVAL, HISTORICAL_SPAN
            )
            df = self.transform_df(df)
            dt_dfs[currency_code] = df
        return dt_dfs

    def execute(self) -> List[CryptoOrder]:
        dt_dfs = self.construct_dt_df()
        processed_orders = []

        orders_to_process = self.limit_orders.copy()

        if self.auto_generate_orders is True:
            for currency_code in self.currency_codes:
                orders_to_process.extend(
                    self.get_auto_generated_orders(currency_code, dt_dfs[currency_code])
                )

        for order in self.limit_orders:
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

                if self.paper_trade:
                    print(f"Paper trading {order.side} order:")
                else:
                    print(f"Executing live {order.side} order:")
                    processed_orders.append(
                        self.broker.buy_crypto_market(order.currency_code, order.amount)
                    )
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
