import subprocess
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

import talib
from conftest import TALIB_UNSTABLE_FUNCTIONS


def test_get_unstable_period_returns_zero_out_of_the_box() -> None:
    assert {
        function: talib.get_unstable_period(function)
        for function in TALIB_UNSTABLE_FUNCTIONS
    } == dict.fromkeys(TALIB_UNSTABLE_FUNCTIONS, 0)


def test_setting_an_unstable_period_fails_the_suite() -> None:
    tests_directory = Path(__file__).parent
    with NamedTemporaryFile(
        "w",
        dir=tests_directory,
        encoding="utf-8",
        prefix="test_talib_mutation_",
        suffix=".py",
        delete=False,
    ) as temporary_test:
        temporary_test.write(
            "import talib\n\n"
            "def test_mutates_process_global_state():\n"
            "    talib.set_unstable_period('RSI', 1)\n"
        )

    mutating_test = Path(temporary_test.name)
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "--no-header",
                "-o",
                "addopts=",
                str(mutating_test),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    finally:
        mutating_test.unlink()

    assert result.returncode != 0
    assert "TA-Lib unstable periods must remain at default 0" in result.stdout + result.stderr
