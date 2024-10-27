import os
from typing import Annotated
import typer
from StratDaemon.daemons.strat import StratDaemon
from StratDaemon.integration.confirmation.crypto_db import CryptoDBConfirmation
from StratDaemon.integration.notification.sms import SMSNotification
from StratDaemon.models.crypto import CryptoLimitOrder
from StratDaemon.strats.boll import BollStrategy
from StratDaemon.strats.fib_vol import FibVolStrategy
from StratDaemon.strats.naive import NaiveStrategy
from StratDaemon.strats.rsi import RsiStrategy
from StratDaemon.strats.rsi_boll import RsiBollStrategy
from StratDaemon.utils.constants import cfg_parser as strat_cfg_parser
from StratDaemon.integration.broker.robinhood import RobinhoodBroker
import asyncio
import json


app = typer.Typer()


@app.command(help="Start the strat daemon")
def start(
    strategy: Annotated[str, typer.Option("--strategy", "-s")] = "rsi",
    path_to_orders: Annotated[str, typer.Option("--path-to-orders", "-pto")] = None,
    integration: Annotated[str, typer.Option("--integration", "-i")] = "robinhood",
    notification: Annotated[str, typer.Option("--notification", "-n")] = "sms",
    confirmation: Annotated[str, typer.Option("--confirmation", "-c")] = "crypto_db",
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
    confirm_before_trade: Annotated[
        bool, typer.Option("--confirm-before-trade", "-cbt")
    ] = False,
    poll_interval: Annotated[int, typer.Option("--poll-interval", "-pi")] = 60 * 5,
    poll_on_start: Annotated[bool, typer.Option("--poll-on-start", "-pos")] = True,
):
    match integration:
        case "robinhood":
            broker = RobinhoodBroker()
        case _:
            raise typer.Exit("Invalid integration. Needs to be one of: robinhood")

    if confirm_before_trade:
        match notification:
            case "sms":
                notif = SMSNotification()
            case _:
                raise typer.Exit("Invalid notification. Needs to be one of: sms")

        match confirmation:
            case "crypto_db":
                conf = CryptoDBConfirmation()
            case _:
                raise typer.Exit("Invalid confirmation. Needs to be one of: crypto_db")
    else:
        notif = None
        conf = None

    match strategy:
        case "naive":
            strat_class = NaiveStrategy
        case "rsi":
            strat_class = RsiStrategy
        case "boll":
            strat_class = BollStrategy
        case "rsi_boll":
            strat_class = RsiBollStrategy
        case "fib_vol":
            strat_class = FibVolStrategy
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

    strat = strat_class(
        broker,
        notif,
        conf,
        currency_codes,
        auto_generate_orders,
        max_amount_per_order,
        paper_trade,
        confirm_before_trade,
    )

    if path_to_orders is not None:
        if not os.path.exists(path_to_orders):
            raise typer.Exit(f"Path to orders does not exist: {path_to_orders}")
        with open(path_to_orders, "r") as f:
            orders = json.load(f)
            for order in orders:
                strat.add_limit_order(CryptoLimitOrder(**order))

    daemon = StratDaemon(strat, poll_interval, poll_on_start)
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
