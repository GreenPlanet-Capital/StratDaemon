from datetime import datetime, timedelta
import warnings
import numpy as np
import pandas as pd
import pymarketstore as pymkts


class AlpacaMarketstoreDB:
    def __init__(self, timeframe: str = "1Min"):
        self.pym_cli = pymkts.Client(endpoint="http://localhost:5993/rpc")
        self.set_symbols = set(self.pym_cli.list_symbols())
        self.timeframe = timeframe

    def check_data_availability(self, ticker, start_timestamp, end_timestamp):
        # TODO: Implement this method
        pass

    def update_ticker_data(self, ticker: str, df: pd.DataFrame):
        df_updated = df.reset_index(drop=True)
        df_updated["timestamp"] = df_updated["timestamp"].apply(
            lambda d: d.value // 10**9
        )
        df_updated = df_updated.rename(columns={"timestamp": "Epoch"})
        df_updated.drop("symbol", axis=1, inplace=True)

        records = df_updated.to_records(index=False)
        data = np.array(records, dtype=records.dtype.descr)

        response = self.pym_cli.write(
            data, f"{ticker}/{self.timeframe}/OHLCV", isvariablelength=True
        )
        assert (
            response is not None and response["responses"] is None
        ), "Error in updating data in database."

    def get_ticker_data(
        self, ticker: str, start_timestamp: datetime, end_timestamp: datetime
    ) -> pd.DataFrame:
        this_params = pymkts.Params(
            ticker,
            self.timeframe,
            "OHLCV",
            int(start_timestamp.timestamp()),
            int(end_timestamp.timestamp()),
        )

        try:
            df = self.pym_cli.query(this_params).first().df().reset_index()
        except Exception as e:
            warnings.warn(f"Error encountered: {e}")
            return pd.DataFrame()

        df.rename(columns={"Epoch": "timestamp"}, inplace=True)
        return df
