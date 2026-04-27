import os
from typing import Generator, Iterator
try:
    from src.adapters.read_history_results import filter_log_files
    from src.adapters.read_xlsx import read_xlsx
    from src.adapters.read_csv import read_csv
    from src.config.settings import get_config
    from src.models.vllm_results import VLLMTestResult
    from src.models.ports import get_ports
except ImportError:
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
    from src.adapters.read_history_results import filter_log_files
    from src.adapters.read_xlsx import read_xlsx
    from src.adapters.read_csv import read_csv
    from src.config.settings import get_config
    from src.models.vllm_results import VLLMTestResult
    from src.models.ports import get_ports


def check(files: tuple[list[str], list[str], list[str]] = filter_log_files()) -> tuple[dict[int, str], dict[int, str], dict[int, str]]:
    return (
        analyze_results(VLLMTestResult.from_reader(read_csv(os.path.join(get_config().csv_output_path, filename))) for filename in files[0]),
        analyze_results(VLLMTestResult.from_reader(read_csv(os.path.join(get_config().csv_output_path, filename))) for filename in files[1]),
        analyze_results(VLLMTestResult.from_reader(read_csv(os.path.join(get_config().csv_output_path, filename))) for filename in files[2])
    )

def analyze_results(results: Generator[Iterator[VLLMTestResult]]) -> dict[int, str]:
    result_dict: dict[int, str] = {}
    for result_iterator in results:
        for result in result_iterator:
            if result.status != "success":
                result_dict[result.port] = result.message
    return result_dict

def check_headers(files: tuple[list[str], list[str], list[str]] = filter_log_files()) -> None:
    for file_list in files:
        for filename in file_list:
            file = read_csv(os.path.join(get_config().csv_output_path, filename))
            header = next(file)
            print(f"{filename} header: {header}")

def check_current(results: tuple[dict[int, str], dict[int, str], dict[int, str]] | None = None) -> tuple[dict[int, str], dict[int, str], dict[int, str]]:
    if results is None:
        results = check()
    for result_dict in results:
        ports = list(result_dict.keys())
        for port in ports:
            if get_config(refresh = True).source_last_type == "xlsx" and port not in get_ports(read_xlsx(get_config(refresh=True).xlsx_input_path)):
                result_dict.pop(port)
                continue
            if port not in get_ports(read_csv(get_config(refresh=True).csv_input_path)):
                result_dict.pop(port)
    return results


def main() -> None:
    check_headers()
    results = check_current()
    print("昨天中午12点到今天凌晨0点的测试结果:")
    for result in results[0]:
        print(f"{result}: {results[0][result]}")
    print("\n今天凌晨0点到今天中午12点的测试结果:")
    for result in results[1]:
        print(f"{result}: {results[1][result]}")
    print("\n今天中午12点到现在的测试结果:")
    for result in results[2]:
        print(f"{result}: {results[2][result]}")

if __name__ == "__main__":
    main()
