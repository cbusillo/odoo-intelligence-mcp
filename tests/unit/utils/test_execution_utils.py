import asyncio
import threading
from functools import partial

import pytest

from odoo_intelligence_mcp.utils.execution_utils import run_docker_operation


@pytest.mark.asyncio
async def test_cancelled_docker_call_finishes_before_releasing_its_caller() -> None:
    operation_started = threading.Event()
    finish_operation = threading.Event()
    operation_finished = threading.Event()

    def execute_operation() -> None:
        operation_started.set()
        assert finish_operation.wait(timeout=2)
        operation_finished.set()

    request = asyncio.create_task(run_docker_operation(execute_operation))
    try:
        assert await asyncio.to_thread(operation_started.wait, 1)
        request.cancel()
        await asyncio.sleep(0)
        request.cancel()
        await asyncio.sleep(0)
        assert not request.done()
        assert not operation_finished.is_set()
    finally:
        finish_operation.set()
        with pytest.raises(asyncio.CancelledError):
            await request
    assert operation_finished.is_set()


@pytest.mark.asyncio
async def test_docker_operations_complete_in_submission_order() -> None:
    completed_operations = []

    def execute_operation(position: int) -> int:
        assert len(completed_operations) == position
        completed_operations.append(position)
        return position

    results = await asyncio.gather(*(run_docker_operation(partial(execute_operation, position)) for position in range(20)))
    assert results == completed_operations


@pytest.mark.asyncio
async def test_docker_operation_failure_reaches_its_caller() -> None:
    def execute_operation() -> None:
        raise RuntimeError("Docker failed")

    with pytest.raises(RuntimeError, match="Docker failed"):
        await run_docker_operation(execute_operation)


@pytest.mark.asyncio
async def test_anyio_cancellation_does_not_repeat_while_docker_finishes() -> None:
    import anyio

    operation_started = threading.Event()
    finish_operation = threading.Event()
    scope_ready = asyncio.get_running_loop().create_future()

    def execute_operation() -> None:
        operation_started.set()
        assert finish_operation.wait(timeout=2)

    async def execute_request() -> None:
        with anyio.CancelScope() as scope:
            scope_ready.set_result(scope)
            await run_docker_operation(execute_operation)

    request = asyncio.create_task(execute_request())
    try:
        scope = await scope_ready
        assert await asyncio.to_thread(operation_started.wait, 1)
        scope.cancel()
        await asyncio.sleep(0)
        cancellation_count = request.cancelling()
        for _ in range(30):
            await asyncio.sleep(0)
        assert request.cancelling() == cancellation_count
        assert not request.done()
    finally:
        finish_operation.set()
        with pytest.raises(asyncio.CancelledError):
            await request


@pytest.mark.asyncio
async def test_cancelled_queued_docker_operation_never_starts() -> None:
    operation_started = threading.Event()
    finish_operation = threading.Event()
    queued_operation_started = threading.Event()

    def execute_operation() -> None:
        operation_started.set()
        assert finish_operation.wait(timeout=2)

    first_request = asyncio.create_task(run_docker_operation(execute_operation))
    queued_request = None
    try:
        assert await asyncio.to_thread(operation_started.wait, 1)
        queued_request = asyncio.create_task(run_docker_operation(queued_operation_started.set))
        await asyncio.sleep(0)
        queued_request.cancel()
        with pytest.raises(asyncio.CancelledError):
            await queued_request
    finally:
        finish_operation.set()
        await first_request
        if queued_request is not None and not queued_request.done():
            await queued_request
    assert not queued_operation_started.is_set()
