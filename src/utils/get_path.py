from pathlib import Path
import sys

def get_path(_path: str | Path) -> Path:
    return (
        (Path(sys.argv[0]).resolve().parent / _path)
        if "__compiled__" in globals() else 
        Path(__file__).resolve().parent.parent.parent / 
        _path
    )