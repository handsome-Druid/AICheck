import asyncio
import datetime
import operator
from collections.abc import AsyncIterator, Iterator
from itertools import islice
from pathlib import Path
from queue import Queue
from typing import cast

import httpx

from src.config import get_config
from src.models.sheet import Sheet, get_sheet_iterator
from src.models.vllm_results import VLLMTestResult
from src.services.test_vllm import check_vllm_models
from src.utils.test_print import test_print_from_dataclass
from src.utils.write_csv import write_csv_from_dataclass


MAX_CONCURRENT_REQUESTS = 30
RESULT_SENTINEL = object()


def iter_batches(items: Iterator[Sheet], batch_size: int) -> Iterator[list[Sheet]]:
    while batch := list(islice(items, batch_size)):
        yield batch


def iter_queue_results(result_queue: Queue[object]) -> Iterator[VLLMTestResult]:
    while True:
        item = result_queue.get()
        if item is RESULT_SENTINEL:
            break
        yield cast(VLLMTestResult, item)


def iter_filtered_sheets() -> Iterator[Sheet]:
    config = get_config()
    end_getter = operator.attrgetter(config.end_tag) if config.end_tag else None

    for sheet in get_sheet_iterator():
        if end_getter and end_getter(sheet) == config.end_value:
            break

        if all(
            getattr(sheet, p_tag, None) != p_val
            for p_tag, p_val in zip(config.pass_tag, config.pass_value)
        ):
            yield sheet


async def iter_results(client: httpx.AsyncClient) -> AsyncIterator[VLLMTestResult]:
    for batch in iter_batches(iter_filtered_sheets(), MAX_CONCURRENT_REQUESTS):
        batch_results = await asyncio.gather(
            *(
                check_vllm_models(
                    client=client,
                    url=sheet.call_method,
                    port=sheet.port,
                    expected_models=[sheet.model_id],
                    api_key=None,
                    container_name=sheet.container_name
                )
                for sheet in batch
            )
        )
        for result in batch_results:
            yield result


async def fanout_result(result: object, print_queue: Queue[object], csv_queue: Queue[object]) -> None:
    await asyncio.gather(
        asyncio.to_thread(print_queue.put, result),
        asyncio.to_thread(csv_queue.put, result),
    )


def build_csv_path() -> Path:
    return Path(get_config().csv_output_path) / f"vllm_test_results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"


async def run() -> None:
    csv_path = build_csv_path()
    print_queue: Queue[object] = Queue(maxsize=MAX_CONCURRENT_REQUESTS)
    csv_queue: Queue[object] = Queue(maxsize=MAX_CONCURRENT_REQUESTS)

    print_task = asyncio.create_task(asyncio.to_thread(test_print_from_dataclass, iter_queue_results(print_queue)))
    csv_task = asyncio.create_task(asyncio.to_thread(write_csv_from_dataclass, iter_queue_results(csv_queue), csv_path))

    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
        async for result in iter_results(client):
            await fanout_result(result, print_queue, csv_queue)

    await fanout_result(RESULT_SENTINEL, print_queue, csv_queue)

    rows_written = await csv_task
    await print_task
    print(f"Wrote {rows_written} rows to {csv_path}")
