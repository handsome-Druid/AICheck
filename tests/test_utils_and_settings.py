from __future__ import annotations

import csv
import io
import json
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence
from unittest.mock import patch

from src.config import settings as settings_module
from src.models import TYPE_CACHE
from src.utils import get_path as get_path_module
from src.utils import test_print as test_print_module
from src.utils import write_csv as write_csv_module


@dataclass
class SingleValueRow:
    value: str


@dataclass(slots=True)
class SlotRow:
    name: str
    count: int


@dataclass
class PrintRow:
    name: str
    score: float
    tags: list[str]


class TestGetPath(unittest.TestCase):
    def test_get_path_repo_branch(self) -> None:
        expected = Path(__file__).resolve().parents[1] / "folder" / "file.txt"
        self.assertEqual(get_path_module.get_path(Path("folder/file.txt")), expected)

    def test_get_path_compiled_branch_uses_sys_argv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_exe = Path(temp_dir) / "app.exe"
            with patch.dict(get_path_module.__dict__, {"__compiled__": True}, clear=False), patch.object(sys, "argv", [str(fake_exe)]):
                self.assertEqual(get_path_module.get_path("data.txt"), fake_exe.resolve().parent / "data.txt")


class TestSettings(unittest.TestCase):
    def setUp(self) -> None:
        settings_module.json_config.clear()
        getattr(settings_module.JsonConfig, "_cache").clear()

    def _make_config_payload(
        self,
        xlsx_input_path: str,
        xlsx_input_sheet_name: str,
        csv_output_path: str,
        end_value: int,
    ) -> str:
        return json.dumps(
            {
                "xlsx": {"input_path": xlsx_input_path, "input_sheet_name": xlsx_input_sheet_name},
                "csv": {"output_path": csv_output_path},
                "end_flag": {"tag": "port", "value": end_value},
            }
        )

    def _write_config_file(self, config_path: Path, payload: str) -> None:
        config_path.write_text(payload, encoding="utf-8")

    def test_json_config_from_json(self) -> None:
        config = settings_module.JsonConfig.from_json(
            self._make_config_payload("input.xlsx", "Sheet1", "output/", 30420)
        )

        self.assertEqual(config.xlsx_input_path, "input.xlsx")
        self.assertEqual(config.xlsx_input_sheet_name, "Sheet1")
        self.assertEqual(config.csv_output_path, "output/")
        self.assertEqual(config.end_tag, "port")
        self.assertEqual(config.end_value, 30420)

    def test_get_config_caches_and_refreshes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "settings.json"
            self._write_config_file(
                config_path,
                self._make_config_payload("input-a.xlsx", "Sheet1", "output-a/", 30420),
            )

            with patch("src.config.settings.get_path", return_value=config_path):
                self._extracted_from_test_get_config_caches_and_refreshes_10(config_path)

    def _extracted_from_test_get_config_caches_and_refreshes_10(self, config_path: Path) -> None:
        first = settings_module.get_config("custom.json", refresh=True)
        self.assertEqual(first.xlsx_input_path, "input-a.xlsx")

        self._write_config_file(
            config_path,
            self._make_config_payload("input-b.xlsx", "Sheet2", "output-b/", 40000),
        )

        cached = settings_module.get_config("custom.json")
        self.assertIs(first, cached)
        self.assertEqual(cached.xlsx_input_path, "input-a.xlsx")

        refreshed = settings_module.get_config("custom.json", refresh=True)
        self.assertEqual(refreshed.xlsx_input_path, "input-b.xlsx")
        self.assertEqual(refreshed.end_value, 40000)


class TestWriteCsv(unittest.TestCase):
    def setUp(self) -> None:
        TYPE_CACHE.clear()

    def test_write_csv_writes_rows_and_logs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "nested" / "rows.csv"
            rows: Iterator[Sequence[str | float]] = iter([("alpha", 1.5), ("beta", 2.25)])
            stdout = io.StringIO()

            with patch("src.utils.write_csv.get_path", return_value=output_path), patch("sys.stdout", stdout):
                write_csv_module.write_csv(rows, "ignored.csv")

            with output_path.open("r", encoding="utf-8-sig", newline="") as handle:
                self.assertEqual(list(csv.reader(handle)), [["alpha", "1.5"], ["beta", "2.25"]])

            output = stdout.getvalue()
            self.assertIn("Wrote 2 rows", output)
            self.assertIn("Finished writing", output)

    def test_write_csv_from_dataclass_uses_slots_header(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "slots.csv"
            rows = iter([SlotRow(name="one", count=1), SlotRow(name="two", count=2)])
            stdout = io.StringIO()

            with patch("src.utils.write_csv.get_path", return_value=output_path), patch("sys.stdout", stdout):
                write_csv_module.write_csv_from_dataclass(rows, "ignored.csv")

            with output_path.open("r", encoding="utf-8-sig", newline="") as handle:
                self.assertEqual(list(csv.reader(handle)), [["name", "count"], ["one", "1"], ["two", "2"]])

            self.assertIn("Finished writing", stdout.getvalue())

    def test_write_csv_from_dataclass_falls_back_to_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "fields.csv"
            rows = iter([SingleValueRow(value="first"), SingleValueRow(value="second")])

            with patch("src.utils.write_csv.get_path", return_value=output_path):
                write_csv_module.write_csv_from_dataclass(rows, "ignored.csv")

            with output_path.open("r", encoding="utf-8-sig", newline="") as handle:
                self.assertEqual(list(csv.reader(handle)), [["value"], ["first"], ["second"]])


class TestPrintHelpers(unittest.TestCase):
    def test_test_print_from_list_formats_float_and_list(self) -> None:
        stdout = io.StringIO()
        rows_data: list[Sequence[str | float | list[str | float]]] = [
            ("score", "tags"),
            (1.23456, ["a", "b"]),
            (2.5, ["c"]),
        ]
        rows = iter(rows_data)

        with patch("sys.stdout", stdout):
            test_print_module.test_print_from_list(rows)

        output = stdout.getvalue()
        self.assertIn("1.2346", output)
        self.assertIn("['a', 'b']", output)
        self.assertIn("['c']", output)

    def test_test_print_from_dataclass_formats_rows(self) -> None:
        stdout = io.StringIO()

        @dataclass
        class Row:
            name: str
            score: float
            tags: list[str]

        rows = iter([Row(name="alpha", score=3.14159, tags=["x", "y"]), Row(name="beta", score=2.5, tags=["z"])])

        with patch("sys.stdout", stdout):
            test_print_module.test_print_from_dataclass(rows)

        output = stdout.getvalue()
        self.assertIn("name", output)
        self.assertIn("3.1416", output)
        self.assertIn("['x', 'y']", output)

    def test_test_print_from_dataclass_handles_single_field_dataclass(self) -> None:
        stdout = io.StringIO()

        @dataclass
        class SingleRow:
            value: str

        rows = iter([SingleRow(value="alpha"), SingleRow(value="beta")])

        with patch("sys.stdout", stdout):
            test_print_module.test_print_from_dataclass(rows)

        output = stdout.getvalue()
        self.assertIn("value", output)
        self.assertIn("alpha", output)
        self.assertIn("beta", output)