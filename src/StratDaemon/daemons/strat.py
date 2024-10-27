from StratDaemon.daemons.base import BaseDaemon
from StratDaemon.strats.base import BaseStrategy


class StratDaemon(BaseDaemon):
    def __init__(
        self, strat: BaseStrategy, poll_interval: int, poll_on_start: bool = True
    ):
        self.strat = strat
        super().__init__(self.task, poll_interval, poll_on_start)

    async def task(self):
        print(
            f"Executing strategy {self.strat.name} with {"paper" if self.strat.paper_trade else "live"} trading"
        )
        self.strat.execute()
        print("Strategy executed.")
