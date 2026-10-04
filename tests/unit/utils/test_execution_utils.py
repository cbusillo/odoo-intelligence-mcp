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
