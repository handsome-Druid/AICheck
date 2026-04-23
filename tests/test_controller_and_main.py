from __future__ import annotations

import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
from typing import Callable
from unittest.mock import AsyncMock, Mock, patch

from src.controllers import vllm_test_controller as controller_module
from src.models.sheet import Sheet
from src.models.vllm_results import VLLMTestResult


class DummyThread:
    def __init__(self, target: Callable[..., object], args: tuple[object, ...], daemon: bool) -> None:
        self.target = target
        self.args = args
        self.daemon = daemon
        self.started = False
        self.joined = False

    def start(self) -> None:
        self.started = True

    def join(self) -> None:
        self.joined = True


class DummyClient:
    async def __aenter__(self) -> DummyClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> bool:
        return False


class TestControllerHelpers(unittest.TestCase):
    def test_iter_batches_groups_items(self) -> None:
        sheets: list[Sheet] = [
            Sheet(1, "m1", "n1", "mon1", "gpu1", 1, 1, "c1", "u1"),
            Sheet(2, "m2", "n2", "mon2", "gpu2", 2, 2, "c2", "u2"),
            Sheet(3, "m3", "n3", "mon3", "gpu3", 3, 3, "c3", "u3"),
            Sheet(4, "m4", "n4", "mon4", "gpu4", 4, 4, "c4", "u4"),
            Sheet(5, "m5", "n5", "mon5", "gpu5", 5, 5, "c5", "u5"),
        ]

        batches = list(controller_module.iter_batches(iter(sheets), 2))
        self.assertEqual([[sheet.port for sheet in batch] for batch in batches], [[1, 2], [3, 4], [5]])

    def test_iter_queue_results_stops_at_sentinel(self) -> None:
        queue: Queue[object] = Queue()
        first = VLLMTestResult("127.0.0.1", 8000, "success", "ok", ["m1"], ["m1"], [], [], 0.1)
        second = VLLMTestResult("127.0.0.2", 8001, "failed", "bad", [], ["m2"], [], ["m2"], 0.2)
        queue.put(first)
        queue.put(second)
        queue.put(controller_module.RESULT_SENTINEL)

        self.assertEqual(list(controller_module.iter_queue_results(queue)), [first, second])


class TestControllerRun(unittest.IsolatedAsyncioTestCase):
    async def test_run_processes_results_and_waits_for_threads(self) -> None:
        result = VLLMTestResult("127.0.0.1", 8000, "success", "ok", ["m1"], ["m1"], [], [], 0.1)
        sheet_one = SimpleNamespace(end="GO", call_method="https://example.com/chat/completions", port=8000, model_id="m1")
        sheet_two = SimpleNamespace(end="STOP", call_method="https://example.com/chat/completions", port=8001, model_id="m2")
        config = SimpleNamespace(end_tag="end", end_value="STOP", csv_output_path=tempfile.gettempdir(), xlsx_input_path="ignored.xlsx")
        created_threads: list[DummyThread] = []

        def fake_to_thread(func: Callable[..., object], *args: object, **kwargs: object) -> object:
            return func(*args, **kwargs)

        check_mock = AsyncMock(return_value=result)
        print_mock = Mock()
        csv_mock = Mock()

        def fake_thread_factory(
            *,
            target: Callable[..., object],
            args: tuple[object, ...],
            daemon: bool,
        ) -> DummyThread:
            thread = DummyThread(target, args, daemon)
            created_threads.append(thread)
            return thread

        with patch("src.controllers.vllm_test_controller.get_config", return_value=config), patch(
            "src.controllers.vllm_test_controller.get_sheet_iterator", return_value=iter([sheet_one, sheet_two])
        ), patch("src.controllers.vllm_test_controller.check_vllm_models", check_mock), patch(
            "src.controllers.vllm_test_controller.httpx.AsyncClient", return_value=DummyClient()
        ), patch("src.controllers.vllm_test_controller.Thread", side_effect=fake_thread_factory), patch(
            "src.controllers.vllm_test_controller.test_print_from_dataclass", print_mock
        ), patch("src.controllers.vllm_test_controller.write_csv_from_dataclass", csv_mock), patch(
            "src.controllers.vllm_test_controller.asyncio.to_thread", side_effect=fake_to_thread
        ):
            await controller_module.run()

        self.assertEqual(len(created_threads), 2)
        self.assertIs(created_threads[0].target, print_mock)
        self.assertIs(created_threads[1].target, csv_mock)
        self.assertTrue(created_threads[0].started)
        self.assertTrue(created_threads[1].started)
        self.assertTrue(created_threads[0].joined)
        self.assertTrue(created_threads[1].joined)
        check_mock.assert_awaited_once()


class TestMainModule(unittest.TestCase):
    def test_main_module_runs_and_pauses(self) -> None:
        main_path = Path(__file__).resolve().parents[1] / "src" / "main.py"

        with patch("src.controllers.vllm_test_controller.run", new=Mock(return_value=None)), patch("asyncio.run", return_value=None) as run_mock, patch(
            "subprocess.run", return_value=None
        ) as pause_mock, patch.object(sys, "argv", ["main.py"]):
            runpy.run_path(str(main_path), run_name="__main__")

        run_mock.assert_called_once()
        pause_mock.assert_called_once_with("pause", shell=True)