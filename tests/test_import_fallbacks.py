from __future__ import annotations

import builtins
import runpy
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from types import ModuleType
from typing import Generator
from unittest.mock import patch


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


class TestImportFallbacks(unittest.TestCase):
    def test_settings_module_uses_import_fallback(self) -> None:
        namespace = (
            self._extracted_from_test_write_csv_module_uses_import_fallback_2(
                "config", "settings.py", "src.utils.get_path", "get_config"
            )
        )
        self.assertIn("JsonConfig", namespace)

    def test_main_module_uses_import_fallback(self) -> None:
        main_path = Path(__file__).resolve().parents[1] / "src" / "main.py"

        with _force_import_error_once("src.controllers.vllm_test_controller"):
            namespace = runpy.run_path(str(main_path), run_name="not_main")

        self.assertIn("run", namespace)

    def test_read_xlsx_module_uses_import_fallback(self) -> None:
        _namespace = (
            self._extracted_from_test_write_csv_module_uses_import_fallback_2(
                "adapters", "read_xlsx.py", "src.config", "read_xlsx"
            )
        )

    def test_read_csv_module_uses_import_fallback(self) -> None:
        _namespace = (
            self._extracted_from_test_write_csv_module_uses_import_fallback_2(
                "adapters", "read_csv.py", "src.models.type", "read_csv"
            )
        )

    def test_sheet_module_uses_import_fallback_and_main_block(self) -> None:
        sheet_path = Path(__file__).resolve().parents[1] / "src" / "models" / "sheet.py"

        with _force_import_error_once("src.adapters.read_xlsx"), patch(
            "src.adapters.read_xlsx.read_xlsx", return_value=iter([])
        ), patch(
            "src.config.get_config",
            return_value=SimpleNamespace(
                xlsx_input_path="ignored.xlsx",
                xlsx_input_sheet_name="Sheet1",
                csv_input_path="ignored.csv",
                csv_output_path=tempfile.gettempdir(),
                source_last_type="xlsx",
            ),
        ), patch(
            "src.utils.test_print.test_print_from_dataclass"
        ) as mock_print, patch("src.utils.write_csv.write_csv_from_dataclass") as mock_write:
            namespace = runpy.run_path(str(sheet_path), run_name="__main__")

        self.assertIn("Sheet", namespace)
        mock_print.assert_called_once()
        mock_write.assert_called_once()

    def test_test_print_module_uses_import_fallback(self) -> None:
        _namespace = (
            self._extracted_from_test_write_csv_module_uses_import_fallback_2(
                "utils", "test_print.py", "src.models", "test_print_from_dataclass"
            )
        )

    def test_write_csv_module_uses_import_fallback(self) -> None:
        _namespace = (
            self._extracted_from_test_write_csv_module_uses_import_fallback_2(
                "utils", "write_csv.py", "src.models", "write_csv_from_dataclass"
            )
        )

    def _extracted_from_test_write_csv_module_uses_import_fallback_2(self, arg0: str, arg1: str, arg2: str, arg3: str) -> dict[str, object]:
        settings_path = Path(__file__).resolve().parents[1] / "src" / arg0 / arg1
        with _force_import_error_once(arg2):
            result = runpy.run_path(str(settings_path), run_name="not_main")
        self.assertIn(arg3, result)
        return result
