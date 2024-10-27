from typing import List
import pandas as pd
from pandera.typing import DataFrame
from StratDaemon.models.crypto import CryptoHistorical
from StratDaemon.utils.constants import FIB_VALUES
import pandas_ta as ta
from StratDaemon.utils.funcs import normalize_values


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
    df["boll_diff"] = boll[f"BBU_14_2.0"] - boll["BBL_14_2.0"]
    df = df.dropna()
    df["boll_diff"] = normalize_values(df["boll_diff"], 0, 1)
    return df


def add_rsi(
    df: DataFrame[CryptoHistorical], length: int
) -> DataFrame[CryptoHistorical]:
    df["rsi"] = ta.rsi(df["close"], length=length)
    return df


def add_trends_upwards(df: DataFrame[CryptoHistorical]) -> DataFrame[CryptoHistorical]:
    sma_50 = ta.sma(df["close"], length=50)
    sma_200 = ta.sma(df["close"], length=200)
    df["trends_upwards"] = sma_50 >= sma_200
    return df
