import httpx
from urllib.parse import urlparse
import time

from src.models.vllm_results import VLLMTestResult

async def check_vllm_models(
        client: httpx.AsyncClient,
        url: str, 
        port: int, 
        expected_models: list[str], 
        api_key: str | None = None,
        ) -> VLLMTestResult:

    url = url.replace("chat/completions","models")
    ip = urlparse(url).hostname or ""

    headers: dict[str, str] = {}

    if api_key is not None:
        headers["Authorization"] = f"Bearer {api_key}"
    
    try:
        start_time = time.time()

        response = await client.get(url, headers = headers)
        response_time = round(time.time() - start_time, 3)

        if response.status_code != 200:
            return VLLMTestResult(
                IP = ip,
                端口 = port,
                状态 = "failed",
                信息 = f"API请求失败，状态码: {response.status_code}",
                实际模型 = [],
                预期模型 = expected_models,
                多余模型 = [],
                缺失模型 = [],
                响应时间 = response_time
            )
        
        try:
            data = response.json()
            if "data" not in data:
                return VLLMTestResult(
                    IP = ip,
                    端口 = port,
                    状态 = "failed",
                    信息 = "API返回格式不正确，缺少'data'字段",
                    实际模型 = [],
                    预期模型 = expected_models,
                    多余模型 = [],
                    缺失模型 = [],
                    响应时间 = response_time
                )
            available_models = [model["id"] for model in data["data"]]
            missing = [model for model in expected_models if model not in available_models]
            extra = [model for model in available_models if model not in expected_models]
            # if missing and extra:
            #     msg_parts: list[str] = []
            #     msg_parts.append(f"发现{len(missing)}个缺失模型")
            #     msg_parts.append(f"发现{len(extra)}个多余模型")
            #     return VLLMTestResult(
            #         IP = ip,
            #         端口 = port,
            #         状态 = "failed",
            #         信息 = "; ".join(msg_parts),
            #         实际模型 = available_models,
            #         预期模型 = expected_models,
            #         多余模型 = extra,
            #         缺失模型 = missing,
            #         响应时间 = response_time
            #     )
            # if missing:
            #     msg_parts: list[str] = []
            #     msg_parts.append(f"发现{len(missing)}个缺失模型")
            #     return VLLMTestResult(
            #         IP = ip,
            #         端口 = port,
            #         状态 = "failed",
            #         信息 =  "; ".join(msg_parts),
            #         实际模型 = available_models,
            #         预期模型 = expected_models,
            #         多余模型 = extra,
            #         缺失模型 = missing,
            #         响应时间 = response_time
            #     )
            # if extra:
            #     msg_parts: list[str] = []
            #     msg_parts.append(f"发现{len(extra)}个多余模型")
            #     return VLLMTestResult(
            #         IP = ip,
            #         端口 = port,
            #         状态 = "failed",
            #         信息 = "; ".join(msg_parts),
            #         实际模型 = available_models,
            #         预期模型 = expected_models,
            #         多余模型 = extra,
            #         缺失模型 = missing,
            #         响应时间 = response_time
            #     )

            # match(missing, extra):
            #     case (m, e) if m and e:
            #         msg_parts: list[str] = []
            #         msg_parts.append(f"发现{len(m)}个缺失模型")
            #         msg_parts.append(f"发现{len(e)}个多余模型")
            #         return VLLMTestResult(
            #             IP = ip,
            #             端口 = port,
            #             状态 = "failed",
            #             信息 = "; ".join(msg_parts),
            #             实际模型 = available_models,
            #             预期模型 = expected_models,
            #             多余模型 = e,
            #             缺失模型 = m,
            #             响应时间 = response_time
            #         )
            #     case (m, []) if m:
            #         msg_parts: list[str] = []
            #         msg_parts.append(f"发现{len(m)}个缺失模型")
            #         return VLLMTestResult(
            #             IP = ip,
            #             端口 = port,
            #             状态 = "failed",
            #             信息 =  "; ".join(msg_parts),
            #             实际模型 = available_models,
            #             预期模型 = expected_models,
            #             多余模型 = [],
            #             缺失模型 = m,
            #             响应时间 = response_time
            #         )
            #     case ([], e) if e:
            #         msg_parts: list[str] = []
            #         msg_parts.append(f"发现{len(e)}个多余模型")
            #         return VLLMTestResult(
            #             IP = ip,
            #             端口 = port,
            #             状态 = "failed",
            #             信息 = "; ".join(msg_parts),
            #             实际模型 = available_models,
            #             预期模型 = expected_models,
            #             多余模型 = e,
            #             缺失模型 = missing,
            #             响应时间 = response_time
            #         )
            #     case ([], []):
            #         return VLLMTestResult(
            #             IP = ip,
            #             端口 = port,
            #             状态 = "success",
            #             信息 = f"模型完全匹配 (共{len(available_models)}个模型)",
            #             实际模型 = available_models,
            #             预期模型 = expected_models,
            #             多余模型 = extra,
            #             缺失模型 = missing,
            #             响应时间 = response_time
            #         )
            #     case _:
            #         raise ValueError("Unexpected case in model comparison logic")

            # return VLLMTestResult(
            #     IP = ip,
            #     端口 = port,
            #     状态 = "success",
            #     信息 = f"模型完全匹配 (共{len(available_models)}个模型)",
            #     实际模型 = available_models,
            #     预期模型 = expected_models,
            #     多余模型 = extra,
            #     缺失模型 = missing,
            #     响应时间 = response_time
            # )
            
            match(missing, extra):
                case ([], []):
                    return VLLMTestResult(
                        IP = ip,
                        端口 = port,
                        状态 = "success",
                        信息 = f"模型完全匹配 (共{len(available_models)}个模型)",
                        实际模型 = available_models,
                        预期模型 = expected_models,
                        多余模型 = [],
                        缺失模型 = [],
                        响应时间 = response_time
                    )
                case (_, []):
                    # msg_parts: list[str] = []
                    # msg_parts.append(f"发现{len(m)}个缺失模型")
                    return VLLMTestResult(
                        IP = ip,
                        端口 = port,
                        状态 = "failed",
                        # 信息 = "; ".join(msg_parts),
                        信息 =  f"发现{len(missing)}个缺失模型",
                        实际模型 = available_models,
                        预期模型 = expected_models,
                        多余模型 = [],
                        缺失模型 = missing,
                        响应时间 = response_time
                    )
                case ([], _):
                    # msg_parts: list[str] = []
                    # msg_parts.append(f"发现{len(e)}个多余模型")
                    return VLLMTestResult(
                        IP = ip,
                        端口 = port,
                        状态 = "failed",
                        # 信息 = "; ".join(msg_parts),
                        信息 = f"发现{len(extra)}个多余模型",
                        实际模型 = available_models,
                        预期模型 = expected_models,
                        多余模型 = extra,
                        缺失模型 = [],
                        响应时间 = response_time
                    )
                case _:
                    # msg_parts: list[str] = []
                    # msg_parts.append(f"发现{len(m)}个缺失模型")
                    # msg_parts.append(f"发现{len(e)}个多余模型")
                    return VLLMTestResult(
                        IP = ip,
                        端口 = port,
                        状态 = "failed",
                        # 信息 = "; ".join(msg_parts),
                        信息 = f"发现{len(missing)}个缺失模型; 发现{len(extra)}个多余模型",
                        实际模型 = available_models,
                        预期模型 = expected_models,
                        多余模型 = extra,
                        缺失模型 = missing,
                        响应时间 = response_time
                    )

        except ValueError:
            return VLLMTestResult(
                IP = ip,
                端口 = port,
                状态 = "failed",
                信息 = "无法解析API返回的JSON数据",
                实际模型 = [],
                预期模型 = expected_models,
                多余模型 = [],
                缺失模型 = [],
                响应时间 = response_time
            )
    except httpx.TimeoutException:
        return VLLMTestResult(
            IP = ip,
            端口 = port,
            状态 = "timeout",
            信息 = "请求超时（超过10秒）",
            实际模型 = [],
            预期模型 = expected_models,
            多余模型 = [],
            缺失模型 = [],
            响应时间 = 10.0
        )
    except httpx.RequestError:
        return VLLMTestResult(
            IP = ip,
            端口 = port,
            状态 = "failed",
            信息 = "连接失败，可能服务未启动或地址错误",
            实际模型 = [],
            预期模型 = expected_models,
            多余模型 = [],
            缺失模型 = [],
            响应时间 = 0.0
        )
    except Exception as e:
        return VLLMTestResult(
            IP = ip,
            端口 = port,
            状态 = "failed",
            信息 = f"发生未知错误: {str(e)}",
            实际模型 = [],
            预期模型 = expected_models,
            多余模型 = [],
            缺失模型 = [],
            响应时间 = 0.0
        )