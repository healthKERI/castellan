# -*- encoding: utf-8 -*-
"""
castellan.app.tasking module

Asyncio background tasks for the castellan credential server.
"""

import asyncio

from sentinel.core import oobiing


async def _make_escrow_task(process_fn, interval=0.5):
    """Create an async task factory for escrow processing.

    Args:
        process_fn: Synchronous function to call for escrow processing.
        interval: Sleep interval between processing cycles (default 0.5s).

    """
    while True:
        await asyncio.sleep(interval)
        process_fn()


class CastellanBackgroundWorker:
    """Owns the background tasks and their lifecycle."""

    def __init__(self, hby, kvy, tvy, rvy, interval: float = 60):
        self.hby = hby
        self.kvy = kvy
        self.tvy = tvy
        self.rvy = rvy
        self._interval = interval
        self._tasks: set[asyncio.Task] = set()
        self.queue: asyncio.Queue = asyncio.Queue()

    async def start(self) -> None:
        self._spawn(_make_escrow_task(self.kvy.processEscrows))
        self._spawn(_make_escrow_task(self.tvy.processEscrows))

        oobiery = oobiing.Oobiery(hby=self.hby, rvy=self.rvy)
        oobiery_tasks = oobiery.start()
        for task in oobiery_tasks:
            self._tasks.add(task)  # keep a strong reference
            task.add_done_callback(self._tasks.discard)

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        results = await asyncio.gather(*self._tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception) and not isinstance(r, asyncio.CancelledError):
                print(f"background task failed: {r!r}")  # use your logger

    def _spawn(self, coro) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)  # keep a strong reference
        task.add_done_callback(self._tasks.discard)


class LifespanMiddleware:
    def __init__(self, *services):
        self._services = services

    async def process_startup(self, _scope, _event):
        for s in self._services:
            await s.start()

    async def process_shutdown(self, _scope, _event):
        for s in reversed(self._services):
            await s.stop()
