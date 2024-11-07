from datetime import datetime
import itertools
from typing import Generator, List, Dict
import pandas as pd
from tqdm import tqdm
from StratDaemon.models.crypto import CryptoHistorical, CryptoOrder
from StratDaemon.strats.fib_vol import FibVolStrategy
from test_models import Portfolio
from StratDaemon.integration.broker.crypto_compare import CryptoCompareBroker
from pandera.typing import DataFrame
from math import isclose
import plotly.express as px
import os
from more_itertools import numeric_range

DEFAULT_BROKER = CryptoCompareBroker()


class BackTester:
    def __init__(
        self,
        strat: FibVolStrategy,
        currency_codes: List[str],
        buy_power: float,
        span: int = 30,
        wait_time: int = 5,
        input_dt_dfs: Dict[str, DataFrame[CryptoHistorical]] | None = None,
    ) -> None:
        self.strat = strat
        self.broker = DEFAULT_BROKER
        self.currency_codes = currency_codes
        self.buy_power = buy_power
        self.strat_name = self.strat.name.split("_")[0]
        self.all_data_dfs = [
            self.broker.get_crypto_historical(
                currency_code, "hour", pull_from_api=False
            )
            for currency_code in self.currency_codes
        ]
        self.input_dt_dfs = input_dt_dfs
        self.span = span
        self.transaction_fee = 0
        self.wait_time = wait_time

    def ensure_data_dfs_consistent(self) -> None: ...

    def save_portfolio(
        self, portfolio_hist: List[Portfolio], num_buy_trades: int, num_sell_trades: int
    ) -> None:
        fig = px.line(
            x=[p.timestamp for p in portfolio_hist], y=[p.value for p in portfolio_hist]
        )
        fig.write_image(
            f"results/"
            f"{'_'.join(crypto_currency_codes)}_{self.strat_name}_{self.strat.percent_diff_threshold}"
            f"_{self.strat.vol_window_size}_backtest.png"
        )
        csv_path = "results/performance.csv"

        if not os.path.exists(csv_path):
            with open(csv_path, "w") as f:
                f.write(
                    "currency_codes,strategy_name,percent_diff_threshold,span,wait_time,risk_factor,"
                    "vol_window_size,final_value,num_buy_trades,num_sell_trades\n"
                )

        with open(csv_path, "a") as f:
            f.write(
                f"{'|'.join(crypto_currency_codes)},{self.strat_name},"
                f"{self.strat.percent_diff_threshold},{self.span},{self.wait_time},{self.strat.risk_factor},"
                f"{self.strat.vol_window_size},"
                f"{portfolio_hist[-1].value},{num_buy_trades},"
                f"{num_sell_trades}\n"
            )

    def run(
        self,
        constrict_range: int | None = None,
        save_data: bool = False,
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

            import pdb

            pdb.set_trace()
            input_dt_dfs = list(zip(self.currency_codes, dfs))
            orders = self.strat.execute(input_dt_dfs, print_orders=False)
            assert (
                len(orders) <= 1
            ), "Only one order (or none) should be generated per interval"
            prev_portfolio = portfolio_hist[-1]

            for order in orders:
                cur_portfolio = self.process_order(dfs, order, prev_portfolio)
                portfolio_hist.append(cur_portfolio)

        cur_portfolio = Portfolio(
            timestamp=datetime.now(),
            value=prev_portfolio.value,
            buy_power=prev_portfolio.buy_power,
            holdings=prev_portfolio.holdings,
        )
        cur_portfolio.value = self.calculate_portfolio_value(
            cur_portfolio,
            {
                currency_code: self.input_dt_dfs[currency_code].iloc[-1].close
                for currency_code in self.currency_codes
            },
        )
        portfolio_hist.append(cur_portfolio)

        print(
            f"Ending with ${round(portfolio_hist[-1].value, 2)} after {self.num_buy_trades} "
            f"buy trades and {self.num_sell_trades} sell trades over "
            f"{constrict_range if constrict_range is not None else len(self.all_data) - self.span} minutes"
            f" making trades every {wait_time} minute"
            f" with percent_diff_threshold={self.strat.percent_diff_threshold}"
            f" and vol_window_size={self.strat.vol_window_size}"
            f" and span={self.span}"
            f" and wait_time={self.wait_time}"
            f" and risk_factor={self.strat.risk_factor}"
        )

        if save_data:
            self.save_portfolio(
                portfolio_hist, self.num_buy_trades, self.num_sell_trades
            )
        return portfolio_hist

    def find_closest_price(self, dt: pd.Timestamp, currency_code: str) -> float:
        input_df = self.input_dt_dfs[currency_code]
        nxt_data = input_df[input_df["timestamp"] >= dt]

        if len(nxt_data) > 0:
            return nxt_data.iloc[0].close

        raise ValueError("Timestamp not found in input_df")

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
            currency_code: self.find_closest_price(dt, currency_code)
            for currency_code in self.currency_codes
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
        # FIXME: Implement a working way of copying holdings
        cur_holdings = prev_portfolio.holdings

        if not self.is_zero(cur_portfolio.buy_power):
            prev_order_amt = order.amount
            order.amount = min(prev_order_amt, cur_portfolio.buy_power)
            order.amount = order.amount * (1 - self.transaction_fee)
            order.quantity *= order.amount / prev_order_amt
            cur_portfolio.buy_power -= prev_order_amt
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
        # FIXME: Implement a working way of copying holdings
        cur_holdings = prev_portfolio.holdings

        # This also updates the amount of each holding
        if self.get_total_holdings_amt(cur_prices_dt, cur_holdings) < order.amount:
            return cur_holdings

        for holding in cur_holdings:
            sell_amount = min(holding.amount, order.amount)
            holding.amount -= sell_amount
            order.amount -= sell_amount
            cur_portfolio.buy_power += sell_amount * (1 - self.transaction_fee)
            self.num_sell_trades += 1

            if self.is_zero(order.amount):
                break

        return [holding for holding in cur_holdings if not self.is_zero(holding.amount)]

    def is_zero(self, num: float) -> bool:
        return isclose(num, 0, abs_tol=1)

    def get_total_holdings_amt(
        self, cur_prices_dt: Dict[str, float], holdings: List[CryptoOrder]
    ) -> float:
        s = 0
        for holding in holdings:
            holding.amount = holding.quantity * cur_prices_dt[holding.currency_code]
            s += holding.amount
        return s

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


if __name__ == "__main__":
    # p_diff_thresholds = [0.008, 0.009, 0.01, 0.02, 0.03, 0.05]
    # p_diff_thresholds = numeric_range(0.003, 0.006, 0.001)
    p_diff_thresholds = [0.1]
    # vol_window_sizes = [1, 5, 10, 50]
    vol_window_sizes = [10]
    spans = [30]
    crypto_currency_codes = ["DOGE", "SHIB", "ETH", "LINK"]
    wait_times = [15]
    # risk_factors = list(numeric_range(0.05, 0.3, 0.05)) + list(
    #     numeric_range(0.3, 0.6, 0.1))
    risk_factors = [0.5]
    buy_power = 1_000

    input_dt_dfs = {
        crypto_currency_code: pd.read_json(
            f"rh_{crypto_currency_code}_historical_data.json"
        )
        for crypto_currency_code in crypto_currency_codes
    }

    for p_diff, vol_window, span, wait_time, risk_factor in itertools.product(
        p_diff_thresholds, vol_window_sizes, spans, wait_times, risk_factors
    ):
        strat = FibVolStrategy(
            broker=DEFAULT_BROKER,
            notif=None,
            conf=None,
            currency_codes=crypto_currency_codes,
            auto_generate_orders=True,
            max_amount_per_order=100,
            paper_trade=False,
            confirm_before_trade=False,
            percent_diff_threshold=p_diff,
            vol_window_size=vol_window,
            risk_factor=risk_factor,
            buy_power=buy_power,
        )
        back_tester = BackTester(
            strat,
            crypto_currency_codes,
            buy_power,
            input_dt_dfs=input_dt_dfs,
            span=span,
            wait_time=wait_time,
        )
        back_tester.run(constrict_range=24 * 60, save_data=True)
