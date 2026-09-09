import os
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).parent.parent
REQUIRED_SETTINGS = (
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "HEALTHCHECKS_PING_URL",
)
VALID_ENVIRONMENT = {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SERVICE_ROLE_KEY": "service-role-secret",
    "HEALTHCHECKS_PING_URL": "https://hc-ping.com/example",
}


def run_config_import(
    temporary_directory: Path,
    environment: dict[str, str],
    code: str = "import ingest.config",
) -> subprocess.CompletedProcess[str]:
    process_environment = os.environ.copy()
    for setting in REQUIRED_SETTINGS:
        process_environment.pop(setting, None)
    process_environment.update(environment)
    python_path = process_environment.get("PYTHONPATH")
    process_environment["PYTHONPATH"] = os.pathsep.join(
        path for path in (str(REPOSITORY_ROOT), python_path) if path
    )
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=temporary_directory,
        env=process_environment,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("missing_setting", REQUIRED_SETTINGS)
def test_config_raises_at_import_when_a_required_variable_is_absent(
    tmp_path: Path,
    missing_setting: str,
) -> None:
    environment = VALID_ENVIRONMENT.copy()
    environment.pop(missing_setting)

    result = run_config_import(tmp_path, environment)

    assert result.returncode != 0
    assert missing_setting.lower() in result.stderr


def test_config_never_logs_a_secret_value(tmp_path: Path) -> None:
    code = """
import logging

from ingest.config import settings

logging.basicConfig(level=logging.INFO)
logging.getLogger(__name__).info("settings=%r", settings)
print(repr(settings))
"""

    result = run_config_import(tmp_path, VALID_ENVIRONMENT, code)

    assert result.returncode == 0, result.stderr
    output = result.stdout + result.stderr
    assert VALID_ENVIRONMENT["SUPABASE_SERVICE_ROLE_KEY"] not in output
    assert "**********" in output
