from typing import Iterator, cast
try: 
    from .type import CellGetValue
    from src.config.settings import get_config
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
    from src.models.type import CellGetValue
    from src.config.settings import get_config
def get_ports(reader: Iterator[CellGetValue]) -> list[int]:
    header = next(reader)
    port_index = header.index("port")
    ports: list[int] = []
    ports.extend(port for row in reader if (port := int(cast(int, row[port_index]))) not in get_config(refresh=True).pass_port)
    return ports

def main() -> None:
    try:
        from src.adapters.read_xlsx import read_xlsx
    except ImportError:
        import sys
        import os
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
        from src.adapters.read_xlsx import read_xlsx
    ports = get_ports(read_xlsx(get_config(refresh=True).xlsx_input_path))
    print(f"Ports: {ports}")

if __name__ == "__main__":
    main()