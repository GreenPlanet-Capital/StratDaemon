import traceback
from StratDaemon.daemons.base import BaseDaemon
from StratDaemon.strats.base import BaseStrategy
from StratDaemon.utils.funcs import print_dt


class StratDaemon(BaseDaemon):
    def __init__(self, strat: BaseStrategy, poll_interval: int):
        self.strat = strat
        super().__init__(self.task, poll_interval)

    async def task(self):
        print_dt(
            f"Executing strategy {self.strat.name} with {"paper" if self.strat.paper_trade else "live"} trading"
            f" and {'auto-generating orders' if self.strat.auto_generate_orders else 'without auto-generating orders'}."
        )
        try:
            self.strat.execute()
        except Exception as _:
            print_dt(f"Error executing strategy: {traceback.format_exc()}")
        print_dt("Strategy executed.")
