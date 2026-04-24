from csv import reader as csv_reader
from typing import cast
from os import PathLike
from typing import Iterator

try:
	from src.models.type import CellGetValue
except ImportError:
	import os
	import sys

	sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
	from src.models.type import CellGetValue


def read_csv(path: str | PathLike[str]) -> Iterator[CellGetValue]:
	try:
		with open(path, mode="r", encoding="utf-8-sig", newline="") as csv_file:
			yield from cast(Iterator[CellGetValue], csv_reader(csv_file))
	except FileNotFoundError as e:
		raise FileNotFoundError(f"CSV file '{path}' not found.") from e
