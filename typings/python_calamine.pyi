from os import PathLike
from src.models.type import CellGetValue
class CalamineSheet:
    def to_python(self, skip_empty_area: bool = False) -> list[CellGetValue]: ...

class CalamineWorkbook:
    @classmethod
    def from_path(
        cls,
        path: str | PathLike[str],
        load_tables: bool = False,
    ) -> CalamineWorkbook: ...

    def get_sheet_by_name(self, sheet_name: str) -> CalamineSheet | None: ...
