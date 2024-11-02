import os
from typing import List
import pandas as pd
from StratDaemon.integration.broker.base import BaseBroker
from StratDaemon.models.crypto import CryptoHistorical, CryptoOrder
from pandera.typing import DataFrame, Series
import requests
from datetime import datetime
from StratDaemon.utils.constants import CRYPTO_COMPARE_API_KEY

LOCAL_DATA_PATH_SUFFIX = "historical_data.json"


class FakeBroker(BaseBroker):
    def __init__(self):
        super().__init__()
        self.hist_base_url = "https://min-api.cryptocompare.com/data/histo"
        self.latest_base_url = "https://min-api.cryptocompare.com/data/price"
        self.max_limit = 2000
        self.save_data_interval = 10

    def authenticate(self):
        pass

    def make_crypto_historical_req(
        self, currency_code: str, interval: str, to_timestamp: datetime | None
    ) -> List[CryptoHistorical]:
        req_args = {
            "fsym": currency_code,
            "tsym": "USD",
            "limit": self.max_limit,
            "api_key": CRYPTO_COMPARE_API_KEY,
        }

        if to_timestamp is not None:
            req_args["toTs"] = int(to_timestamp.timestamp())

        try:
            response = requests.get(
                self.formulate_url(self.hist_base_url, interval, req_args), timeout=10
            )
            response.raise_for_status()
        except Exception as e:
            print(f"Error encountered: {e}")
            return []

        return [
            {
                "open": float(data["open"]),
                "close": float(data["close"]),
                "high": float(data["high"]),
                "low": float(data["low"]),
                "volume": float(
                    data["volumefrom"]
                ),  # volumefrom is the of in the cryptocurrency
                "timestamp": datetime.fromtimestamp(data["time"]),
            }
            for data in response.json()["Data"]
        ]

    def get_crypto_latest(self, currency_code: str) -> float:
        req_args = {
            "fsym": currency_code,
            "tsyms": "USD",
            "api_key": CRYPTO_COMPARE_API_KEY,
        }
        response = requests.get(self.formulate_url(self.latest_base_url, "", req_args))
        response.raise_for_status()
        return response.json()["USD"]

    def get_crypto_historical(
        self,
        currency_code: str,
        interval: str,
        pull_from_api: bool = False,
    ) -> DataFrame[CryptoHistorical]:
        local_data_path = f"{currency_code}_{LOCAL_DATA_PATH_SUFFIX}"

        df = (
            pd.read_json(local_data_path)
            if os.path.exists(local_data_path)
            else pd.DataFrame()
        )

        if pull_from_api is True:
            crypto_hist = []
            to_timestamp = None if df.empty else df["timestamp"].min()
            save_data_interval = self.save_data_interval

            while data := self.make_crypto_historical_req(
                currency_code, interval, to_timestamp
            ):
                if all([d["volume"] == 0 for d in data]):
                    break

                crypto_hist.extend(data)
                to_timestamp = data[0]["timestamp"]
                save_data_interval -= 1

                if save_data_interval <= 0:
                    df = self.combine_df_and_save(df, crypto_hist, local_data_path)
                    save_data_interval = self.save_data_interval

            df = self.combine_df_and_save(df, crypto_hist, local_data_path)

        df = df.sort_values("timestamp", ascending=True)
        return self.clean_data(CryptoHistorical.validate(df))

    def combine_df_and_save(
        self,
        df: DataFrame[CryptoHistorical],
        crypto_hist: List[CryptoHistorical],
        local_data_path: str,
    ) -> DataFrame[CryptoHistorical]:
        print("Saving data...")
        df = pd.concat([df, pd.DataFrame(crypto_hist)], ignore_index=True)
        df.to_json(local_data_path)
        return df

    def formulate_url(self, base_url, interval, req_args):
        return f"{base_url}{interval}?{'&'.join([f'{k}={v}' for k, v in req_args.items()])}"

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

    def clean_data(
        self, df: DataFrame[CryptoHistorical]
    ) -> DataFrame[CryptoHistorical]:
        return df[df["volume"] != 0]


if __name__ == "__main__":
    broker = FakeBroker()
    hist = broker.get_crypto_historical("DOGE", "hour", pull_from_api=False)
