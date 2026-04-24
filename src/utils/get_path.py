from pathlib import Path
import sys

def get_path(_path: str | Path, *, allow_absolute: bool = False) -> Path:
    base_path = (
        Path(sys.argv[0]).resolve().parent
        if "__compiled__" in globals()
        else Path(__file__).resolve().parent.parent.parent
    )
    candidate = Path(_path)
    if candidate.is_absolute():
        if allow_absolute:
            return candidate.resolve()
        raise ValueError(f"Absolute paths are not allowed: {candidate}")

    resolved_path = (base_path / candidate).resolve()
    try:
        resolved_path.relative_to(base_path)
    except ValueError as exc:
        raise ValueError(f"Path escapes the base directory: {candidate}") from exc

    return resolved_path