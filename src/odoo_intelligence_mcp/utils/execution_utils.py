import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

import anyio

if TYPE_CHECKING:
    from collections.abc import Callable

DOCKER_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="odoo-docker")


async def run_docker_operation[T](operation: Callable[[], T]) -> T:
    worker_future = DOCKER_EXECUTOR.submit(operation)
    operation_future = asyncio.wrap_future(worker_future)
    cancelled = False
    while not operation_future.done():
        with anyio.CancelScope(shield=cancelled):
            try:
                await asyncio.shield(operation_future)
            except asyncio.CancelledError:
                if worker_future.cancel():
                    raise
                cancelled = True
            except Exception:
                break
    operation_future.exception()
    if cancelled:
        raise asyncio.CancelledError
    return operation_future.result()
