# PRD-002 · Determinism and contract harness — research

Research stage. No spec, no implementation. Read-only sandbox.

---

## What we already knew, and whether it still holds

| Claim we hold | Still true? | What the source says | Citation |
|---|---|---|---|
| TA-Lib as "the computation engine, golden-file pinned" settles the smoothing ambiguity, so an indicator is a pure function of `(bars, window)` | **Half true, and the wrong half is the one this PRD is built on.** TA-Lib settles the *formula*. It does not make the function history-independent. | "Others are recursive, so their earliest values depend on how much history precedes them, converging as more bars are supplied — the Exponential Moving Average is the classic example." And: "Take one bar and compute an indicator for it twice: once with a year of history before it, once with a decade. Do you get the same value? For many functions, always — they read a fixed number of bars and ignore everything older." The implication is that for the rest, no. | https://ta-lib.org/api/?h=unstable |
| Determinism is about pinning `(bars, window)` | **Incomplete.** The affected function list is long and covers most of what a crypto dashboard wants. | Functions with an unstable period: "ADX, ATR, CMO, DX, EMA, HT_DCPERIOD, HT_DCPHASE, HT_PHASOR, HT_SINE, HT_TRENDLINE, HT_TRENDMODE, KAMA, MAMA, MINUS_DI, MINUS_DM, NATR, PLUS_DI, PLUS_DM, RSI, T3, RMA, HA, RVI." Default unstable period is `0`, which "discards nothing: you get every value the function can compute." Most charting sites ignore the problem because "the latest bar has plenty of history behind it," which "quietly uses bad values" for short series. | https://ta-lib.org/api/unstable-period/ |
| "Windows wheels/MSI available since v0.6.5" | **Out of date.** | Latest is **0.7.1, released 2026-07-16**, with wheels for CPython 3.9 through 3.14 on Linux x86_64/arm64, macOS x86_64/arm64, and Windows x86_64/x86/arm64. Wheels from 0.6.5 onward bundle the underlying C library. The MSI/Homebrew instructions remain on the page for unsupported platforms only. | https://pypi.org/project/TA-Lib/ |
| `pandas-ta` heading to archival; `pandas-ta-classic` maintained as fallback | **Holds.** | The archival deadline was 2026-07-01; `pandas-ta-classic` shipped 0.6.52 on 2026-06-24 and is the community-maintained continuation. | https://pypi.org/project/pandas-ta-classic/ |
| "Recorded-cassette tests must fail loudly when a response shape changes" | **Wrong as a mechanism.** A cassette replays the recorded response forever. It is structurally incapable of noticing that the live vendor changed. | Conventional API tests validate values and assertions, not structural integrity: "Your assertions test what you thought to check. They don't test what you didn't think to check." The article walks five undetected changes on one endpoint (number to string, string to array, ISO 8601 to Unix timestamp, nested object flattened, new field) and concludes "Zero failed tests." | https://dev.to/qa-leaders/your-api-tests-are-lying-to-you-the-schema-drift-problem-nobody-talks-about-4h86 |
| VCR.py is a viable cassette layer for this stack | **Holds.** | Supported libraries include `httpx` and `httpcore` alongside `requests`, `urllib3`, `aiohttp`. Python 3.9+. | https://vcrpy.readthedocs.io/en/latest/installation.html |
| A paginated fetch that dies mid-walk returns a shorter-but-plausible series | **Holds, and there is a shipped instance on our exact venue.** | On OKX, ccxt's own endpoint-switching arithmetic caused users requesting 300 candles to "silently receive fewer candles than requested — specifically 100 history candles instead of 300 live candles — without obvious notification." | https://github.com/ccxt/ccxt/issues/20756 |
| Pydantic will catch a reshaped vendor response | **We never wrote this down, and the default is the opposite.** | "By default, Pydantic models won't error when you provide extra data, and these values will simply be ignored." The three options are `ignore` (default), `forbid`, `allow`. | https://pydantic.dev/docs/validation/latest/concepts/models/ |

Our database knowledge (Supabase free tier, direct port, pause-after-idle) is unchanged by this PRD and was not re-checked.

---

## Existing implementations

**TA-Lib ships the escape hatch and documents it as a global.** `TA_SetUnstablePeriod(TA_FuncUnstId id, unsigned int unstablePeriod)` strips a configurable number of leading bars per function group. The setting "follows the function wherever it runs," including indicators that internally depend on EMA. It is documented as a global that "must be initialized from a single thread." That is process-wide mutable state inside the determinism layer (https://ta-lib.org/api/?h=unstable, https://ta-lib.org/api/unstable-period/).

**ccxt is the reference implementation of the OKX pagination hazard.** OKX allows up to 300 candles from the live endpoint and 100 from history, with roughly 1440 live bars available. ccxt's switch condition `(1440 - limit - 1) * duration` subtracted the caller's own request size from the available window, switching to the history endpoint prematurely and truncating the series with no error (https://github.com/ccxt/ccxt/issues/20756).

**Freqtrade shows what the industry does about gaps, and why it is the wrong default here.** It runs an automatic "Missing data fillup" that synthesises candles across gaps, logging lines like `Missing data fillup for BCH/USDT, 15m: before: 39 - after: 124 - 217.95%`. A series that arrived 68 percent incomplete becomes structurally valid and silently backtestable (https://github.com/freqtrade/freqtrade/issues/9751). This is guarantee 3 inverted: repair instead of error.

**pytest-regressions is the mature Python golden-file fixture.** `num_regression.check()` and `dataframe_regression.check()` take `tolerances` per key (`{'U': dict(atol=1e-2)}`) and `default_tolerance` (`dict(atol=1e-7, rtol=1e-18)`), falling back to numpy `isclose` defaults when omitted. Golden values are stored as CSV and regenerated with `--force-regen` or `--regen-all`, and the files "should be committed to version control" (https://pytest-regressions.readthedocs.io/en/latest/api.html, https://pytest-regressions.readthedocs.io/en/latest/overview.html).

**pytest-recording defaults to safe.** It uses VCR record mode `none` by default so tests cannot silently reach the network, and adds `pytest.mark.block_network`, which raises on any attempted network access (https://github.com/kiwicom/pytest-recording).

---

## Approach options

**Option A — Full off-the-shelf stack.** `pytest-regressions` for goldens, `pytest-recording` + VCR cassettes for vendor shapes, Hypothesis for pagination invariants. Trade-off: brings pandas and numpy into an ingestion package that currently has neither, plus three new test dependencies and three new file formats to review. Cost: zero dollars, meaningful complexity. Used by scientific-Python projects and by teams with dozens of endpoints.

**Option B — Extend what PRD-001 already built.** Keep `httpx.MockTransport` (already used in `tests/test_okx_fetcher.py:21`) as the vendor-shape layer; add pydantic response models with `extra='forbid'` and strict types; store goldens as small committed JSON with exact float equality over a fixed-length bar slice. Trade-off: no snapshot-review tooling, no `--force-regen`, so updating a golden is a deliberate hand edit. Cost: one new runtime dependency (`pydantic`, already present transitively via `pydantic-settings`). This is roughly what small ingestion services do.

**Option C — Contract-as-schema plus a live canary.** Do not record response bodies at all. Record the response *shape* (a JSON Schema or a pydantic model dump) and run a scheduled job that fetches the vendor live and validates it against that shape. Trade-off: this is the only option that can actually detect vendor drift, because the other two only ever see the recording. It costs a network-touching scheduled job and its own dead-man's-switch. This is what the schema-drift tooling market exists to sell (https://dev.to/qa-leaders/your-api-tests-are-lying-to-you-the-schema-drift-problem-nobody-talks-about-4h86).

**Option D — Property-based invariants only.** Hypothesis generates bar sequences and asserts invariants: contiguity, monotonic timestamps, expected count, and that computing over a window twice gives the same number. Trade-off: catches classes of bug that goldens miss, but cannot catch a wrong-but-consistent value, which is exactly the US-006 defect.

**Recommendation: Option B for the offline harness, plus Option C's canary as one story.** B costs almost nothing new and matches the existing test idiom, so the harness will not be fought by later stories. C is the only mechanism that satisfies the PRD's stated intent for guarantee 2, and without it the "vendor contract" story ships a test that can never fail for the reason it was written.

---

## Edge cases and gotchas

**The unstable period is process-global mutable state.** `TA_SetUnstablePeriod` "must be initialized from a single thread" and the setting "follows the function wherever it runs" (https://ta-lib.org/api/?h=unstable). One test that sets it changes every later test in the same process. Under random test ordering or `pytest-xdist`, that reproduces "same market, different score" *inside the determinism suite*. If TA-Lib enters this repo, an autouse fixture that asserts the unstable period is at its default is a required part of the harness, not a nicety.

**Pinning `(bars, window)` is not enough; you must pin the slice length.** Because recursive functions converge rather than snap to a value (https://ta-lib.org/api/unstable-period/), an indicator computed over the last 500 bars and the same indicator computed over the last 5000 bars differ at the *final* bar, not just early ones. The prior system's bug was "whatever `ohlcv_cache` currently holds, which grows forever from a 500-bar seed" — a golden file that fixes the bars but lets production pass a growing slice still permits that bug. The contract has to be "exactly N bars, most recent first," asserted at the call site.

**Pydantic's defaults will not catch a reshape.** `extra` defaults to `ignore`, so a vendor renaming `role` to `roles` produces a model where the field is simply absent or default-valued rather than an error (https://pydantic.dev/docs/validation/latest/concepts/models/). Separately, OKX returns every candle field as a string; a lax `float` field accepts `"79111.8"` happily, so a vendor switching to a number, or to a null, may also pass. Both `extra='forbid'` and strict typing are needed, and neither is on by default.

**Regenerating a golden is how a bug gets blessed.** `--force-regen` rewrites the baseline (https://pytest-regressions.readthedocs.io/en/latest/overview.html). Snapshots that change often "train you to accept changes blindly," and a snapshot "does not explain why output is correct" — the reviewed baseline is the entire oracle (https://qajobfit.com/resources/snapshot-testing-guide). US-006 is the proof: 6/6 criteria passed, verified by a second vendor, storing a Hong Kong day close. A golden generated by the code under test would have locked that in permanently. At least one golden value must come from arithmetic done outside this codebase.

**OKX's own limits make "fetch N bars" a two-endpoint problem.** Live candles cap at 300 per request with roughly 1440 available; history candles cap at 100 (https://github.com/ccxt/ccxt/issues/20756). Any window longer than 300 bars is inherently a paginated walk, and any window longer than about 1440 crosses an endpoint boundary with a different limit. The mid-walk failure this PRD is about is not hypothetical for windows the dashboard will plausibly want.

**Gap-filling is the failure, not the fix.** Freqtrade's fillup turned 39 candles into 124 and reported it as a 217.95 percent improvement (https://github.com/freqtrade/freqtrade/issues/9751). Anything in this harness that interpolates, forward-fills, or pads a short series re-creates the exact hazard R9 named.

**A cassette-missing test that skips is indistinguishable from a passing one.** Already recorded in our own lessons: a suite printing "31 passed, 4 skipped" cleared a gate while the four tests proving the requirement never ran. `pytest-recording` defaults to record mode `none` and blocks the network (https://github.com/kiwicom/pytest-recording), which is correct, but the fixture must raise rather than skip when a cassette is absent.

**UNVERIFIED:** numpy's `isclose` defaults are `rtol=1e-5, atol=1e-8`. The pytest-regressions docs say defaults are used when `default_tolerance` is omitted but do not restate the numbers. At `rtol=1e-5`, the 0.35 percent gap between OKX `1D` and `1Dutc` would still be caught; a hand-set loose `atol` would hide it.

---

## Services and keys this PRD needs

| Service | Why | Env var | Provisioned? |
|---|---|---|---|
| Healthchecks.io | A second check for the live vendor-contract canary, if Option C's canary ships. The canary is only useful if its silence is noticed, which is the failure mode the existing dead-man's-switch exists for. | `HEALTHCHECK_URL_CONTRACT_CANARY` (new; existing PRD-001 var is separate) | Account yes, this check no |

No new vendor, no new key, no new paid tier. OKX public market data is unauthenticated.

---

## Open questions for the human

| # | Question | My committed hypothesis | What breaks if I am wrong |
|---|---|---|---|
| 1 | What exactly does "deterministic" bind? The pair `(bars, window)`, or `(last_n_bars, window)` with `n` fixed in the registry? | **`(last_n_bars, window)` with `n` declared per indicator in `registry.yaml` and asserted at the call site.** Because TA-Lib's recursive functions converge rather than settle, pinning only the window lets a growing cache change the answer. | Goldens pass forever while production drifts, which is precisely the prior system's bug surviving the harness built to kill it. |
| 2 | Does PRD-002 add TA-Lib, or harden without it? There are currently zero indicators and no numeric dependency in `pyproject.toml`. | **Add TA-Lib now, with one trivial indicator as the pinning subject.** A determinism harness validated only against a pure-Python function proves nothing about the engine that will compute everything later, and the unstable-period global is a TA-Lib-specific hazard the harness must own. | If deferred, story 1 of PRD-003 discovers the global-state problem and the harness gets rewritten anyway. If added and rejected as scope creep, we carry an unused dependency. |
| 3 | Is a scheduled network-touching test in scope, or does "no new vendors" also mean "no new jobs"? | **In scope as one story.** Cassettes cannot detect drift; only a live fetch can. One daily job validating the live OKX response against the committed shape. | Guarantee 2 ships as a test that cannot fail for its stated reason. Four vendors broke in nine months on the prior system; the harness would have caught none of them. |
| 4 | Does partial-failure integrity require a schema change? The brief forbids one "unless a guarantee genuinely requires one." | **No column change; carry bar count and contiguity in the fetch result type, and refuse to persist an incomplete window at all.** An incomplete series becomes `Unavailable`, which `datapoints` already represents. | If the dashboard later needs to show "computed over 480 of 500 expected bars," that is a column, and retrofitting it costs a migration. |
| 5 | New test dependencies: `pydantic` explicit, plus VCR, or stay on `httpx.MockTransport`? | **Add `pydantic` explicitly; stay on `MockTransport`; skip `pytest-regressions`, pandas and numpy.** The existing fetcher test already does cassette-shaped work in 15 lines with zero new deps. | If the vendor surface grows past three or four endpoints, hand-written transports get unwieldy and VCR would have been cheaper. |
| 6 | Golden comparison: exact float equality, or a tolerance? | **Exact equality, with the golden stored as the shortest round-trippable repr.** A tolerance is a place to hide a real divergence, and the failure we are guarding against (0.35 percent) is enormous. | Cross-platform or TA-Lib-version float differences turn into flaky failures on CI versus the Windows dev machine. |

---

## Blind spots

**1. The harness will be validated against itself.** Every golden file in a first implementation is produced by running the code under test and saving the output. Such a file cannot fail on the day it is written and encodes whatever the code did, correct or not. US-006 already demonstrated that a wrong value survives six passing criteria and a second-vendor cross-check. At least one golden in this PRD must be computed by hand or copied from a source outside this repository, and the story that produces it must show the arithmetic in its evidence directory. Without that, PRD-002 ships twenty indicators' worth of confidence built on zero independent verification.

**2. The cassette becomes the specification, and it inherits our mistakes.** Once a recorded OKX response is committed, every later indicator story will be written against it, and no agent will re-read the vendor documentation. If the cassette is recorded from a slightly wrong request, the error propagates to every indicator built afterwards and is invisible because everything agrees. This is not speculative: PRD-001 recorded `bar=1D` and produced a Hong Kong day close. The cassette-recording story needs its own criterion asserting the *request* matches the registry entry, not just that the response parses.

**3. Determinism and freshness are in direct conflict, and only one of them is being specified.** Pinning "exactly the last 500 bars" makes an indicator reproducible. It also means the value changes every time a new bar closes, and that two runs eleven minutes apart legitimately produce different numbers over an identically-named window. The harness will be asked to prove "same bars, same number," which is trivially true, while the question the dashboard actually raises is "why did this move when nothing happened." If the golden fixture uses a frozen bar set and production uses a rolling one, the test suite is green and the product still exhibits the symptom the prior post-mortem named. Somebody needs to decide whether a stored datapoint records which bar range produced it, and that decision has schema consequences the brief currently rules out.

---

## Sources

- https://ta-lib.org/api/?h=unstable
- https://ta-lib.org/api/unstable-period/
- https://ta-lib.org/functions/
- https://github.com/TA-Lib/ta-lib-python/issues/479
- https://pypi.org/project/TA-Lib/
- https://pypi.org/project/pandas-ta-classic/
- https://pydantic.dev/docs/validation/latest/concepts/models/
- https://github.com/ccxt/ccxt/issues/20756
- https://github.com/freqtrade/freqtrade/issues/9751
- https://vcrpy.readthedocs.io/en/latest/installation.html
- https://github.com/kiwicom/pytest-recording
- https://pytest-regressions.readthedocs.io/en/latest/api.html
- https://pytest-regressions.readthedocs.io/en/latest/overview.html
- https://dev.to/qa-leaders/your-api-tests-are-lying-to-you-the-schema-drift-problem-nobody-talks-about-4h86
- https://qajobfit.com/resources/snapshot-testing-guide
- https://www.okx.com/docs-v5/en/
