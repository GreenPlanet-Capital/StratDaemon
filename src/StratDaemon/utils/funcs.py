from datetime import datetime
import sys
from typing import List, Tuple
import optuna
import pandas as pd
import os

from pydantic import BaseModel

from StratDaemon.utils.constants import (
    DEFAULT_INDICATOR_LENGTH,
    NUMERICAL_SPAN,
    OPTUNA_DB_URL,
    PERCENT_DIFF_THRESHOLD,
    RSI_BUY_THRESHOLD,
    RSI_PERCENT_INCR_THRESHOLD,
    RSI_SELL_THRESHOLD,
    RSI_TREND_SPAN,
    TRAILING_STOP_LOSS,
    TRAILING_TAKE_PROFIT,
    VOL_WINDOW_SIZE,
    WAIT_TIME,
)


def restart_program():
    os.execl(sys.executable, sys.executable, *sys.argv)


def get_normalized_value(x, lower_bound, upper_bound, max_x, min_x):
    return (
        ((upper_bound - lower_bound) * (x - min_x))
        / ((max_x - min_x) if max_x != min_x else 1e-6)
    ) + lower_bound


def normalize_values(series: pd.Series, lower_bound, upper_bound) -> pd.Series:
    min_x = series.min()
    max_x = series.max()

    args = (lower_bound, upper_bound, max_x, min_x)
    series_out = series.apply(get_normalized_value, args=args)
    return series_out


def percent_difference(value1, value2):
    return (value1 - value2) / value2 if value2 != 0 else 0


def print_dt(*args, **kw):
    print("[%s]" % (datetime.now()), *args, **kw)


def create_db_uid(start_dt: datetime, end_dt: datetime) -> str:
    return f"{start_dt.strftime('%s')}_{end_dt.strftime('%s')}"


class Parameters(BaseModel):
    p_diff: float
    vol_window: int
    indicator_length: int
    rsi_buy_threshold: float
    rsi_sell_threshold: float
    rsi_percent_incr_threshold: float
    rsi_trend_span: int
    trailing_stop_loss: float
    trailing_take_profit: float
    span: int
    wait_time: int


def load_best_study_parameters(start_dt: datetime, end_dt: datetime) -> Parameters:
    try:
        studies = optuna.get_all_study_names(storage=OPTUNA_DB_URL)
        study_dts: List[Tuple[datetime, datetime]] = []

        for study in studies:
            study_dt = study.split("_")
            study_dt_start = datetime.fromtimestamp(int(study_dt[-2]))
            study_dt_end = datetime.fromtimestamp(int(study_dt[-1]))
            if study_dt_end > end_dt:
                continue
            study_dts.append((study_dt_start, study_dt_end))

        dt_diffs = [
            abs((start_dt - study_dt[0]).total_seconds())
            + abs((end_dt - study_dt[1]).total_seconds())
            for study_dt in study_dts
        ]
        idx = dt_diffs.index(min(dt_diffs))
        study_name = studies[idx]

        print(
            f"Loading study from optuna trained from {study_dts[idx][0]} to {study_dts[idx][1]}"
        )
        study = optuna.load_study(study_name, storage=OPTUNA_DB_URL)
        return Parameters.model_validate(study.best_trials[0].params)
    except Exception as e:
        print(f"Error encountered while loading study parameters: {e}")
        return Parameters(
            p_diff=PERCENT_DIFF_THRESHOLD,
            vol_window=VOL_WINDOW_SIZE,
            indicator_length=DEFAULT_INDICATOR_LENGTH,
            rsi_buy_threshold=RSI_BUY_THRESHOLD,
            rsi_sell_threshold=RSI_SELL_THRESHOLD,
            rsi_percent_incr_threshold=RSI_PERCENT_INCR_THRESHOLD,
            rsi_trend_span=RSI_TREND_SPAN,
            trailing_stop_loss=TRAILING_STOP_LOSS,
            trailing_take_profit=TRAILING_TAKE_PROFIT,
            span=NUMERICAL_SPAN,
            wait_time=WAIT_TIME,
        )
