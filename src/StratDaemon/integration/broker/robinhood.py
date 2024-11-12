from datetime import datetime
import time
from typing import Any, Dict, List
import pandas as pd
from StratDaemon.integration.broker.utils import (
    ExceptionType,
    BrokerException,
    retry_function,
)
import robin_stocks.robinhood as r
from StratDaemon.integration.broker.base import BaseBroker
from StratDaemon.integration.broker.crypto_compare import CryptoCompareBroker
from StratDaemon.models.crypto import (
    CryptoAsset,
    CryptoHistorical,
    CryptoOrder,
)
from StratDaemon.utils.constants import (
    CRYPTO_COMPARE_HISTORICAL_INTERVAL,
    NUMERICAL_SPAN,
    ROBINHOOD_EMAIL,
    ROBINHOOD_PASSWORD,
)
from pandera.typing import DataFrame, Series
import traceback


class RobinhoodBroker(BaseBroker):
    def __init__(self) -> None:
        super().__init__()
        self.fallback_broker = CryptoCompareBroker()

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

    def get_crypto_latest(self, currency_code: str) -> Dict[str, Any]:
        cur_data = r.get_crypto_quote(currency_code)
        return {
            "open": float(cur_data["open_price"]),
            "high": float(cur_data["high_price"]),
            "close": float(cur_data["mark_price"]),
            "low": float(cur_data["low_price"]),
            "volume": float(cur_data["volume"]),
            "timestamp": datetime.now(),
        }

    @retry_function(max_retries=2, wait_time=2)
    def get_crypto_historical(
        self, currency_code: str, interval: str, span: str
    ) -> DataFrame[CryptoHistorical]:
        try:
            hist_data = r.get_crypto_historicals(
                currency_code, interval=interval, span=span
            )
        except Exception as _:
            print(
                f"Error encountered while pulling data from RH: {traceback.format_exc()}"
            )
            print("Falling back to CryptoCompare API.")
            df = self.fallback_broker.get_crypto_historical(
                currency_code,
                CRYPTO_COMPARE_HISTORICAL_INTERVAL,
                pull_from_api=True,
                is_backtest=False,
            )
        else:
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
            hist_data_parsed.append(self.get_crypto_latest(currency_code))
            df = pd.DataFrame(hist_data_parsed)
        df = self.convert_to_backtest_compatible(df)
        return CryptoHistorical.validate(df)

    def convert_to_backtest_compatible(
        self,
        df: DataFrame[CryptoHistorical],
    ) -> DataFrame[CryptoHistorical]:
        df = df[df["timestamp"].dt.second == 0]
        return df.iloc[len(df) - NUMERICAL_SPAN :]

    def buy_crypto_limit(
        self, currency_code: str, amount: float, limit_price: float
    ) -> CryptoOrder:
        return self.wait_for_order_conf_and_convert(
            r.order_buy_crypto_limit_by_price(currency_code, amount, limit_price)
        )

    def sell_crypto_limit(
        self, currency_code: str, amount: float, limit_price: float
    ) -> CryptoOrder:
        return self.wait_for_order_conf_and_convert(
            r.order_sell_crypto_limit_by_price(currency_code, amount, limit_price)
        )

    @retry_function(max_retries=5, wait_time=5)
    def buy_crypto_market(
        self,
        currency_code: str,
        amount: float,
        cur_df: Series[CryptoHistorical] | None,
    ) -> CryptoOrder:
        return self.wait_for_order_conf_and_convert(
            r.order_buy_crypto_by_price(currency_code, amount)
        )

    @retry_function(max_retries=5, wait_time=5)
    def sell_crypto_market(
        self,
        currency_code: str,
        amount: float,
        cur_df: Series[CryptoHistorical] | None,
    ) -> CryptoOrder:
        return self.wait_for_order_conf_and_convert(
            r.order_sell_crypto_by_price(currency_code, amount)
        )

    def wait_for_order_conf_and_convert(
        self, order: Dict[str, Any], max_retries: int = 5
    ) -> CryptoOrder:
        order_state = order["state"]

        for _ in range(max_retries):
            order_info = r.get_crypto_order_info(order["id"])
            order_state = order_info["state"]
            if order_state == "rejected":
                raise BrokerException(
                    f"Order was rejected", ExceptionType.ORDER_REJECTED
                )
            elif order_state == "filled":
                break
            time.sleep(5)

        if order_state != "filled":
            raise BrokerException(
                f"Order was not filled after {max_retries} retries",
                ExceptionType.ORDER_NOT_FILLED,
            )

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
