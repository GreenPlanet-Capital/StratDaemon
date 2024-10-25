from typing import List
from StratDaemon.integration.base import BaseIntegration
from StratDaemon.models.crypto import CryptoHistorical, CryptoLimitOrder, CryptoOrder
from pandera.typing import DataFrame, Series
from devtools import pprint


class BaseStrategy:
    def __init__(
        self, name: str, integration: BaseIntegration, paper_trade: bool = False
    ) -> None:
        self.name = name
        self.integration = integration
        self.limit_orders: List[CryptoLimitOrder] = []
        self.paper_trade = paper_trade

    def add_limit_order(self, order: CryptoLimitOrder):
        self.limit_orders.append(order)

    def execute(self, df: DataFrame[CryptoHistorical]) -> List[CryptoOrder]:
        most_recent_data: Series[CryptoHistorical] = df.iloc[-1]
        orders = []

        for order in self.limit_orders:
            order = CryptoOrder(
                side=order.side,
                currency_code=order.currency_code,
                asset_price=most_recent_data.close,
                amount=order.amount,
                limit_price=order.limit_price,
                quantity=most_recent_data.close / order.limit_price,
                timestamp=most_recent_data.timestamp,
            )

            match order.side:
                case "buy":
                    if self.execute_buy_condition(df, order):
                        if self.paper_trade:
                            print(f"Paper trading buy order:")
                        else:
                            pprint(f"Executing buy order:")
                            orders.append(
                                self.integration.buy_crypto_market(
                                    order.currency_code, order.amount
                                )
                            )
                        pprint(order)
                case "sell":
                    if self.execute_sell_condition(df, order):
                        if self.paper_trade:
                            print(f"Paper trading sell order:")
                        else:
                            print(f"Executing sell order:")
                            orders.append(
                                self.integration.sell_crypto_market(
                                    order.currency_code, order.amount
                                )
                            )
                        pprint(order)

        return orders

    def execute_buy_condition(
        self, df: DataFrame[CryptoHistorical], order: CryptoLimitOrder
    ) -> bool:
        raise NotImplementedError("This method should be overridden by subclasses")

    def execute_sell_condition(
        self, df: DataFrame[CryptoHistorical], order: CryptoLimitOrder
    ) -> bool:
        raise NotImplementedError("This method should be overridden by subclasses")
