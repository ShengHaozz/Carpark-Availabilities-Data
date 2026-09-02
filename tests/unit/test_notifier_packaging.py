import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
NOTIFIER_SOURCE = ROOT / "packages" / "notifier" / "src"


def test_notifier_handler_imports_from_lambda_style_zip(tmp_path: Path):
    """Guard against packaging handler.py without its notifier package."""
    archive_path = tmp_path / "notifier.zip"

    with zipfile.ZipFile(archive_path, "w") as archive:
        for source_file in NOTIFIER_SOURCE.rglob("*.py"):
            archive.write(source_file, source_file.relative_to(NOTIFIER_SOURCE))

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import importlib, sys; "
                f"sys.path.insert(0, {str(archive_path)!r}); "
                "module = importlib.import_module('notifier.handler'); "
                "assert callable(module.handler)"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
