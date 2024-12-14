import asyncio


class BaseDaemon:
    """A daemon that executes a task every x seconds"""

    def __init__(self, task: callable, delay: int) -> None:
        self._task = task
        self._delay = delay

    async def _execute_task(self) -> None:
        await self._task()

    async def start(self) -> None:
        await self._execute_task()

        while True:
            await asyncio.sleep(self._delay)
            await self._execute_task()
