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



def write_csv(results: Iterator[Iterable[str | float]], _path: str | Path) -> None:
    _path = get_path(_path)
    os.makedirs(
        Path(_path).resolve().parent, 
        exist_ok=True
    )
    with open(_path, mode='w', newline='', encoding='utf-8-sig') as csvfile:
        _len = len
        _writerows = csv.writer(csvfile).writerows
        _write = sys.stdout.write
        _list = list
        _islice = islice
        while True:
            chunk = _list(_islice(results, 5000))
            if not chunk:
                break
            _writerows(chunk)
            _write(f"Wrote {_len(chunk)} rows to {_path}\n")
        _write(f"Finished writing to {_path}\n")


def write_csv_from_dataclass(results: Iterator[T_Dataclass], _path: str | Path) -> None:
    _path = get_path(_path)
    os.makedirs(
        Path(_path).resolve().parent, 
        exist_ok=True
    )
    _write = sys.stdout.write
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
        _len = len
        _writer = csv.writer(csvfile)
        _writerow = _writer.writerow
        _writerows = _writer.writerows
        
        _writerow(header)
        _writerow(getter(first_class))
        _write(f"Wrote header and first row to {_path}\n")
        
        while True:
            chunk = _list(_islice(results, 5000))
            if not chunk:
                break
            _writerows(_map(getter, chunk))
            _write(f"Wrote {_len(chunk)} rows to {_path}\n")
        _write(f"Finished writing to {_path}\n")