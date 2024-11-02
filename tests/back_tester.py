from typing import Generator, List
from devtools import pprint
from tqdm import tqdm
from StratDaemon.models.crypto import CryptoHistorical, CryptoOrder
from StratDaemon.strats.base import BaseStrategy
from StratDaemon.strats.fib_vol import FibVolStrategy
from test_models import Portfolio
from fake_broker import FakeBroker
from pandera.typing import DataFrame
from math import isclose
from copy import deepcopy

DEFAULT_BROKER = FakeBroker()


class BackTester:
    def __init__(self, strat: BaseStrategy, currency_code: str, buy_power: float):
        self.strat = strat
        self.broker = DEFAULT_BROKER
        self.currency_code = currency_code
        self.buy_power = buy_power
        self.all_data = self.broker.get_crypto_historical(
            self.currency_code, "hour", pull_from_api=False
        )
        self.span = 24

    def run(self):
        portfolio_hist = [Portfolio(value=self.buy_power, buy_power=self.buy_power)]
        print(f"Starting with ${self.buy_power}")

        for df in tqdm(
            self.get_data_by_interval(self.span),
            desc=f"Backtesting {self.currency_code} with {self.strat.name.split('_')[0]} strategy",
            total=len(self.all_data) - self.span,
        ):
            input_dt_dfs = {self.currency_code: df}
            orders = self.strat.execute(input_dt_dfs, print_orders=False)
            prev_portfolio = portfolio_hist[-1]

            for order in orders:
                cur_portfolio = self.process_order(order, prev_portfolio)
                portfolio_hist.append(cur_portfolio)

        print(f"Ending with ${portfolio_hist[-1].value}")
        return portfolio_hist

    def process_order(self, order: CryptoOrder, prev_portfolio: Portfolio) -> Portfolio:
        cur_portfolio = Portfolio(
            value=prev_portfolio.value,
            buy_power=prev_portfolio.buy_power,
        )
        cur_holdings = getattr(self, f"handle_{order.side}_order")(
            order, prev_portfolio, cur_portfolio, cur_holdings
        )
        cur_portfolio.holdings = cur_holdings
        cur_portfolio.value = self.calculate_portfolio_value(cur_portfolio)
        return cur_portfolio

    def calculate_portfolio_value(self, portfolio: Portfolio) -> float:
        cur_price = self.broker.get_crypto_latest(self.currency_code)
        holdings_value = portfolio.buy_power + sum(
            holding.quantity * cur_price for holding in portfolio.holdings
        )
        return holdings_value

    def handle_buy_order(
        self,
        order: CryptoOrder,
        prev_portfolio: Portfolio,
        cur_portfolio: Portfolio,
    ) -> List[CryptoOrder]:
        # FIXME: Implement a more efficient way of copying holdings
        cur_holdings = deepcopy(prev_portfolio.holdings)

        if not self.is_zero(order.limit_price):
            order.amount = min(order.amount, prev_portfolio.buy_power)
            cur_portfolio.buy_power -= order.amount
            cur_holdings.append(order)

        return cur_holdings

    def handle_sell_order(
        self,
        order: CryptoOrder,
        prev_portfolio: Portfolio,
        cur_portfolio: Portfolio,
    ) -> List[CryptoOrder]:
        cur_holdings = deepcopy(prev_portfolio.holdings)

        if self.get_total_amt(cur_holdings) < order.amount:
            return

        for holding in cur_holdings:
            sell_amount = min(holding.amount, order.amount)
            holding.amount -= sell_amount
            order.amount -= sell_amount

            if self.is_zero(order.amount):
                break

        cur_portfolio.buy_power += order.amount

        return [holding for holding in cur_holdings if not self.is_zero(holding.amount)]

    def is_zero(self, num: float) -> bool:
        return isclose(num, 0, abs_tol=1)

    def get_total_amt(self, holdings: List[CryptoOrder]) -> float:
        return sum(holding.amount for holding in holdings)

    def get_data_by_interval(
        self, span: int
    ) -> Generator[DataFrame[CryptoHistorical], None, None]:
        # FIXME: Implement a more efficient way of getting data by interval
        for i in range(span, len(self.all_data)):
            yield self.all_data.iloc[i - span + 1 : i + 1]


if __name__ == "__main__":
    strat = FibVolStrategy(
        broker=DEFAULT_BROKER,
        notif=None,
        conf=None,
        currency_codes=["DOGE"],
        auto_generate_orders=True,
        max_amount_per_order=100,
        paper_trade=True,
        confirm_before_trade=False,
    )
    back_tester = BackTester(strat, "DOGE", 1000)
    hist = back_tester.run()
    pprint(hist[-1])
