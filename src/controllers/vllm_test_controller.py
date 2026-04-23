import asyncio
import datetime
import operator
from collections.abc import AsyncIterator, Iterator
from itertools import islice
from pathlib import Path
from queue import Queue
from threading import Thread
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


async def run() -> None:
    async def results() -> AsyncIterator[VLLMTestResult]:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            end_tag = get_config().end_tag
            end_value = get_config().end_value

            def bounded_sheets() -> Iterator[Sheet]:
                _getter = operator.attrgetter(end_tag)
                for sheet in get_sheet_iterator():
                    if _getter(sheet) == end_value:
                        break
                    yield sheet

            for batch in iter_batches(bounded_sheets(), MAX_CONCURRENT_REQUESTS):
                batch_results = await asyncio.gather(
                    *(
                        check_vllm_models(
                            client=client,
                            url=sheet.call_method,
                            port=sheet.port,
                            expected_models=[sheet.model_id],
                            api_key=None,
                        )
                        for sheet in batch
                    )
                )
                for result in batch_results:
                    yield result

    csv_path = Path(get_config().csv_output_path) / f"vllm_test_results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    print_queue: Queue[object] = Queue(maxsize=MAX_CONCURRENT_REQUESTS)
    csv_queue: Queue[object] = Queue(maxsize=MAX_CONCURRENT_REQUESTS)

    print_thread = Thread(
        target=test_print_from_dataclass,
        args=(iter_queue_results(print_queue),),
        daemon=True,
    )
    csv_thread = Thread(
        target=write_csv_from_dataclass,
        args=(iter_queue_results(csv_queue), csv_path),
        daemon=True,
    )

    print_thread.start()
    csv_thread.start()

    async for result in results():
        await asyncio.gather(
            asyncio.to_thread(print_queue.put, result),
            asyncio.to_thread(csv_queue.put, result),
        )

    await asyncio.gather(
        asyncio.to_thread(print_queue.put, RESULT_SENTINEL),
        asyncio.to_thread(csv_queue.put, RESULT_SENTINEL),
    )

    await asyncio.gather(
        asyncio.to_thread(print_thread.join),
        asyncio.to_thread(csv_thread.join),
    )
