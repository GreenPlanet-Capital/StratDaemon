import configparser
from datetime import datetime
from typing import Any, Dict, List
import robin_stocks.robinhood as r
from Quantify.positions.opportunity import Opportunity
from Quantify.positions.position import Position
from StratDaemon.integration.base import BaseIntegration
from StratDaemon.utils.constants import CRYPTO_EXCHANGE


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

    def get_crypto_positions(self) -> List[Position]:
        orders = r.get_all_crypto_orders() # aggregate all crypto orders by currency_code
        import pdb

        pdb.set_trace()

    def convert_crypto_order_to_position(self, order: Dict[str, Any]) -> Position:
        opportunity = Opportunity(
            strategy_id=-1,
            ticker=order["currency_code"],
            timestamp=order["last_transaction_at"],
            default_price=order["average_price"],
            exchangeName=CRYPTO_EXCHANGE,
            order_type=1,
            metadata={},
        )

    def convert_rh_dt_to_datetime(self, rh_dt: str) -> datetime:
        # 2024-10-18T21:44:48.150000-04:00
        return datetime.strptime(rh_dt, "%Y-%m-%dT%H:%M:%S.%f%z")
