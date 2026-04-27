from dataclasses import Field, dataclass, fields
from typing import ClassVar, Callable, Iterator, Self, cast
try:
    from src.models.type import CellGetValue
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
    from src.models.type import CellGetValue


@dataclass(slots = True, frozen = True)
class BaseReaderModel:
    _cache: ClassVar[dict[tuple[type, tuple[int, ...]], Callable[[CellGetValue], Self]]] = {}
    _tags: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def get_field_lines_(cls, f: Field[int | float | str | bool | None], index: int | None, value_type: type) -> list[str]:
        lines: list[str] = []
        if index is None:
            default = cls.get_default_value_(value_type)
            lines.append(f"    {f.name} = {default}")
        else:
            lines.extend(cls.get_conversion_lines_(f.name, index, value_type))
        return lines

    @classmethod
    def get_default_value_(cls, value_type: type) -> str:
        match getattr(value_type, "__name__", str(value_type)):
            case "int":
                return "0"
            case "float":
                return "0.0"
            case "str":
                return "''"
            case "bool":
                return "False"
            case _:
                return "None"

    @classmethod
    def get_conversion_lines_(cls, field_name: str, index: int, value_type: type) -> list[str]:
        match getattr(value_type, "__name__", str(value_type)):
            case "int":
                return [
                    f"    if type(value := row[{index}]) is int: {field_name} = value",
                    "    else:",
                    "        try:",
                    f"            {field_name} = _int(value)",
                    "        except (TypeError, ValueError):",
                    f"            {field_name} = 0",
                ]
            case "float":
                return [
                    f"    if type(value := row[{index}]) is float: {field_name} = value",
                    "    else:",
                    "        try:",
                    f"            {field_name} = _float(value)",
                    "        except (TypeError, ValueError):",
                    f"            {field_name} = 0.0",
                ]
            case "str":
                return [f"    {field_name} = '' if row[{index}] is None else _str(row[{index}])"]
            case "bool":
                return [f"    {field_name} = _bool(row[{index}])"]
            case _:
                return [f"    {field_name} = row[{index}]"]

    @classmethod
    def from_reader(cls, reader: Iterator[CellGetValue]) -> Iterator[Self]:

        header_map = {str(name): i for i, name in enumerate(next(reader))}

        if not getattr(cls, "_tags", None):
            cls._tags = tuple(
                f.metadata["tag"]
                for f in fields(cls)
                if "tag" in f.metadata
            )

        sig_indices = tuple(header_map.get(tag, -1) for tag in cls._tags)
        cache_key = (cls, sig_indices)

        loader = cls._cache.get(cache_key)

        if loader is None:
            loader = cls._build_loader(header_map)
            cls._cache[cache_key] = loader
        for row in reader:
            yield loader(row)

    @classmethod
    def _build_loader(cls, header_map: dict[str, int]) -> Callable[[CellGetValue], Self]:
        lines = [
            "def loader(row, cls=cls, _int=int, _float=float, _str=str, _bool=bool):",
        ]

        kwargs: list[str] = []

        for f in fields(cls):
            if "tag" not in f.metadata:
                continue

            index = header_map.get(f.metadata["tag"])
            value_type = f.metadata["type"]

            lines.extend(cls.get_field_lines_(f, index, value_type))
            kwargs.append(f"{f.name}={f.name}")

        lines.append(f"    return cls({', '.join(kwargs)})")

        ns: dict[str, object] = {"cls": cls}
        exec("\n".join(lines), ns)
        return cast(Callable[[CellGetValue], Self], ns["loader"])

