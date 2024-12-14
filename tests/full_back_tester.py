import os
from typing import List

import pandas as pd
from StratDaemon.models.crypto import CryptoOrder
from StratDaemon.strats.base import BaseStrategy
from StratDaemon.strats.fib_vol_rsi import FibVolRsiStrategy
from datetime import datetime, timedelta

from StratDaemon.utils.funcs import load_best_study_parameters
from ml.tuning.test import test_optuna
from tests.back_tester import conduct_back_test

START_DT = datetime(2024, 1, 1)
END_DT = datetime.now() - timedelta(days=1)
OPTUNA_DATA_SPAN = 1  # in weeks
OPTUNA_RUN_FREQ = 24 * 60  # in minutes
OPTUNA_TRIALS = 10

BUY_POWER = 1000
MAX_AMOUNT_PER_ORDER = 100
MAX_HOLDING_PER_CURRENCY = 500


class FullBackTester:
    def __init__(self, strat: BaseStrategy, currency_codes: List[str]):
        self.currency_codes = currency_codes
        self.strat = strat
        self.buy_power = BUY_POWER
        self.holdings: List[CryptoOrder] = []

    def conduct_full_back_test(self):
        # start from 1 week after the start date & test from 2nd week
        start_dt = START_DT
        end_dt = START_DT + timedelta(weeks=OPTUNA_DATA_SPAN)

        while end_dt <= END_DT:
            print(f"Finetuning optuna from {start_dt} to {end_dt}")
            test_optuna(
                start_dt,
                end_dt,
                self.currency_codes,
                BUY_POWER,
                MAX_AMOUNT_PER_ORDER,
                MAX_HOLDING_PER_CURRENCY,
                trials=OPTUNA_TRIALS,
                debug=False,
            )

            optuna_start_dt = start_dt
            optuna_end_dt = end_dt

            start_dt = end_dt
            end_dt = start_dt + timedelta(minutes=OPTUNA_RUN_FREQ)

            print(f"Backtesting from {start_dt} to {end_dt}")
            wait_time = self.backtest_after_optuna(
                optuna_start_dt, optuna_end_dt, start_dt, end_dt
            )
            wait_time = 45

            end_dt += timedelta(minutes=wait_time)
            start_dt = end_dt - timedelta(weeks=OPTUNA_DATA_SPAN)

    def backtest_after_optuna(
        self,
        optuna_start_dt: datetime,
        optuna_end_dt: datetime,
        start_dt: datetime,
        end_dt: datetime,
    ) -> int:
        params = load_best_study_parameters(optuna_start_dt, optuna_end_dt)
        port_hist, buy_trades, sell_trades = conduct_back_test(
            self.strat,
            MAX_AMOUNT_PER_ORDER,
            MAX_HOLDING_PER_CURRENCY,
            params.p_diff,
            params.vol_window,
            params.indicator_length,
            params.rsi_buy_threshold,
            params.rsi_sell_threshold,
            params.rsi_percent_incr_threshold,
            params.rsi_trend_span,
            params.trailing_stop_loss,
            self.currency_codes,
            self.buy_power,
            params.span,
            params.wait_time,
            start_dt=start_dt,
            end_dt=end_dt,
            prev_holdings=self.holdings,
        )
        final_port = port_hist[-1]
        self.buy_power = final_port.buy_power
        self.holdings = final_port.holdings
        self.save_result(start_dt, end_dt, final_port.value, buy_trades, sell_trades)
        return params.wait_time

    def save_result(
        self,
        start_dt: datetime,
        end_dt: datetime,
        portfolio_value: float,
        num_buy_trades: int,
        num_sell_trades: int,
    ):
        csv_path = "results/performance_full.csv"
        if not os.path.exists(csv_path):
            with open(csv_path, "w") as f:
                f.write(
                    "date_start,date_end,portfolio_value,num_buy_trades,num_sell_trades\n"
                )

        with open(csv_path, "a") as f:
            f.write(
                f"{start_dt},{end_dt},{portfolio_value},{num_buy_trades},{num_sell_trades}\n"
            )


if __name__ == "__main__":
    currency_codes = ["DOGE", "SHIB"]
    full_back_tester = FullBackTester(FibVolRsiStrategy, currency_codes)
    full_back_tester.conduct_full_back_test()
