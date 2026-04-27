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
    csv_input_path: str = field(metadata={"path": ("csv", "input_path")})
    csv_output_path: str = field(metadata={"path": ("csv", "output_path")})
    source_last_type: str = field(metadata={"path": ("source", "last_type")})
    end_tag: str = field(metadata={"path": ("end_flag", "tag")})
    end_value: str = field(metadata={"path": ("end_flag", "value")})
    pass_port: list[int] = field(metadata={"path": ("pass_port",), "type": list[int]})

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



import os

json_config: dict[str, JsonConfig] = {}
def get_config(_json: str = "settings.json", refresh: bool = False) -> JsonConfig:
    _json = os.path.basename(_json)
    global json_config
    if _json not in json_config or refresh:
        try:
            with open(get_path(_json), "r", encoding="utf-8") as f:
                json_content = f.read()
            json_config[_json] = JsonConfig.from_json(json_content)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Configuration file '{_json}' not found.") from e
    return json_config[_json]


def update_config(
    _json: str = "settings.json",
    *,
    xlsx_input_path: str | None = None,
    xlsx_input_sheet_name: str | None = None,
    csv_input_path: str | None = None,
    csv_output_path: str | None = None,
    source_last_type: str | None = None,
) -> JsonConfig:
    _json = os.path.basename(_json)
    config_path = get_path(_json)
    
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if xlsx_input_path is not None:
        data.setdefault("xlsx", {})["input_path"] = xlsx_input_path

    if xlsx_input_sheet_name is not None:
        data.setdefault("xlsx", {})["input_sheet_name"] = xlsx_input_sheet_name

    if csv_input_path is not None:
        data.setdefault("csv", {})["input_path"] = csv_input_path

    if csv_output_path is not None:
        data.setdefault("csv", {})["output_path"] = csv_output_path

    if source_last_type is not None:
        data.setdefault("source", {})["last_type"] = source_last_type

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        
    json_config.pop(_json, None)
    return get_config(_json, refresh=True)

def main() -> None:
        config = get_config()
        print(config.xlsx_input_path)
        print(config.csv_output_path)

if __name__ == "__main__":
    main()