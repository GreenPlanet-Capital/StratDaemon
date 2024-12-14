from datetime import datetime, timedelta
from typing import List, Tuple
import optuna
import optunahub
from optuna.trial import Trial
from StratDaemon.strats.fib_vol_rsi import FibVolRsiStrategy
from StratDaemon.utils.funcs import create_db_uid
from tests.back_tester import conduct_back_test


class Objective(object):
    def __init__(
        self,
        start_dt: datetime,
        end_dt: datetime,
        currency_codes: List[str],
        buy_power: int,
        max_amount_per_order: int,
        max_holding_per_currency: int,
    ):
        self.start_dt = start_dt
        self.end_dt = end_dt
        self.currency_codes = currency_codes
        self.buy_power = buy_power
        self.max_amount_per_order = max_amount_per_order
        self.max_holding_per_currency = max_holding_per_currency

    # The constraints are to satisfy `c1 <= 0`
    @staticmethod
    def constraints(trial: Trial) -> List[float]:
        # assert span - (indicator_length - 1) > vol_window, "Interval inputs are invalid"
        params = trial.params
        span, indicator_length, vol_window = (
            params["span"],
            params["indicator_length"],
            params["vol_window"],
        )
        return [vol_window - span + indicator_length]

    def _get_result(self, trial: Trial) -> Tuple[float, int]:
        portfolio_hist, num_buy_trades, num_sell_trades = conduct_back_test(
            start_dt=self.start_dt,
            end_dt=self.end_dt,
            strat_def=FibVolRsiStrategy,
            buy_power=self.buy_power,
            max_amount_per_order=self.max_amount_per_order,
            max_holding_per_currency=self.max_holding_per_currency,
            p_diff=trial.suggest_float("p_diff", 0.01, 0.11, step=0.01),
            vol_window=trial.suggest_int("vol_window", 10, 21),
            indicator_length=trial.suggest_int("indicator_length", 10, 21),
            rsi_buy_threshold=trial.suggest_int("rsi_buy_threshold", 20, 50, step=5),
            rsi_sell_threshold=trial.suggest_int("rsi_sell_threshold", 50, 85, step=5),
            rsi_percent_incr_threshold=trial.suggest_float(
                "rsi_percent_incr_threshold", 0.01, 0.41, step=0.01
            ),
            rsi_trend_span=trial.suggest_int("rsi_trend_span", 5, 30, step=5),
            crypto_currency_codes=self.currency_codes,
            span=trial.suggest_int("span", 30, 65, step=5),
            wait_time=trial.suggest_int("wait_time", 5, 65, step=5),
            trailing_stop_loss=trial.suggest_float(
                "trailing_stop_loss", 0.01, 0.21, step=0.01
            ),
            trailing_take_profit=trial.suggest_float(
                "trailing_take_profit", 0.05, 0.50, step=0.05
            ),
        )
        return portfolio_hist[-1].value, num_buy_trades + num_sell_trades

    def __call__(self, trial: optuna.trial.Trial) -> float:
        try:
            return self._get_result(trial)
        except Exception as e:
            print(f"Error: {e}")
            return float("-inf"), float("inf")


def test_optuna(
    start_dt: datetime,
    end_dt: datetime,
    currency_codes: List[str],
    buy_power: int,
    max_amount_per_order: int,
    max_holding_per_currency: int,
    trials: int = 1_000,
    debug: bool = False,
):
    objective = Objective(
        start_dt,
        end_dt,
        currency_codes,
        buy_power,
        max_amount_per_order,
        max_holding_per_currency,
    )
    module = optunahub.load_module(package="samplers/auto_sampler")

    # https://medium.com/optuna/autosampler-automatic-selection-of-optimization-algorithms-in-optuna-1443875fd8f9
    # These are soft constraints, so the sampler will try to avoid these values, but it is not guaranteed.
    sampler = module.AutoSampler(constraints_func=objective.constraints, seed=42)

    db_uid = create_db_uid(start_dt, end_dt)
    study = optuna.create_study(
        directions=["maximize", "minimize"],
        sampler=sampler,
        storage=f"sqlite:///results/optuna_db.sqlite3",
        study_name=f"fib_vol_rsi_{db_uid}",
        load_if_exists=True,
    )
    study.set_metric_names(["portfolio_value", "num_trades"])
    study.optimize(objective, n_trials=trials)

    if debug:
        for t in study.best_trials[:5]:
            print(t.params, t.values)


if __name__ == "__main__":
    currency_codes = ["DOGE", "SHIB"]
    dt_today = datetime.now()
    test_optuna(
        dt_today - timedelta(days=7),
        dt_today,
        currency_codes,
        trials=100,
        debug=True,
    )
