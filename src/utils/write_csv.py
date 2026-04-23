from dataclasses import fields
from itertools import islice
from typing import Callable, Iterable, Iterator, Sequence, cast
import csv
import operator
from pathlib import Path
import os
import sys
try:
    from src.models import T_Dataclass, TYPE_CACHE
    from src.utils.get_path import get_path
except ImportError:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
    from src.models import T_Dataclass, TYPE_CACHE
    from src.utils.get_path import get_path



def write_csv(results: Iterator[Iterable[str | float]], _path: str | Path) -> int:
    _path = get_path(_path)
    os.makedirs(
        Path(_path).resolve().parent, 
        exist_ok=True
    )
    with open(_path, mode='w', newline='', encoding='utf-8-sig') as csvfile:
        _writerows = csv.writer(csvfile).writerows
        _list = list
        _islice = islice
        total_rows = 0
        while True:
            chunk = _list(_islice(results, 5000))
            if not chunk:
                break
            _writerows(chunk)
            total_rows += len(chunk)
    return total_rows


def write_csv_from_dataclass(results: Iterator[T_Dataclass], _path: str | Path) -> int:
    _path = get_path(_path)
    os.makedirs(
        Path(_path).resolve().parent, 
        exist_ok=True
    )
    first_class = next(results)
    cls = type(first_class)

    if cls not in TYPE_CACHE:
        try:
            header = first_class.__slots__
        except Exception:
            header = tuple(f.name for f in fields(cls))
        if len(header) == 1:
            getter_fn: Callable[[object], Sequence[object]] = lambda obj: (operator.attrgetter(header[0])(obj),)
        else:
            getter_fn = operator.attrgetter(*header)
        TYPE_CACHE[cls] = (header, getter_fn)

    header, getter = cast(tuple[tuple[str, ...], Callable[[T_Dataclass], Sequence[object]]], TYPE_CACHE[cls])

    _list = list
    _islice = islice
    _map = map

    with open(_path, mode='w', newline='', encoding='utf-8-sig') as csvfile:
        _writer = csv.writer(csvfile)
        _writerow = _writer.writerow
        _writerows = _writer.writerows
        _writerow(header)
        _writerow(getter(first_class))
        total_rows = 0 + 1
        while True:
            if chunk := _list(_islice(results, 5000)):
                _writerows(_map(getter, chunk))
                total_rows += len(chunk)
            else:
                break
    return total_rows