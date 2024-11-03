from typing import Generator, List
from tqdm import tqdm
from StratDaemon.models.crypto import CryptoHistorical, CryptoOrder
from StratDaemon.strats.base import BaseStrategy
from StratDaemon.strats.fib_vol import FibVolStrategy
from test_models import Portfolio
from fake_broker import FakeBroker
from pandera.typing import DataFrame
from math import isclose
import plotly.express as px

DEFAULT_BROKER = FakeBroker()


class BackTester:
    def __init__(self, strat: BaseStrategy, currency_code: str, buy_power: float):
        self.strat = strat
        self.broker = DEFAULT_BROKER
        self.currency_code = currency_code
        self.buy_power = buy_power
        self.strat_name = self.strat.name.split("_")[0]
        self.all_data = self.broker.get_crypto_historical(
            self.currency_code, "hour", pull_from_api=False
        )
        self.span = 24

    def save_portfolio(self, portfolio_hist: List[Portfolio]) -> None:
        fig = px.line(
            x=[p.timestamp for p in portfolio_hist], y=[p.value for p in portfolio_hist]
        )
        fig.write_image(f"{self.currency_code}_{self.strat_name}_backtest.png")

    def run(self, constrict_range: int | None = None) -> List[Portfolio]:
        portfolio_hist: List[Portfolio] = []
        num_buy_trades = num_sell_trades = 0
        print(f"Starting with ${self.buy_power}")

        for df in tqdm(
            self.get_data_by_interval(self.span, constrict_range),
            desc=f"Backtesting {self.currency_code} with {self.strat_name} strategy",
            total=(
                len(self.all_data) - self.span
                if constrict_range is None
                else constrict_range
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
            prev_portfolio = portfolio_hist[-1]

            for order in orders:
                num_buy_trades += order.side == "buy"
                num_sell_trades += order.side == "sell"
                cur_portfolio = self.process_order(df, order, prev_portfolio)
                portfolio_hist.append(cur_portfolio)

        print(
            f"Ending with ${round(portfolio_hist[-1].value, 2)} after {num_buy_trades} "
            f"buy trades and {num_sell_trades} sell trades over "
            f"{round(constrict_range / self.span, 2) if constrict_range is not None else round((len(self.all_data) - self.span) / self.span, 2)} days"
        )
        return portfolio_hist

    def process_order(
        self,
        df: DataFrame[CryptoHistorical],
        order: CryptoOrder,
        prev_portfolio: Portfolio,
    ) -> Portfolio:
        cur_portfolio = Portfolio(
            value=prev_portfolio.value,
            buy_power=prev_portfolio.buy_power,
            timestamp=df.iloc[-1].timestamp,
        )
        cur_price = df.iloc[-1].close
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
            order.quantity = order.quantity * (order.amount / prev_order_amt)
            cur_portfolio.buy_power -= order.amount
            cur_holdings.append(order)

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
            cur_portfolio.buy_power += sell_amount

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
        self, span: int, constrict_range: int | None = None
    ) -> Generator[DataFrame[CryptoHistorical], None, None]:
        # FIXME: Implement a more efficient way of getting data by interval
        n = len(self.all_data)
        start_idx = span if constrict_range is None else n - constrict_range
        for i in range(start_idx, n):
            yield self.all_data.iloc[i - span + 1 : i + 1]


if __name__ == "__main__":
    strat = FibVolStrategy(
        broker=DEFAULT_BROKER,
        notif=None,
        conf=None,
        currency_codes=["DOGE"],
        auto_generate_orders=True,
        max_amount_per_order=100,
        paper_trade=False,
        confirm_before_trade=False,
    )
    back_tester = BackTester(strat, "DOGE", 1000)
    hist = back_tester.run(constrict_range=1_000)
    back_tester.save_portfolio(hist)
