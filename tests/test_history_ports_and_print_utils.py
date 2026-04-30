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
    def test_filter_log_files_uses_december_month_end_branch(self) -> None:
        class FixedDecemberDatetime(real_datetime):
            @classmethod
            def now(cls, tz: Optional[tzinfo] = None):
                return cls(2026, 12, 15, 10, 0, 0, tzinfo=tz)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            (output_dir / "vllm_test_results_20261215_080000.csv").write_text("", encoding="utf-8")
            sample_result = VLLMTestResult("127.0.0.1", 8010, "m10", "c10", "failed", "bad", ["m10"], ["m10"], [], [], 1.0)

            with patch.object(history_adapter, "get_config", return_value=SimpleNamespace(csv_output_path=str(output_dir))), patch.object(
                history_adapter, "datetime", FixedDecemberDatetime
            ), patch.object(history_adapter.VLLMTestResult, "from_reader", return_value=iter([sample_result])):
                results = list(history_adapter.filter_log_files(None))

        self.assertEqual(results, [("2026-12-15 上午", [sample_result])])

    def test_filter_log_files_handles_default_directory_and_import_fallback(self) -> None:
        class FixedDatetime(real_datetime):
            @classmethod
            def now(cls, tz: Optional[tzinfo] = None):
                return cls(2026, 4, 30, 15, 0, 0, tzinfo=tz)

        def mock_from_reader(*_args: object, **_kwargs: object) -> Iterator[VLLMTestResult]:
            sample_result = VLLMTestResult("127.0.0.1", 8000, "m1", "c1", "failed", "bad", ["m1"], ["m1"], [], [], 0.1)
            return iter([sample_result])

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            (output_dir / "subdir").mkdir()
            (output_dir / "not_a_result.txt").write_text("", encoding="utf-8")
            (output_dir / "vllm_test_results_bad.csv").write_text("", encoding="utf-8")
            (output_dir / "vllm_test_results_20260430_080000.csv").write_text("", encoding="utf-8")
            (output_dir / "vllm_test_results_20260430_130000.csv").write_text("", encoding="utf-8")
            (output_dir / "vllm_test_results_20260501_080000.csv").write_text("", encoding="utf-8")

            sample_result = VLLMTestResult("127.0.0.1", 8000, "m1", "c1", "failed", "bad", ["m1"], ["m1"], [], [], 0.1)

            with patch.object(history_adapter, "get_config", return_value=SimpleNamespace(csv_output_path=str(output_dir))), patch.object(
                history_adapter, "datetime", FixedDatetime
            ), _force_import_error_once("src.adapters.read_csv"), patch.object(
                history_adapter.VLLMTestResult,
                "from_reader",
                side_effect=mock_from_reader,
            ):
                results = list(history_adapter.filter_log_files(None))

        self.assertCountEqual([period for period, _ in results], ["2026-04-30 上午", "2026-04-30 下午"])
        self.assertTrue(all(group == [sample_result] for _, group in results))

    def test_filter_log_files_handles_missing_dir_and_bad_name(self) -> None:
        class FixedDatetime(real_datetime):
            @classmethod
            def now(cls, tz: Optional[tzinfo] = None):
                return cls(2026, 4, 28, 15, 0, 0, tzinfo=tz)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            valid_path = output_dir / "vllm_test_results_20260428_080000.csv"
            valid_path.write_text("", encoding="utf-8")
            (output_dir / "vllm_test_results_bad_name.csv").write_text("", encoding="utf-8")

            sample_result = VLLMTestResult("127.0.0.1", 8000, "m1", "c1", "failed", "bad", ["m1"], ["m1"], [], [], 0.1)

            with patch.object(history_adapter, "datetime", FixedDatetime), patch.object(
                history_adapter.VLLMTestResult,
                "from_reader",
                return_value=iter([sample_result]),
            ) as from_reader_mock:
                results = list(history_adapter.filter_log_files(output_dir))

        self.assertEqual(results, [("2026-04-28 上午", [sample_result])])
        from_reader_mock.assert_called_once()
        self.assertEqual(valid_path.name, "vllm_test_results_20260428_080000.csv")

    def test_history_adapter_main_prints_three_periods(self) -> None:
        output = io.StringIO()
        results = [
            ("昨天上午", [VLLMTestResult("127.0.0.1", 8000, "m1", "c1", "failed", "a", ["m1"], ["m1"], [], [], 0.1)]),
            ("今天上午", [VLLMTestResult("127.0.0.1", 8001, "m2", "c2", "success", "b", ["m2"], ["m2"], [], [], 0.2)]),
            ("今天下午", [VLLMTestResult("127.0.0.1", 8002, "m3", "c3", "failed", "c", ["m3"], ["m3"], [], [], 0.3)]),
        ]

        with patch.object(history_adapter, "filter_log_files", return_value=iter(results)), patch("sys.stdout", output):
            history_adapter.main()

        text = output.getvalue()
        self.assertIn("昨天上午: 8000: a (failed)", text)
        self.assertIn("今天上午: 8001: b (success)", text)
        self.assertIn("今天下午: 8002: c (failed)", text)


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

    def test_from_reader_builds_loader_and_returns_base_instance(self) -> None:
        @dataclass(slots=True, frozen=True)
        class _TaggedReader(BaseReaderModel):
            value: int = field(default=0, metadata={"tag": "value", "type": int})
            ignored: int = field(default=0)

            @classmethod
            def reset_reader_state_for_test(cls) -> None:
                cls._cache.clear()
                cls._tags = ()

        _TaggedReader.reset_reader_state_for_test()

        header_row: CellGetValue = ["value"]
        data_row: CellGetValue = [123]
        rows: Iterator[CellGetValue] = iter([header_row, data_row])

        results = list(_TaggedReader.from_reader(rows))

        self.assertEqual(results, [_TaggedReader(value=123)])

    def test_from_reader_handles_empty_input(self) -> None:
        self.assertEqual(list(BaseReaderModel.from_reader(iter([]))), [])


class TestPortsAndHistoryService(unittest.TestCase):
    def test_get_ports_filters_pass_port(self) -> None:
        rows = cast(Iterator[CellGetValue], iter([["port", "x"], [8000, "a"], [8001, "b"]]))
        with patch.object(ports_module, "get_config", return_value=SimpleNamespace(pass_port=[8001])):
            ports = ports_module.get_ports(rows)
        self.assertEqual(ports, [8000])

    def test_analyze_results_filters_failed_rows_and_deduplicates(self) -> None:
        failed_one = VLLMTestResult("127.0.0.1", 8000, "m1", "c1", "failed", "e1", ["m1"], ["m1"], [], [], 0.1)
        failed_two = VLLMTestResult("127.0.0.1", 8001, "m2", "c2", "failed", "e2", ["m2"], ["m2"], [], [], 0.2)
        success = VLLMTestResult("127.0.0.1", 8002, "m3", "c3", "success", "ok", ["m3"], ["m3"], [], [], 0.3)

        inputs = iter([
            ("昨天中午12点到今天凌晨0点的测试结果", [failed_one, failed_one, success]),
            ("今天凌晨0点到今天中午12点的测试结果", [failed_two]),
        ])

        results = set(history_service.analyze_results(inputs))

        self.assertEqual(
            results,
            {
                ("昨天中午12点到今天凌晨0点的测试结果", 8000, "e1", "m1"),
                ("今天凌晨0点到今天中午12点的测试结果", 8001, "e2", "m2"),
            },
        )

    def test_analyze_results_uses_default_filter_log_files(self) -> None:
        failed = VLLMTestResult("127.0.0.1", 8003, "m4", "c4", "failed", "e4", ["m4"], ["m4"], [], [], 0.4)

        with patch.object(history_service, "filter_log_files", return_value=iter([("今天下午", [failed])])) as filter_mock:
            results = list(history_service.analyze_results())

        filter_mock.assert_called_once()
        self.assertEqual(results, [("今天下午", 8003, "e4", "m4")])

    def test_history_service_main_prints_results(self) -> None:
        output = io.StringIO()
        with patch.object(history_service, "analyze_results", return_value=iter([("今天下午", 8004, "e5", "m5")])):
            with patch("sys.stdout", output):
                history_service.main()

        self.assertIn("今天下午: 8004: e5 (m5)", output.getvalue())


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
            (self._module_path("services", "check_history_results.py"), "src.adapters.read_history_results", "analyze_results"),
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
        main_output = self._run_history_adapter_main_with_mocked_results()
        self.assertIn("今天下午: 8000: bad (failed)", main_output.getvalue())

    def test_check_history_results_module_fallback_import_and_main(self) -> None:
        output = self._run_history_service_main_with_mocked_results()
        text = output.getvalue()
        self.assertIn("昨天中午12点到今天凌晨0点的测试结果: 8000: bad (m1)", text)
        self.assertIn("今天凌晨0点到今天中午12点的测试结果: 8001: warn (m2)", text)
        self.assertIn("今天中午12点到现在的测试结果: 8002: ok (m3)", text)

    def test_read_history_results_module_main_guard(self) -> None:
        history_path = self._module_path("adapters", "read_history_results.py")
        result = io.StringIO()

        class FixedDatetime(real_datetime):
            @classmethod
            def now(cls, tz: Optional[tzinfo] = None):
                return cls(2026, 4, 30, 15, 0, 0, tzinfo=tz)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            (output_dir / "vllm_test_results_20260430_080000.csv").write_text("", encoding="utf-8")
            sample_result = VLLMTestResult("127.0.0.1", 8009, "m9", "c9", "failed", "bad", ["m9"], ["m9"], [], [], 0.9)

            with patch("sys.stdout", result), patch("datetime.datetime", FixedDatetime), patch(
                "src.config.settings.get_config", return_value=SimpleNamespace(csv_output_path=str(output_dir))
            ), patch(
                "src.models.vllm_results.VLLMTestResult.from_reader",
                return_value=iter([sample_result]),
            ), patch("src.adapters.read_csv.read_csv", return_value=iter([["port"], [8009]])):
                self._run_module(history_path, "__main__")

        self.assertIn("2026-04-30 上午: 8009: bad (failed)", result.getvalue())

    def test_check_history_results_module_main_guard(self) -> None:
        history_path = self._module_path("services", "check_history_results.py")
        result = io.StringIO()

        with patch("sys.stdout", result), patch(
            "src.adapters.read_history_results.filter_log_files",
            return_value=iter([("今天下午", [VLLMTestResult("127.0.0.1", 8007, "m7", "c7", "failed", "bad", ["m7"], ["m7"], [], [], 0.7)])]),
        ):
            self._run_module(history_path, "__main__")

        self.assertIn("今天下午: 8007: bad (m7)", result.getvalue())

    def _run_history_adapter_main_with_mocked_results(self) -> io.StringIO:
        result = io.StringIO()
        sample_failed = VLLMTestResult("127.0.0.1", 8000, "m1", "c1", "failed", "bad", ["m1"], ["m1"], [], [], 0.1)

        with patch("sys.stdout", result), patch(
            "src.adapters.read_history_results.filter_log_files", return_value=iter([("今天下午", [sample_failed])])
        ):
            history_adapter.main()

        return result

    def _run_history_service_main_with_mocked_results(self) -> io.StringIO:
        result = io.StringIO()
        sample_results = iter([
            ("昨天中午12点到今天凌晨0点的测试结果", 8000, "bad", "m1"),
            ("今天凌晨0点到今天中午12点的测试结果", 8001, "warn", "m2"),
            ("今天中午12点到现在的测试结果", 8002, "ok", "m3"),
        ])

        with patch("sys.stdout", result), patch(
            "src.services.check_history_results.analyze_results", return_value=sample_results
        ):
            history_service.main()

        return result

if __name__ == "__main__":
    unittest.main()
