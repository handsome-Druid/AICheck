from typing import Iterable
from dataclasses import fields
import sys
from itertools import islice
try:
    from src.models.vllm_results import VLLMTestResult
except ImportError:
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
    from src.models.vllm_results import VLLMTestResult

def print_results(results: Iterable[VLLMTestResult]) -> None:
    _write = sys.stdout.write
    failure: bool = False
    _list = list
    _islice = islice
    _join = "\n".join

    def iter_result_fields(result: VLLMTestResult) -> Iterable[str]:
        for field in fields(result):
            if (attr := getattr(result, name := field.name)) != []:
                yield f"{name}: {attr}"

    for result in results:
        if result.status == "success":
            continue
        
        result_iter = iter_result_fields(result)

        while True:
            if chunk := _list(_islice(result_iter, 10)):
                _write(_join(chunk))
            else:
                break

        _write("\n")
        failure = True

    if not failure:
        _write("所有测试均成功！")
