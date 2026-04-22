import asyncio
import httpx
import datetime
import os
from pathlib import Path
import subprocess
import operator
try:
    from src.services.test_vllm import check_vllm_models
    from src.models.sheet import Sheet, get_sheet_iterator
    from src.models.vllm_results import VLLMTestResult
    from src.utils.write_csv import write_csv_from_dataclass
    from src.utils.test_print import test_print_from_dataclass
    from src.config import get_config
except ImportError:
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
    from src.services.test_vllm import check_vllm_models
    from src.models.sheet import Sheet, get_sheet_iterator
    from src.models.vllm_results import VLLMTestResult
    from src.utils.write_csv import write_csv_from_dataclass
    from src.utils.test_print import test_print_from_dataclass
    from src.config import get_config


# def main() -> None:

#     def iter_results():
#         end_tag = get_config().end_tag
#         end_value = get_config().end_value
#         for sheet in get_sheet_iterator():
#             if operator.attrgetter(end_tag)(sheet) == end_value:
#                 break
#             yield check_vllm_models(
#                 url=sheet.call_method,
#                 port=sheet.port,
#                 expected_models=[sheet.model_id],
#                 api_key=None,
#             )


#     test_print_from_dataclass(iter_results())

#     write_csv_from_dataclass(
#         iter_results(),
#         Path(get_config().csv_output_path) / f"vllm_test_results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
#     )

async def main() -> None:
    async def results() -> list[VLLMTestResult]:
        async with httpx.AsyncClient(timeout = httpx.Timeout(10.0)) as client:
            end_tag = get_config().end_tag
            end_value = get_config().end_value
            sheets: list[Sheet] = []
            for sheet in get_sheet_iterator():
                if operator.attrgetter(end_tag)(sheet) == end_value:
                    break
                sheets.append(sheet)
            return await asyncio.gather(
                *(
                    check_vllm_models(
                        client=client,
                        url=sheet.call_method,
                        port=sheet.port,
                        expected_models=[sheet.model_id],
                        api_key=None,
                    )
                    for sheet in sheets
                )
            )
    
    _results = await results()
    test_print_from_dataclass(iter(_results))
    write_csv_from_dataclass(
        iter(_results),
        Path(get_config().csv_output_path) / f"vllm_test_results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )

    
if __name__ == "__main__":
    asyncio.run(main())
    subprocess.run("pause", shell=True)