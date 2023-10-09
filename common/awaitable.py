import asyncio
from typing import Any


def await_for(coro) -> Any:
    """Runs [coro] and await for result in sync"""
    loop = asyncio.get_event_loop()
    task = loop.create_task(coro)
    loop.run_until_complete(task)
    return task.result()


async def aenumerate(asequence, start=0):
    """Asynchronously enumerate an async iterator from a given start value"""
    n = start
    async for elem in asequence:
        yield n, elem
        n += 1
