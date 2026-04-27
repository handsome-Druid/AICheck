from __future__ import annotations

import builtins
import io
import runpy
import sys
import tempfile
import unittest
from contextlib import contextmanager
from dataclasses import dataclass, field, fields as dataclass_fields
from datetime import datetime as real_datetime, tzinfo
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Generator, Iterator, cast, Optional
from unittest.mock import patch

from src.adapters import read_history_results as history_adapter
from src.models.base import BaseReaderModel
from src.models.type import CellGetValue
from src.models.vllm_results import VLLMTestResult
from src.models import ports as ports_module
from src.services import check_history_results as history_service
from src.utils import print_results as print_results_module

@contextmanager
def _force_import_error_once(target: str) -> Generator[None, None, None]:
    original_import = builtins.__import__
    state = {"raised": False}
    saved_module = sys.modules.pop(target, None)

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

    try:
        with patch("builtins.__import__", side_effect=fake_import):
            yield
    finally:
        if saved_module is not None:
            sys.modules[target] = saved_module


class TestHistoryAdapter(unittest.TestCase):
    def test_filter_log_files_handles_missing_dir_and_bad_name(self) -> None:
        with patch.object(history_adapter, "get_config", return_value=SimpleNamespace(csv_output_path="missing-dir")):
            self.assertEqual(history_adapter.filter_log_files(None), ([], [], []))

        class FixedDatetime(real_datetime):
            @classmethod
            def now(cls, tz: Optional[tzinfo] =None):
                return cls(2026, 4, 28, 15, 0, 0, tzinfo=tz)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            (output_dir / "vllm_test_results_20260428_080000.csv").write_text("", encoding="utf-8")
            (output_dir / "vllm_test_results_bad_name.csv").write_text("", encoding="utf-8")

            with patch.object(history_adapter, "datetime", FixedDatetime):
                previous_after_noon, today_morning, today_after_noon = history_adapter.filter_log_files(output_dir)

        self.assertEqual(previous_after_noon, [])
        self.assertEqual(today_morning, ["vllm_test_results_20260428_080000.csv"])
        self.assertEqual(today_after_noon, [])

    def test_history_adapter_main_prints_three_periods(self) -> None:
        output = io.StringIO()
        with patch.object(history_adapter, "filter_log_files", return_value=(["a.csv"], ["b.csv"], ["c.csv"])), patch(
            "sys.stdout", output
        ):
            history_adapter.main()

        text = output.getvalue()
        self.assertIn("昨天下午:", text)
        self.assertIn("今天上午:", text)
        self.assertIn("今天下午:", text)


class TestBaseReaderModelBranches(unittest.TestCase):
    def test_default_and_conversion_branches(self) -> None:
        self.assertEqual(BaseReaderModel.get_default_value_(int), "0")
        self.assertEqual(BaseReaderModel.get_default_value_(float), "0.0")
        self.assertEqual(BaseReaderModel.get_default_value_(str), "''")
        self.assertEqual(BaseReaderModel.get_default_value_(bool), "False")
        self.assertEqual(BaseReaderModel.get_default_value_(tuple), "None")

        @dataclass
        class _FieldHolder:
            v: int = field(metadata={"tag": "v", "type": int})

        typed_field = dataclass_fields(_FieldHolder)[0]
        self.assertEqual(BaseReaderModel.get_field_lines_(typed_field, None, int), ["    v = 0"])

        int_lines = BaseReaderModel.get_conversion_lines_("v", 0, int)
        float_lines = BaseReaderModel.get_conversion_lines_("v", 1, float)
        str_lines = BaseReaderModel.get_conversion_lines_("v", 2, str)
        bool_lines = BaseReaderModel.get_conversion_lines_("v", 3, bool)
        other_lines = BaseReaderModel.get_conversion_lines_("v", 4, tuple)

        self.assertIn("_int", "\n".join(int_lines))
        self.assertIn("_float", "\n".join(float_lines))
        self.assertIn("_str", "\n".join(str_lines))
        self.assertIn("_bool", "\n".join(bool_lines))
        self.assertEqual(other_lines, ["    v = row[4]"])


class TestPortsAndHistoryService(unittest.TestCase):
    def test_get_ports_filters_pass_port(self) -> None:
        rows = cast(Iterator[CellGetValue], iter([["port", "x"], [8000, "a"], [8001, "b"]]))
        with patch.object(ports_module, "get_config", return_value=SimpleNamespace(pass_port=[8001])):
            ports = ports_module.get_ports(rows)
        self.assertEqual(ports, [8000])

    def test_history_service_check_and_analyze_and_headers(self) -> None:
        row_header = [
            "ip",
            "port",
            "modelID",
            "container_name",
            "status",
            "message",
            "actual_model",
            "expected_model",
            "extra_model",
            "missing_model",
            "response_time",
        ]
        row_failed = ["127.0.0.1", 8000, "m1", "c1", "failed", "e1", ["m1"], ["m1"], [], [], 0.1]
        row_success = ["127.0.0.1", 8001, "m2", "c2", "success", "ok", ["m2"], ["m2"], [], [], 0.2]

        with patch.object(history_service, "get_config", return_value=SimpleNamespace(csv_output_path="C:/out")), patch.object(
            history_service, "read_csv", return_value=iter([row_header, row_failed, row_success])
        ):
            results = history_service.check(( ["a.csv"], [], [] ))

        self.assertEqual(results[0], {8000: "e1"})
        self.assertEqual(results[1], {})
        self.assertEqual(results[2], {})

        output = io.StringIO()
        with patch.object(history_service, "get_config", return_value=SimpleNamespace(csv_output_path="C:/out")), patch.object(
            history_service, "read_csv", return_value=iter([["h1", "h2"], [1, 2]])
        ), patch("sys.stdout", output):
            history_service.check_headers((["a.csv"], [], []))

        self.assertIn("a.csv header: ['h1', 'h2']", output.getvalue())

    def test_check_current_filters_ports_and_main(self) -> None:
        with patch.object(
            history_service,
            "get_config",
            return_value=SimpleNamespace(source_last_type="xlsx", xlsx_input_path="x.xlsx", csv_input_path="x.csv"),
        ), patch.object(history_service, "read_xlsx", return_value=iter([["port"], [8000]])), patch.object(
            history_service, "read_csv", return_value=iter([["port"], [8000]])
        ), patch.object(history_service, "get_ports", side_effect=[[8000], [8000], [8000]]):
            filtered = history_service.check_current(({8000: "e0", 8001: "e1"}, {}, {}))

        self.assertEqual(filtered[0], {8000: "e0"})

        output = io.StringIO()
        with patch.object(history_service, "check_headers", return_value=None), patch.object(
            history_service, "check_current", return_value=({8000: "e0"}, {8100: "e1"}, {9000: "e9"})
        ), patch("sys.stdout", output):
            history_service.main()

        text = output.getvalue()
        self.assertIn("昨天中午12点到今天凌晨0点的测试结果:", text)
        self.assertIn("8000: e0", text)
        self.assertIn("8100: e1", text)
        self.assertIn("9000: e9", text)

    def test_check_current_none_and_csv_filter_branch(self) -> None:
        with patch.object(history_service, "check", return_value=({8000: "e0"}, {}, {})), patch.object(
            history_service,
            "get_config",
            return_value=SimpleNamespace(source_last_type="csv", xlsx_input_path="x.xlsx", csv_input_path="x.csv"),
        ), patch.object(history_service, "read_csv", return_value=iter([["port"], [9000]])), patch.object(
            history_service, "get_ports", return_value=[9000]
        ):
            filtered = history_service.check_current(None)

        self.assertEqual(filtered, ({}, {}, {}))


class TestPrintResults(unittest.TestCase):
    def test_print_results_success_and_failure_paths(self) -> None:
        success_output = io.StringIO()
        success_row = VLLMTestResult("127.0.0.1", 8000, "m1", "c1", "success", "ok", ["m1"], ["m1"], [], [], 0.1)
        with patch("sys.stdout", success_output):
            print_results_module.print_results([success_row])
        self.assertIn("所有测试均成功", success_output.getvalue())

        failure_output = io.StringIO()
        failed_row = VLLMTestResult(
            "127.0.0.1",
            8000,
            "m1",
            "c1",
            "failed",
            "bad",
            ["m1", "m2"],
            ["m1"],
            ["m2"],
            ["m3"],
            1.5,
        )
        with patch("sys.stdout", failure_output):
            print_results_module.print_results([failed_row])

        text = failure_output.getvalue()
        self.assertIn("status: failed", text)
        self.assertIn("response_time: 1.5", text)


class TestFallbackImports(unittest.TestCase):
    @staticmethod
    def _run_module(path: Path, run_name: str) -> dict[str, object]:
        return cast(dict[str, object], runpy.run_path(str(path), run_name=run_name))

    @staticmethod
    def _module_path(*parts: str) -> Path:
        return Path(__file__).resolve().parents[1].joinpath("src", *parts)

    def _assert_fallback_module_contains(self, path: Path, forced_target: str, symbol: str) -> None:
        with _force_import_error_once(forced_target):
            namespace = self._run_module(path, "not_main")
        self.assertIn(symbol, namespace)

    def test_fallback_import_modules(self) -> None:
        cases = [
            (self._module_path("models", "base.py"), "src.models.type", "BaseReaderModel"),
            (self._module_path("adapters", "read_history_results.py"), "src.config.settings", "filter_log_files"),
            (self._module_path("services", "check_history_results.py"), "src.adapters.read_history_results", "check_current"),
            (self._module_path("utils", "print_results.py"), "src.models.vllm_results", "print_results"),
        ]

        for path, target, symbol in cases:
            with self.subTest(path=str(path), target=target, symbol=symbol):
                self._assert_fallback_module_contains(path, target, symbol)

    def test_ports_module_fallback_import_and_main(self) -> None:
        ports_path = (
            self._extracted_from_test_vllm_results_module_fallback_import_2(
                "ports.py", "get_ports"
            )
        )
        output = io.StringIO()
        with patch("src.adapters.read_xlsx.read_xlsx", return_value=iter([["port"], [8000], [8002]])), patch.object(
            ports_module, "get_config", return_value=SimpleNamespace(xlsx_input_path="x.xlsx", pass_port=[8002])
        ), patch("sys.stdout", output):
            ports_module.main()
        self.assertIn("Ports: [8000]", output.getvalue())

        with _force_import_error_once("src.adapters.read_xlsx"), patch(
            "src.adapters.read_xlsx.read_xlsx", return_value=iter([["port"], [8000]])
        ), patch.object(
            ports_module, "get_config", return_value=SimpleNamespace(xlsx_input_path="x.xlsx", pass_port=[])
        ), patch("sys.stdout", io.StringIO()):
            ports_module.main()

        main_output = io.StringIO()
        with patch("src.adapters.read_xlsx.read_xlsx", return_value=iter([["port"], [7000]])), patch(
            "src.config.settings.get_config", return_value=SimpleNamespace(xlsx_input_path="x.xlsx", pass_port=[])
        ), patch("sys.stdout", main_output):
            self._run_module(ports_path, "__main__")
        self.assertIn("Ports: [7000]", main_output.getvalue())

    def test_vllm_results_module_fallback_import(self) -> None:
        _ = (
            self._extracted_from_test_vllm_results_module_fallback_import_2(
                "vllm_results.py", "VLLMTestResult"
            )
        )

    def _extracted_from_test_vllm_results_module_fallback_import_2(self, arg0: str, arg1: str) -> Path:
        result = self._module_path("models", arg0)
        namespace = self._run_module(result, "not_main")
        self.assertIn(arg1, namespace)
        return result

    def test_read_history_results_module_fallback_import(self) -> None:
        main_output = self._extracted_from_test_check_history_results_module_fallback_import_and_main_2(
            "adapters", "read_history_results.py"
        )
        self.assertIn("今天下午:", main_output.getvalue())

    def test_check_history_results_module_fallback_import_and_main(self) -> None:
        output = self._extracted_from_test_check_history_results_module_fallback_import_and_main_2(
            "services", "check_history_results.py"
        )
        text = output.getvalue()
        self.assertIn("昨天中午12点到今天凌晨0点的测试结果:", text)
        self.assertIn("今天凌晨0点到今天中午12点的测试结果:", text)
        self.assertIn("今天中午12点到现在的测试结果:", text)


    def _extracted_from_test_check_history_results_module_fallback_import_and_main_2(self, arg0: str, arg1: str) -> io.StringIO:
        history_path = self._module_path(arg0, arg1)
        result = io.StringIO()
        with patch("sys.stdout", result):
            self._run_module(history_path, "__main__")
        return result


if __name__ == "__main__":
    unittest.main()
