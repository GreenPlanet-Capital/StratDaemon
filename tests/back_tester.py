from datetime import datetime, timedelta
from typing import Generator, List, Dict, Tuple
from devtools import pprint
import optuna
import pandas as pd
from pydantic import BaseModel
from tqdm import tqdm
from StratDaemon.integration.broker.alpaca import AlpacaBroker
from StratDaemon.models.crypto import CryptoHistorical, CryptoOrder, Portfolio
from StratDaemon.portfolio.graph_positions import GraphHandler
from StratDaemon.strats.base import BaseStrategy
from StratDaemon.strats.fib_vol_rsi import FibVolRsiStrategy
from pandera.typing import DataFrame
import plotly.express as px
import os
import numpy as np
from collections import defaultdict

from StratDaemon.utils.funcs import create_db_uid

DEFAULT_BROKER = AlpacaBroker()


class BackTester:
    def __init__(
        self,
        strat: FibVolRsiStrategy,
        currency_codes: List[str],
        buy_power: float,
        span: int = 30,
        wait_time: int = 5,
    ) -> None:
        self.strat = strat
        self.broker = DEFAULT_BROKER
        self.currency_codes = currency_codes
        strat_split = self.strat.name.split("_")
        self.strat_name = f"{strat_split[0]}_{strat_split[-1]}"
        self.all_data_dfs = [
            self.broker.get_crypto_historical(
                currency_code, "hour", pull_from_api=False
            )
            for currency_code in self.currency_codes
        ]
        self.ensure_data_dfs_consistent()
        self.span = span
        self.wait_time = wait_time
        self.buy_power = buy_power
        self.sanity_checks()

    def sanity_checks(self) -> None:
        assert len(self.currency_codes) == len(
            self.all_data_dfs
        ), "Currency codes and data must be of the same length"

    def ensure_data_dfs_consistent(self) -> None:
        dates = self.all_data_dfs[0].timestamp
        for df in self.all_data_dfs[1:]:
            cur_dates = df.timestamp
            dates = np.intersect1d(dates, cur_dates)

        for i, df in enumerate(self.all_data_dfs):
            self.all_data_dfs[i] = df[df.timestamp.isin(dates)]

    def save_portfolio(
        self,
        portfolio_hist: List[Portfolio],
        num_buy_trades: int,
        num_sell_trades: int,
        transactions: List[CryptoOrder],
        save_graph: bool = True,
    ) -> None:
        strat_rsi_buy_threshold = getattr(self.strat, "rsi_buy_threshold", -1)
        strat_rsi_sell_threshold = getattr(self.strat, "rsi_sell_threshold", -1)
        strat_rsi_percent_incr_threshold = getattr(
            self.strat, "rsi_percent_incr_threshold", -1
        )
        strat_rsi_trend_span = getattr(self.strat, "rsi_trend_span", -1)

        csv_path = "results/performance.csv"
        if not os.path.exists(csv_path):
            with open(csv_path, "w") as f:
                f.write(
                    "currency_codes,strategy_name,percent_diff_threshold,span,wait_time,"
                    "rsi_buy_threshold,rsi_sell_threshold,rsi_percent_incr_threshold,"
                    "rsi_trend_span,indicator_length,trailing_stop_loss,"
                    "vol_window_size,final_value,num_buy_trades,num_sell_trades\n"
                )

        with open(csv_path, "a") as f:
            f.write(
                f"{'|'.join(self.currency_codes)},{self.strat_name},"
                f"{self.strat.percent_diff_threshold},{self.span},{self.wait_time},"
                f"{strat_rsi_buy_threshold},{strat_rsi_sell_threshold},{strat_rsi_percent_incr_threshold},"
                f"{strat_rsi_trend_span},{self.strat.indicator_length},{self.strat.portfolio_mgr.trailing_stop_loss},"
                f"{self.strat.vol_window_size},"
                f"{portfolio_hist[-1].value},{num_buy_trades},"
                f"{num_sell_trades}\n"
            )

    def print_agg_holdings(
        self, orders: List[CryptoOrder], cur_prices_dt: Dict[str, float]
    ) -> None:
        holdings = defaultdict(
            lambda: {
                "amount": 0,
                "average_price": 0,
                "num_buy_orders": 0,
            }
        )
        for order in orders:
            cur_holding = holdings[order.currency_code]
            amount = (
                cur_prices_dt[order.currency_code] * order.quantity
                if order.side == "buy"
                else -order.amount
            )
            cur_holding["amount"] += amount
            if order.side == "buy":
                cur_holding["average_price"] += order.asset_price
                cur_holding["num_buy_orders"] += 1

        def safe_div(a: float, b: float) -> float:
            return "{:.10f}".format(a / b) if b != 0 else 0

        for _, holding in holdings.items():
            holding["average_price"] = safe_div(
                holding["average_price"], holding["num_buy_orders"]
            )

        pprint(dict(holdings))

    def run(
        self,
        start_dt: datetime | None = None,
        end_dt: datetime | None = None,
        save_data: bool = False,
        save_graph: bool = False,
        debug: bool = False,
        prev_holdings: List[CryptoOrder] | None = None,
    ) -> Tuple[List[Portfolio], int, int]:
        print(f"Starting with ${self.buy_power}")
        transactions: List[CryptoOrder] = []

        if prev_holdings is not None:
            self.strat.portfolio_mgr.portfolio_hist[-1].holdings.extend(prev_holdings)

        if start_dt is None and end_dt is None:
            start_dt, end_dt = (
                self.all_data_dfs[0].iloc[0].timestamp,
                self.all_data_dfs[0].iloc[-1].timestamp,
            )
        print(f"Testing from {start_dt} to {end_dt}")
        total_time = (
            int(
                (((end_dt - start_dt).total_seconds() / 60) - self.span)
                / self.wait_time
            )
            + 1
        )

        for dfs in tqdm(
            self.get_data_by_interval(start_dt, end_dt, self.span, self.wait_time),
            desc=f"Backtesting {'|'.join(self.currency_codes)} cryptos with {self.strat_name} strategy",
            total=total_time,
        ):
            assert all(
                len(df) == len(dfs[0]) == self.span for df in dfs
            ), f"All dataframes must have the same length as the span: {[len(df) for df in dfs]}"
            input_dt_dfs = {
                currency_code: df for currency_code, df in zip(self.currency_codes, dfs)
            }
            orders = self.strat.execute(
                input_dt_dfs, print_orders=debug, save_positions=False
            )
            transactions.extend(orders)

        prev_portfolio = self.strat.portfolio_mgr.portfolio_hist[-1]
        cur_portfolio = Portfolio(
            timestamp=datetime.now(),
            value=prev_portfolio.value,
            buy_power=prev_portfolio.buy_power,
            holdings=prev_portfolio.holdings,
        )
        cur_prices_dt = {
            currency_code: self.all_data_dfs[idx].iloc[-1].close
            for idx, currency_code in enumerate(self.currency_codes)
        }
        cur_portfolio.value = self.strat.portfolio_mgr.calculate_portfolio_value(
            cur_portfolio,
            cur_prices_dt,
        )
        self.strat.portfolio_mgr.portfolio_hist.append(cur_portfolio)

        num_buy_trades = self.strat.portfolio_mgr.num_buy_trades
        num_sell_trades = self.strat.portfolio_mgr.num_sell_trades
        print(
            f"Ending with ${round(cur_portfolio.value, 2)}\n"
            f"  after {num_buy_trades} buy trades \n"
            f"  and {num_sell_trades} sell trades over \n"
            f"  {total_time} minutes\n"
            f"  making trades every {self.wait_time} minutes\n"
            f"  with percent_diff_threshold={self.strat.percent_diff_threshold}\n"
            f"  and vol_window_size={self.strat.vol_window_size}\n"
            f"  and span={self.span}\n"
            f"  and rsi_buy_threshold={getattr(self.strat, 'rsi_buy_threshold', -1)}\n"
            f"  and rsi_sell_threshold={getattr(self.strat, 'rsi_sell_threshold', -1)}\n"
            f"  and rsi_percent_incr_threshold={getattr(self.strat, 'rsi_percent_incr_threshold', -1)}\n"
            f"  and rsi trend span={getattr(self.strat, 'rsi_trend_span', -1)}\n"
            f"  and indicator_length={self.strat.indicator_length}\n"
            f"  and trailing_stop_loss={self.strat.portfolio_mgr.trailing_stop_loss}\n"
        )

        print(f"Buy power left: ${cur_portfolio.buy_power}")
        self.print_agg_holdings(cur_portfolio.holdings, cur_prices_dt)
        portfolio_hist = self.strat.portfolio_mgr.portfolio_hist

        if save_data:
            print("Saving portfolio data. This may take a while...")
            self.save_portfolio(
                portfolio_hist,
                num_buy_trades,
                num_sell_trades,
                transactions,
                save_graph=save_graph,
            )
        return (
            portfolio_hist,
            num_buy_trades,
            num_sell_trades,
        )

    def get_data_by_interval(
        self,
        start_dt: datetime,
        end_dt: datetime,
        span: int,
        wait_time: int = 0,
    ) -> Generator[DataFrame[CryptoHistorical], None, None]:
        dfs: List[DataFrame[CryptoHistorical]] = []

        # FIXME: Implement a more efficient way of getting data by interval
        for i, df in enumerate(self.all_data_dfs):
            df = df[(df.timestamp >= start_dt) & (df.timestamp <= end_dt)]
            df = df.set_index("timestamp", drop=True)
            df = df.reindex(pd.date_range(start_dt, end_dt, freq="1 min"))
            df = df.interpolate(method="linear")
            df = df.reset_index().rename(columns={"index": "timestamp"})
            df = df.fillna(method="ffill").fillna(method="bfill")

            assert not df.isnull().values.any(), f"Dataframe {i} has NaN values"

            dfs.append(df)

        n = len(df)
        for i in range(span, n, wait_time):
            yield [df[i - span + 1 : i + 1] for df in dfs]


def create_strat(
    strat: BaseStrategy,
    crypto_currency_codes: List[str],
    buy_power: float,
    max_amount_per_order: float,
    max_holding_per_currency: float,
    p_diff: float,
    vol_window: int,
    indicator_length: int,
    rsi_buy_threshold: float,
    rsi_sell_threshold: float,
    rsi_percent_incr_threshold: float,
    rsi_trend_span: int,
    trailing_stop_loss: float,
) -> BaseStrategy:
    return strat(
        broker=DEFAULT_BROKER,
        notif=None,
        currency_codes=crypto_currency_codes,
        auto_generate_orders=True,
        max_amount_per_order=max_amount_per_order,
        paper_trade=False,
        percent_diff_threshold=p_diff,
        vol_window_size=vol_window,
        buy_power=buy_power,
        max_holding_per_currency=max_holding_per_currency,
        indicator_length=indicator_length,
        rsi_buy_threshold=rsi_buy_threshold,
        rsi_sell_threshold=rsi_sell_threshold,
        rsi_percent_incr_threshold=rsi_percent_incr_threshold,
        rsi_trend_span=rsi_trend_span,
        trailing_stop_loss=trailing_stop_loss,
    )


def conduct_back_test(
    strat_def: BaseStrategy,
    max_amount_per_order: float,
    max_holding_per_currency: float,
    p_diff: float,
    vol_window: int,
    indicator_length: int,
    rsi_buy_threshold: float,
    rsi_sell_threshold: float,
    rsi_percent_incr_threshold: float,
    rsi_trend_span: int,
    trailing_stop_loss: float,
    crypto_currency_codes: List[str],
    buy_power: float,
    span: int,
    wait_time: int,
    start_dt: datetime | None = None,
    end_dt: datetime | None = None,
    prev_holdings: List[CryptoOrder] | None = None,
) -> Tuple[List[Portfolio], int, int]:
    assert span - (indicator_length - 1) > vol_window, "Interval inputs are invalid"
    strat = create_strat(
        strat_def,
        crypto_currency_codes,
        buy_power,
        max_amount_per_order,
        max_holding_per_currency,
        p_diff,
        vol_window,
        indicator_length,
        rsi_buy_threshold,
        rsi_sell_threshold,
        rsi_percent_incr_threshold,
        rsi_trend_span,
        trailing_stop_loss,
    )
    back_tester = BackTester(
        strat,
        crypto_currency_codes,
        buy_power,
        span=span,
        wait_time=wait_time,
    )
    return back_tester.run(
        start_dt=start_dt,
        end_dt=end_dt,
        save_data=False,
        save_graph=False,
        debug=False,
        prev_holdings=prev_holdings,
    )


class Parameters(BaseModel):
    p_diff: float
    vol_window: int
    indicator_length: int
    rsi_buy_threshold: float
    rsi_sell_threshold: float
    rsi_percent_incr_threshold: float
    rsi_trend_span: int
    trailing_stop_loss: float
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
            p_diff=0.02,
            vol_window=18,
            indicator_length=20,
            rsi_buy_threshold=55,
            rsi_sell_threshold=80,
            rsi_percent_incr_threshold=0.1,
            rsi_trend_span=5,
            trailing_stop_loss=0.05,
            span=50,
            wait_time=45,
        )


if __name__ == "__main__":
    dt_now = datetime.now()
    start_dt = dt_now - timedelta(days=7)
    end_dt = dt_now
    params = load_best_study_parameters(start_dt, end_dt)
    crypto_currency_codes = ["DOGE", "SHIB"]

    # Modifications
    params.trailing_stop_loss = 0.005
    params.wait_time = 1

    strat_def = FibVolRsiStrategy
    max_amount_per_order = 100
    max_holding_per_currency = 500
    buy_power = 1_000

    conduct_back_test(
        strat_def,
        max_amount_per_order,
        max_holding_per_currency,
        params.p_diff,
        params.vol_window,
        params.indicator_length,
        params.rsi_buy_threshold,
        params.rsi_sell_threshold,
        params.rsi_percent_incr_threshold,
        params.rsi_trend_span,
        params.trailing_stop_loss,
        crypto_currency_codes,
        buy_power,
        params.span,
        params.wait_time,
        start_dt=datetime(2024, 2, 1),
        end_dt=datetime(2024, 2, 2),
    )
