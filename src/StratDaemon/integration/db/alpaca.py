from datetime import datetime, timedelta
from typing import List, Tuple
import warnings
import numpy as np
import pandas as pd
import pymarketstore as pymkts


class AlpacaMarketstoreDB:
    def __init__(self, timeframe: str = "1Min"):
        self.pym_cli = pymkts.Client(endpoint="http://localhost:5993/rpc")
        self.set_symbols = set(self.pym_cli.list_symbols())
        self.timeframe = timeframe

    def check_data_availability(
        self, ticker: str, start_timestamp: datetime, end_timestamp: datetime
    ) -> List[Tuple[datetime, datetime]]:
        all_dates: List[pd.Timestamp] = list(
            self.pym_cli.sql([f"SELECT Epoch FROM `{ticker}/{self.timeframe}/OHLCV`;"])
            .first()
            .df()
            .index
        )
        req_dates = pd.date_range(
            start=start_timestamp, end=end_timestamp, freq=self.timeframe
        )
        req_dates = [d.to_pydatetime().replace(tzinfo=None) for d in req_dates]
        all_dates = [d.to_pydatetime().replace(tzinfo=None) for d in all_dates]

        missing_dates = sorted(set(req_dates) - set(all_dates))
        dt_pairs: List[Tuple[datetime, datetime]] = []

        if len(missing_dates) == 0:
            return []

        missing_dates = sorted(set(dt.date() for dt in missing_dates))
        consec_dates = self.get_consec_dts(missing_dates, timedelta(days=1))
        for consec in consec_dates:
            if len(consec) == 1:
                dt_pairs.append((consec[0], consec[0] + timedelta(days=1)))
            else:
                dt_pairs.append((consec[0], consec[-1]))

        import pdb

        pdb.set_trace()
        return dt_pairs

    def get_consec_dts(self, v: List[datetime], timedelta: timedelta) -> List[datetime]:
        consec: List[datetime] = []
        run = []

        for i in range(1, len(v) + 1):
            run.append(v[i - 1])
            if i == len(v) or v[i - 1] + timedelta != v[i]:
                consec.append(run)
                run = []

        return consec

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
