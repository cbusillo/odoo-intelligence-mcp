import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

DOCKER_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="odoo-docker")


async def run_docker_operation[T](operation: Callable[[], T]) -> T:
    operation_future = asyncio.wrap_future(DOCKER_EXECUTOR.submit(operation))
    cancelled = False
    while not operation_future.done():
        try:
            await asyncio.shield(operation_future)
        except asyncio.CancelledError:
            cancelled = True
        except Exception:
            break
    operation_future.exception()
    if cancelled:
        raise asyncio.CancelledError
    return operation_future.result()
