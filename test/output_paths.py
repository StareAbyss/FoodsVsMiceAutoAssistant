from pathlib import Path

from function.globals.get_paths import PATHS


def get_test_output_dir(test_group: str, *parts: str) -> Path:
    """Return the local output directory beside a test group."""
    output_dir = Path(PATHS["root"]) / "test" / test_group / "output"
    output_dir = output_dir.joinpath(*parts)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir
