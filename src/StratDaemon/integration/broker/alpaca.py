import glob
import os
import os
from typing import List
import pandas as pd
from StratDaemon.integration.broker.base import BaseBroker
from StratDaemon.models.crypto import CryptoHistorical, CryptoOrder
from pandera.typing import DataFrame, Series
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame


class AlpacaBroker(BaseBroker):
    def __init__(self):
        super().__init__()
        self.client = CryptoHistoricalDataClient()

    def authenticate(self):
        pass

    def get_crypto_historical(
        self,
        currency_code: str,
        interval: str,
        pull_from_api: bool = False,
        is_backtest: bool = False,
    ) -> DataFrame[CryptoHistorical]:
        
        symbol = f"{currency_code}/USD"
        
        request_params = CryptoBarsRequest(
            symbol_or_symbols=[symbol],
            timeframe=TimeFrame.Minute,
            start="2024-11-23",
            end="2024-11-30"
        )
        
        if pull_from_api:
            bars = self.client.get_crypto_bars(request_params)
            data = bars.data[symbol]
            df = pd.DataFrame([d.model_dump() for d in data])
            df['timestamp'] = df['timestamp'].dt.tz_localize(None)
        else:
            local_data_path = f"alpaca_{currency_code}_historical_data.json"
            if not os.path.exists(local_data_path):
                raise FileNotFoundError(f"Path does not exist: {local_data_path}")
            df = pd.read_json(
                local_data_path,
            )
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
