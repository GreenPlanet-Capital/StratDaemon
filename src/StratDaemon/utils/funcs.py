from datetime import datetime
import sys
import optuna
import pandas as pd
import os

from pydantic import BaseModel

from StratDaemon.utils.constants import (
    DEFAULT_INDICATOR_LENGTH,
    NUMERICAL_SPAN,
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


def load_best_study_parameters(start_dt: str, end_dt: str) -> Parameters:
    try:
        db_uid = create_db_uid(start_dt, end_dt)
        study = optuna.load_study(
            study_name=f"fib_vol_rsi_{db_uid}",
            storage=f"sqlite:///results/optuna_db.sqlite3",
        )
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
