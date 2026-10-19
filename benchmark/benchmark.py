"""Bounded, reproducible instrumented Min-Max experiments (Member 1)."""

import argparse
import collections
import csv
from datetime import date, datetime, timezone
import importlib
import inspect
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter_ns

from algorithms.baseline import baseline_min_max
from benchmark.analysis import analyze_case
from scripts.prepare_dataset import ROOT, OUTPUT_COLUMNS, file_sha256

TARGET_SIZES = (1000, 10000, 100000, 500000, 1000000)
TIMING_MODE = "instrumented end-to-end callable; validation and comparison counting included"


def discover_algorithms():
    algorithms = {"baseline": baseline_min_max}
    try:
        module = importlib.import_module("algorithms.pairwise_minmax")
        pairwise = getattr(module, "pairwise_min_max", None)
        if callable(pairwise):
            algorithms["pairwise"] = pairwise
            status = "available: real algorithms.pairwise_minmax.pairwise_min_max"
        else:
            status = "unavailable: Member 2 has not defined pairwise_min_max"
    except Exception as exc:
        status = f"unavailable: Pairwise import failed ({type(exc).__name__}: {exc})"
    return algorithms, status


def load_dataset(path, *, max_records=1_000_000, prefix_sizes=TARGET_SIZES):
    """Load prepared prices outside timing and verify the provenance sidecar hash."""
    path = Path(path).resolve()
    if not 1 <= max_records <= 1_000_000:
        raise ValueError("max_records must be between 1 and 1,000,000")
    metadata = json.loads(path.with_suffix(".metadata.json").read_text(encoding="utf-8"))
    if metadata.get("schema_version") != 1 or metadata.get("csv_sha256") != file_sha256(path):
        raise ValueError("Dataset metadata version or CSV checksum mismatch")
    prices, tickers, sources, prefixes = [], collections.Counter(), set(), {}
    date_min = date_max = None
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != OUTPUT_COLUMNS:
            raise ValueError("Prepared CSV schema mismatch")
        for row in reader:
            if len(prices) >= max_records:
                break
            day = date.fromisoformat(row["date"]).isoformat()
            value = float(row["price"])
            if not math.isfinite(value) or value < 0 or not row["ticker"]:
                raise ValueError(f"Invalid prepared record at line {reader.line_num}")
            prices.append(value)
            tickers[f'{row["asset_type"]}/{row["ticker"]}'] += 1
            sources.add(row["source_file"])
            date_min = day if date_min is None else min(date_min, day)
            date_max = day if date_max is None else max(date_max, day)
            if len(prices) in prefix_sizes:
                prefixes[str(len(prices))] = {"ticker_counts": dict(tickers), "date_min": date_min,
                                              "date_max": date_max, "source_files": sorted(sources)}
    if not prices:
        raise ValueError("Prepared dataset is empty")
    if len(prices) < max_records and metadata.get("record_count") != len(prices):
        raise ValueError("Dataset record count disagrees with metadata")
    prefixes[str(len(prices))] = {"ticker_counts": dict(tickers), "date_min": date_min,
                                 "date_max": date_max, "source_files": sorted(sources)}
    return tuple(prices), {"prepared_file": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                           "metadata": metadata, "loaded_records": len(prices), "prefixes": prefixes}


def runtime_environment(algorithms):
    from importlib.metadata import version
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    implementations = {}
    for name, function in algorithms.items():
        try:
            source = inspect.getsourcefile(function)
        except TypeError:
            source = None
        label = getattr(function, "__qualname__", type(function).__qualname__)
        implementations[name] = {"callable": f"{getattr(function, '__module__', type(function).__module__)}.{label}",
                                 "source_sha256": file_sha256(source) if source else None}
    return {"python": sys.version, "executable": sys.executable, "platform": platform.platform(),
            "processor": platform.processor(), "logical_cpus": os.cpu_count(),
            "packages": {name: version(name) for name in ("pandas", "streamlit", "pytest")},
            "git_head": commit, "implementations": implementations}


def _check_result(result, expected, name, n):
    if (type(result) is not tuple or len(result) != 3
            or type(result[0]) not in (int, float) or type(result[1]) not in (int, float)
            or any(type(value) is float and not math.isfinite(value) for value in result[:2])
            or result[:2] != expected or type(result[2]) is not int or result[2] < 0):
        raise ValueError(f"{name} violates result contract/correctness at n={n}")


def run_benchmark(values, *, sizes=TARGET_SIZES, repetitions=7, warmups=2,
                  algorithms=None, provenance=None, max_seconds=60):
    """Time real callables only. Cooperative runtime bound checked between calls.

    Tuples prevent input mutation. Correctness and analysis are outside timers.
    Rotating order balances position counts to within one repetition.
    """
    if type(values) not in (list, tuple) or not values or len(values) > 1_000_000:
        raise ValueError("Provide 1..1,000,000 prepared values")
    for value in values:
        if type(value) not in (int, float):
            raise TypeError("Benchmark values must be Python int/float")
        if type(value) is float and not math.isfinite(value):
            raise ValueError("Benchmark values must be finite")
    if not 3 <= repetitions <= 31 or not 1 <= warmups <= 5 or not 0 < max_seconds <= 300:
        raise ValueError("Use repetitions 3..31, warmups 1..5, runtime bound (0,300]s")
    sizes = sorted(set(sizes))
    if not sizes or any(type(n) is not int or not 1 <= n <= 1_000_000 for n in sizes):
        raise ValueError("Sizes must be integers in 1..1,000,000")
    discovered, pairwise_status = discover_algorithms()
    algorithms = discovered if algorithms is None else dict(algorithms)
    if not algorithms or any(not callable(fn) for fn in algorithms.values()):
        raise ValueError("Algorithm registry must contain callables")
    if "pairwise" in algorithms and "pairwise" not in discovered:
        pairwise_status = "injected callable (caller responsible for provenance); not automatic Pairwise discovery"
    if "pairwise" not in algorithms:
        pairwise_status = "not selected" if "pairwise" in discovered else pairwise_status
    available = [n for n in sizes if n <= len(values)]
    if len(values) < sizes[-1] and len(values) not in available:
        available.append(len(values))
    started = perf_counter_ns()
    cases, deadline = [], started + int(max_seconds * 1e9)

    def check_deadline():
        if perf_counter_ns() >= deadline:
            raise TimeoutError("Experiment runtime budget reached between calls; no partial official result exported")

    for n in available:
        check_deadline()
        data = tuple(values[:n])
        expected = (min(data), max(data))
        measurements = {name: {"samples_ns": []} for name in algorithms}
        names = list(algorithms)
        for _ in range(warmups):
            for name in names:
                check_deadline()
                _check_result(algorithms[name](data), expected, name, n)
        orders = []
        for repetition in range(repetitions):
            offset = repetition % len(names)
            order = names[offset:] + names[:offset]
            orders.append(order)
            for name in order:
                check_deadline()
                before = perf_counter_ns()
                result = algorithms[name](data)
                elapsed = perf_counter_ns() - before
                _check_result(result, expected, name, n)
                measured = measurements[name]
                if "comparison_count" in measured and measured["comparison_count"] != result[2]:
                    raise ValueError(f"Nondeterministic comparison count: {name}")
                measured.update(minimum=result[0], maximum=result[1], comparison_count=result[2])
                measured["samples_ns"].append(elapsed)
        case = {"n": n, "algorithms": measurements, "execution_orders": orders,
                "prefix_provenance": (provenance or {}).get("prefixes", {}).get(str(n))}
        case["analysis"] = analyze_case(case)
        for name, stats in case["analysis"]["algorithms"].items():
            if stats["comparison_delta"] not in (None, 0):
                raise ValueError(f"{name} comparison count differs from agreed theory at n={n}")
        cases.append(case)
    check_deadline()
    return {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
            "timing_mode": TIMING_MODE, "uninstrumented_timing_available": False,
            "method": {"clock": "time.perf_counter_ns", "repetitions": repetitions, "warmups": warmups,
                       "order": "cyclic rotation each repetition", "max_seconds": max_seconds,
                       "loading_included": False, "correctness_checks_included": False,
                       "quartiles": "statistics.quantiles, inclusive"},
            "requested_sizes": sizes, "omitted_sizes": [n for n in sizes if n > len(values)],
            "available_records": len(values), "pairwise_status": pairwise_status,
            "environment": runtime_environment(algorithms), "dataset": provenance,
            "cases": cases}


def save_results(result, output):
    output = Path(output).resolve()
    if not output.is_relative_to(ROOT / "results/generated") or output.suffix != ".json":
        raise ValueError("Benchmark outputs must be JSON under results/generated/")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(output)


def load_results(path):
    result = json.loads(Path(path).read_text(encoding="utf-8"))
    required = {"created_utc", "timing_mode", "dataset", "environment", "method", "omitted_sizes"}
    if (not isinstance(result, dict) or result.get("schema_version") != 1
            or not isinstance(result.get("cases"), list) or not result["cases"]
            or not required.issubset(result)):
        raise ValueError("Unsupported or empty benchmark result")
    for case in result["cases"]:
        if (not isinstance(case, dict) or type(case.get("n")) is not int
                or not 1 <= case["n"] <= 1_000_000 or not isinstance(case.get("algorithms"), dict)
                or not case["algorithms"]):
            raise ValueError("Invalid benchmark case")
        for name, measured in case["algorithms"].items():
            _check_result((measured["minimum"], measured["maximum"], measured["comparison_count"]),
                          (measured["minimum"], measured["maximum"]), name, case["n"])
        case["analysis"] = analyze_case(case)
        if any(stats["comparison_delta"] not in (None, 0) for stats in case["analysis"]["algorithms"].values()):
            raise ValueError("Loaded comparison count disagrees with theory")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "datasets/generated/benchmark_prices.csv")
    parser.add_argument("--sizes", nargs="+", type=int, default=list(TARGET_SIZES))
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--max-seconds", type=float, default=60)
    parser.add_argument("--baseline-only", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "results/generated/baseline_benchmark.json")
    args = parser.parse_args()
    try:
        values, provenance = load_dataset(args.data, prefix_sizes=args.sizes)
        algorithms = {"baseline": baseline_min_max} if args.baseline_only else None
        result = run_benchmark(values, sizes=args.sizes, repetitions=args.repetitions,
                               warmups=args.warmups, max_seconds=args.max_seconds,
                               algorithms=algorithms, provenance=provenance)
        save_results(result, args.output)
    except (OSError, ValueError, TypeError, KeyError, TimeoutError) as exc:
        parser.exit(1, f"Benchmark failed: {exc}\n")
    print(result["pairwise_status"])
    for case in result["cases"]:
        print(json.dumps(case["analysis"]))
    print(f"Exported: {args.output}")


if __name__ == "__main__":
    main()
