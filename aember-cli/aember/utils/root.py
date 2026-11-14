from pathlib import Path


def find_root(start: Path | None = None) -> Path:
    """Walk up from `start` (default: cwd) to the aember-resources root."""
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "kas" / "base.yml").is_file():
            return candidate
    raise RuntimeError(f"Not inside aember-resources (no kas/base.yml above {here})")
