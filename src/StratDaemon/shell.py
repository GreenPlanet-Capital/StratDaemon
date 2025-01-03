import os
from typing import Annotated
import typer
from StratDaemon.daemons.strat import StratDaemon
from StratDaemon.integration.notification.sms import SMSNotification
from StratDaemon.models.crypto import CryptoLimitOrder
from StratDaemon.strats.base import BaseStrategy
from StratDaemon.strats.fib_vol_rsi import FibVolRsiStrategy
from StratDaemon.utils.constants import WAIT_TIME, cfg_parser as strat_cfg_parser
from StratDaemon.integration.broker.robinhood import RobinhoodBroker
import asyncio
import json


app = typer.Typer()


@app.command(help="Start the strat daemon")
def start(
    strategy: Annotated[str, typer.Option("--strategy", "-s")] = "rsi",
    path_to_orders: Annotated[str, typer.Option("--path-to-orders", "-pto")] = None,
    path_to_holdings: Annotated[str, typer.Option("--path-to-holdings", "-pth")] = None,
    integration: Annotated[str, typer.Option("--integration", "-i")] = "robinhood",
    path_to_currency_codes: Annotated[
        str, typer.Option("--path-to-currency-codes", "-ptc")
    ] = None,
    auto_generate_orders: Annotated[
        bool, typer.Option("--auto-generate-orders", "-ago")
    ] = False,
    max_amount_per_order: Annotated[
        float, typer.Option("--max-amount-per-order", "-mapo")
    ] = 0.0,
    paper_trade: Annotated[bool, typer.Option("--paper-trade", "-p")] = False,
):
    match integration:
        case "robinhood":
            broker = RobinhoodBroker()
        case _:
            raise typer.Exit("Invalid integration. Needs to be one of: robinhood")

    match strategy:
        case "fib_vol_rsi":
            strat_class = FibVolRsiStrategy
        case _:
            raise typer.Exit(
                "Invalid strategy. Needs to be one of: naive, rsi, boll, rsi_boll, fib_vol"
            )

    if path_to_currency_codes is not None:
        if not os.path.exists(path_to_currency_codes):
            raise typer.Exit(
                f"Path to currency codes does not exist: {path_to_currency_codes}"
            )
        with open(path_to_currency_codes, "r") as f:
            currency_codes = [line.strip() for line in f.readlines()]
    else:
        currency_codes = None

    strat: BaseStrategy = strat_class(
        broker,
        SMSNotification(),
        currency_codes,
        auto_generate_orders,
        max_amount_per_order,
        paper_trade,
    )

    if path_to_holdings is not None:
        if not os.path.exists(path_to_holdings):
            raise typer.Exit(f"Path to holdings does not exist: {path_to_holdings}")
        with open(path_to_holdings, "r") as f:
            holdings = json.load(f)
        for holding in holdings:
            strat.holdings[holding["currency_code"]] = holding["amount"]

    if path_to_orders is not None:
        if not os.path.exists(path_to_orders):
            raise typer.Exit(f"Path to orders does not exist: {path_to_orders}")
        with open(path_to_orders, "r") as f:
            orders = json.load(f)
            for order in orders:
                strat.add_limit_order(CryptoLimitOrder(**order))

    strat.init()
    poll_interval = WAIT_TIME * 60
    daemon = StratDaemon(strat, poll_interval)
    asyncio.run(daemon.start())


@app.command(help="Show the current configuration")
def show_config():
    content = get_config_file_str(strat_cfg_parser)
    if not content:
        msg = "EMPTY"
    else:
        msg = content
    typer.echo(msg)


def get_config_file_str(cfg_parser):
    content = ""
    config_dict = {
        section: dict(cfg_parser[section]) for section in cfg_parser.sections()
    }
    for section, v in config_dict.items():
        content += f"[{section}]\n"
        for var, val in v.items():
            content += f"{var}={val}\n"
        content += "\n"
    return content


def main():
    app()
