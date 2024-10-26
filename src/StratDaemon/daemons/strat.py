from StratDaemon.daemons.base import BaseDaemon
from StratDaemon.strats.base import BaseStrategy


class StratDaemon(BaseDaemon):
    def __init__(
        self, strat: BaseStrategy, poll_interval: int, poll_on_start: bool = True
    ):
        self.strat = strat
        super().__init__(self.task, poll_interval, poll_on_start)

    async def task(self):
        self.strat.execute()
