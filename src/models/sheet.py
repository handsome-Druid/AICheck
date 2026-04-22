from dataclasses import dataclass, fields, field
from typing import ClassVar, Callable, Iterator, Self, cast
from pathlib import Path
try:
    from src.adapters.read_xlsx import read_xlsx
    from src.models.type import CellGetValue
    from src.config import get_config
    from src.utils.test_print import test_print_from_dataclass
    from src.utils.write_csv import write_csv_from_dataclass
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
    from src.adapters.read_xlsx import read_xlsx
    from src.models.type import CellGetValue
    from src.config import get_config
    from src.utils.test_print import test_print_from_dataclass
    from src.utils.write_csv import write_csv_from_dataclass

@dataclass(slots = True,frozen = True)
class Sheet:

    port: int = field(metadata = {"tag": "port", "type": int})
    model_id: str = field(metadata = {"tag": "modelID", "type": str})
    model_name: str = field(metadata = {"tag": "模型名", "type": str})
    monitor_id: str = field(metadata = {"tag": "监控id", "type": str})
    gpu_model: str = field(metadata = {"tag": "GPU型号", "type": str})
    gpu_count: int = field(metadata = {"tag": "GPU数量", "type": int})
    context_length: int = field(metadata = {"tag": "上下文长度（K）", "type": int})
    container_name: str = field(metadata = {"tag": "容器名", "type": str})
    call_method: str = field(metadata = {"tag": "调用方法", "type": str})

    _cache: ClassVar[dict[tuple[type, tuple[int, ...]], Callable[[CellGetValue], Self]]] = {}
    _tags: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def from_reader(cls, reader: Iterator[CellGetValue] | None = None) -> Iterator[Self]:
        if reader is None:
            reader = read_xlsx()

        header_map = {name: i for i, name in enumerate(next(reader))}

        if not cls._tags:
            cls._tags = tuple(
                f.metadata["tag"]
                for f in fields(cls)
                if "tag" in f.metadata
            )

        sig_indices = tuple(header_map[tag] for tag in cls._tags)
        cache_key = (cls, sig_indices)

        loader = cls._cache.get(cache_key)

        if loader is None:
            lines = [
                "def loader(row, cls=cls, _int=int, _float=float, _str=str, _bool=bool):",
            ]

            kwargs: list[str] = []

            for f in fields(cls):
                if "tag" not in f.metadata:
                    continue

                index = header_map[f.metadata["tag"]]
                value_type = f.metadata["type"]

                match value_type.__name__:
                    case "int":
                        lines.extend(
                            [
                                "    try:",
                                f"        {f.name} = _int(row[{index}])",
                                "    except (TypeError, ValueError):",
                                f"        {f.name} = 0",
                            ]
                        )
                    case "float":
                        lines.extend(
                            [
                                "    try:",
                                f"        {f.name} = _float(row[{index}])",
                                "    except (TypeError, ValueError):",
                                f"        {f.name} = 0.0",
                            ]
                        )
                    case "str":
                        lines.append(
                            f"    {f.name} = '' if row[{index}] is None else _str(row[{index}])"
                        )
                    case "bool":
                        lines.append(f"    {f.name} = _bool(row[{index}])")
                    case _:
                        lines.append(f"    {f.name} = row[{index}]")

                kwargs.append(f"{f.name}={f.name}")

            lines.append(f"    return cls({', '.join(kwargs)})")

            ns: dict[str, object] = {"cls": cls}
            exec("\n".join(lines), ns)
            loader = cast(Callable[[CellGetValue], Self], ns["loader"])
            cls._cache[cache_key] = loader
        for row in reader:
            yield loader(row)

_sheet_cache: dict[str, Iterator[Sheet]] = {}
def get_sheet_iterator(path: str | Path = get_config().xlsx_input_path, refresh: bool = True) -> Iterator[Sheet]:
    if refresh or str(path) not in _sheet_cache:
        _sheet_cache[str(path)] = Sheet.from_reader(read_xlsx(path))
    return _sheet_cache[str(path)]

def main() -> None:
    test_print_from_dataclass(get_sheet_iterator())
    write_csv_from_dataclass(
        get_sheet_iterator(),
        Path(get_config().csv_output_path) / "test_sheet.csv"
    )


if __name__ == "__main__":
    main()