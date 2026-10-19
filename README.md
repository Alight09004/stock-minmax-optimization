# stock-minmax-optimization
Stock Price Analytics Dashboard using Optimized Pairwise Min-Max Algorithm

## Member 1 — Baseline, real-data preparation and benchmark

This repository is a Design and Analysis of Algorithms course project. The
Member 1 pipeline runs independently. Pairwise and the shared stock dashboard
remain Member 2 integration work; no Pairwise measurement is invented when its
callable is absent.

### Setup — Windows PowerShell, repository root

Verified with CPython 3.14.8 on Windows x64. `python` on this workstation points
to 3.7.4, so use the explicit launcher and then the project's interpreter.

```powershell
py -3.14 --version
# Create only if .venv does not already exist:
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

Do not recreate an existing environment blindly; confirm its interpreter first.
Direct dependency versions are pinned; transitive dependencies are resolved by
pip and are not a complete environment lockfile.

### Raw dataset and canonical inputs

Source: [Huge Stock Market Dataset, Kaggle](https://www.kaggle.com/datasets/borismarjanovic/price-volume-data-for-all-us-stocks-etfs).
Place the downloaded archive locally as:

```text
datasets/archive/Stocks/*.txt
datasets/archive/ETFs/*.txt
```

TXT files contain CSV columns `Date,Open,High,Low,Close,Volume,OpenInt`. The local
`archive/Data/` tree is a duplicate and is never read by preparation. Do not
merge all four source directories. Local upstream dataset version and checksum
have not been independently authenticated against Kaggle.

**Git safety:** archive is ignored for new files, but its existing 17,078 files
remain tracked from earlier commits. No dataset untracking or history rewrite
is performed. `datasets/generated/`, `results/generated/`, `.venv/` and rejection
logs are ignored. Never stage raw archive changes with the implementation.

### Prepare the small, real dashboard sample

```powershell
.\.venv\Scripts\python.exe scripts/prepare_dataset.py --help
.\.venv\Scripts\python.exe scripts/prepare_dataset.py --assets Stocks --tickers aapl.us msft.us --start 2016-01-01 --end 2017-12-31 --limit 240 --per-ticker-limit 120 --output datasets/sample_stock.csv
```

The checked-in sample has 120 genuine AAPL and 120 MSFT observations, dated
2016-01-04 through 2016-06-23. It is an aggregate historical price series, not
one stock's chronological history. Dates in `--start`/`--end` are inclusive;
`--limit` is global and `--per-ticker-limit` caps each selected file.

### Prepare up to one million genuine observations

```powershell
.\.venv\Scripts\python.exe scripts/prepare_dataset.py --limit 1000000 --price-column Close --output datasets/generated/benchmark_prices.csv
```

Supported price columns: Close, Open, High, Low. `--assets Stocks ETFs` is the
default. Selection is deterministic: requested asset order, filename ascending,
then date ascending within each source file. Preparation stops at the requested
prefix; it does not fabricate or repeat observations when data is insufficient.
The default million-row prefix currently reaches its limit within Stocks, so
it contains no ETFs and is not a random or market-balanced sample.

Preparation reads one ticker file at a time, validates all four OHLC columns
as finite nonnegative numbers, validates dates, and rejects duplicate ticker/date
rows (first valid row wins). It skips empty/unreadable/malformed files. A file
with a CSV parse error is discarded even if some earlier rows parsed.

Each output has:

- `.csv`: `date,ticker,asset_type,price,price_column,source_file,source_row`.
- `.metadata.json`: selection rules, SHA-256 of examined sources/output,
  counts, ticker/date coverage and provenance.
- `.rejections.jsonl`: source file, source row and rejection reason; row 0
  denotes a file-level error. These diagnostics cover examined files only.

Only `datasets/generated/` or `datasets/sample_stock.csv` are accepted output
locations. Re-running intentionally replaces that prepared output and its
sidecars, never the source archive. Each artifact is atomically replaced, but
the three-file bundle is not a transaction: if interrupted, rerun preparation;
benchmark loading detects CSV/metadata hash mismatches.

### Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_baseline.py
.\.venv\Scripts\python.exe -m pytest -q
```

Tests cover baseline validation/counts/immutability, parser rejection paths,
statistical definitions, registry ordering/correctness, Streamlit interactions
and an HTTP server smoke test. Real-data tests compare every prepared row with
its indicated raw source row; they skip when the local archive/generated data
is absent. The protected Member 2 test file is not modified.

### Run and export a bounded experiment

Run the benchmark separately from tests or other CPU-heavy jobs.

```powershell
.\.venv\Scripts\python.exe -m benchmark.benchmark --help
.\.venv\Scripts\python.exe -m benchmark.benchmark --data datasets/generated/benchmark_prices.csv --sizes 1000 10000 100000 500000 1000000 --repetitions 7 --warmups 2 --max-seconds 60 --output results/generated/baseline_benchmark.json
```

Add `--baseline-only` to explicitly select Baseline. Otherwise the engine imports
the real `algorithms.pairwise_minmax.pairwise_min_max` only if callable. An absent
implementation is reported as unavailable; an incorrect callable fails
correctness checks rather than producing an official comparison.

The engine caps input at 1,000,000 records, repetitions at 31, and warmups at 5.
It checks a runtime budget between calls (not a hard preemption of one hung
callable). If insufficient genuine records exist, it omits oversized targets
and also measures the actual available count. All algorithms receive the same
immutable tuple, with rotating execution order. CSV parsing, correctness oracle,
analysis and export are outside `perf_counter_ns()` timers.

**Timing is instrumented:** it includes the public function's validation and
comparison-count updates. There is no uninstrumented implementation or timing
claim. JSON includes raw nanosecond samples, median, inclusive-quartile IQR,
counts versus theory, environment, source-code hash and dataset provenance.
Speedup is Baseline median / Pairwise median and is absent without both real
results. Reduced comparison count does not guarantee proportional time savings.

### Independent benchmark dashboard

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard/benchmark_view.py
```

Use **Run benchmark** for a selected size or **Load results** for the exported
JSON. The page shows source/ticker/date provenance, actual extrema, comparison
counts, median/IQR, scaling and clearly labelled theoretical Pairwise projections.
Missing data or missing Pairwise produces an actionable message, not fake values.

Minimal integration into the shared dashboard shell, when both members agree:

```python
from dashboard.benchmark_view import render_benchmark_view

# After the shared shell configures Streamlit and selects the benchmark page:
render_benchmark_view()
```

The view function does not call `set_page_config`. The independent entry point
does. `dashboard/app.py` and Member 2's stock-view implementation are untouched.

### Academic evidence

- [Baseline proof and complexity](docs/baseline_analysis.md)
- [Actual experiment report and limitations](docs/experiment_report.md)
- [Proposed team interface contract](docs/interface_contract.md)

Member 1's baseline follows the finite-input contract. The shared contract
document remains **PROPOSED — WAITING FOR TEAMMATE CONFIRMATION** until Member 2
confirms the integration. The overall two-member project is not yet complete.
