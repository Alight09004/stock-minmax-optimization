"""Descriptive statistics, with theory kept separate from measured evidence."""

import math
from statistics import median, quantiles


def timing_statistics(samples_ns):
    if not samples_ns or any(type(value) is not int or value <= 0 for value in samples_ns):
        raise ValueError("timings must be nonempty positive integer nanoseconds")
    middle = median(samples_ns)
    q1, q3 = quantiles(samples_ns, n=4, method="inclusive")[::2] if len(samples_ns) > 1 else (middle, middle)
    return {"median_ns": middle, "q1_ns": q1, "q3_ns": q3, "iqr_ns": q3 - q1,
            "sample_count": len(samples_ns)}


def theoretical_comparisons(algorithm, n):
    if type(n) is not int or n < 1:
        raise ValueError("n must be a positive integer")
    if algorithm == "baseline":
        return 2 * (n - 1)
    if algorithm == "pairwise":
        return 0 if n == 1 else (3 * n + 1) // 2 - 2
    return None


def analyze_case(case):
    """Summarize genuine samples; absent Pairwise means absent empirical metrics."""
    algorithms = {}
    for name, measured in case["algorithms"].items():
        stats = timing_statistics(measured["samples_ns"])
        theoretical = theoretical_comparisons(name, case["n"])
        algorithms[name] = {
            **stats, "minimum": measured["minimum"], "maximum": measured["maximum"],
            "comparison_count": measured["comparison_count"],
            "theoretical_comparison_count": theoretical,
            "comparison_delta": measured["comparison_count"] - theoretical if theoretical is not None else None,
        }
    baseline, pairwise = algorithms.get("baseline"), algorithms.get("pairwise")
    reduction = speedup = None
    if baseline and pairwise:
        if baseline["comparison_count"] > 0:
            reduction = 100 * (baseline["comparison_count"] - pairwise["comparison_count"]) / baseline["comparison_count"]
        if pairwise["median_ns"] > 0 and math.isfinite(pairwise["median_ns"]):
            speedup = baseline["median_ns"] / pairwise["median_ns"]
    base_theory = theoretical_comparisons("baseline", case["n"])
    pair_theory = theoretical_comparisons("pairwise", case["n"])
    return {"n": case["n"], "algorithms": algorithms,
            "measured_comparison_reduction_pct": reduction, "empirical_speedup": speedup,
            "theoretical_pairwise_comparisons": pair_theory,
            "theoretical_comparison_reduction_pct": 100 * (base_theory - pair_theory) / base_theory if base_theory else None}
