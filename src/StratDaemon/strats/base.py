import json
from pathlib import Path
from typing import Dict, List, Tuple
from StratDaemon.integration.broker.base import BaseBroker
from StratDaemon.integration.notification.base import BaseNotification
from StratDaemon.models.crypto import CryptoHistorical, CryptoLimitOrder, CryptoOrder
from pandera.typing import DataFrame, Series
from devtools import pprint
from StratDaemon.portfolio.portfolio_manager import PortfolioManager
from StratDaemon.utils.constants import (
    BUY_POWER,
    MAX_HOLDING_PER_CURRENCY,
    RH_HISTORICAL_INTERVAL,
    RH_HISTORICAL_SPAN,
    TRAILING_STOP_LOSS,
    TRAILING_TAKE_PROFIT,
)
from collections import defaultdict
from uuid import uuid4
from StratDaemon.utils.funcs import print_dt


class BaseStrategy:
    def __init__(
        self,
        name: str,
        broker: BaseBroker,
        notif: BaseNotification,
        currency_codes: List[str] = None,
        auto_generate_orders: bool = False,
        max_amount_per_order: float = 0.0,
        paper_trade: bool = False,
        buy_power: float = BUY_POWER,
        trailing_stop_loss: float = TRAILING_STOP_LOSS,
        trailing_take_profit: float = TRAILING_TAKE_PROFIT,
        max_holding_per_currency: float = MAX_HOLDING_PER_CURRENCY,
    ) -> None:
        self.name = name
        self.broker = broker
        self.notif = notif
        self.limit_orders: List[CryptoLimitOrder] = []
        self.currency_codes = currency_codes or []
        self.auto_generate_orders = auto_generate_orders
        self.max_amount_per_order = max_amount_per_order
        self.paper_trade = paper_trade
        self.max_holding_per_currency = max_holding_per_currency
        self.portfolio_mgr = PortfolioManager(
            currency_codes, buy_power, trailing_stop_loss, trailing_take_profit
        )
        self.path_to_positions = Path(f"{self.name}_{uuid4()}.json")

    def init(self) -> None:
        if self.paper_trade:
            print_dt(
                "Paper trading is enabled. Ensure below values are correct for correct simulation."
            )
        else:
            print_dt(
                "WARNING: Live trading is enabled. Ensure below values are correct for correct execution."
            )
        pprint(self.__dict__)

    def add_limit_order(self, order: CryptoLimitOrder):
        if self.auto_generate_orders:
            print_dt(
                "Auto-generating orders is enabled. It is recommended not to add limit orders manually."
            )
        self.limit_orders.append(order)

    def construct_dt_dfs(
        self, dt_dfs_input: Dict[str, DataFrame[CryptoHistorical]] | None
    ) -> Dict[str, DataFrame[CryptoHistorical]]:
        currency_codes = {order.currency_code for order in self.limit_orders}
        currency_codes.update(self.currency_codes)
        dt_dfs = dict()
        for currency_code in currency_codes:
            if dt_dfs_input is not None and currency_code in dt_dfs_input:
                df = dt_dfs_input[currency_code]
            else:
                df = self.broker.get_crypto_historical(
                    currency_code, RH_HISTORICAL_INTERVAL, RH_HISTORICAL_SPAN
                )
            df = self.transform_df(df)
            df = df.reset_index(drop=True)
            dt_dfs[currency_code] = df
        return dt_dfs

    def filter_orders(
        self,
        orders: List[CryptoLimitOrder],
        dt_dfs: Dict[str, DataFrame[CryptoHistorical]],
    ) -> Tuple[List[CryptoLimitOrder], List[Tuple[bool, bool]]]:
        filtered_orders: List[CryptoLimitOrder] = []
        order_signals = []
        orders_per_currency = defaultdict(list)

        for order in orders:
            orders_per_currency[order.currency_code].append(order)

        for currency_code, orders in orders_per_currency.items():
            df = dt_dfs[currency_code]
            if len(orders) > 2:
                raise ValueError(
                    f"Too many orders generated for {currency_code}: {len(orders)}"
                )
            elif len(orders) == 2:
                confident_signal_fst, risk_signal_fst = getattr(
                    self, f"execute_{orders[0].side}_condition"
                )(df, orders[0])
                confident_signal_snd, risk_signal_snd = getattr(
                    self, f"execute_{orders[1].side}_condition"
                )(df, orders[1])

                assert (not confident_signal_fst and not confident_signal_snd) or (
                    confident_signal_fst ^ confident_signal_snd
                ), "Confident signals for both orders cannot be True at the same time."

                assert (not risk_signal_fst and not risk_signal_snd) or (
                    risk_signal_fst ^ risk_signal_snd
                ), "Risk signals for both orders cannot be True at the same time."

                if confident_signal_fst:
                    filtered_orders.append(orders[0])
                    order_signals.append((confident_signal_fst, risk_signal_fst))
                elif confident_signal_snd:
                    filtered_orders.append(orders[1])
                    order_signals.append((confident_signal_snd, risk_signal_snd))
                elif risk_signal_fst:
                    filtered_orders.append(orders[0])
                    order_signals.append((confident_signal_fst, risk_signal_fst))
                elif risk_signal_snd:
                    filtered_orders.append(orders[1])
                    order_signals.append((confident_signal_snd, risk_signal_snd))
            elif len(orders) == 1:
                confident_signal, risk_signal = getattr(
                    self, f"execute_{orders[0].side}_condition"
                )(df, orders[0])
                order_signals.append((confident_signal, risk_signal))
                filtered_orders.append(orders[0])

        return filtered_orders, order_signals

    def execute(
        self,
        dt_dfs_input: Dict[str, DataFrame[CryptoHistorical]] | None = None,
        print_orders: bool = True,
        save_positions: bool = True,
    ) -> List[CryptoOrder]:
        dt_dfs = self.construct_dt_dfs(dt_dfs_input)
        processed_orders = []

        orders_to_process = self.limit_orders.copy()

        if self.auto_generate_orders is True:
            for currency_code in self.currency_codes:
                orders_to_process.extend(
                    self.get_auto_generated_orders(currency_code, dt_dfs[currency_code])
                )

        order_scores = [
            self.get_score(dt_dfs[order.currency_code], order)
            for order in orders_to_process
        ]
        final_orders = list(zip(orders_to_process, order_scores))
        final_orders.sort(key=lambda x: x[1], reverse=True)

        filtered_orders, order_signals = self.filter_orders(
            [order for order, _ in final_orders], dt_dfs
        )

        cnts = defaultdict(set)
        for order in filtered_orders:
            cnts[order.currency_code].add(order.side)
        assert all(
            len(cnt) <= 1 for cnt in cnts.values()
        ), "Only one order (or none) of each type should be generated per cryptocurrency per interval"

        stop_loss_orders = self.portfolio_mgr.check_stop_loss(dt_dfs)
        if stop_loss_orders and print_orders:
            print_dt(f"{len(stop_loss_orders)} stop loss orders found.")

        filtered_orders.extend(stop_loss_orders)
        order_signals.extend([(True, True) for _ in stop_loss_orders])

        for order, (confident_signal, risk_signal) in zip(
            filtered_orders, order_signals
        ):
            df = dt_dfs[order.currency_code]
            most_recent_data: Series[CryptoHistorical] = df.iloc[-1]

            order = CryptoOrder(
                side=order.side,
                currency_code=order.currency_code,
                asset_price=most_recent_data.close,
                amount=order.amount,
                limit_price=order.limit_price,
                quantity=order.amount / most_recent_data.close,
                timestamp=most_recent_data.timestamp,
            )

            if confident_signal or risk_signal:
                currency_code = order.currency_code
                executed_orders = self.portfolio_mgr.process_order(dt_dfs, order)

                for exec_order in executed_orders:
                    if self.paper_trade:
                        if print_orders:
                            print_dt(
                                f"Paper trading {exec_order.side} order for {currency_code}:"
                            )
                    else:
                        if print_orders:
                            print_dt(
                                f"Executing live {exec_order.side} order for {currency_code}:"
                            )

                        processed_orders.append(
                            getattr(self.broker, f"{exec_order.side}_crypto_market")(
                                exec_order.currency_code,
                                exec_order.amount,
                                most_recent_data,
                            )
                        )

                    if print_orders:
                        pprint(exec_order)

                    if save_positions:
                        self.write_order_to_file(exec_order)

                if print_orders:
                    print_dt(
                        f"Remaining buy power: {self.portfolio_mgr.portfolio_hist[-1].buy_power}"
                    )

        return processed_orders

    def write_order_to_file(self, order: CryptoOrder) -> None:
        positions = []
        if self.path_to_positions.exists():
            with open(self.path_to_positions, "r") as f:
                positions = json.load(f)

        positions.append(order.model_dump_json())

        with open(self.path_to_positions, "w") as f:
            json.dump(positions, f)

    def execute_buy_condition(
        self, df: DataFrame[CryptoHistorical], order: CryptoLimitOrder
    ) -> Tuple[bool, bool]:
        raise NotImplementedError("This method should be overridden by subclasses")

    def execute_sell_condition(
        self, df: DataFrame[CryptoHistorical], order: CryptoLimitOrder
    ) -> Tuple[bool, bool]:
        raise NotImplementedError("This method should be overridden by subclasses")

    def transform_df(
        self, df: DataFrame[CryptoHistorical]
    ) -> DataFrame[CryptoHistorical]:
        return df

    def get_auto_generated_orders(
        self, currency_code: str, df: DataFrame[CryptoHistorical]
    ) -> List[CryptoLimitOrder]:
        return []

    def get_score(
        self, df: DataFrame[CryptoHistorical], order: CryptoLimitOrder
    ) -> float:
        raise NotImplementedError("This method should be overridden by subclasses")
