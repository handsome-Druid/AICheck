from os import PathLike
from typing import Iterator
from python_calamine import CalamineWorkbook
try:
	from src.config import get_config
	from src.models.type import CellGetValue
except ImportError:
	import os
	import sys

	sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
	from src.config import get_config
	from src.models.type import CellGetValue


def read_xlsx(path: str | PathLike[str] = get_config().xlsx_input_path) -> Iterator[CellGetValue]:
	sheet_name = get_config().xlsx_input_sheet_name
	try:
		sheet = CalamineWorkbook.from_path(str(path)).get_sheet_by_name(sheet_name)
	except FileNotFoundError as e:
		raise FileNotFoundError(f"Excel file '{path}' not found.") from e
	
	if sheet is None:
		raise ValueError(
			f"Sheet '{sheet_name}' not found in workbook '{path}'"
		)
	
	yield from sheet.to_python()