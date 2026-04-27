from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, ClassVar, Protocol, Callable, Sequence
from dataclasses import Field
from datetime import datetime, date, time, timedelta

if TYPE_CHECKING:  # pragma: no cover
    from PySide6.QtWidgets import QLineEdit

type CellGetValue = list[int | float | str | bool | datetime | date | time | timedelta]


class SignalLike0(Protocol):  # pragma: no cover
    def connect(self, slot: Callable[[], None]) -> None: ...

    def emit(self) -> None: ...


class SignalLike1[T_Signal](Protocol):  # pragma: no cover
    def connect(self, slot: Callable[[T_Signal], None]) -> None: ...

    def emit(self, arg1: T_Signal) -> None: ...


class SignalLike2[T_Signal, T_Two](Protocol):  # pragma: no cover
    def connect(self, slot: Callable[[T_Signal, T_Two], None]) -> None: ...

    def emit(self, arg1: T_Signal, arg2: T_Two) -> None: ...


class MainWindowUiLike(Protocol):  # pragma: no cover
    lineEditSheetName: QLineEdit


class MainWindowLike(Protocol):  # pragma: no cover
    dataSourceChanged: SignalLike2[str, str]
    sheetNameChanged: SignalLike1[str]
    outputDirChanged: SignalLike1[str]
    startTestRequested: SignalLike2[str, str]
    showHistoryRequested: SignalLike0
    ui: MainWindowUiLike

    def append_std_info(self, text: str) -> None: ...

    def show_history_results(self, rows: list[tuple[str, int, str]]) -> None: ...

    def setEnabled(self, enabled: bool) -> None: ...


class WorkerLike(Protocol):  # pragma: no cover
    def isRunning(self) -> bool: ...

    def start(self) -> None: ...


class DataclassProtocol(Protocol):  # pragma: no cover
    __dataclass_fields__: ClassVar[dict[str, Field[str]]]
    __slots__: ClassVar[tuple[str, ...]]

T_Dataclass = TypeVar("T_Dataclass", bound=DataclassProtocol)

TYPE_CACHE: dict[type, tuple[tuple[str, ...], Callable[[object], Sequence[object]]]] = {}

