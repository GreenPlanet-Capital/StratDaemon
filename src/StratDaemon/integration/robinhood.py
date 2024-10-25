from datetime import datetime
from typing import Any, Dict, List
import pandas as pd
import robin_stocks.robinhood as r
from StratDaemon.integration.base import BaseIntegration
from StratDaemon.models.crypto import (
    CryptoAsset,
    CryptoHistorical,
    CryptoOrder,
)
from StratDaemon.utils.constants import ROBINHOOD_EMAIL, ROBINHOOD_PASSWORD


class RobinhoodIntegration(BaseIntegration):
    def __init__(self) -> None:
        super().__init__()

    def authenticate(self) -> None:
        # This is cached for the session
        r.login(
            username=ROBINHOOD_EMAIL,
            password=ROBINHOOD_PASSWORD,
        )

    def deauthenticate(self) -> None:
        r.logout()

    def get_crypto_positions(self) -> List[CryptoAsset]:
        orders = r.get_crypto_positions()
        return [
            CryptoAsset(
                currency_code=order["currency"]["code"],
                quantity=float(order["quantity"]),
                initial_cost_basis=float(order["cost_bases"][0]["direct_cost_basis"]),
                initial_quantity=float(order["cost_bases"][0]["direct_quantity"]),
                created_at=self.convert_rh_pos_dt_to_datetime(order["created_at"]),
                updated_at=self.convert_rh_pos_dt_to_datetime(order["updated_at"]),
            )
            for order in orders
        ]

    def get_crypto_historical(
        self, currency_code: str, interval: str, span: str
    ) -> CryptoHistorical:
        hist_data = r.get_crypto_historicals(
            currency_code, interval=interval, span=span
        )
        hist_data_parsed = [
            {
                "open": float(data["open_price"]),
                "close": float(data["close_price"]),
                "high": float(data["high_price"]),
                "low": float(data["low_price"]),
                "volume": float(data["volume"]),
                "timestamp": self.convert_rh_historical_dt_to_datetime(
                    data["begins_at"]
                ),
            }
            for data in hist_data
        ]
        df = pd.DataFrame(hist_data_parsed)
        return CryptoHistorical.validate(df)

    def buy_crypto_limit(
        self, currency_code: str, amount: float, limit_price: float
    ) -> CryptoOrder:
        return self.convert_order_to_obj(
            r.order_buy_crypto_limit_by_price(currency_code, amount, limit_price)
        )

    def buy_crypto_market(self, currency_code: str, amount: float) -> CryptoOrder:
        return self.convert_order_to_obj(
            r.order_buy_crypto_by_price(currency_code, amount)
        )

    def sell_crypto_limit(
        self, currency_code: str, amount: float, limit_price: float
    ) -> CryptoOrder:
        return self.convert_order_to_obj(
            r.order_sell_crypto_limit_by_price(currency_code, amount, limit_price)
        )

    def sell_crypto_market(self, currency_code: str, amount: float) -> CryptoOrder:
        return self.convert_order_to_obj(
            r.order_sell_crypto_by_price(currency_code, amount)
        )

    def convert_order_to_obj(self, order: Dict[str, Any]) -> CryptoOrder:
        return CryptoOrder(
            side=order["side"],
            currency_code=order["currency_code"],
            asset_price=float(order["price"]),
            amount=float(order["entered_price"]),
            limit_price=float(
                order["limit_price"] if order["limit_price"] is not None else -1
            ),
            quantity=float(order["quantity"]),
            timestamp=self.convert_rh_pos_dt_to_datetime(order["created_at"]),
        )

    def convert_rh_pos_dt_to_datetime(self, rh_dt: str) -> datetime:
        return datetime.strptime(rh_dt, "%Y-%m-%dT%H:%M:%S.%f%z")

    def convert_rh_historical_dt_to_datetime(self, rh_dt: str) -> datetime:
        return datetime.strptime(rh_dt, "%Y-%m-%dT%H:%M:%SZ")
