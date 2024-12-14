import pandas as pd
from StratDaemon.integration.broker.base import BaseBroker
from StratDaemon.integration.db.alpaca import AlpacaMarketstoreDB
from StratDaemon.models.crypto import CryptoHistorical, CryptoOrder
from pandera.typing import DataFrame, Series
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timezone

DATA_BEGIN_DATE = "2024-01-01"


class AlpacaBroker(BaseBroker):
    def __init__(self):
        super().__init__()
        self.client = CryptoHistoricalDataClient()
        self.db = AlpacaMarketstoreDB()

    def authenticate(self):
        pass

    def perform_alpaca_req(self, start_dt: datetime, end_dt: datetime, symbol: str):
        start_req = start_dt.strftime("%Y-%m-%d")
        end_req = end_dt.strftime("%Y-%m-%d")
        print(f"Getting data from {start_req} to {end_req}")

        assert (
            start_dt < end_dt
        ), "Start date must be before end date for Alpaca request"

        request_params = CryptoBarsRequest(
            symbol_or_symbols=[symbol],
            timeframe=TimeFrame.Minute,
            start=start_req,
            end=end_req,
        )
        bars = self.client.get_crypto_bars(request_params)
        data = bars.data[symbol]

        assert len(data) > 0, "No data returned from Alpaca"
        print(f"Received {len(data)} data points from Alpaca")
        df = pd.DataFrame([d.model_dump() for d in data])

        currency_code = symbol.split("/")[0]
        self.db.update_ticker_data(currency_code, df)

    def get_crypto_historical(
        self,
        currency_code: str,
        interval: str,
        pull_from_api: bool = False,
        is_backtest: bool = False,
    ) -> DataFrame[CryptoHistorical]:
        symbol = f"{currency_code}/USD"

        start_dt, end_dt = (
            datetime.strptime(DATA_BEGIN_DATE, "%Y-%m-%d").replace(tzinfo=timezone.utc),
            datetime.now(tz=timezone.utc),
        )

        if pull_from_api:
            dt_pairs = self.db.check_data_availability(currency_code, start_dt, end_dt)
            print(f"For {currency_code}, missing data for {len(dt_pairs)} date pairs")
            for start, end in dt_pairs:
                self.perform_alpaca_req(start, end, symbol)

        df = self.db.get_ticker_data(currency_code, start_dt, end_dt)
        df["timestamp"] = df["timestamp"].dt.tz_localize(None)
        df = df.sort_values("timestamp").reset_index(drop=True)
        df = df.drop_duplicates(subset=["timestamp"], keep="first")
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
