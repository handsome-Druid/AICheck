from __future__ import annotations

import builtins
import runpy
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from queue import Queue
from types import ModuleType, SimpleNamespace
from typing import Callable, Generator, cast
from unittest.mock import AsyncMock, Mock, patch

from src.controllers import vllm_test_controller as controller_module
from src.models.sheet import Sheet
from src.models.vllm_results import VLLMTestResult


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


@contextmanager
def _force_import_error_once(target: str) -> Generator[None, None, None]:
    original_import = builtins.__import__
    state = {"raised": False}

    def fake_import(
        name: str,
        globals: dict[str, object] | None = None,
        locals: dict[str, object] | None = None,
        fromlist: tuple[str, ...] | list[str] = (),
        level: int = 0,
    ) -> ModuleType:
        if not state["raised"] and name == target:
            state["raised"] = True
            raise ImportError(f"forced ImportError for {target}")
        return original_import(name, globals, locals, fromlist, level)

    with patch("builtins.__import__", side_effect=fake_import):
        yield


class _FakeApp:
    def __init__(self) -> None:
        self.exec_called = False

    def exec(self) -> int:
        self.exec_called = True
        return 0


class _FakeWindow:
    def __init__(self) -> None:
        self.controller: object | None = None
        self.show_called = False

    def show(self) -> None:
        self.show_called = True


def _fake_app_factory(argv: object) -> _FakeApp:
    return _FakeApp()


def _fake_window_factory() -> _FakeWindow:
    return _FakeWindow()


def _fake_controller_factory(window: _FakeWindow) -> object:
    controller = object()
    window.controller = controller
    return controller


class TestControllerHelpers(unittest.TestCase):
    def test_iter_batches_groups_items(self) -> None:
        sheets: list[Sheet] = [
            Sheet(1, "m1", "n1", "u1"),
            Sheet(2, "m2", "n2", "u2"),
            Sheet(3, "m3", "n3", "u3"),
            Sheet(4, "m4", "n4", "u4"),
            Sheet(5, "m5", "n5", "u5"),
        ]

        batches = list(controller_module.iter_batches(iter(sheets), 2))
        self.assertEqual([[sheet.port for sheet in batch] for batch in batches], [[1, 2], [3, 4], [5]])

    def test_iter_queue_results_stops_at_sentinel(self) -> None:
        queue: Queue[object] = Queue()
        first = VLLMTestResult("127.0.0.1", 8000, "m1", "c1", "success", "ok", ["m1"], ["m1"], [], [], 0.1)
        second = VLLMTestResult("127.0.0.2", 8001, "m2", "c2", "failed", "bad", [], ["m2"], [], ["m2"], 0.2)
        queue.put(first)
        queue.put(second)
        queue.put(controller_module.RESULT_SENTINEL)

        self.assertEqual(list(controller_module.iter_queue_results(queue)), [first, second])


class TestControllerRun(unittest.IsolatedAsyncioTestCase):
    async def test_run_processes_results_and_prints_summary(self) -> None:
        result = VLLMTestResult("127.0.0.1", 8000, "m1", "c1", "success", "ok", ["m1"], ["m1"], [], [], 0.1)
        sheet_one = SimpleNamespace(end="GO", call_method="https://example.com/chat/completions", port=8000, model_id="m1", container_name="c1")
        sheet_two = SimpleNamespace(end="STOP", call_method="https://example.com/chat/completions", port=8001, model_id="m2", container_name="c2")
        config = SimpleNamespace(
            end_tag="end", 
            end_value="STOP", 
            pass_port=[], 
            csv_output_path=tempfile.gettempdir(), 
            xlsx_input_path="ignored.xlsx"
        )

        def fake_to_thread(func: Callable[..., object], *args: object, **kwargs: object) -> object:
            return func(*args, **kwargs)

        check_mock = AsyncMock(return_value=result)
        print_mock = Mock()
        csv_mock = Mock()

        with patch("src.controllers.vllm_test_controller.get_config", return_value=config), patch(
            "src.controllers.vllm_test_controller.get_sheet_iterator", return_value=iter([sheet_one, sheet_two])
        ), patch("src.controllers.vllm_test_controller.check_vllm_models", check_mock), patch(
            "httpx.AsyncClient", return_value=DummyClient()
        ), patch("src.controllers.vllm_test_controller.print_results", print_mock), patch(
            "src.controllers.vllm_test_controller.write_csv_from_dataclass", csv_mock
        ), patch("src.controllers.vllm_test_controller.asyncio.to_thread", side_effect=fake_to_thread), patch(
            "builtins.print"
        ) as print_spy:
            await controller_module.run()

        check_mock.assert_awaited_once()
        print_mock.assert_called_once()
        csv_mock.assert_called_once()
        print_spy.assert_called_once()


class TestMainModule(unittest.TestCase):
    def setUp(self) -> None:
        self.main_module_mod = self._load_main_module()

    @staticmethod
    def _run_and_close(coro: object) -> None:
        close = getattr(coro, "close", None)
        if callable(close):
            close()

    @staticmethod
    def _load_main_module() -> ModuleType:
        import src.main as main_module

        return cast(ModuleType, main_module)

    @staticmethod
    def _assert_loaded_components_bound(module: ModuleType, components: tuple[object, object, object]) -> None:
        first, second, third = components
        self_module = module
        assert getattr(self_module, "QApplication") is first
        assert getattr(self_module, "MainController") is second
        assert getattr(self_module, "MainWindow") is third

    @staticmethod
    def _reset_lazy_gui_symbols(module: ModuleType) -> None:
        setattr(module, "QApplication", None)
        setattr(module, "MainController", None)
        setattr(module, "MainWindow", None)

    def test_main_module_entrypoint_nogui_runs_and_pauses(self) -> None:
        main_path = Path(__file__).resolve().parents[1] / "src" / "main.py"

        with patch("src.controllers.vllm_test_controller.run", new=Mock(return_value=None)), patch(
            "asyncio.run", side_effect=self._run_and_close
        ) as run_mock, patch("subprocess.run", return_value=None) as pause_mock, patch.object(
            sys, "argv", ["main.py", "--nogui"]
        ):
            runpy.run_path(str(main_path), run_name="__main__")

        run_mock.assert_called_once()
        pause_mock.assert_called_once_with("pause", shell=True)

    def test_main_module_nogui_branch_runs_and_pauses(self) -> None:
        main_module_mod = self.main_module_mod

        with patch.object(sys, "argv", ["main.py", "--nogui"]), patch.object(main_module_mod, "run", new=Mock(return_value=None)), patch.object(
            main_module_mod.asyncio, "run", side_effect=self._run_and_close
        ) as run_mock, patch.object(
            main_module_mod.subprocess, "run", return_value=None
        ) as pause_mock:
            main_module_mod.main()

        run_mock.assert_called_once()
        pause_mock.assert_called_once_with("pause", shell=True)

    def test_main_module_load_gui_components_uses_imports(self) -> None:
        main_module_mod = getattr(self, "main_module_mod")

        self._reset_lazy_gui_symbols(main_module_mod)

        fake_pyside6 = ModuleType("PySide6")
        setattr(fake_pyside6, "__path__", [])
        fake_qtwidgets = ModuleType("PySide6.QtWidgets")
        setattr(fake_pyside6, "QtWidgets", fake_qtwidgets)
        setattr(fake_qtwidgets, "QApplication", _fake_app_factory)

        fake_main_controller = ModuleType("src.controllers.main_controller")
        setattr(fake_main_controller, "MainController", _fake_controller_factory)

        fake_main_view = ModuleType("src.views.main_view")
        setattr(fake_main_view, "MainWindow", _fake_window_factory)

        with patch.dict(
            sys.modules,
            {
                "PySide6": fake_pyside6,
                "PySide6.QtWidgets": fake_qtwidgets,
                "src.controllers.main_controller": fake_main_controller,
                "src.views.main_view": fake_main_view,
            },
            clear=False,
        ):
            qapplication_class, main_controller_class, main_window_class = main_module_mod._load_gui_components()

        self._assert_loaded_components_bound(main_module_mod, (qapplication_class, main_controller_class, main_window_class))

    def test_main_module_load_gui_components_uses_import_fallback(self) -> None:
        main_module_mod = self.main_module_mod

        self._reset_lazy_gui_symbols(main_module_mod)

        with _force_import_error_once("PySide6.QtWidgets"):
            qapplication_class, main_controller_class, main_window_class = main_module_mod._load_gui_components()

        self._assert_loaded_components_bound(main_module_mod, (qapplication_class, main_controller_class, main_window_class))

    def test_main_module_gui_branch_creates_window(self) -> None:
        main_module_mod = self.main_module_mod

        fake_app = _FakeApp()
        fake_window = _FakeWindow()
        controller = object()

        def fake_app_factory(argv: object) -> _FakeApp:
            return fake_app

        def fake_controller_factory(window: object) -> object:
            return controller

        def fake_window_factory() -> _FakeWindow:
            return fake_window

        with patch.object(sys, "argv", ["main.py"]), patch.object(
            main_module_mod, "_load_gui_components", return_value=(
                fake_app_factory,
                fake_controller_factory,
                fake_window_factory,
            )
        ) as loader_mock:
            main_module_mod.main()

        loader_mock.assert_called_once()
        self.assertIs(fake_window.controller, controller)
        self.assertTrue(fake_window.show_called)
        self.assertTrue(fake_app.exec_called)