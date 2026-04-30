from typing import Iterator
try:
    from src.adapters.read_history_results import filter_log_files
    from src.models.vllm_results import VLLMTestResult
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
    from src.adapters.read_history_results import filter_log_files
    from src.models.vllm_results import VLLMTestResult

def analyze_results(files: Iterator[tuple[str, list[VLLMTestResult]]] | None = None) -> Iterator[tuple[str, int, str, str]]:
    if files is None:
        files = filter_log_files()
    for period, results in files:
        result_list: list[tuple[str, int, str, str]] = []
        result_list.extend(
            (period, result.port, result.message, result.model_id)
            for result in results
            if result.status != "success"
        )
        yield from set(result_list)

def main() -> None:
    for period, port, message, model_id in analyze_results():
        print(f"{period}: {port}: {message} ({model_id})")

if __name__ == "__main__":
    main()