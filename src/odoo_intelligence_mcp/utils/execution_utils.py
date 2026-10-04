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
    cancellation: asyncio.CancelledError | None = None
    while not operation_future.done():
        with anyio.CancelScope(shield=cancellation is not None):
            try:
                await asyncio.shield(operation_future)
            except asyncio.CancelledError as error:
                if worker_future.cancel():
                    raise
                cancellation = cancellation or error
            except Exception:
                break
    operation_future.exception()
    if cancellation is not None:
        raise cancellation
    return operation_future.result()
