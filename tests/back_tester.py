import itertools
from typing import Generator, List
import pandas as pd
from tqdm import tqdm
from StratDaemon.models.crypto import CryptoHistorical, CryptoOrder
from StratDaemon.strats.fib_vol import FibVolStrategy
from test_models import Portfolio
from fake_broker import FakeBroker
from pandera.typing import DataFrame
from math import isclose
import plotly.express as px
import os
from more_itertools import numeric_range

DEFAULT_BROKER = FakeBroker()


class BackTester:
    def __init__(
        self,
        strat: FibVolStrategy,
        currency_code: str,
        buy_power: float,
        span: int = 30,
        wait_time: int = 5,
        input_df: DataFrame[CryptoHistorical] | None = None,
    ) -> None:
        self.strat = strat
        self.broker = DEFAULT_BROKER
        self.currency_code = currency_code
        self.buy_power = buy_power
        self.strat_name = self.strat.name.split("_")[0]
        self.all_data = self.broker.get_crypto_historical(
            self.currency_code, "hour", pull_from_api=False
        )
        self.input_df = input_df
        self.span = span
        self.transaction_fee = 0.03
        self.wait_time = wait_time

    def save_portfolio(
        self, portfolio_hist: List[Portfolio], num_buy_trades: int, num_sell_trades: int
    ) -> None:
        fig = px.line(
            x=[p.timestamp for p in portfolio_hist], y=[p.value for p in portfolio_hist]
        )
        fig.write_image(
            f"results/"
            f"{self.currency_code}_{self.strat_name}_{self.strat.percent_diff_threshold}"
            f"_{self.strat.vol_window_size}_backtest.png"
        )
        csv_path = "results/performance.csv"

        if not os.path.exists(csv_path):
            with open(csv_path, "w") as f:
                f.write(
                    "currency_code,strategy_name,percent_diff_threshold,span,wait_time,risk_factor,"
                    "vol_window_size,final_value,num_buy_trades,num_sell_trades\n"
                )

        with open(csv_path, "a") as f:
            f.write(
                f"{self.currency_code},{self.strat_name},"
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

        for df in tqdm(
            self.get_data_by_interval(self.span, constrict_range, self.wait_time),
            desc=f"Backtesting {self.currency_code} with {self.strat_name} strategy",
            total=(
                (len(self.all_data) // self.wait_time) - self.span
                if constrict_range is None
                else constrict_range // self.wait_time
            ),
        ):
            if len(portfolio_hist) == 0:
                portfolio_hist.append(
                    Portfolio(
                        value=self.buy_power,
                        buy_power=self.buy_power,
                        timestamp=df.iloc[-2].timestamp,
                    )
                )

            input_dt_dfs = {self.currency_code: df}
            orders = self.strat.execute(input_dt_dfs, print_orders=False)
            assert (
                len(orders) <= 1
            ), "Only one order (or none) should be generated per interval"
            prev_portfolio = portfolio_hist[-1]

            for order in orders:
                cur_portfolio = self.process_order(df, order, prev_portfolio)
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

    def find_closest_price(self, dt: pd.Timestamp) -> float:
        nxt_data = self.input_df[self.input_df["timestamp"] >= dt]

        if len(nxt_data) > 0:
            return nxt_data.iloc[0].close

        raise ValueError("Timestamp not found in input_df")

    def process_order(
        self,
        df: DataFrame[CryptoHistorical],
        order: CryptoOrder,
        prev_portfolio: Portfolio,
    ) -> Portfolio:
        dt = df.iloc[-1].timestamp
        cur_portfolio = Portfolio(
            value=prev_portfolio.value,
            buy_power=prev_portfolio.buy_power,
            timestamp=dt,
        )
        # cur_price = df.iloc[-1].close
        cur_price = self.find_closest_price(dt)
        cur_holdings = getattr(self, f"handle_{order.side}_order")(
            cur_price, order, prev_portfolio, cur_portfolio
        )
        cur_portfolio.holdings = cur_holdings
        cur_portfolio.value = self.calculate_portfolio_value(cur_portfolio, cur_price)
        return cur_portfolio

    def calculate_portfolio_value(
        self, portfolio: Portfolio, cur_price: float
    ) -> float:
        holdings_value = portfolio.buy_power + sum(
            holding.quantity * cur_price for holding in portfolio.holdings
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
            order.quantity = order.quantity * (order.amount / prev_order_amt)
            cur_portfolio.buy_power -= order.amount
            cur_holdings.append(order)
            self.num_buy_trades += 1

        return cur_holdings

    def handle_sell_order(
        self,
        cur_price: float,
        order: CryptoOrder,
        prev_portfolio: Portfolio,
        cur_portfolio: Portfolio,
    ) -> List[CryptoOrder]:
        # FIXME: Implement a working way of copying holdings
        cur_holdings = prev_portfolio.holdings

        # This also updates the amount of each holding
        if self.get_total_holdings_amt(cur_price, cur_holdings) < order.amount:
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
        self, cur_price: float, holdings: List[CryptoOrder]
    ) -> float:
        s = 0
        for holding in holdings:
            holding.amount = holding.quantity * cur_price
            s += holding.amount
        return s

    def get_data_by_interval(
        self, span: int, constrict_range: int | None = None, wait_time: int = 0
    ) -> Generator[DataFrame[CryptoHistorical], None, None]:
        # FIXME: Implement a more efficient way of getting data by interval
        n = len(self.all_data)
        start_idx = span if constrict_range is None else n - constrict_range
        if constrict_range is not None:
            assert (
                n > constrict_range
            ), "Start index must be less than the length of the data"
        for i in range(start_idx, n, wait_time):
            yield self.all_data.iloc[i - span + 1 : i + 1]


if __name__ == "__main__":
    # p_diff_thresholds = [0.008, 0.009, 0.01, 0.02, 0.03, 0.05]
    # p_diff_thresholds = numeric_range(0.003, 0.006, 0.001)
    p_diff_thresholds = [0.005]
    # vol_window_sizes = [1, 5, 10, 50]
    vol_window_sizes = [10]
    spans = [30]
    crypto_currency_code = "DOGE"
    wait_times = [15]
    # risk_factors = list(numeric_range(0.05, 0.3, 0.05)) + list(
    #     numeric_range(0.3, 0.6, 0.1))
    risk_factors = [0.1]
    buy_power = 1_000

    df = pd.read_json(f"rh_{crypto_currency_code}_historical_data.json")

    for p_diff, vol_window, span, wait_time, risk_factor in itertools.product(
        p_diff_thresholds, vol_window_sizes, spans, wait_times, risk_factors
    ):
        strat = FibVolStrategy(
            broker=DEFAULT_BROKER,
            notif=None,
            conf=None,
            currency_codes=[crypto_currency_code],
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
            crypto_currency_code,
            buy_power,
            input_df=df,
            span=span,
            wait_time=wait_time,
        )
        back_tester.run(constrict_range=None, save_data=True)
