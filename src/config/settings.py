import json
from dataclasses import dataclass, field, fields
from typing import ClassVar, Callable, Self
try:
    from src.utils.get_path import get_path
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
    from src.utils.get_path import get_path

@dataclass(slots=True, frozen=True)
class JsonConfig:
    xlsx_input_path: str = field(metadata={"path": ("xlsx", "input_path")})
    xlsx_input_sheet_name: str = field(metadata={"path": ("xlsx", "input_sheet_name")})
    csv_output_path: str = field(metadata={"path": ("csv", "output_path")})
    end_tag: str = field(metadata={"path": ("end_flag", "tag")})
    end_value: str = field(metadata={"path": ("end_flag", "value")})


    _cache: ClassVar[dict[type, Callable[[dict[str, object]], Self]]] = {}

    @classmethod
    def from_json(cls, json_str: str) -> "JsonConfig":
        if cls not in cls._cache:
            
            lines = [
                "def loader(data):",
                "    inst = cls.__new__(cls)",
            ]
            
            _repr = repr
            _append = lines.append
            _join = "".join
            
            for f in fields(cls):
                if "path" in f.metadata:
                    access_path = _join(f"[{_repr(k)}]" for k in f.metadata["path"])
                    _append(f"    set_{f.name}(inst, data{access_path})")
            
            _append("    return inst")
            
            _getattr = getattr
            ns: dict[str, type | Callable[[dict[str, object]], Self]] = {
                "cls": cls, **{
                    f"set_{f.name}": _getattr(cls, f.name).__set__ 
                    for f in fields(cls)
                }
            }
            exec("\n".join(lines), ns)
            cls._cache[cls] = ns["loader"]

        return cls._cache[cls](json.loads(json_str))



json_config: dict[str, JsonConfig] = {}
def get_config(_json: str = "settings.json", refresh: bool = False) -> JsonConfig:
    global json_config
    if _json not in json_config or refresh:
        json_config[_json] = JsonConfig.from_json(
            get_path(_json)
            .read_text(encoding="utf-8")
        )
    return json_config[_json]

def main() -> None:
        config = get_config()
        print(config.xlsx_input_path)
        print(config.csv_output_path)

if __name__ == "__main__":
    main()