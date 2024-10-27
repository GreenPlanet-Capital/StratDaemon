import asyncio


class BaseDaemon:
    """A daemon that executes a task every x seconds"""

    def __init__(self, task: callable, delay: int, run_on_start: bool = True) -> None:
        self._task = task
        self._delay = delay
        self.run_on_start = run_on_start

    async def _execute_task(self) -> None:
        await self._task()

    async def start(self) -> None:
        while True:
            if self.run_on_start:
                await self._execute_task()
                self.run_on_start = False

            await asyncio.sleep(self._delay)
            await self._execute_task()
