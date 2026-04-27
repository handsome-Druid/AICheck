from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Protocol, cast

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHeaderView, QLineEdit, QMainWindow, QPlainTextEdit, QPushButton, QTableWidget, QTableWidgetItem

from src.config import get_config


class MainWindowUiProtocol(Protocol):
	lineEditDataSourcePath: QLineEdit
	lineEditSheetName: QLineEdit
	lineEditOutputDirPath: QLineEdit
	plainTextEditStdInfo: QPlainTextEdit
	tableWidgetHistoryResults: QTableWidget
	pushButtonBrowseDataSource: QPushButton
	pushButtonBrowseOutputDir: QPushButton
	pushButtonStartTest: QPushButton
	pushButtonShowHistoryResults: QPushButton

	def setupUi(self, main_window: QMainWindow) -> None: ...


class MainWindowUiModule(Protocol):
	Ui_MainWindow: type[MainWindowUiProtocol]


class MainWindow(QMainWindow):
	dataSourceChanged = Signal(str, str)
	sheetNameChanged = Signal(str)
	outputDirChanged = Signal(str)
	startTestRequested = Signal(str, str)
	showHistoryRequested = Signal()
	controller: object | None = None

	def __init__(self, parent: QMainWindow | None = None) -> None:
		super().__init__(parent)
		ui_module = cast(MainWindowUiModule, import_module("src.views.ui.main_window_ui"))
		self.ui: MainWindowUiProtocol = ui_module.Ui_MainWindow()
		self.ui.setupUi(self)
		self._configure_history_table()

		font = self.font()
		font.setPointSize(13)
		self.setFont(font)

		self._source_type = "xlsx"
		self._load_settings()
		self._connect_signals()

	def _configure_history_table(self) -> None:
		table = self.ui.tableWidgetHistoryResults
		header = table.horizontalHeader()

		header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
		header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
		header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
		header.setMinimumSectionSize(110)

		vertical_header = table.verticalHeader()
		vertical_header.setVisible(False)

	def _load_settings(self) -> None:
		config = get_config()
		self.ui.lineEditSheetName.setText(config.xlsx_input_sheet_name)
		self.ui.lineEditSheetName.setCursorPosition(0)
		self.ui.lineEditOutputDirPath.setText(config.csv_output_path)
		self.ui.lineEditOutputDirPath.setCursorPosition(0)
		self._apply_source_type(config.source_last_type)
		if self._source_type == "csv":
			self.ui.lineEditDataSourcePath.setText(config.csv_input_path)
		else:
			self.ui.lineEditDataSourcePath.setText(config.xlsx_input_path)
		self.ui.lineEditDataSourcePath.setCursorPosition(0)
		self.append_std_info("已读取当前设置。")

	def _apply_source_type(self, source_type: str) -> None:
		self._source_type = source_type if source_type in {"csv", "xlsx"} else "xlsx"
		self.ui.lineEditSheetName.setEnabled(self._source_type == "xlsx")

	def _connect_signals(self) -> None:
		self.ui.pushButtonBrowseDataSource.clicked.connect(self._choose_data_source)
		self.ui.pushButtonBrowseOutputDir.clicked.connect(self._choose_output_dir)
		self.ui.pushButtonStartTest.clicked.connect(self._start_test)
		self.ui.pushButtonShowHistoryResults.clicked.connect(self._show_history_results)
		self.ui.lineEditSheetName.textChanged.connect(self._on_sheet_name_changed)

	def _choose_data_source(self) -> None:
		file_path, _ = QFileDialog.getOpenFileName(
			self,
			"选择模型 API 数据源",
			"",
			"Data Files (*.csv *.xlsx);;CSV Files (*.csv);;Excel Files (*.xlsx)",
		)
		if not file_path:
			return

		source_type = "csv" if Path(file_path).suffix.lower() == ".csv" else "xlsx"
		self._apply_source_type(source_type)
		self.ui.lineEditDataSourcePath.setText(file_path)
		self.ui.lineEditDataSourcePath.setCursorPosition(0)
		self.dataSourceChanged.emit(file_path, source_type)
		self.append_std_info(f"已选择数据源: {file_path}")

	def _choose_output_dir(self) -> None:
		directory = QFileDialog.getExistingDirectory(
			self,
			"选择输出目录",
		)
		if not directory:
			return

		self.ui.lineEditOutputDirPath.setText(directory)
		self.ui.lineEditOutputDirPath.setCursorPosition(0)
		self.outputDirChanged.emit(directory)
		self.append_std_info(f"已选择输出目录: {directory}")

	def _on_sheet_name_changed(self, sheet_name: str) -> None:
		if self.ui.lineEditSheetName.isEnabled():
			self.sheetNameChanged.emit(sheet_name)

	def _start_test(self) -> None:
		data_source_path = self.ui.lineEditDataSourcePath.text().strip()
		output_dir_path = self.ui.lineEditOutputDirPath.text().strip()
		sheet_name = self.ui.lineEditSheetName.text().strip()

		if not data_source_path:
			self.append_std_info("请先选择模型 API 数据源。")
			return

		if self.ui.lineEditSheetName.isEnabled() and not sheet_name:
			self.append_std_info("请先填写 Sheet 名称。")
			return

		if not output_dir_path:
			self.append_std_info("请先选择输出目录。")
			return

		self.append_std_info("开始测试。")
		self.startTestRequested.emit(data_source_path, output_dir_path)

	def _show_history_results(self) -> None:
		self.showHistoryRequested.emit()

	def show_history_results(self, rows: list[tuple[str, int, str]]) -> None:
		table = self.ui.tableWidgetHistoryResults
		table.clearContents()
		table.setRowCount(len(rows))
		for row_index, row_data in enumerate(rows):
			for column_index, column_value in enumerate(row_data):
				table.setItem(row_index, column_index, QTableWidgetItem(str(column_value)))

	def append_std_info(self, text: str) -> None:
		self.ui.plainTextEditStdInfo.appendPlainText(text)

