import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
import talib


def pytest_configure(config: pytest.Config) -> None:
    """Point pytest's own temp-dir housekeeping at a fresh directory before it can touch a
    poisoned one.

    pytest's tmp_path_factory lazily scans the OS default temp root (on Windows,
    %TEMP%\\pytest-of-<user>) to prune old numbered run directories the first time any test
    requests tmp_path - this happens regardless of --basetemp, and regardless of which
    invocation path called pytest (a wrapped gate command, a story's own literal [cmd:]
    criterion, or a bare `uv run pytest`). If that directory has ever acquired an
    unreclaimable ACL (confirmed to happen in this project's own sandboxed execution
    history), every test run fails identically until a fresh, never-yet-touched directory
    is used instead. Redirecting TEMP/TMP here, before any fixture resolves a temp path,
    protects every invocation path uniformly rather than only the ones explicitly wrapped
    with an env override.
    """

    if config.option.basetemp is not None:
        return
    tmp_root = Path(os.getcwd()) / ".tmp"
    tmp_root.mkdir(parents=True, exist_ok=True)
    fresh_root = Path(tempfile.mkdtemp(prefix="pytest-tmp-", dir=tmp_root))
    os.environ["TEMP"] = str(fresh_root)
    os.environ["TMP"] = str(fresh_root)
    # tempfile.gettempdir() caches its result at the module level on first call, so a
    # TEMP/TMP env var change alone has no effect once anything (pytest internals, another
    # import) has already called it in this process. Overriding tempfile.tempdir directly
    # bypasses that cache regardless of import order.
    tempfile.tempdir = str(fresh_root)

TALIB_UNSTABLE_FUNCTIONS = (
    "ADX",
    "ADXR",
    "ATR",
    "CMO",
    "DX",
    "EMA",
    "HT_DCPERIOD",
    "HT_DCPHASE",
    "HT_PHASOR",
    "HT_SINE",
    "HT_TRENDLINE",
    "HT_TRENDMODE",
    "KAMA",
    "MAMA",
    "MFI",
    "MINUS_DI",
    "MINUS_DM",
    "NATR",
    "PLUS_DI",
    "PLUS_DM",
    "RSI",
    "STOCHRSI",
    "T3",
)


def assert_talib_unstable_periods_are_default() -> None:
    changed = {
        function: period
        for function in TALIB_UNSTABLE_FUNCTIONS
        if (period := talib.get_unstable_period(function)) != 0
    }
    assert not changed, f"TA-Lib unstable periods must remain at default 0; changed: {changed}"


@pytest.fixture(autouse=True)
def guard_talib_unstable_periods() -> Iterator[None]:
    assert_talib_unstable_periods_are_default()
    yield
    assert_talib_unstable_periods_are_default()
