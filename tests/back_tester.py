from datetime import datetime
import itertools
from typing import Generator, List, Dict, Tuple
from devtools import pprint
import pandas as pd
from tqdm import tqdm
from StratDaemon.models.crypto import CryptoHistorical, CryptoOrder
from StratDaemon.strats.base import BaseStrategy
from StratDaemon.strats.fib_vol import FibVolStrategy
from StratDaemon.strats.fib_vol_rsi import FibVolRsiStrategy
from test_models import Portfolio
from StratDaemon.integration.broker.crypto_compare import CryptoCompareBroker
from StratDaemon.integration.broker.kraken import KrakenBroker
from pandera.typing import DataFrame
from math import isclose
import plotly.express as px
import os
from more_itertools import numeric_range
import numpy as np
from collections import Counter, defaultdict

# DEFAULT_BROKER = KrakenBroker()
DEFAULT_BROKER = CryptoCompareBroker()
CONSTRICT_RANGE = None
SAVE_GRAPH = False


class BackTester:
    def __init__(
        self,
        strat: FibVolRsiStrategy | FibVolStrategy,
        currency_codes: List[str],
        buy_power: float,
        span: int = 30,
        wait_time: int = 5,
    ) -> None:
        self.strat = strat
        self.broker = DEFAULT_BROKER
        self.currency_codes = currency_codes
        self.buy_power = buy_power
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
        self.transaction_fee = 0.01
        self.wait_time = wait_time
        self.crypto_currency_codes = currency_codes
        self.sanity_checks()

    def sanity_checks(self) -> None:
        assert len(self.currency_codes) == len(
            self.all_data_dfs
        ), "Currency codes and data must be of the same length"
        assert all(
            len(df) == len(self.all_data_dfs[0]) for df in self.all_data_dfs
        ), "All dataframes must have the same length in all_data_dfs"

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
        save_graph: bool = True,
    ) -> None:
        strat_rsi_buy_threshold = getattr(self.strat, "rsi_buy_threshold", -1)
        strat_rsi_sell_threshold = getattr(self.strat, "rsi_sell_threshold", -1)
        strat_rsi_percent_incr_threshold = getattr(
            self.strat, "rsi_percent_incr_threshold", -1
        )
        strat_rsi_trend_span = getattr(self.strat, "rsi_trend_span", -1)

        if save_graph:
            fig = px.line(
                x=[p.timestamp for p in portfolio_hist],
                y=[p.value for p in portfolio_hist],
            )
            fig.write_image(
                f"results/"
                f"{'_'.join(self.crypto_currency_codes)}_{self.strat_name}_{self.strat.percent_diff_threshold}"
                f"_{self.span}_{self.wait_time}_{self.strat.risk_factor}"
                f"_{strat_rsi_buy_threshold}_{strat_rsi_sell_threshold}"
                f"_{self.strat.indicator_length}"
                f"_{self.strat.vol_window_size}_backtest.png"
            )

        csv_path = "results/performance.csv"
        if not os.path.exists(csv_path):
            with open(csv_path, "w") as f:
                f.write(
                    "currency_codes,strategy_name,percent_diff_threshold,span,wait_time,risk_factor,"
                    "rsi_buy_threshold,rsi_sell_threshold,rsi_percent_incr_threshold,"
                    "rsi_trend_span,indicator_length,"
                    "vol_window_size,final_value,num_buy_trades,num_sell_trades\n"
                )

        with open(csv_path, "a") as f:
            f.write(
                f"{'|'.join(self.crypto_currency_codes)},{self.strat_name},"
                f"{self.strat.percent_diff_threshold},{self.span},{self.wait_time},{self.strat.risk_factor},"
                f"{strat_rsi_buy_threshold},{strat_rsi_sell_threshold},{strat_rsi_percent_incr_threshold},"
                f"{strat_rsi_trend_span},{self.strat.indicator_length},"
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
        constrict_range: int | None = None,
        save_data: bool = False,
        save_graph: bool = False,
        debug: bool = False,
    ) -> List[Portfolio]:
        portfolio_hist: List[Portfolio] = []
        self.num_buy_trades = self.num_sell_trades = 0
        print(f"Starting with ${self.buy_power}")

        for dfs in tqdm(
            self.get_data_by_interval(self.span, constrict_range, self.wait_time),
            desc=f"Backtesting {'|'.join(self.currency_codes)} cryptos with {self.strat_name} strategy",
            total=(
                (len(self.all_data_dfs[0]) // self.wait_time) - self.span
                if constrict_range is None
                else constrict_range // self.wait_time
            ),
        ):
            if len(portfolio_hist) == 0:
                portfolio_hist.append(
                    Portfolio(
                        value=self.buy_power,
                        buy_power=self.buy_power,
                        timestamp=dfs[0].iloc[-2].timestamp,
                    )
                )

            assert all(
                len(df) == len(dfs[0]) == self.span for df in dfs
            ), "All dataframes must have the same length as the span"

            input_dt_dfs = {
                currency_code: df for currency_code, df in zip(self.currency_codes, dfs)
            }
            orders = self.strat.execute(
                input_dt_dfs, print_orders=debug, save_positions=False
            )

            cnts = Counter()
            for order in orders:
                cnts[order.currency_code] += 1
            assert all(
                cnt <= 1 for cnt in cnts.values()
            ), "Only one order (or none) should be generated per cryptocurrency per interval"

            prev_portfolio = portfolio_hist[-1]

            for order in orders:
                cur_portfolio = self.process_order(dfs, order, prev_portfolio)
                prev_portfolio = cur_portfolio
            portfolio_hist.append(cur_portfolio)

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
        cur_portfolio.value = self.calculate_portfolio_value(
            cur_portfolio,
            cur_prices_dt,
        )
        portfolio_hist.append(cur_portfolio)

        print(
            f"Ending with ${round(cur_portfolio.value, 2)} after {self.num_buy_trades} "
            f"buy trades and {self.num_sell_trades} sell trades over "
            f"{constrict_range if constrict_range is not None else len(self.all_data_dfs[0]) - self.span} minutes"
            f" making trades every {self.wait_time} minutes"
            f" with percent_diff_threshold={self.strat.percent_diff_threshold}"
            f" and vol_window_size={self.strat.vol_window_size}"
            f" and span={self.span}"
            f" and risk_factor={self.strat.risk_factor}"
            f" and rsi_buy_threshold={getattr(self.strat, 'rsi_buy_threshold', -1)}"
            f" and rsi_sell_threshold={getattr(self.strat, 'rsi_sell_threshold', -1)}"
            f" and rsi_percent_incr_threshold={getattr(self.strat, 'rsi_percent_incr_threshold', -1)}"
            f" and rsi trend span={getattr(self.strat, 'rsi_trend_span', -1)}"
            f" and indicator_length={self.strat.indicator_length}"
        )

        print(f"Buy power left: ${cur_portfolio.buy_power}")
        self.print_agg_holdings(cur_portfolio.holdings, cur_prices_dt)

        if save_data:
            self.save_portfolio(
                portfolio_hist,
                self.num_buy_trades,
                self.num_sell_trades,
                save_graph=save_graph,
            )
        return portfolio_hist, self.num_buy_trades, self.num_sell_trades

    def process_order(
        self,
        dfs: List[DataFrame[CryptoHistorical]],
        order: CryptoOrder,
        prev_portfolio: Portfolio,
    ) -> Portfolio:
        dt = dfs[0].iloc[-1].timestamp
        cur_portfolio = Portfolio(
            value=prev_portfolio.value,
            buy_power=prev_portfolio.buy_power,
            timestamp=dt,
        )
        cur_prices_dt = {
            currency_code: dfs[i].iloc[-1].close
            for i, currency_code in enumerate(self.currency_codes)
        }

        cur_holdings = getattr(self, f"handle_{order.side}_order")(
            cur_prices_dt, order, prev_portfolio, cur_portfolio
        )
        cur_portfolio.holdings = cur_holdings

        cur_portfolio.value = self.calculate_portfolio_value(
            cur_portfolio, cur_prices_dt
        )
        return cur_portfolio

    def calculate_portfolio_value(
        self, portfolio: Portfolio, cur_prices_dt: Dict[str, float]
    ) -> float:
        holdings_value = portfolio.buy_power + sum(
            holding.quantity * cur_prices_dt[holding.currency_code]
            for holding in portfolio.holdings
        )
        return holdings_value

    def handle_buy_order(
        self,
        _: float,
        order: CryptoOrder,
        prev_portfolio: Portfolio,
        cur_portfolio: Portfolio,
    ) -> List[CryptoOrder]:
        cur_holdings = prev_portfolio.holdings

        if not self.is_zero(cur_portfolio.buy_power):
            order.amount = min(order.amount, cur_portfolio.buy_power)
            cur_portfolio.buy_power -= order.amount

            order.amount = order.amount * (1 - self.transaction_fee)
            order.quantity = order.amount / order.asset_price

            cur_holdings.append(order)
            self.num_buy_trades += 1

        return cur_holdings

    def handle_sell_order(
        self,
        cur_prices_dt: Dict[str, float],
        order: CryptoOrder,
        prev_portfolio: Portfolio,
        cur_portfolio: Portfolio,
    ) -> List[CryptoOrder]:
        cur_holdings = prev_portfolio.holdings
        currency_code = order.currency_code

        # This also updates the amount of each holding
        total_holdings_amt = self.get_total_holdings_amt(cur_prices_dt, cur_holdings)
        order.amount = min(order.amount, sum(total_holdings_amt[currency_code]))

        for holding in cur_holdings:
            if holding.currency_code != order.currency_code:
                continue

            sell_amount = min(holding.amount, order.amount)
            holding.amount -= sell_amount
            order.amount -= sell_amount
            holding.quantity -= sell_amount / cur_prices_dt[currency_code]
            cur_portfolio.buy_power += sell_amount * (1 - self.transaction_fee)
            self.num_sell_trades += 1

            if self.is_zero(order.amount):
                break

        return [holding for holding in cur_holdings if not self.is_zero(holding.amount)]

    def is_zero(self, num: float) -> bool:
        return isclose(num, 0, abs_tol=1)

    def get_total_holdings_amt(
        self, cur_prices_dt: Dict[str, float], holdings: List[CryptoOrder]
    ) -> Dict[str, List[float]]:
        total_holdings = defaultdict(list)
        for holding in holdings:
            currency_code = holding.currency_code
            holding.amount = holding.quantity * cur_prices_dt[currency_code]
            total_holdings[currency_code].append(holding.amount)
        return total_holdings

    def get_data_by_interval(
        self, span: int, constrict_range: int | None = None, wait_time: int = 0
    ) -> Generator[DataFrame[CryptoHistorical], None, None]:
        # FIXME: Implement a more efficient way of getting data by interval
        n = len(self.all_data_dfs[0])
        start_idx = span if constrict_range is None else n - constrict_range
        if constrict_range is not None:
            assert (
                n > constrict_range
            ), "Start index must be less than the length of the data"
        for i in range(start_idx, n, wait_time):
            yield [df[i - span + 1 : i + 1] for df in self.all_data_dfs]


def create_strat(
    strat: BaseStrategy,
    crypto_currency_codes: List[str],
    buy_power: float,
    max_amount_per_order: float,
    max_holding_per_currency: float,
    p_diff: float,
    vol_window: int,
    risk_factor: float,
    indicator_length: int,
    rsi_buy_threshold: float,
    rsi_sell_threshold: float,
    rsi_percent_incr_threshold: float,
    rsi_trend_span: int,
) -> BaseStrategy:
    return strat(
        broker=DEFAULT_BROKER,
        notif=None,
        conf=None,
        currency_codes=crypto_currency_codes,
        auto_generate_orders=True,
        max_amount_per_order=max_amount_per_order,
        paper_trade=False,
        confirm_before_trade=False,
        percent_diff_threshold=p_diff,
        vol_window_size=vol_window,
        risk_factor=risk_factor,
        buy_power=buy_power,
        max_holding_per_currency=max_holding_per_currency,
        indicator_length=indicator_length,
        rsi_buy_threshold=rsi_buy_threshold,
        rsi_sell_threshold=rsi_sell_threshold,
        rsi_percent_incr_threshold=rsi_percent_incr_threshold,
        rsi_trend_span=rsi_trend_span,
    )


def conduct_back_test(
    strat_def: BaseStrategy,
    max_amount_per_order: float,
    max_holding_per_currency: float,
    p_diff: float,
    vol_window: int,
    risk_factor: float,
    indicator_length: int,
    rsi_buy_threshold: float,
    rsi_sell_threshold: float,
    rsi_percent_incr_threshold: float,
    rsi_trend_span: int,
    crypto_currency_codes: List[str],
    buy_power: float,
    span: int,
    wait_time: int,
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
        risk_factor,
        indicator_length,
        rsi_buy_threshold,
        rsi_sell_threshold,
        rsi_percent_incr_threshold,
        rsi_trend_span,
    )
    back_tester = BackTester(
        strat,
        crypto_currency_codes,
        buy_power,
        span=span,
        wait_time=wait_time,
    )
    return back_tester.run(
        constrict_range=CONSTRICT_RANGE,
        save_data=True,
        debug=False,
        save_graph=SAVE_GRAPH,
    )


if __name__ == "__main__":
    # p_diff_thresholds = [0.008, 0.009, 0.01, 0.02, 0.03, 0.05]
    # p_diff_thresholds = numeric_range(0.003, 0.011, 0.001)
    # p_diff_thresholds = numeric_range(0.02, 0.11, 0.01)
    # p_diff_thresholds = numeric_range(0.005, 0.05, 0.001)
    p_diff_thresholds = [0.02]
    # vol_window_sizes = [10]
    crypto_currency_codes = ["DOGE", "SHIB"]
    # crypto_currency_codes = ["SHIB"]
    wait_times = [45]
    # risk_factors = list(numeric_range(0.05, 0.3, 0.05)) + list(
    #     numeric_range(0.3, 0.6, 0.1))
    risk_factors = [0.1]
    buy_power = 1_000
    max_amount_per_order = 100
    max_holding_per_currency = 500

    # span, indicator_length, vol_window_size
    interval_inputs = [(50, 20, 18)]

    # rsi_percent_incr_thresholds = numeric_range(0.01, 0.4, 0.01)
    rsi_percent_incr_thresholds = [0.1]
    # rsi_trend_spans = list(range(5, 20))
    rsi_trend_spans = [5]

    rsi_buy_thresholds = [55]
    rsi_sell_thresholds = [80]

    strats_def = [
        FibVolRsiStrategy,
        # FibVolStrategy
    ]

    for (
        strat_def,
        p_diff,
        wait_time,
        risk_factor,
        (span, indicator_length, vol_window),
        rsi_buy_threshold,
        rsi_sell_threshold,
        rsi_percent_incr_threshold,
        rsi_trend_span,
    ) in itertools.product(
        strats_def,
        p_diff_thresholds,
        wait_times,
        risk_factors,
        interval_inputs,
        rsi_buy_thresholds,
        rsi_sell_thresholds,
        rsi_percent_incr_thresholds,
        rsi_trend_spans,
    ):
        conduct_back_test(
            strat_def,
            max_amount_per_order,
            max_holding_per_currency,
            p_diff,
            vol_window,
            risk_factor,
            indicator_length,
            rsi_buy_threshold,
            rsi_sell_threshold,
            rsi_percent_incr_threshold,
            rsi_trend_span,
            crypto_currency_codes,
            buy_power,
            span,
            wait_time,
        )
