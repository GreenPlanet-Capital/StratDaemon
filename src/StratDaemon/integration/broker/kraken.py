import glob
import os
import os
from typing import List
import pandas as pd
from StratDaemon.integration.broker.base import BaseBroker
from StratDaemon.models.crypto import CryptoHistorical, CryptoOrder
from pandera.typing import DataFrame, Series

LOCAL_DATA_PATH = "kraken"


class KrakenBroker(BaseBroker):
    def __init__(self):
        super().__init__()
        self.local_data_path = LOCAL_DATA_PATH

    def authenticate(self):
        pass

    def get_crypto_historical(
        self,
        currency_code: str,
        interval: str,
        pull_from_api: bool = False,
        is_backtest: bool = False,
    ) -> DataFrame[CryptoHistorical]:
        local_data_path = os.path.join(
            self.local_data_path, f"{currency_code}USD_1.csv"
        )
        if not os.path.exists(self.local_data_path):
            raise FileNotFoundError(f"Path does not exist: {self.local_data_path}")
        df = pd.read_csv(
            local_data_path,
            header=None,
            usecols=list(range(6)),
            names=["timestamp", "open", "high", "low", "close", "volume"],
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
        return CryptoHistorical.validate(df)

    def buy_crypto_market(
        self, currency_code: str, amount: float, cur_df: Series[CryptoHistorical] | None
    ) -> CryptoOrder:
        return CryptoOrder(
            side="buy",
            currency_code=currency_code,
            asset_price=cur_df.close,
            quantity=amount / cur_df.close,
            amount=amount,
            limit_price=-1,
            timestamp=cur_df.timestamp,
        )

    def sell_crypto_market(
        self, currency_code: str, amount: float, cur_df: Series[CryptoHistorical] | None
    ) -> CryptoOrder:
        return CryptoOrder(
            side="sell",
            currency_code=currency_code,
            asset_price=cur_df.close,
            quantity=amount / cur_df.close,
            amount=amount,
            limit_price=-1,
            timestamp=cur_df.timestamp,
        )
