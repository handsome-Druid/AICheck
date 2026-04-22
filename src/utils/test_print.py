from dataclasses import fields
from itertools import chain, islice, repeat
from typing import Callable, Iterator, Sequence, cast
import operator
import sys
try:
    from src.models import T_Dataclass
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
    from src.models import T_Dataclass


def test_print_from_list(results: Iterator[Sequence[str | float | list[str | float]]]) -> None:
    keys = next(results)
    first_row = next(results)
    _write = sys.stdout.write
    _join = "".join
    _islice = islice
    _str = str
    parts: list[str] = []
    _append = parts.append
    _replace = _str.replace
    _isinstance = isinstance
    _tuple = tuple
    _list = list
    for i, (k, v) in enumerate(zip(keys, first_row)):
        safe_k = (_replace(_replace(_replace(_str(k), "'", "\\'"), "{", "{{"), "}", "}}"))
        match(v):
            case(v) if _isinstance(v, float):
                _append(f"{safe_k}: {{row[{i}]:.4f}}")
            case(v) if _isinstance(v, _list | _tuple):
                _append(f"{safe_k}: {{_str(row[{i}])}}")
            case _:
                _append(f"{safe_k}: {{row[{i}]}}")

    ns: dict[str, Callable[[Sequence[str | float | list[str | float]]], str]] = {}
    exec(compile(
        f"def _fmt(row):\n    _str = str\n    return f'{' '.join(parts)}\\n'",
        filename="<string>",
        mode="exec",
        optimize=2
    ), {}, ns)
    formatter = ns["_fmt"]

    string_iterator = map(formatter, results)
    _write(formatter(first_row))
    while True:
        if chunk := _list(_islice(string_iterator, 5000)):
            _write(_join(chunk))
        else:
            break


_TYPE_CACHE: dict[type, tuple[tuple[str, ...], Callable[[object], Sequence[object]]]] = {}

def test_print_from_dataclass(results: Iterator[T_Dataclass]) -> None:
    first_class = next(results)
    cls = type(first_class)
    
    if cls not in _TYPE_CACHE:
        try:
            header = first_class.__slots__
        except Exception:
            header = tuple(f.name for f in fields(cls))
        if len(header) == 1:
            getter_fn: Callable[[object], Sequence[object]] = lambda obj: (operator.attrgetter(header[0])(obj),)
        else:
            getter_fn = operator.attrgetter(*header)
        _TYPE_CACHE[cls] = (header, getter_fn)
    
    header, getter = cast(tuple[tuple[str, ...], Callable[[T_Dataclass], Sequence[object]]], _TYPE_CACHE[cls])
    _cast = cast
    
    test_print_from_list(chain(
        repeat(header, 1),
        repeat(_cast(tuple[str | float | list[str | float]],getter(first_class)), 1),
        (
            _cast(tuple[str | float | list[str | float]],getter(instance))
            for instance in results
        )
    ))