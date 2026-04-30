import os
from datetime import datetime
from typing import Tuple, Iterator
try:
    from src.config.settings import get_config
    from src.models.vllm_results import VLLMTestResult
except ImportError:
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
    from src.config.settings import get_config
    from src.models.vllm_results import VLLMTestResult

from collections import defaultdict
from typing import Iterator, Tuple
from datetime import datetime

def filter_log_files(directory: None | str | os.PathLike[str] = None) -> Iterator[Tuple[str, list[VLLMTestResult]]]:
    if directory is None:
        directory = get_config().csv_output_path

    month_start, month_end = _get_current_month_bounds()

    # 导入处理（可保持你的原有方式）
    try:
        from src.adapters.read_csv import read_csv
    except ImportError:
        import sys
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
        from src.adapters.read_csv import read_csv

    # 用字典聚合同一个 period 的结果
    period_results: dict[str, list[VLLMTestResult]] = defaultdict(list)

    with os.scandir(directory) as it:
        for entry in it:
            if not entry.is_file():
                continue
            if not entry.name.startswith("vllm_test_results_") or not entry.name.endswith(".csv"):
                continue

            # 提取时间戳，避免文件名异常导致崩溃
            try:
                ts_str = entry.name.replace("vllm_test_results_", "").replace(".csv", "")
                file_time = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
            except ValueError:
                continue  # 跳过不符合时间格式的文件

            if not (month_start <= file_time < month_end):
                continue

            day_str = file_time.strftime("%Y-%m-%d")
            period = f"{day_str} 上午" if file_time.hour < 12 else f"{day_str} 下午"

            # 直接读取 CSV 并转换为 VLLMTestResult 列表
            results = list(VLLMTestResult.from_reader(read_csv(entry.path)))
            period_results[period].extend(results)

    # 按 period 顺序（字典插入顺序即为扫描顺序）逐个返回合并后的列表
    yield from period_results.items()

def _get_current_month_bounds() -> tuple[datetime, datetime]:
    now = datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    if month_start.month == 12:
        month_end = month_start.replace(year=month_start.year + 1, month=1)
    else:
        month_end = month_start.replace(month=month_start.month + 1)

    return month_start, month_end


def main() -> None:
    triples = filter_log_files()
    for period, results in triples:
        for result in results:
            print(f"{period}: {result.port}: {result.message} ({result.status})")

if __name__ == "__main__":
    main()