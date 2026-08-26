import logging
import multiprocessing
import multiprocessing.synchronize
import os
from pathlib import Path
import shutil
import threading
from typing import Any, Dict

# Monkey-patch multiprocessing primitives to support AWS Lambda's stripped environment (no /dev/shm)
multiprocessing.synchronize.RLock = lambda *args, **kwargs: threading.RLock()
multiprocessing.synchronize.Lock = lambda *args, **kwargs: threading.Lock()
multiprocessing.synchronize.Semaphore = lambda value=1, *args, **kwargs: (
    threading.Semaphore(value)
)
multiprocessing.synchronize.BoundedSemaphore = lambda value=1, *args, **kwargs: (
    threading.BoundedSemaphore(value)
)
multiprocessing.synchronize.Condition = lambda lock=None, *args, **kwargs: (
    threading.Condition(lock)
)
multiprocessing.synchronize.Event = lambda *args, **kwargs: threading.Event()

from dbt.cli.main import dbtRunner, dbtRunnerResult  # noqa: E402

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DBT_TEMP_DIR = Path("/tmp/dbt")


def setup_dbt_environment(project_src_dir: Path, temp_dir: Path = DBT_TEMP_DIR) -> Path:
    """Copies dbt project assets into a writeable /tmp directory for Lambda."""
    temp_dir.mkdir(parents=True, exist_ok=True)

    items_to_copy = [
        "dbt_project.yml",
        "profiles.yml",
        "models",
        "snapshots",
        "tests",
        "macros",
        "seeds",
        "analyses",
    ]

    for item in items_to_copy:
        src = project_src_dir / item
        dst = temp_dir / item
        if src.exists():
            if src.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

    return temp_dir


def run_dbt_commands(project_dir: Path) -> Dict[str, Any]:
    """Executes dbt snapshot, run, and test sequentially."""
    os.environ["DO_NOT_TRACK"] = "1"
    dbt = dbtRunner()

    stages = [
        (
            "snapshot",
            [
                "snapshot",
                "--project-dir",
                str(project_dir),
                "--profiles-dir",
                str(project_dir),
            ],
        ),
        (
            "run",
            [
                "run",
                "--project-dir",
                str(project_dir),
                "--profiles-dir",
                str(project_dir),
            ],
        ),
        (
            "test",
            [
                "test",
                "--project-dir",
                str(project_dir),
                "--profiles-dir",
                str(project_dir),
            ],
        ),
    ]

    results = {}

    for stage_name, cmd_args in stages:
        logger.info(f"Starting dbt stage: {stage_name}")
        res: dbtRunnerResult = dbt.invoke(cmd_args)

        if not res.success:
            err_msg = f"dbt stage '{stage_name}' failed."
            if res.exception:
                err_msg += f" Exception: {res.exception}"
            logger.error(err_msg)
            raise RuntimeError(err_msg)

        logger.info(f"dbt stage '{stage_name}' completed successfully.")
        results[stage_name] = "SUCCESS"

    return results


def handler(event: Dict[str, Any] | None = None, context: Any = None) -> Dict[str, Any]:
    """AWS Lambda entrypoint for the Gold dbt pipeline."""
    logger.info("Starting Gold dbt Lambda execution...")

    # Determine dbt project source directory based on ENV
    env_mode = os.environ.get("ENV", "dev").lower()
    if env_mode in ("prod", "production"):
        package_dir = Path(os.environ.get("LAMBDA_TASK_ROOT", "/var/task"))
    else:
        package_dir = Path(
            os.environ.get(
                "DBT_PROJECT_DIR", Path(__file__).resolve().parent.parent.parent
            )
        )

    logger.info(f"Source dbt project directory: {package_dir}")
    work_dir = setup_dbt_environment(package_dir)

    results = run_dbt_commands(work_dir)

    return {
        "status": "SUCCESS",
        "stages": results,
    }
