from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from dbt.cli.main import dbtRunnerResult
from packages.gold.src.gold.handler import (
    handler,
    run_dbt_commands,
    setup_dbt_environment,
)


def test_setup_dbt_environment(tmp_path: Path):
    # Create fake source project files
    src_dir = tmp_path / "src_project"
    src_dir.mkdir()
    (src_dir / "dbt_project.yml").write_text("name: test_project")
    models_dir = src_dir / "models"
    models_dir.mkdir()
    (models_dir / "test_model.sql").write_text("select 1 as id")

    dest_dir = tmp_path / "dest_tmp"

    result_path = setup_dbt_environment(src_dir, dest_dir)

    assert result_path == dest_dir
    assert (dest_dir / "dbt_project.yml").exists()
    assert (dest_dir / "dbt_project.yml").read_text() == "name: test_project"
    assert (dest_dir / "models" / "test_model.sql").exists()


def test_run_dbt_commands_success(tmp_path: Path):
    mock_runner = MagicMock()
    success_result = dbtRunnerResult(success=True)
    mock_runner.invoke.return_value = success_result

    with patch("packages.gold.src.gold.handler.dbtRunner", return_value=mock_runner):
        results = run_dbt_commands(tmp_path)

        assert results == {
            "snapshot": "SUCCESS",
            "run": "SUCCESS",
            "test": "SUCCESS",
        }
        assert mock_runner.invoke.call_count == 3


def test_run_dbt_commands_failure(tmp_path: Path):
    mock_runner = MagicMock()
    failed_result = dbtRunnerResult(
        success=False, exception=Exception("dbt syntax error")
    )
    mock_runner.invoke.return_value = failed_result

    with patch("packages.gold.src.gold.handler.dbtRunner", return_value=mock_runner):
        with pytest.raises(RuntimeError, match="dbt stage 'snapshot' failed"):
            run_dbt_commands(tmp_path)


def test_handler_dev_mode(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("DBT_PROJECT_DIR", str(tmp_path))

    with (
        patch(
            "packages.gold.src.gold.handler.setup_dbt_environment",
            return_value=tmp_path,
        ) as mock_setup,
        patch("packages.gold.src.gold.handler.run_dbt_commands") as mock_run,
    ):
        mock_run.return_value = {
            "snapshot": "SUCCESS",
            "run": "SUCCESS",
            "test": "SUCCESS",
        }

        response = handler({}, None)

        assert response["status"] == "SUCCESS"
        assert response["stages"]["run"] == "SUCCESS"
        mock_setup.assert_called_once_with(tmp_path)
        mock_run.assert_called_once_with(tmp_path)


def test_handler_prod_mode(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("LAMBDA_TASK_ROOT", str(tmp_path))

    with (
        patch(
            "packages.gold.src.gold.handler.setup_dbt_environment",
            return_value=tmp_path,
        ) as mock_setup,
        patch("packages.gold.src.gold.handler.run_dbt_commands") as mock_run,
    ):
        mock_run.return_value = {
            "snapshot": "SUCCESS",
            "run": "SUCCESS",
            "test": "SUCCESS",
        }

        response = handler({}, None)

        assert response["status"] == "SUCCESS"
        mock_setup.assert_called_once_with(tmp_path)
        mock_run.assert_called_once_with(tmp_path)


def test_multiprocessing_lambda_patch():
    """Verify that multiprocessing primitives are patched to use threading primitives for AWS Lambda."""
    import multiprocessing
    import multiprocessing.synchronize
    import threading
    from dbt.mp_context import get_mp_context

    # Ensure synchronization primitives return threading objects
    rlock = multiprocessing.synchronize.RLock()
    lock = multiprocessing.synchronize.Lock()
    sem = multiprocessing.synchronize.Semaphore()
    bounded_sem = multiprocessing.synchronize.BoundedSemaphore()
    cond = multiprocessing.synchronize.Condition()
    event = multiprocessing.synchronize.Event()

    assert isinstance(rlock, type(threading.RLock()))
    assert isinstance(lock, type(threading.Lock()))
    assert isinstance(sem, threading.Semaphore)
    assert isinstance(bounded_sem, threading.BoundedSemaphore)
    assert isinstance(cond, threading.Condition)
    assert isinstance(event, threading.Event)

    # Verify dbt's mp_context retrieves non-failing threading locks
    mp_ctx = get_mp_context()
    ctx_rlock = mp_ctx.RLock()
    assert isinstance(ctx_rlock, type(threading.RLock()))

    # Verify lock behavior
    with ctx_rlock:
        assert True
