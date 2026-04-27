from typing import TYPE_CHECKING
from urllib.parse import urlparse
import time

from src.models.vllm_results import VLLMTestResult

if TYPE_CHECKING:
    import httpx

async def check_vllm_models(
        client: "httpx.AsyncClient",
        url: str, 
        port: int, 
        container_name: str,
        expected_models: list[str], 
        model_id: str,
        api_key: str | None = None
        ) -> VLLMTestResult:

    import httpx

    url = url.replace("chat/completions","models")
    ip = urlparse(url).hostname or ""

    headers: dict[str, str] = {}

    if api_key is not None:
        headers["Authorization"] = f"Bearer {api_key}"

    def build_result(
        status: str,
        message: str,
        actual_model: list[str],
        extra_model: list[str],
        missing_model: list[str],
        response_time: float,
        container_name: str,
        model_id: str
    ) -> VLLMTestResult:
        return VLLMTestResult(
            ip=ip,
            port=port,
            status=status,
            message=message,
            actual_model=actual_model,
            expected_model=expected_models,
            extra_model=extra_model,
            missing_model=missing_model,
            response_time=response_time,
            container_name=container_name,
            model_id=model_id
        )
    
    try:
        start_time = time.time()

        response = await client.get(url, headers=headers)
        response_time = round(time.time() - start_time, 3)

        if response.status_code != 200:
            return build_result(
                status="failed",
                message=f"API请求失败，状态码: {response.status_code}",
                actual_model=[],
                extra_model=[],
                missing_model=[],
                response_time=response_time,
                container_name=container_name,
                model_id=model_id
            )
        
        try:
            data = response.json()
            if "data" not in data:
                return build_result(
                    status="failed",
                    message="API返回格式不正确，缺少'data'字段",
                    actual_model=[],
                    extra_model=[],
                    missing_model=[],
                    response_time=response_time,
                    container_name=container_name,
                    model_id=model_id
                )

            available_models = [model["id"] for model in data["data"]]
            missing = [model for model in expected_models if model not in available_models]
            extra = [model for model in available_models if model not in expected_models]
            
            match (missing, extra):
                case ([], []):
                    return build_result(
                        status="success",
                        message=f"模型完全匹配 (共{len(available_models)}个模型)",
                        actual_model=available_models,
                        extra_model=[],
                        missing_model=[],
                        response_time=response_time,
                        container_name=container_name,
                        model_id=model_id
                    )
                case (_, []):
                    return build_result(
                        status="failed",
                        message=f"发现{len(missing)}个缺失模型",
                        actual_model=available_models,
                        extra_model=[],
                        missing_model=missing,
                        response_time=response_time,
                        container_name=container_name,
                        model_id=model_id
                    )
                case ([], _):
                    return build_result(
                        status="failed",
                        message=f"发现{len(extra)}个多余模型",
                        actual_model=available_models,
                        extra_model=extra,
                        missing_model=[],
                        response_time=response_time,
                        container_name=container_name,
                        model_id=model_id
                    )
                case _:
                    return build_result(
                        status="failed",
                        message=f"发现{len(missing)}个缺失模型; 发现{len(extra)}个多余模型",
                        actual_model=available_models,
                        extra_model=extra,
                        missing_model=missing,
                        response_time=response_time,
                        container_name=container_name,
                        model_id=model_id
                    )

        except ValueError:
            return build_result(
                status="failed",
                message="无法解析API返回的JSON数据",
                actual_model=[],
                extra_model=[],
                missing_model=[],
                response_time=response_time,
                container_name=container_name,
                model_id=model_id
            )
    except httpx.TimeoutException:
        return build_result(
            status="timeout",
            message="请求超时（超过10秒）",
            actual_model=[],
            extra_model=[],
            missing_model=[],
            response_time=10.0,
            container_name=container_name,
            model_id=model_id
        )
    except httpx.RequestError:
        return build_result(
            status="failed",
            message="连接失败，可能服务未启动或地址错误",
            actual_model=[],
            extra_model=[],
            missing_model=[],
            response_time=0.0,
            container_name=container_name,
            model_id=model_id
        )
    except Exception as e:
        return build_result(
            status="failed",
            message=f"发生未知错误: {str(e)}",
            actual_model=[],
            extra_model=[],
            missing_model=[],
            response_time=0.0,
            container_name=container_name,
            model_id=model_id
        )