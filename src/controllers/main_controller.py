from __future__ import annotations

import asyncio
from contextlib import redirect_stderr, redirect_stdout
import io
from collections.abc import Callable
from typing import TextIO, cast

from PySide6.QtCore import QObject, QThread, Signal

from src.config.settings import update_config
from src.controllers.vllm_test_controller import run
from src.models.type import MainWindowLike, WorkerLike
from src.services.check_history_results import analyze_results



class SignalStream(io.TextIOBase):
	def __init__(self, emit: Callable[[str], None]) -> None:
		self._emit = emit

	def write(self, text: str) -> int:
		if text:
			self._emit(text)
		return len(text)


class TestRunThread(QThread):
	message = Signal(str)
	finishedWithStatus = Signal(bool, str)

	def __init__(self, parent: QObject | None = None) -> None:
		super().__init__(parent)

	def run(self) -> None:
		try:
			stream = cast(TextIO, SignalStream(self.message.emit))
			with redirect_stdout(stream), redirect_stderr(stream):
				asyncio.run(run())
		except Exception as exc:
			self.message.emit(f"运行失败: {exc}")
			self.finishedWithStatus.emit(False, str(exc))
		else:
			self.finishedWithStatus.emit(True, "")


class MainController(QObject):
	def __init__(self, window: object) -> None:
		super().__init__()
		self.window = cast(MainWindowLike, window)
		self.worker: WorkerLike | None = None
		self.connect_signals()

	def connect_signals(self) -> None:
		self.window.dataSourceChanged.connect(self.on_data_source_changed)
		self.window.sheetNameChanged.connect(self.on_sheet_name_changed)
		self.window.outputDirChanged.connect(self.on_output_dir_changed)
		self.window.startTestRequested.connect(self.on_start_test_requested)
		self.window.showHistoryRequested.connect(self.on_show_history_requested)

	def on_data_source_changed(self, data_source_path: str, source_type: str) -> None:
		if source_type == "csv":
			update_config(csv_input_path=data_source_path, source_last_type=source_type)
		else:
			update_config(xlsx_input_path=data_source_path, source_last_type=source_type)
		self.window.append_std_info(f"数据源已选择: {data_source_path}")

	def on_sheet_name_changed(self, sheet_name: str) -> None:
		update_config(xlsx_input_sheet_name=sheet_name)

	def on_output_dir_changed(self, output_dir_path: str) -> None:
		update_config(csv_output_path=output_dir_path)
		self.window.append_std_info(f"输出目录已选择: {output_dir_path}")

	def on_start_test_requested(self, data_source_path: str, output_dir_path: str) -> None:
		if self.worker is not None and self.worker.isRunning():
			self.window.append_std_info("测试正在运行中，请稍后。")
			return

		source_type = "xlsx" if self.window.ui.lineEditSheetName.isEnabled() else "csv"
		sheet_name = self.window.ui.lineEditSheetName.text().strip()
		if source_type == "csv":
			update_config(csv_input_path=data_source_path, csv_output_path=output_dir_path, source_last_type=source_type)
		else:
			update_config(
				xlsx_input_path=data_source_path,
				xlsx_input_sheet_name=sheet_name,
				csv_output_path=output_dir_path,
				source_last_type=source_type,
			)

		self.window.append_std_info("准备启动测试。")
		self.window.setEnabled(False)
		self.worker = TestRunThread(self)
		self.worker.message.connect(self.window.append_std_info)
		self.worker.finishedWithStatus.connect(self.on_worker_finished)
		self.worker.start()

	def on_show_history_requested(self) -> None:
		try:
			results = analyze_results()
		except Exception as exc:
			self.window.append_std_info(f"加载历史结果失败: {exc}")
			return

		# analyze_results() yields Iterator[tuple[str, int, str, str]]
		# 返回顺序是: (period, port, message, model_id)
		# 表格列顺序需要是: (period, port, model_id, message)
		rows: list[tuple[str, int, str, str]] = []
		rows.extend((period, port, model_id, message) for period, port, message, model_id in results)
		self.window.show_history_results(rows)
		self.window.append_std_info(f"已加载历史测试结果，共 {len(rows)} 条。")

	def on_worker_finished(self, success: bool, message: str) -> None:
		self.window.setEnabled(True)
		if success:
			self.window.append_std_info("测试完成。")
		elif message:
			self.window.append_std_info(f"测试结束: {message}")
