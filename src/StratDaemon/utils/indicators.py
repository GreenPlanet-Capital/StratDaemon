import pandas as pd
from pandera.typing import DataFrame
from StratDaemon.models.crypto import CryptoHistorical
from StratDaemon.utils.constants import FIB_VALUES
import pandas_ta as ta


def add_fib_ret_lvls(
    df: DataFrame[CryptoHistorical], trends_upward: bool
) -> DataFrame[CryptoHistorical]:
    low, high = df["close"].min(), df["close"].max()
    diff = high - low
    if trends_upward:
        vals = [high + (diff * fib) for fib in FIB_VALUES]
    else:
        vals = [low - (diff * fib) for fib in FIB_VALUES]

    for i, val in enumerate(vals):
        df[f"fib_{i}"] = val

    return df


def add_boll_diff(
    df: DataFrame[CryptoHistorical], length: int
) -> DataFrame[CryptoHistorical]:
    boll = ta.bbands(df["close"], length=length)
    df["upper_bb"] = boll[f"BBU_{length}_2.0"]
    df["lower_bb"] = boll[f"BBL_{length}_2.0"]
    df["boll_diff"] = df["upper_bb"] - df["lower_bb"]
    return df


def add_rsi(
    df: DataFrame[CryptoHistorical], length: int
) -> DataFrame[CryptoHistorical]:
    df["rsi"] = ta.rsi(df["close"], length=length)
    return df


def add_trends_upwards(df: DataFrame[CryptoHistorical]) -> DataFrame[CryptoHistorical]:
    sma_50, sma_200 = sma(df, "close")
    # sma_50, sma_200 = sma(df, "SUPERT_14_3.0")
    df["trends_upwards"] = sma_50 > sma_200
    return df


def sma(df: DataFrame, col: str) -> DataFrame:
    n = len(df)
    sma_50 = ta.sma(df[col], length=n // 2)
    sma_200 = ta.sma(df[col], length=n)
    return sma_50, sma_200


def add_super_trend(
    df: DataFrame[CryptoHistorical], atr_length: int, multiplier: float
) -> DataFrame:
    df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=atr_length)
    super_trend = ta.supertrend(
        df["high"], df["low"], df["close"], atr_length, multiplier
    )
    super_trend = super_trend.fillna(method="bfill")
    super_trend["SUPERT_14_3.0"].iloc[0] = super_trend["SUPERT_14_3.0"].iloc[1]
    df = pd.concat([df, super_trend], axis=1)
    return df
