from dataclasses import dataclass


    # result: dict[str, object] = {
    #     "ip": ip,
    #     "端口": 端口,
    #     "状态": "failed",  # failed, success, timeout
    #     "信息": "",
    #     "实际模型": [],
    #     "expected_models": expected_models,
    #     "多余模型": [],    # 存在但不在预期列表中的模型
    #     "缺失模型": [],  # 预期但不存在的模型
    #     "response_time": 0.0
    # }

@dataclass(slots = True, frozen = True)
class VLLMTestResult:
    IP: str
    端口: int
    状态: str
    信息: str
    实际模型: list[str]
    预期模型: list[str]
    多余模型: list[str]
    缺失模型: list[str]
    响应时间: float
    # @classmethod
    # def from_results(
    #     cls,
    #     IP: str,
    #     端口: int,
    #     状态: str,
    #     信息: str,
    #     实际模型: list[str],
    #     预期模型: list[str],
    #     多余模型: list[str],
    #     缺失模型: list[str],
    #     响应时间: float
    # ) -> "VLLMTestResult":
    #     return cls(
    #         IP = IP,
    #         端口 = 端口,
    #         状态 = 状态,
    #         信息 = 信息,
    #         实际模型 = 实际模型,
    #         预期模型 = 预期模型,
    #         多余模型 = 多余模型,
    #         缺失模型 = 缺失模型,
    #         响应时间 = 响应时间
    #     )