from typing import List, Tuple
import optuna
import optunahub
from optuna.trial import Trial
from StratDaemon.strats.fib_vol_rsi import FibVolRsiStrategy
from tests.back_tester import conduct_back_test


class Objective(object):
    def __init__(self, currency_codes: List[str]):
        self.currency_codes = currency_codes

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
            strat_def=FibVolRsiStrategy,
            max_amount_per_order=100,
            max_holding_per_currency=500,
            p_diff=trial.suggest_float("p_diff", 0.01, 0.11, step=0.01),
            vol_window=trial.suggest_int("vol_window", 10, 21),
            risk_factor=-1,
            indicator_length=trial.suggest_int("indicator_length", 10, 21),
            rsi_buy_threshold=trial.suggest_int("rsi_buy_threshold", 30, 55, step=5),
            rsi_sell_threshold=trial.suggest_int("rsi_sell_threshold", 50, 85, step=5),
            rsi_percent_incr_threshold=trial.suggest_float(
                "rsi_percent_incr_threshold", 0.01, 0.41, step=0.01
            ),
            rsi_trend_span=trial.suggest_int("rsi_trend_span", 5, 30, step=5),
            crypto_currency_codes=self.currency_codes,
            buy_power=1_000,
            span=trial.suggest_int("span", 30, 65, step=5),
            wait_time=trial.suggest_int("wait_time", 5, 65, step=5),
            trailing_stop_loss=trial.suggest_float(
                "trailing_stop_loss", 0.01, 0.21, step=0.01
            ),
            save_graph=False,
        )
        return portfolio_hist[-1].value, num_buy_trades + num_sell_trades

    def __call__(self, trial: optuna.trial.Trial) -> float:
        try:
            return self._get_result(trial)
        except Exception as e:
            print(f"Error: {e}")
            return float("-inf"), float("inf")


if __name__ == "__main__":
    currency_codes = ["DOGE", "SHIB"]
    objective = Objective(currency_codes)

    module = optunahub.load_module(package="samplers/auto_sampler")

    # https://medium.com/optuna/autosampler-automatic-selection-of-optimization-algorithms-in-optuna-1443875fd8f9
    # These are soft constraints, so the sampler will try to avoid these values, but it is not guaranteed.
    sampler = module.AutoSampler(constraints_func=objective.constraints, seed=42)

    study = optuna.create_study(
        directions=["maximize", "minimize"],
        sampler=sampler,
        storage="sqlite:///optuna_db.sqlite3",
        study_name="fib_vol_rsi",
        load_if_exists=True,
    )
    study.set_metric_names(["portfolio_value", "num_trades"])
    study.optimize(objective, n_trials=1_000)
    for t in study.best_trials[:5]:
        print(t.params, t.values)
