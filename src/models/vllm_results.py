from dataclasses import dataclass, field
try:
    from .base import BaseReaderModel
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
    from src.models.base import BaseReaderModel

@dataclass(slots = True, frozen = True)
class VLLMTestResult(BaseReaderModel):
    ip: str = field(metadata = {"tag": "ip", "type": str})
    port: int   = field(metadata = {"tag": "port", "type": int})
    model_id: str = field(metadata = {"tag": "model_id", "type": str})
    container_name: str = field(metadata = {"tag": "container_name", "type": str})
    status: str = field(metadata = {"tag": "status", "type": str})
    message: str = field(metadata = {"tag": "message", "type": str})
    actual_model: list[str] = field(metadata = {"tag": "actual_model", "type": list[str]})
    expected_model: list[str] = field(metadata = {"tag": "expected_model", "type": list[str]})
    extra_model: list[str] = field(metadata = {"tag": "extra_model", "type": list[str]})
    missing_model: list[str] = field(metadata = {"tag": "missing_model", "type": list[str]})
    response_time: float = field(metadata = {"tag": "response_time", "type": float})