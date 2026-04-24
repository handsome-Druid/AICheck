from __future__ import annotations

import asyncio
import sys
import unittest
from collections.abc import Callable
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication

from src.controllers import main_controller as controller_module
from src.views import main_view as main_view_module


class Signal0:
    def __init__(self) -> None:
        self.callbacks: list[Callable[[], None]] = []

    def connect(self, callback: Callable[[], None]) -> None:
        self.callbacks.append(callback)

    def emit(self) -> None:
        for callback in self.callbacks:
            callback()


class Signal1[TOne]:
    def __init__(self) -> None:
        self.callbacks: list[Callable[[TOne], None]] = []

    def connect(self, callback: Callable[[TOne], None]) -> None:
        self.callbacks.append(callback)

    def emit(self, arg1: TOne) -> None:
        for callback in self.callbacks:
            callback(arg1)


class Signal2[TOne, TTwo]:
    def __init__(self) -> None:
        self.callbacks: list[Callable[[TOne, TTwo], None]] = []

    def connect(self, callback: Callable[[TOne, TTwo], None]) -> None:
        self.callbacks.append(callback)

    def emit(self, arg1: TOne, arg2: TTwo) -> None:
        for callback in self.callbacks:
            callback(arg1, arg2)


class FakeLineEdit:
    def __init__(self, text: str = "", enabled: bool = True) -> None:
        self._text = text
        self._enabled = enabled
        self.text_changed = Signal1[str]()
        setattr(self, "textChanged", self.text_changed)
        setattr(self, "setText", self.set_text)
        setattr(self, "setEnabled", self.set_enabled)
        setattr(self, "isEnabled", self.is_enabled)

    def set_text(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def is_enabled(self) -> bool:
        return self._enabled


class FakePlainTextEdit:
    def __init__(self) -> None:
        self.lines: list[str] = []
        setattr(self, "appendPlainText", self.append_plain_text)

    def append_plain_text(self, text: str) -> None:
        self.lines.append(text)


class FakeButton:
    def __init__(self) -> None:
        self.clicked = Signal0()


class FakeUiMainWindow:
    def __init__(self) -> None:
        setattr(self, "setupUi", self.setup_ui)

    def setup_ui(self, main_window: object) -> None:
        setattr(self, "lineEditDataSourcePath", FakeLineEdit())
        setattr(self, "lineEditSheetName", FakeLineEdit())
        setattr(self, "lineEditOutputDirPath", FakeLineEdit())
        setattr(self, "plainTextEditStdInfo", FakePlainTextEdit())
        setattr(self, "pushButtonBrowseDataSource", FakeButton())
        setattr(self, "pushButtonBrowseOutputDir", FakeButton())
        setattr(self, "pushButtonStartTest", FakeButton())


class FakeWindow:
    def __init__(self, sheet_enabled: bool = True) -> None:
        self.data_source_changed = Signal2[str, str]()
        self.sheet_name_changed = Signal1[str]()
        self.output_dir_changed = Signal1[str]()
        self.start_test_requested = Signal2[str, str]()
        setattr(self, "dataSourceChanged", self.data_source_changed)
        setattr(self, "sheetNameChanged", self.sheet_name_changed)
        setattr(self, "outputDirChanged", self.output_dir_changed)
        setattr(self, "startTestRequested", self.start_test_requested)
        setattr(self, "setEnabled", self.set_enabled)
        self.ui = SimpleNamespace(lineEditSheetName=FakeLineEdit(enabled=sheet_enabled))
        self.messages: list[str] = []
        self.enabled_states: list[bool] = []

    def append_std_info(self, text: str) -> None:
        self.messages.append(text)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled_states.append(enabled)


class FakeThread:
    def __init__(self, parent: object | None = None) -> None:
        self.parent = parent
        self.message_signal = Signal1[str]()
        self.finished_with_status = Signal2[bool, str]()
        self.is_running = self._is_running
        setattr(self, "message", self.message_signal)
        setattr(self, "finishedWithStatus", self.finished_with_status)
        setattr(self, "isRunning", self.is_running)
        self.started = False

    def _is_running(self) -> bool:
        return False

    def start(self) -> None:
        self.started = True


class RunningFakeThread(FakeThread):
    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        self.is_running = self._is_running_running
        setattr(self, "isRunning", self.is_running)

    def _is_running_running(self) -> bool:
        return True


class TestMainWindow(unittest.TestCase):
    _app: QApplication | None

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = cast(QApplication, QApplication.instance() or QApplication([]))

    def _make_config(self, source_last_type: str = "xlsx") -> SimpleNamespace:
        return SimpleNamespace(
            xlsx_input_path="input.xlsx",
            xlsx_input_sheet_name="Sheet1",
            csv_input_path="input.csv",
            csv_output_path="output/",
            source_last_type=source_last_type,
        )

    def test_main_window_loads_settings_and_connects_buttons(self) -> None:
        fake_module = SimpleNamespace(Ui_MainWindow=FakeUiMainWindow)

        with patch.object(main_view_module, "import_module", return_value=fake_module), patch.object(
            main_view_module, "get_config", return_value=self._make_config("csv")
        ):
            window = main_view_module.MainWindow()

        self.assertEqual(window.ui.lineEditDataSourcePath.text(), "input.csv")
        self.assertEqual(window.ui.lineEditOutputDirPath.text(), "output/")
        self.assertEqual(window.ui.lineEditSheetName.text(), "Sheet1")
        self.assertFalse(window.ui.lineEditSheetName.isEnabled())
        plain_text = cast(FakePlainTextEdit, window.ui.plainTextEditStdInfo)
        self.assertIn("已读取当前设置。", plain_text.lines)

    def test_main_window_csv_and_xlsx_selection_and_start_validation(self) -> None:
        fake_module = SimpleNamespace(Ui_MainWindow=FakeUiMainWindow)

        with patch.object(main_view_module, "import_module", return_value=fake_module), patch.object(
            main_view_module, "get_config", return_value=self._make_config("xlsx")
        ):
            window = main_view_module.MainWindow()

        data_sources: list[tuple[str, str]] = []
        sheets: list[str] = []
        outputs: list[str] = []
        starts: list[tuple[str, str]] = []

        def on_data_source(path: str, source_type: str) -> None:
            data_sources.append((path, source_type))

        def on_sheet_name(sheet_name: str) -> None:
            sheets.append(sheet_name)

        def on_output_dir(output_dir: str) -> None:
            outputs.append(output_dir)

        def on_start(path: str, output: str) -> None:
            starts.append((path, output))

        window.dataSourceChanged.connect(on_data_source)
        window.sheetNameChanged.connect(on_sheet_name)
        window.outputDirChanged.connect(on_output_dir)
        window.startTestRequested.connect(on_start)
        plain_text = cast(FakePlainTextEdit, window.ui.plainTextEditStdInfo)
        browse_data_button = cast(FakeButton, window.ui.pushButtonBrowseDataSource)
        browse_output_button = cast(FakeButton, window.ui.pushButtonBrowseOutputDir)
        start_button = cast(FakeButton, window.ui.pushButtonStartTest)
        line_edit = cast(FakeLineEdit, window.ui.lineEditSheetName)

        with patch.object(main_view_module.QFileDialog, "getOpenFileName", return_value=("C:/tmp/data.csv", "CSV Files (*.csv)")):
            browse_data_button.clicked.emit()

        self.assertEqual(data_sources[-1], ("C:/tmp/data.csv", "csv"))
        self.assertFalse(window.ui.lineEditSheetName.isEnabled())

        line_edit.text_changed.emit("ignored")
        self.assertEqual(sheets, [])

        with patch.object(main_view_module.QFileDialog, "getOpenFileName", return_value=("C:/tmp/data.xlsx", "Excel Files (*.xlsx)")):
            browse_data_button.clicked.emit()

        self.assertEqual(data_sources[-1], ("C:/tmp/data.xlsx", "xlsx"))
        self.assertTrue(window.ui.lineEditSheetName.isEnabled())

        with patch.object(main_view_module.QFileDialog, "getExistingDirectory", return_value="C:/out"):
            browse_output_button.clicked.emit()

        self.assertEqual(outputs[-1], "C:/out")

        window.ui.lineEditDataSourcePath.setText("")
        window.ui.lineEditOutputDirPath.setText("C:/out")
        line_edit.set_text("Sheet1")
        start_button.clicked.emit()
        self.assertIn("请先选择模型 API 数据源。", plain_text.lines)

        window.ui.lineEditDataSourcePath.setText("C:/tmp/data.xlsx")
        window.ui.lineEditOutputDirPath.setText("")
        start_button.clicked.emit()
        self.assertIn("请先选择输出目录。", plain_text.lines)

        window.ui.lineEditOutputDirPath.setText("C:/out")
        line_edit.set_text("")
        start_button.clicked.emit()
        self.assertIn("请先填写 Sheet 名称。", plain_text.lines)

        line_edit.set_text("Sheet1")
        start_button.clicked.emit()
        self.assertEqual(starts[-1], ("C:/tmp/data.xlsx", "C:/out"))
        self.assertIn("开始测试。", plain_text.lines)

    def test_main_window_cancelled_dialogs_do_not_change_state(self) -> None:
        fake_module = SimpleNamespace(Ui_MainWindow=FakeUiMainWindow)

        with patch.object(main_view_module, "import_module", return_value=fake_module), patch.object(
            main_view_module, "get_config", return_value=self._make_config("xlsx")
        ):
            window = main_view_module.MainWindow()

        plain_text = cast(FakePlainTextEdit, window.ui.plainTextEditStdInfo)
        line_edit = cast(FakeLineEdit, window.ui.lineEditSheetName)
        browse_data_button = cast(FakeButton, window.ui.pushButtonBrowseDataSource)
        browse_output_button = cast(FakeButton, window.ui.pushButtonBrowseOutputDir)

        line_edit.text_changed.emit("SheetX")
        self.assertEqual(plain_text.lines.count("已读取当前设置。"), 1)

        with patch.object(main_view_module.QFileDialog, "getOpenFileName", return_value=("", "")):
            browse_data_button.clicked.emit()

        with patch.object(main_view_module.QFileDialog, "getExistingDirectory", return_value=""):
            browse_output_button.clicked.emit()

        self.assertEqual(window.ui.lineEditDataSourcePath.text(), "input.xlsx")
        self.assertEqual(window.ui.lineEditOutputDirPath.text(), "output/")

    def test_main_window_covers_remaining_branches(self) -> None:
        fake_module = SimpleNamespace(Ui_MainWindow=FakeUiMainWindow)

        with patch.object(main_view_module, "import_module", return_value=fake_module), patch.object(
            main_view_module, "get_config", return_value=self._make_config("invalid")
        ):
            window = main_view_module.MainWindow()

        data_sources: list[tuple[str, str]] = []
        outputs: list[str] = []
        sheets: list[str] = []
        starts: list[tuple[str, str]] = []

        def on_data_source(path: str, source_type: str) -> None:
            data_sources.append((path, source_type))

        def on_output_dir(output_dir: str) -> None:
            outputs.append(output_dir)

        def on_sheet_name(sheet_name: str) -> None:
            sheets.append(sheet_name)

        def on_start(path: str, output: str) -> None:
            starts.append((path, output))

        window.dataSourceChanged.connect(on_data_source)
        window.outputDirChanged.connect(on_output_dir)
        window.sheetNameChanged.connect(on_sheet_name)
        window.startTestRequested.connect(on_start)

        plain_text = cast(FakePlainTextEdit, window.ui.plainTextEditStdInfo)
        browse_data_button = cast(FakeButton, window.ui.pushButtonBrowseDataSource)
        browse_output_button = cast(FakeButton, window.ui.pushButtonBrowseOutputDir)
        start_button = cast(FakeButton, window.ui.pushButtonStartTest)
        line_edit = cast(FakeLineEdit, window.ui.lineEditSheetName)

        self.assertTrue(window.ui.lineEditSheetName.isEnabled())

        with patch.object(main_view_module.QFileDialog, "getOpenFileName", return_value=("C:/tmp/data.csv", "CSV Files (*.csv)")):
            browse_data_button.clicked.emit()

        self.assertFalse(window.ui.lineEditSheetName.isEnabled())

        line_edit.text_changed.emit("Ignored")
        self.assertEqual(sheets, [])

        with patch.object(main_view_module.QFileDialog, "getOpenFileName", return_value=("C:/tmp/data.xlsx", "Excel Files (*.xlsx)")):
            browse_data_button.clicked.emit()

        self.assertTrue(window.ui.lineEditSheetName.isEnabled())

        with patch.object(main_view_module.QFileDialog, "getExistingDirectory", return_value="C:/out"):
            browse_output_button.clicked.emit()

        self.assertEqual(outputs[-1], "C:/out")

        line_edit.text_changed.emit("SheetA")
        self.assertEqual(sheets, ["SheetA"])

        with patch.object(main_view_module.QFileDialog, "getOpenFileName", return_value=("", "")):
            browse_data_button.clicked.emit()

        line_edit.set_text("Sheet1")
        window.ui.lineEditDataSourcePath.setText("")
        window.ui.lineEditOutputDirPath.setText("C:/out")
        start_button.clicked.emit()
        self.assertIn("请先选择模型 API 数据源。", plain_text.lines)

        window.ui.lineEditDataSourcePath.setText("C:/tmp/data.xlsx")
        window.ui.lineEditOutputDirPath.setText("")
        start_button.clicked.emit()
        self.assertIn("请先选择输出目录。", plain_text.lines)

        window.ui.lineEditOutputDirPath.setText("C:/out")
        line_edit.set_text("")
        start_button.clicked.emit()
        self.assertIn("请先填写 Sheet 名称。", plain_text.lines)

        line_edit.set_text("Sheet1")
        start_button.clicked.emit()
        self.assertEqual(starts[-1], ("C:/tmp/data.xlsx", "C:/out"))
        self.assertEqual(data_sources[0], ("C:/tmp/data.csv", "csv"))
        self.assertEqual(data_sources[1], ("C:/tmp/data.xlsx", "xlsx"))
        self.assertIn("开始测试。", plain_text.lines)


class TestMainController(unittest.TestCase):
    def _make_window_with_sheet(self, sheet_enabled: bool, sheet_text: str) -> tuple[FakeWindow, FakeLineEdit]:
        window = FakeWindow(sheet_enabled=sheet_enabled)
        line_edit = cast(FakeLineEdit, window.ui.lineEditSheetName)
        line_edit.set_text(sheet_text)
        return window, line_edit

    def test_controller_routes_signals_and_worker_flow(self) -> None:
        window = FakeWindow(sheet_enabled=False)

        with patch.object(controller_module, "update_config") as update_mock, patch.object(
            controller_module, "TestRunThread", FakeThread
        ):
            controller = controller_module.MainController(window)

            window.data_source_changed.emit("C:/tmp/data.csv", "csv")
            window.sheet_name_changed.emit("Sheet2")
            window.output_dir_changed.emit("C:/out")
            window.start_test_requested.emit("C:/tmp/data.csv", "C:/out")

            self.assertEqual(update_mock.call_args_list[0].kwargs, {"csv_input_path": "C:/tmp/data.csv", "source_last_type": "csv"})
            self.assertEqual(update_mock.call_args_list[1].kwargs, {"xlsx_input_sheet_name": "Sheet2"})
            self.assertEqual(update_mock.call_args_list[2].kwargs, {"csv_output_path": "C:/out"})
            self.assertEqual(update_mock.call_args_list[3].kwargs, {"csv_input_path": "C:/tmp/data.csv", "csv_output_path": "C:/out", "source_last_type": "csv"})
            self.assertTrue(cast(FakeThread, controller.worker).started)

            controller.worker = cast(controller_module.WorkerLike, RunningFakeThread())
            window.start_test_requested.emit("C:/tmp/data.csv", "C:/out")
            self.assertIn("测试正在运行中，请稍后。", window.messages)

    def test_controller_handles_xlsx_branch_and_thread_run(self) -> None:
        window, _ = self._make_window_with_sheet(True, "Sheet9")

        with patch.object(controller_module, "update_config") as update_mock, patch.object(
            controller_module, "TestRunThread", FakeThread
        ):
            controller_module.MainController(window)
            window.data_source_changed.emit("C:/tmp/data.xlsx", "xlsx")
            window.start_test_requested.emit("C:/tmp/data.xlsx", "C:/out")

        self.assertEqual(update_mock.call_args_list[0].kwargs, {"xlsx_input_path": "C:/tmp/data.xlsx", "source_last_type": "xlsx"})
        self.assertEqual(update_mock.call_args_list[1].kwargs, {
            "xlsx_input_path": "C:/tmp/data.xlsx",
            "xlsx_input_sheet_name": "Sheet9",
            "csv_output_path": "C:/out",
            "source_last_type": "xlsx",
        })

    def test_controller_reports_worker_failure(self) -> None:
        window, _line_edit = self._make_window_with_sheet(True, "Sheet1")

        controller = controller_module.MainController(window)
        controller.window.setEnabled(False)
        controller.on_worker_finished(True, "")
        controller.on_worker_finished(False, "boom")

        self.assertIn(True, window.enabled_states)
        self.assertIn("测试结束: boom", window.messages)

    def test_signal_stream_and_test_run_thread(self) -> None:
        captured: list[str] = []
        stream = controller_module.SignalStream(captured.append)
        self.assertEqual(stream.write("hello"), 5)
        self.assertEqual(captured, ["hello"])

        thread = controller_module.TestRunThread()
        messages: list[str] = []
        finished: list[tuple[bool, str]] = []
        thread.message.connect(messages.append)

        def on_finished(success: bool, message: str) -> None:
            finished.append((success, message))

        thread.finishedWithStatus.connect(on_finished)

        async def fake_run() -> None:
            print("from-run")
            await asyncio.sleep(0)

        with patch.object(controller_module, "run", fake_run):
            thread.run()

        self.assertIn("from-run", messages)
        self.assertEqual(finished[-1], (True, ""))

        failed_thread = controller_module.TestRunThread()
        failed_messages: list[str] = []
        failed_finished: list[tuple[bool, str]] = []
        failed_thread.message.connect(failed_messages.append)

        def on_failed_finished(success: bool, message: str) -> None:
            failed_finished.append((success, message))

        failed_thread.finishedWithStatus.connect(on_failed_finished)

        with patch.object(controller_module, "run", Mock(return_value="not-a-coroutine")), patch.object(
            controller_module.asyncio, "run", side_effect=RuntimeError("boom")
        ):
            failed_thread.run()

        self.assertIn("运行失败: boom", failed_messages)
        self.assertEqual(failed_finished[-1], (False, "boom"))


class TestMainModule(unittest.TestCase):
    @staticmethod
    def _run_and_close(coro: object) -> None:
        close = getattr(coro, "close", None)
        if callable(close):
            close()

    def test_main_nogui_branch_runs_and_pauses(self) -> None:
        import src.main as main_module

        with patch.object(sys, "argv", ["main.py", "--nogui"]), patch.object(main_module, "run", new=Mock(return_value=None)), patch.object(
            main_module.asyncio, "run", side_effect=self._run_and_close
        ) as run_mock, patch.object(
            main_module.subprocess, "run", return_value=None
        ) as pause_mock:
            main_module.main()

        run_mock.assert_called_once()
        pause_mock.assert_called_once_with("pause", shell=True)

    def test_main_gui_branch_creates_window(self) -> None:
        import src.main as main_module

        fake_app = Mock()
        fake_app.exec.return_value = 0
        fake_window = Mock()

        with patch.object(sys, "argv", ["main.py"]), patch.object(main_module, "QApplication", return_value=fake_app) as app_mock, patch.object(
            main_module, "MainWindow", return_value=fake_window
        ) as window_mock, patch.object(main_module, "MainController", return_value=Mock()) as controller_mock:
            main_module.main()

        app_mock.assert_called_once()
        window_mock.assert_called_once()
        controller_mock.assert_called_once_with(fake_window)
        fake_window.show.assert_called_once()
        fake_app.exec.assert_called_once()
