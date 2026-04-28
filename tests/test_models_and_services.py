from __future__ import annotations

import unittest
import importlib
import tempfile
from datetime import datetime as real_datetime, tzinfo
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Iterator, NoReturn, cast, Optional
from unittest.mock import AsyncMock, patch

import httpx

read_xlsx_module = importlib.import_module("src.adapters.read_xlsx")
read_csv_module = importlib.import_module("src.adapters.read_csv")
read_history_results_module = importlib.import_module("src.adapters.read_history_results")
from src.models import sheet as sheet_module
from src.models.type import CellGetValue
from src.models.vllm_results import VLLMTestResult
from src.services import test_vllm as service_module


class FakeSheet:
    def __init__(self, rows: list[list[object]]) -> None:
        self._rows = rows

    def to_python(self) -> Iterator[list[object]]:
        return iter(self._rows)


class FakeWorkbook:
    def __init__(self, sheet: FakeSheet | None) -> None:
        self._sheet = sheet

    def get_sheet_by_name(self, name: str) -> FakeSheet | None:
        return self._sheet


@dataclass
class FakeClientCase:
    expected_models: list[str]
    payload: object
    status_code: int = 200
    api_key: str | None = None


class TestSheetAndAdapter(unittest.TestCase):
    def setUp(self) -> None:
        cache = getattr(sheet_module.Sheet, "_cache")
        cache.clear()
        setattr(sheet_module.Sheet, "_tags", ())
        sheet_cache = getattr(sheet_module, "_sheet_cache")
        sheet_cache.clear()

    def test_sheet_from_reader_converts_values_and_defaults(self) -> None:
        header: CellGetValue = [
            "port",
            "modelID",
            "模型名",
            "监控id",
            "GPU型号",
            "GPU数量",
            "上下文长度（K）",
            "容器名",
            "调用方法",
        ]
        row_one: CellGetValue = [30000, "model-a", "name-a", "monitor-a", "A100", 2, 8, "container-a", "https://a/chat/completions"]
        row_two: CellGetValue = ["bad", "model-b", "", "monitor-b", "B200", "bad", "oops", "container-b", "https://b/chat/completions"]
        rows: Iterator[CellGetValue] = iter([header, row_one, row_two])

        results = list(sheet_module.Sheet.from_reader(rows))

        self.assertEqual(results[0].port, 30000)
        self.assertEqual(results[0].model_id, "model-a")
        self.assertEqual(results[1].port, 0)
        self.assertEqual(results[1].model_name, "")
        self.assertEqual(results[1].gpu_count, 0)
        self.assertEqual(results[1].context_length, 0)

    def test_sheet_from_reader_uses_default_reader(self) -> None:
        header: CellGetValue = [
            "port",
            "modelID",
            "模型名",
            "监控id",
            "GPU型号",
            "GPU数量",
            "上下文长度（K）",
            "容器名",
            "调用方法",
        ]
        row: CellGetValue = [30002, "model-d", "name-d", "monitor-d", "L40", 8, 32, "container-d", "https://d/chat/completions"]

        config = SimpleNamespace(xlsx_input_path="input.xlsx", csv_input_path="ignored.csv", source_last_type="xlsx")

        with patch("src.models.sheet.get_config", return_value=config), patch(
            "src.models.sheet.read_xlsx", return_value=iter([header, row])
        ):
            results: list[sheet_module.Sheet] = list(sheet_module.get_sheet_iterator())

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].model_id, "model-d")

    def test_sheet_from_reader_supports_bool_and_passthrough_types(self) -> None:
        header: CellGetValue = [
            "port",
            "modelID",
            "模型名",
            "监控id",
            "GPU型号",
            "GPU数量",
            "上下文长度（K）",
            "容器名",
            "调用方法",
        ]
        row = cast(
            CellGetValue,
            [30003, "model-e", "name-e", "monitor-e", "RTX6000", "yes", ("raw", "value"), "container-e", "https://e/chat/completions"],
        )

        fake_field_specs = [
            SimpleNamespace(name="port", metadata={"tag": "port", "type": int}),
            SimpleNamespace(name="model_id", metadata={"tag": "modelID", "type": str}),
            SimpleNamespace(name="model_name", metadata={"tag": "模型名", "type": str}),
            SimpleNamespace(name="monitor_id", metadata={"tag": "监控id", "type": str}),
            SimpleNamespace(name="gpu_model", metadata={"tag": "GPU型号", "type": str}),
            SimpleNamespace(name="gpu_count", metadata={"tag": "GPU数量", "type": bool}),
            SimpleNamespace(name="context_length", metadata={"tag": "上下文长度（K）", "type": object}),
            SimpleNamespace(name="container_name", metadata={"tag": "容器名", "type": str}),
            SimpleNamespace(name="call_method", metadata={"tag": "调用方法", "type": str}),
        ]

        def fake_fields(cls: type[object]) -> list[SimpleNamespace]:
            return fake_field_specs if cls is sheet_module.Sheet else []

        with patch("src.models.base.fields", side_effect=fake_fields):
            results = list(sheet_module.Sheet.from_reader(iter([header, row])))

        self.assertTrue(results[0].gpu_count)
        self.assertEqual(results[0].context_length, ("raw", "value"))

    def test_sheet_from_reader_covers_float_and_untagged_fields(self) -> None:
        header: CellGetValue = [
            "port",
            "modelID",
            "模型名",
            "监控id",
            "GPU型号",
            "GPU数量",
            "上下文长度（K）",
            "容器名",
            "调用方法",
        ]
        row: CellGetValue = [30004, "model-f", "name-f", "monitor-f", "A800", 6, 12.5, "container-f", "https://f/chat/completions"]

        fake_field_specs = [
            SimpleNamespace(name="port", metadata={"tag": "port", "type": int}),
            SimpleNamespace(name="model_id", metadata={"tag": "modelID", "type": str}),
            SimpleNamespace(name="model_name", metadata={"tag": "模型名", "type": str}),
            SimpleNamespace(name="monitor_id", metadata={"tag": "监控id", "type": str}),
            SimpleNamespace(name="gpu_model", metadata={"tag": "GPU型号", "type": str}),
            SimpleNamespace(name="gpu_count", metadata={"tag": "GPU数量", "type": int}),
            SimpleNamespace(name="context_length", metadata={"tag": "上下文长度（K）", "type": float}),
            SimpleNamespace(name="container_name", metadata={"tag": "容器名", "type": str}),
            SimpleNamespace(name="call_method", metadata={"tag": "调用方法", "type": str}),
            SimpleNamespace(name="ignored", metadata={}),
        ]

        with patch("src.models.base.fields", return_value=fake_field_specs):
            results = list(sheet_module.Sheet.from_reader(iter([header, row])))

        self.assertEqual(results[0].context_length, 12.5)

    def test_get_sheet_iterator_caches_iterator(self) -> None:
        header = [
            "port",
            "modelID",
            "模型名",
            "监控id",
            "GPU型号",
            "GPU数量",
            "上下文长度（K）",
            "容器名",
            "调用方法",
        ]
        row = [30001, "model-c", "name-c", "monitor-c", "H100", 4, 16, "container-c", "https://c/chat/completions"]

        with patch("src.models.sheet.read_xlsx", side_effect=[iter([header, row]), iter([header, row])]):
            first = sheet_module.get_sheet_iterator("input.xlsx", refresh=True)
            second = sheet_module.get_sheet_iterator("input.xlsx", refresh=False)
            self.assertIs(first, second)
            self.assertEqual(len(list(first)), 1)

            third = sheet_module.get_sheet_iterator("input.xlsx", refresh=True)
            self.assertIsNot(first, third)
            self.assertEqual(len(list(third)), 1)

    def test_get_sheet_iterator_uses_csv_reader_when_config_says_csv(self) -> None:
        header = [
            "port",
            "modelID",
            "模型名",
            "监控id",
            "GPU型号",
            "GPU数量",
            "上下文长度（K）",
            "容器名",
            "调用方法",
        ]
        row = [30005, "model-g", "name-g", "monitor-g", "A10", 1, 4, "container-g", "https://g/chat/completions"]
        config = SimpleNamespace(csv_input_path="input.csv", xlsx_input_path="ignored.xlsx", source_last_type="csv")

        with patch("src.models.sheet.get_config", return_value=config), patch(
            "src.models.sheet.read_csv", return_value=iter([header, row])
        ) as csv_mock:
            results = list(sheet_module.get_sheet_iterator())

        csv_mock.assert_called_once_with(Path("input.csv"))
        self.assertEqual(results[0].model_id, "model-g")

    def test_get_sheet_iterator_uses_csv_reader_for_explicit_csv_path(self) -> None:
        header = [
            "port",
            "modelID",
            "模型名",
            "监控id",
            "GPU型号",
            "GPU数量",
            "上下文长度（K）",
            "容器名",
            "调用方法",
        ]
        row = [30007, "model-i", "name-i", "monitor-i", "L4", 3, 24, "container-i", "https://i/chat/completions"]

        with patch("src.models.sheet.read_csv", return_value=iter([header, row])) as csv_mock:
            results = list(sheet_module.get_sheet_iterator("input.csv"))

        csv_mock.assert_called_once_with(Path("input.csv"))
        self.assertEqual(results[0].model_id, "model-i")

    def test_get_sheet_iterator_defaults_to_xlsx_when_source_type_is_unknown(self) -> None:
        header = [
            "port",
            "modelID",
            "模型名",
            "监控id",
            "GPU型号",
            "GPU数量",
            "上下文长度（K）",
            "容器名",
            "调用方法",
        ]
        row = [30006, "model-h", "name-h", "monitor-h", "A30", 2, 64, "container-h", "https://h/chat/completions"]
        config = SimpleNamespace(csv_input_path="ignored.csv", xlsx_input_path="fallback.xlsx", source_last_type="unknown")

        with patch("src.models.sheet.get_config", return_value=config), patch(
            "src.models.sheet.read_xlsx", return_value=iter([header, row])
        ) as xlsx_mock:
            results = list(sheet_module.get_sheet_iterator())

        xlsx_mock.assert_called_once_with(Path("fallback.xlsx"))
        self.assertEqual(results[0].model_id, "model-h")

    def test_main_delegates_to_print_and_write_helpers(self) -> None:
        sentinel_iterator = object()

        with patch("src.models.sheet.get_sheet_iterator", return_value=sentinel_iterator) as iterator_mock, patch(
            "src.models.sheet.test_print_from_dataclass"
        ) as print_mock, patch("src.models.sheet.write_csv_from_dataclass") as write_mock, patch(
            "src.models.sheet.get_config", return_value=SimpleNamespace(csv_output_path="output")
        ):
            sheet_module.main()

        self.assertEqual(iterator_mock.call_count, 2)
        print_mock.assert_called_once_with(sentinel_iterator)
        write_mock.assert_called_once_with(sentinel_iterator, Path("output") / "test_sheet.csv")

    def test_read_csv_yields_rows_and_raises_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "rows.csv"
            csv_path.write_text("a,b\n1,2\n", encoding="utf-8-sig")

            self.assertEqual(list(read_csv_module.read_csv(csv_path)), [["a", "b"], ["1", "2"]])

            missing_path = Path(temp_dir) / "missing.csv"
            with self.assertRaises(FileNotFoundError) as context:
                list(read_csv_module.read_csv(missing_path))

        self.assertIn("missing.csv", str(context.exception))

    def test_read_csv_supports_custom_encoding_and_error_replace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "rows_gbk.csv"
            csv_path.write_bytes("a,b\n1,2\n坏,3\n".encode("gbk"))

            rows = list(read_csv_module.read_csv(csv_path, encoding="utf-8"))

        self.assertEqual(rows[0], ["a", "b"])
        self.assertEqual(rows[1], ["1", "2"])
        self.assertEqual(rows[2][1], "3")

    def test_read_xlsx_yields_rows(self) -> None:
        fake_sheet = FakeSheet([[1, 2], [3, 4]])
        fake_workbook = FakeWorkbook(fake_sheet)

        with patch("src.adapters.read_xlsx.get_config", return_value=SimpleNamespace(xlsx_input_sheet_name="Sheet1")), patch(
            "src.adapters.read_xlsx.CalamineWorkbook.from_path", return_value=fake_workbook
        ):
            self.assertEqual(list(read_xlsx_module.read_xlsx(Path("dummy.xlsx"))), [[1, 2], [3, 4]])

    def test_read_xlsx_uses_default_path_when_path_is_missing(self) -> None:
        fake_sheet = FakeSheet([[5, 6]])
        fake_workbook = FakeWorkbook(fake_sheet)

        with patch(
            "src.adapters.read_xlsx.get_config",
            return_value=SimpleNamespace(xlsx_input_path="default.xlsx", xlsx_input_sheet_name="Sheet1"),
        ), patch("src.adapters.read_xlsx.CalamineWorkbook.from_path", return_value=fake_workbook) as from_path_mock:
            self.assertEqual(list(read_xlsx_module.read_xlsx()), [[5, 6]])

        from_path_mock.assert_called_once_with("default.xlsx")

    def test_read_xlsx_raises_when_sheet_missing(self) -> None:
        fake_workbook = FakeWorkbook(None)

        with patch("src.adapters.read_xlsx.get_config", return_value=SimpleNamespace(xlsx_input_sheet_name="Missing")), patch(
            "src.adapters.read_xlsx.CalamineWorkbook.from_path", return_value=fake_workbook
        ):
            with self.assertRaises(ValueError) as context:
                list(read_xlsx_module.read_xlsx(Path("dummy.xlsx")))

        self.assertIn("Missing", str(context.exception))

    def test_read_xlsx_raises_when_file_missing(self) -> None:
        with patch("src.adapters.read_xlsx.get_config", return_value=SimpleNamespace(xlsx_input_sheet_name="Sheet1")), patch(
            "src.adapters.read_xlsx.CalamineWorkbook.from_path", side_effect=FileNotFoundError
        ):
            with self.assertRaises(FileNotFoundError) as context:
                list(read_xlsx_module.read_xlsx(Path("missing.xlsx")))

        self.assertIn("missing.xlsx", str(context.exception))

    def test_filter_log_files_uses_friday_afternoon_window_on_monday(self) -> None:
        class FixedMondayDatetime(real_datetime):
            @classmethod
            def now(cls, tz: Optional[tzinfo] =None):
                return cls(2026, 4, 27, 10, 0, 0, tzinfo=tz)

        filenames = [
            "vllm_test_results_20260424_130000.csv",  # Friday afternoon
            "vllm_test_results_20260426_150000.csv",  # Sunday afternoon
            "vllm_test_results_20260427_090000.csv",  # Monday morning
            "vllm_test_results_20260427_130000.csv",  # Monday afternoon
            "vllm_test_results_20260424_110000.csv",  # Friday before noon
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            for name in filenames:
                (output_dir / name).write_text("", encoding="utf-8")

            with patch.object(read_history_results_module, "datetime", FixedMondayDatetime):
                previous_after_noon, today_morning, today_after_noon = read_history_results_module.filter_log_files(output_dir)

        self.assertCountEqual(
            previous_after_noon,
            [
                "vllm_test_results_20260424_130000.csv",
                "vllm_test_results_20260426_150000.csv",
            ],
        )
        self.assertEqual(today_morning, ["vllm_test_results_20260427_090000.csv"])
        self.assertEqual(today_after_noon, ["vllm_test_results_20260427_130000.csv"])


class TestCheckVllmModels(unittest.IsolatedAsyncioTestCase):
    async def _run_case(
        self,
        case: FakeClientCase,
        json_side_effect: Exception | None = None,
    ) -> tuple[VLLMTestResult, AsyncMock]:
        client = AsyncMock()

        if json_side_effect is None:
            response = SimpleNamespace(status_code=case.status_code, json=lambda: case.payload)
        else:
            def raise_json() -> NoReturn:
                raise json_side_effect

            response = SimpleNamespace(status_code=case.status_code, json=raise_json)

        client.get = AsyncMock(return_value=response)

        with patch("src.services.test_vllm.time.time", side_effect=[100.0, 100.25]):
            result = await service_module.check_vllm_models(
                client=client,
                url="https://example.com/chat/completions",
                port=8000,
                container_name="test_c",
                expected_models=case.expected_models,
                model_id="m-under-test",
                api_key=case.api_key,
            )

        return result, client

    async def test_check_vllm_models_success_and_headers(self) -> None:
        case = FakeClientCase(
            expected_models=["m1", "m2"],
            payload={"data": [{"id": "m1"}, {"id": "m2"}]},
            api_key="secret",
        )

        result, client = await self._run_case(case)

        self.assertEqual(result.status, "success")
        self.assertEqual(result.actual_model, ["m1", "m2"])
        self.assertEqual(result.message, "模型完全匹配 (共2个模型)")
        client.get.assert_awaited_once()
        called_url = client.get.await_args.args[0]
        called_headers = client.get.await_args.kwargs["headers"]
        self.assertEqual(called_url, "https://example.com/models")
        self.assertEqual(called_headers, {"Authorization": "Bearer secret"})

    async def test_check_vllm_models_reports_missing_extra_and_both(self) -> None:
        cases = [
            (FakeClientCase(["m1", "m2"], {"data": [{"id": "m1"}]}), "发现1个缺失模型"),
            (FakeClientCase(["m1"], {"data": [{"id": "m1"}, {"id": "extra"}]}), "发现1个多余模型"),
            (FakeClientCase(["m1", "m2"], {"data": [{"id": "m1"}, {"id": "extra"}]}), "发现1个缺失模型; 发现1个多余模型"),
        ]

        for case, expected_message in cases:
            with self.subTest(expected_message=expected_message):
                result, _ = await self._run_case(case)
                self.assertEqual(result.status, "failed")
                self.assertIn(expected_message, result.message)

    async def test_check_vllm_models_reports_non_200_and_bad_json(self) -> None:
        non_200, _ = await self._run_case(FakeClientCase(["m1"], {"data": [{"id": "m1"}]}, status_code=500))
        self.assertEqual(non_200.status, "failed")
        self.assertIn("状态码: 500", non_200.message)

        missing_data, _ = await self._run_case(FakeClientCase(["m1"], {}))
        self.assertEqual(missing_data.status, "failed")
        self.assertIn("缺少'data'字段", missing_data.message)

        malformed, _ = await self._run_case(FakeClientCase(["m1"], object()), json_side_effect=ValueError("bad json"))
        self.assertEqual(malformed.status, "failed")
        self.assertIn("无法解析API返回的JSON数据", malformed.message)

    async def test_check_vllm_models_handles_empty_expected_and_extra_models(self) -> None:
        result, _ = await self._run_case(FakeClientCase([], {"data": [{"id": "m1"}, {"id": "m2"}]}))

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.extra_model, ["m1", "m2"])
        self.assertEqual(result.missing_model, [])

async def test_check_vllm_models_handles_timeout(self: TestCheckVllmModels) -> None:
    timeout_client = AsyncMock()
    
    expected_timeout_val = 5.0
    timeout_client.timeout.connect = expected_timeout_val

    timeout_client.get.side_effect = httpx.TimeoutException("Connect Timeout")
    
    with patch("src.services.test_vllm.time.time", return_value=100.0):
        timeout_result = await service_module.check_vllm_models(
            client=timeout_client,
            url="https://example.com/chat/completions",
            port=8000,
            container_name="test_c",
            expected_models=["m1"],
            model_id="m1",
        )
    
    self.assertEqual(timeout_result.status, "timeout")
    self.assertEqual(timeout_result.response_time, expected_timeout_val)
    self.assertIn(f"请求超时（超过{expected_timeout_val}秒）", timeout_result.message)

    request_client = AsyncMock()
    request_client.get = AsyncMock(side_effect=httpx.RequestError("boom", request=httpx.Request("GET", "https://example.com")))
    with patch("src.services.test_vllm.time.time", side_effect=[100.0, 100.25]):
        request_result = await service_module.check_vllm_models(
            client=request_client,
            url="https://example.com/chat/completions",
            port=8000,
            container_name="test_c",
            expected_models=["m1"],
            model_id="m1",
        )
    self.assertEqual(request_result.status, "failed")
    self.assertIn("连接失败", request_result.message)

    unknown_client = AsyncMock()
    unknown_client.get = AsyncMock(side_effect=RuntimeError("boom"))
    with patch("src.services.test_vllm.time.time", side_effect=[100.0, 100.25]):
        unknown_result = await service_module.check_vllm_models(
            client=unknown_client,
            url="https://example.com/chat/completions",
            port=8000,
            container_name="test_c",
            expected_models=["m1"],
            model_id="m1",
        )
    self.assertEqual(unknown_result.status, "failed")
    self.assertIn("发生未知错误", unknown_result.message)
    self.assertEqual(unknown_result.model_id, "m1")