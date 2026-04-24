from dataclasses import dataclass


@dataclass(slots = True, frozen = True)
class VLLMTestResult:
    ip: str
    port: int
    container_name:str
    status: str
    message: str
    actual_model: list[str]
    expected_model: list[str]
    extra_model: list[str]
    missing_model: list[str]
    response_time: float