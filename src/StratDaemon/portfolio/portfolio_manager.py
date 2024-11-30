from collections import defaultdict
from math import isclose
from typing import Dict, List, Tuple
from pandera.typing import DataFrame
from datetime import datetime

from StratDaemon.models.crypto import CryptoHistorical, CryptoOrder, Portfolio


class PortfolioManager:
    def __init__(
        self,
        currency_codes: List[str],
        buy_power: float,
        initial_timestamp: datetime | None = None,
    ):
        self.initial_buy_power = buy_power
        self.transaction_fee = 0.01
        self.currency_codes = currency_codes
        self.num_buy_trades = self.num_sell_trades = 0
        self.portfolio_hist = [
            Portfolio(
                value=buy_power,
                buy_power=buy_power,
                timestamp=initial_timestamp or datetime.now(),
            )
        ]

    def process_order(
        self,
        dt_dfs: Dict[str, DataFrame[CryptoHistorical]],
        order: CryptoOrder,
    ) -> List[CryptoOrder]:
        prev_portfolio = self.portfolio_hist[-1]

        cur_prices_dt = {
            currency_code: dt_dfs[currency_code].iloc[-1].close
            for currency_code in self.currency_codes
        }
        dt = dt_dfs[next(iter(dt_dfs))].iloc[-1].timestamp
        cur_portfolio = Portfolio(
            value=prev_portfolio.value,
            buy_power=prev_portfolio.buy_power,
            timestamp=dt,
        )
        cur_holdings, executed_orders = getattr(self, f"handle_{order.side}_order")(
            cur_prices_dt, order, prev_portfolio, cur_portfolio
        )
        cur_portfolio.holdings = cur_holdings

        cur_portfolio.value = self.calculate_portfolio_value(
            cur_portfolio, cur_prices_dt
        )
        self.portfolio_hist.append(cur_portfolio)
        return executed_orders

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
    ) -> Tuple[List[CryptoOrder], List[CryptoOrder]]:
        cur_holdings = prev_portfolio.holdings
        executed_orders = []

        if not self.is_zero(cur_portfolio.buy_power):
            order.amount = min(order.amount, cur_portfolio.buy_power)
            cur_portfolio.buy_power -= order.amount

            order.amount = order.amount * (1 - self.transaction_fee)
            order.quantity = order.amount / order.asset_price

            executed_orders.append(order)
            cur_holdings.append(order)
            self.num_buy_trades += 1

        return cur_holdings, executed_orders

    def handle_sell_order(
        self,
        cur_prices_dt: Dict[str, float],
        order: CryptoOrder,
        prev_portfolio: Portfolio,
        cur_portfolio: Portfolio,
    ) -> Tuple[List[CryptoOrder], List[CryptoOrder]]:
        cur_holdings = prev_portfolio.holdings
        currency_code = order.currency_code
        executed_orders = []

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
            executed_orders.append(order)
            self.num_sell_trades += 1

            if self.is_zero(order.amount):
                break

        return [
            holding for holding in cur_holdings if not self.is_zero(holding.amount)
        ], executed_orders

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
