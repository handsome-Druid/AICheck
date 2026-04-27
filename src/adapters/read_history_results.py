import os
from datetime import datetime, timedelta
try:
    from src.config.settings import get_config
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
    from src.config.settings import get_config

def filter_log_files(directory: None | str | os.PathLike[str] = None) -> tuple[list[str], list[str], list[str]]:
    if directory is None:
        directory = get_config().csv_output_path
    
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_noon = now.replace(hour=12, minute=0, second=0, microsecond=0)

    days_back = 3 if now.weekday() == 0 else 1
    previous_window_noon = (today_start - timedelta(days=days_back)).replace(hour=12)

    results: tuple[list[str], list[str], list[str]] = ([], [], [])  # (yesterday_after_noon, today_morning, today_after_noon)

    if not os.path.exists(directory):
        return results

    with os.scandir(directory) as it:
        for entry in it:
            if entry.is_file() and entry.name.startswith("vllm_test_results_") and entry.name.endswith(".csv"):
                try:
                    time_str = entry.name.replace("vllm_test_results_", "").replace(".csv", "")
                    file_time = datetime.strptime(time_str, "%Y%m%d_%H%M%S")

                    if previous_window_noon <= file_time < today_start:
                        results[0].append(entry.name)
                    elif today_start <= file_time < today_noon:
                        results[1].append(entry.name)
                    elif file_time >= today_noon:
                        results[2].append(entry.name)
                except ValueError:
                    continue

    return results


def main() -> None:
    files = filter_log_files()
    print("昨天下午:", files[0])
    print("今天上午:", files[1])
    print("今天下午:", files[2])

if __name__ == "__main__":
    main()