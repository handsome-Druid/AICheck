from typing import Iterable
from dataclasses import fields
import sys
from itertools import islice
from operator import attrgetter
try:
    from src.models.vllm_results import VLLMTestResult
except ImportError:
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
    from src.models.vllm_results import VLLMTestResult


def print_results(results: Iterable[VLLMTestResult]) -> None:
    _write = sys.stdout.write
    _list = list
    _islice = islice
    _join = "\n".join
    _failure = False
    _headers= [field.name for field in fields(VLLMTestResult)]

    results_iter = iter_result_fields(results, _headers)

    while True:
        if chunk := _list(_islice(results_iter, 100)):
            _write(_join(chunk) + "\n")
            _failure = True
        else:
            break


        
    if not _failure:
        _write("所有测试均成功！")

def iter_result_fields(result_iter: Iterable[VLLMTestResult], _headers: list[str]) -> Iterable[str]:
    _status_getter = attrgetter("status")
    _getattr = getattr
    _separator = "-" * 40

    for result in result_iter:
        if _status_getter(result) == "success":
            continue
        
        for header in _headers:
            if attr := _getattr(result, header):
                yield f"{header}: {attr}"
        yield _separator
