import os
from typing import List

import pandas as pd
from StratDaemon.models.crypto import CryptoOrder
from StratDaemon.strats.base import BaseStrategy
from StratDaemon.strats.fib_vol_rsi import FibVolRsiStrategy
from datetime import datetime, timedelta

from StratDaemon.utils.funcs import Parameters, load_best_study_parameters
from ml.tuning.test import test_optuna
from tests.back_tester import conduct_back_test
from sys import argv

START_DT = datetime(2024, 1, 1)
END_DT = datetime(2024, 12, 19)

OPTUNA_DATA_SPAN = 1  # in weeks
OPTUNA_RUN_FREQ = 24 * 60  # in minutes
OPTUNA_TRIALS = 5

BUY_POWER = 10_000
MAX_AMOUNT_PER_ORDER = 10_000
MAX_HOLDING_PER_CURRENCY = 10_000


class FullBackTester:
    def __init__(self, strat: BaseStrategy, currency_codes: List[str]):
        self.currency_codes = currency_codes
        self.strat = strat
        self.buy_power = BUY_POWER
        self.holdings: List[CryptoOrder] = []

    def conduct_full_back_test(
        self, finetune_only: bool = False, backtest_only: bool = False
    ):
        # start from 1 week after the start date & test from 2nd week
        start_dt = START_DT
        end_dt = START_DT + timedelta(weeks=OPTUNA_DATA_SPAN)
        print(
            f"Starting full backtest with{'out' if backtest_only else ''} finetuning"
            " and "
            f"with{'out' if finetune_only else ''} backtesting"
            f" for {(end_dt - start_dt).days} days"
        )
        if backtest_only is True:
            self.save_result(start_dt, end_dt, self.buy_power, 0, 0)

        while end_dt <= END_DT:
            # TODO: revisit this logic
            if backtest_only is False:
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

            if finetune_only is False:
                print(f"Backtesting from {start_dt} to {end_dt}")
                params = load_best_study_parameters(
                    optuna_start_dt, optuna_end_dt, fallback_nearest=True
                )
                # params = Parameters(
                #     p_diff=0.02,
                #     vol_window=18,
                #     indicator_length=20,
                #     rsi_buy_threshold=55,
                #     rsi_sell_threshold=80,
                #     rsi_percent_incr_threshold=0.1,
                #     rsi_trend_span=5,
                #     trailing_stop_loss=0.05,
                #     trailing_take_profit=0.1,
                #     span=60,
                #     wait_time=60,
                # )

                self.backtest_after_optuna(params, start_dt, end_dt)
                # end_dt += timedelta(minutes=params.wait_time) # this is needed but is harder to test

            start_dt = end_dt - timedelta(weeks=OPTUNA_DATA_SPAN)

    def backtest_after_optuna(
        self,
        params: Parameters,
        start_dt: datetime,
        end_dt: datetime,
    ) -> int:
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
            params.trailing_take_profit,
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
    # currency_codes = ["DOGE", "SHIB"]
    currency_codes = ["DOGE"]
    full_back_tester = FullBackTester(FibVolRsiStrategy, currency_codes)
    finetune_only = backtest_only = False
    if len(argv) > 1:
        if argv[1] == "finetune":
            finetune_only = True
        elif argv[1] == "backtest":
            backtest_only = True
    full_back_tester.conduct_full_back_test(finetune_only, backtest_only)
