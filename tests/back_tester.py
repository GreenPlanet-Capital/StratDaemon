from datetime import datetime
from typing import Generator, List, Dict, Tuple
from devtools import pprint
import optuna
from pydantic import BaseModel
from tqdm import tqdm
from StratDaemon.integration.broker.alpaca import AlpacaBroker
from StratDaemon.models.crypto import CryptoHistorical, CryptoOrder, Portfolio
from StratDaemon.portfolio.graph_positions import GraphHandler
from StratDaemon.strats.base import BaseStrategy
from StratDaemon.strats.fib_vol import FibVolStrategy
from StratDaemon.strats.fib_vol_rsi import FibVolRsiStrategy
from pandera.typing import DataFrame
import plotly.express as px
import os
import numpy as np
from collections import defaultdict

# DEFAULT_BROKER = KrakenBroker()
# DEFAULT_BROKER = CryptoCompareBroker()
DEFAULT_BROKER = AlpacaBroker()
CONSTRICT_RANGE = 24 * 60 * 6
SAVE_GRAPH = True


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
        strat_split = self.strat.name.split("_")
        self.strat_name = f"{strat_split[0]}_{strat_split[-1]}"
        self.all_data_dfs = [
            self.broker.get_crypto_historical(currency_code, "hour", pull_from_api=False)
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
        transactions: List[CryptoOrder],
        save_graph: bool = True,
    ) -> None:
        strat_rsi_buy_threshold = getattr(self.strat, "rsi_buy_threshold", -1)
        strat_rsi_sell_threshold = getattr(self.strat, "rsi_sell_threshold", -1)
        strat_rsi_percent_incr_threshold = getattr(self.strat, "rsi_percent_incr_threshold", -1)
        strat_rsi_trend_span = getattr(self.strat, "rsi_trend_span", -1)

        if save_graph:
            sliced_dfs = [
                df[(len(df) - CONSTRICT_RANGE) :] if CONSTRICT_RANGE is not None else df
                for df in self.all_data_dfs
            ]
            GraphHandler.graph_positions(
                {
                    currency_code: self.strat.transform_df(df)
                    for currency_code, df in zip(self.currency_codes, sliced_dfs)
                },
                transactions,
                show_enter_exit=True,
            )
            fig = px.line(
                x=[p.timestamp for p in portfolio_hist],
                y=[p.value for p in portfolio_hist],
            )
            fig.write_image(
                f"results/"
                f"{'_'.join(self.currency_codes)}_{self.strat_name}_{self.strat.percent_diff_threshold}"
                f"_{self.span}_{self.wait_time}_{self.strat.risk_factor}"
                f"_{strat_rsi_buy_threshold}_{strat_rsi_sell_threshold}"
                f"_{self.strat.indicator_length}_{self.strat.portfolio_mgr.trailing_stop_loss}"
                f"_{self.strat.vol_window_size}_backtest.png"
            )

        csv_path = "results/performance.csv"
        if not os.path.exists(csv_path):
            with open(csv_path, "w") as f:
                f.write(
                    "currency_codes,strategy_name,percent_diff_threshold,span,wait_time,risk_factor,"
                    "rsi_buy_threshold,rsi_sell_threshold,rsi_percent_incr_threshold,"
                    "rsi_trend_span,indicator_length,trailing_stop_loss,"
                    "vol_window_size,final_value,num_buy_trades,num_sell_trades\n"
                )

        with open(csv_path, "a") as f:
            f.write(
                f"{'|'.join(self.currency_codes)},{self.strat_name},"
                f"{self.strat.percent_diff_threshold},{self.span},{self.wait_time},{self.strat.risk_factor},"
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
            holding["average_price"] = safe_div(holding["average_price"], holding["num_buy_orders"])

        pprint(dict(holdings))

    def run(
        self,
        constrict_range: int | None = None,
        save_data: bool = False,
        save_graph: bool = False,
        debug: bool = False,
    ) -> List[Portfolio]:
        print(f"Starting with ${self.buy_power}")
        transactions: List[CryptoOrder] = []

        for dfs in tqdm(
            self.get_data_by_interval(self.span, constrict_range, self.wait_time),
            desc=f"Backtesting {'|'.join(self.currency_codes)} cryptos with {self.strat_name} strategy",
            total=(
                (len(self.all_data_dfs[0]) // self.wait_time) - self.span
                if constrict_range is None
                else constrict_range // self.wait_time
            ),
        ):
            assert all(
                len(df) == len(dfs[0]) == self.span for df in dfs
            ), "All dataframes must have the same length as the span"

            input_dt_dfs = {
                currency_code: df for currency_code, df in zip(self.currency_codes, dfs)
            }
            orders = self.strat.execute(input_dt_dfs, print_orders=debug, save_positions=False)
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
            f"  {constrict_range if constrict_range is not None else len(self.all_data_dfs[0]) - self.span} minutes\n"
            f"  making trades every {self.wait_time} minutes\n"
            f"  with percent_diff_threshold={self.strat.percent_diff_threshold}\n"
            f"  and vol_window_size={self.strat.vol_window_size}\n"
            f"  and span={self.span}\n"
            f"  and risk_factor={self.strat.risk_factor}\n"
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
        self, span: int, constrict_range: int | None = None, wait_time: int = 0
    ) -> Generator[DataFrame[CryptoHistorical], None, None]:
        # FIXME: Implement a more efficient way of getting data by interval
        n = len(self.all_data_dfs[0])
        start_idx = span if constrict_range is None else n - constrict_range
        if constrict_range is not None:
            assert n > constrict_range, "Start index must be less than the length of the data"
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
        conf=None,
        currency_codes=crypto_currency_codes,
        auto_generate_orders=True,
        max_amount_per_order=max_amount_per_order,
        paper_trade=False,
        confirm_before_trade=False,
        percent_diff_threshold=p_diff,
        vol_window_size=vol_window,
        risk_factor=-1,
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
        constrict_range=CONSTRICT_RANGE,
        save_data=True,
        debug=False,
        save_graph=SAVE_GRAPH,
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


def load_best_study_parameters() -> Parameters:
    study = optuna.load_study(study_name="fib_vol_rsi", storage="sqlite:///optuna_db.sqlite3")
    return Parameters.model_validate(study.best_trials[0].params)


if __name__ == "__main__":
    params = load_best_study_parameters()
    # crypto_currency_codes = ["DOGE", "SHIB"]
    crypto_currency_codes = ["DOGE"]
    
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
    )
