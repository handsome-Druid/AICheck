from dataclasses import dataclass, field
from typing import Iterator
from pathlib import Path
try:
    from src.adapters.read_csv import read_csv
    from src.adapters.read_xlsx import read_xlsx
    from .base import BaseReaderModel
    from src.config import get_config
    from src.utils.test_print import test_print_from_dataclass
    from src.utils.write_csv import write_csv_from_dataclass
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
    from src.adapters.read_csv import read_csv
    from src.adapters.read_xlsx import read_xlsx
    from src.models.base import BaseReaderModel
    from src.config import get_config
    from src.utils.test_print import test_print_from_dataclass
    from src.utils.write_csv import write_csv_from_dataclass


@dataclass(slots = True, frozen = True)
class Sheet(BaseReaderModel):

    port: int = field(metadata = {"tag": "port", "type": int})
    model_id: str = field(metadata = {"tag": "modelID", "type": str})
    model_name: str = field(metadata = {"tag": "模型名", "type": str})
    monitor_id: str = field(metadata = {"tag": "监控id", "type": str})
    gpu_model: str = field(metadata = {"tag": "GPU型号", "type": str})
    gpu_count: int = field(metadata = {"tag": "GPU数量", "type": int})
    context_length: int = field(metadata = {"tag": "上下文长度（K）", "type": int})
    container_name: str = field(metadata = {"tag": "容器名", "type": str})
    call_method: str = field(metadata = {"tag": "调用方法", "type": str})

_sheet_cache: dict[tuple[str, str], Iterator[Sheet]] = {}
def get_sheet_iterator(path: str | Path | None = None, refresh: bool = True) -> Iterator[Sheet]:
    match path:
        case str() | Path() as selected_path:
            source_path = Path(selected_path)
            match source_path.suffix.lower():
                case ".csv":
                    source_type = "csv"
                case _:
                    source_type = "xlsx"
        case None:
            match getattr(config := get_config(refresh=True), "source_last_type", "xlsx"):
                case "csv":
                    source_path = Path(config.csv_input_path)
                    source_type = "csv"
                case "xlsx":
                    source_path = Path(config.xlsx_input_path)
                    source_type = "xlsx"
                case _:
                    source_path = Path(config.xlsx_input_path)
                    source_type = "xlsx"

    cache_key = (source_type, str(source_path))

    if refresh or cache_key not in _sheet_cache:
        reader = read_csv(source_path) if source_type == "csv" else read_xlsx(source_path)
        _sheet_cache[cache_key] = Sheet.from_reader(reader)
    return _sheet_cache[cache_key]

def main() -> None:
    test_print_from_dataclass(get_sheet_iterator())
    write_csv_from_dataclass(
        get_sheet_iterator(),
        Path(get_config().csv_output_path) / "test_sheet.csv"
    )


if __name__ == "__main__":
    main()