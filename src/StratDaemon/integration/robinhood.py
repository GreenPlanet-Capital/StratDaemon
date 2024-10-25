import configparser
from datetime import datetime
from typing import Any, Dict, List
import robin_stocks.robinhood as r
from StratDaemon.integration.base import BaseIntegration
from StratDaemon.utils.constants import CRYPTO_EXCHANGE
from StratDaemon.models.crypto import CryptoAsset


class RobinhoodIntegration(BaseIntegration):
    def __init__(self) -> None:
        super().__init__()

    def authenticate(self) -> None:
        cfg_parser = configparser.ConfigParser()
        cfg_parser.read("creds.ini")
        r.login(
            username=cfg_parser.get("robinhood", "email"),
            password=cfg_parser.get("robinhood", "password"),
        )

    def get_rh_crypto_positions(self) -> List[Dict[str, Any]]:
        RH_ENDPOINT_URL = "https://nummus.robinhood.com/holdings/"
        payload = {"nonzero": "true"}
        return r.request_get(RH_ENDPOINT_URL, "pagination", payload)

    def get_crypto_positions(self) -> List[CryptoAsset]:
        orders = self.get_rh_crypto_positions()
        return [
            CryptoAsset(
                currency_code=order["currency"]["code"],
                quantity=float(order["quantity"]),
                initial_cost_basis=float(order["cost_bases"][0]["direct_cost_basis"]),
                initial_quantity=float(order["cost_bases"][0]["direct_quantity"]),
                created_at=self.convert_rh_dt_to_datetime(order["created_at"]),
                updated_at=self.convert_rh_dt_to_datetime(order["updated_at"]),
            )
            for order in orders
        ]

    def convert_rh_dt_to_datetime(self, rh_dt: str) -> datetime:
        return datetime.strptime(rh_dt, "%Y-%m-%dT%H:%M:%S.%f%z")
