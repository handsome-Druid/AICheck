from typing import TypeAlias, TypeVar, ClassVar, Protocol, Callable, Sequence
from dataclasses import Field
from datetime import datetime, date, time, timedelta

CellGetValue: TypeAlias = list[int | float | str | bool | datetime | date | time | timedelta]

class DataclassProtocol(Protocol):
    __dataclass_fields__: ClassVar[dict[str, Field[str]]]
    __slots__: ClassVar[tuple[str, ...]]

T_Dataclass = TypeVar("T_Dataclass", bound=DataclassProtocol)

TYPE_CACHE: dict[type, tuple[tuple[str, ...], Callable[[object], Sequence[object]]]] = {}

