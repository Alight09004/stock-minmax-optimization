"""Independent Streamlit benchmark page. Shared shell may call render_benchmark_view()."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from benchmark.benchmark import (TARGET_SIZES, discover_algorithms, load_dataset,
                                 load_results, run_benchmark)


def render_benchmark_view():
    st.title("Min–Max Benchmark Laboratory")
    st.write("Historical stock prices · Baseline versus Pairwise · Reproducible algorithm analysis")
    st.caption("Only real callable measurements are displayed. Data preparation and file loading are outside algorithm timers.")
    _, pairwise_status = discover_algorithms()
    if pairwise_status.startswith("unavailable"):
        st.warning(f"Pairwise pending — {pairwise_status}. Baseline experiments remain available.")

    default_data = ROOT / "datasets/generated/benchmark_prices.csv"
    if not default_data.exists():
        default_data = ROOT / "datasets/sample_stock.csv"
    with st.expander("Experiment inputs", expanded=True):
        data_path = st.text_input("Prepared CSV", value=str(default_data))
        try:
            metadata = json.loads(Path(data_path).with_suffix(".metadata.json").read_text(encoding="utf-8"))
            count = metadata["record_count"]
            if type(count) is not int or not 1 <= count <= 1_000_000:
                raise ValueError("record_count must be in 1..1,000,000")
            st.write(f"Source: {metadata['dataset']} · {count:,} prepared records · {metadata['selection']['price_column']} prices")
            st.caption(f"{metadata['series_kind']}. {metadata['ordering']}")
            with st.expander("Dataset provenance and tickers"):
                st.json(metadata)
            sizes = sorted(set([n for n in TARGET_SIZES if n <= count] + [count]))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            metadata, sizes = None, [1000]
            st.error(f"Prepared data is unavailable or invalid: {exc}. Run scripts/prepare_dataset.py first.")
        size = st.selectbox("Input size", sizes, format_func=lambda n: f"{n:,} records")
        repetitions = st.slider("Measurement repetitions", min_value=3, max_value=15, value=7, step=2)
        if st.button("Run benchmark", type="primary", disabled=metadata is None):
            try:
                with st.spinner("Validating provenance, then measuring real algorithms…"):
                    values, provenance = load_dataset(data_path, max_records=size, prefix_sizes=[size])
                    st.session_state["benchmark_result"] = run_benchmark(
                        values, sizes=[size], repetitions=repetitions, warmups=2,
                        provenance=provenance, max_seconds=60)
            except (OSError, ValueError, TypeError, KeyError, TimeoutError) as exc:
                st.error(f"Benchmark failed: {exc}")

    with st.expander("Load a saved experiment"):
        result_path = st.text_input("Result JSON", value=str(ROOT / "results/generated/baseline_benchmark.json"))
        if st.button("Load results"):
            try:
                if Path(result_path).stat().st_size > 10 * 1024 * 1024:
                    raise ValueError("Result file exceeds the 10 MiB dashboard limit")
                st.session_state["benchmark_result"] = load_results(result_path)
            except (OSError, ValueError, TypeError, KeyError) as exc:
                st.error(f"Cannot load results: {exc}")

    result = st.session_state.get("benchmark_result")
    if not result:
        st.info("Run a benchmark or load an exported JSON to inspect measured results.")
        st.write("Theory: Baseline uses 2(n−1) comparisons; optimized Pairwise targets ⌈3n/2⌉−2 for n ≥ 2.")
        return

    st.header("Measured results")
    st.caption(f"Experiment: {result['created_utc']} · {result['timing_mode']}")
    st.info("Instrumented timing includes input validation and comparison counting. No uninstrumented timing is available.")
    if not any("pairwise" in case["algorithms"] for case in result["cases"]):
        st.warning("No measured Pairwise result in this experiment. Speedup is unavailable; theoretical counts are projections only.")
    selected = st.selectbox("Result size", [case["n"] for case in result["cases"]],
                            format_func=lambda n: f"n = {n:,}")
    case = next(case for case in result["cases"] if case["n"] == selected)
    summary = case["analysis"]
    baseline = summary["algorithms"].get("baseline")
    if baseline:
        left, right = st.columns(2)
        left.metric("Baseline minimum", f"{baseline['minimum']:.8g}")
        right.metric("Baseline maximum", f"{baseline['maximum']:.8g}")
    rows = [{"Algorithm": name, "Comparisons (measured)": stats["comparison_count"],
             "Comparisons (theory)": stats["theoretical_comparison_count"],
             "Count difference": stats["comparison_delta"],
             "Median (ms)": stats["median_ns"] / 1e6, "IQR (ms)": stats["iqr_ns"] / 1e6,
             "Repetitions": stats["sample_count"]}
            for name, stats in summary["algorithms"].items()]
    frame = pd.DataFrame(rows).set_index("Algorithm")
    st.dataframe(frame, width="stretch")
    st.subheader("Measured execution time")
    st.bar_chart(frame[["Median (ms)"]], color="#2463a0")
    st.subheader("Comparison counts: evidence and theory")
    st.bar_chart(frame[["Comparisons (measured)", "Comparisons (theory)"]])
    st.caption(f"Pairwise theoretical projection at n={selected:,}: {summary['theoretical_pairwise_comparisons']:,} comparisons. This is not a measurement.")
    if summary["empirical_speedup"] is not None:
        st.write(f"Empirical speedup (Baseline / Pairwise): {summary['empirical_speedup']:.3f}×")
        if summary["measured_comparison_reduction_pct"] is not None:
            st.write(f"Measured comparison reduction: {summary['measured_comparison_reduction_pct']:.3f}%")
    else:
        st.write("Empirical speedup: unavailable.")
    st.caption("Fewer comparisons do not guarantee a proportional reduction in execution time.")
    st.subheader("Scaling across measured sizes")
    scaling = [{"n": item["n"], **{name: stats["median_ns"] / 1e6
               for name, stats in item["analysis"]["algorithms"].items()}} for item in result["cases"]]
    st.line_chart(pd.DataFrame(scaling).set_index("n"), y_label="Median (ms)", x_label="Input records")
    with st.expander("Selected prefix provenance, environment and raw samples"):
        st.json({"prefix": case.get("prefix_provenance"), "dataset": result["dataset"],
                 "environment": result["environment"], "method": result["method"],
                 "raw_samples": case["algorithms"], "omitted_sizes": result["omitted_sizes"]})
    st.download_button("Download experiment JSON", json.dumps(result, indent=2, allow_nan=False),
                       file_name="minmax_experiment.json", mime="application/json")


if __name__ == "__main__":
    st.set_page_config(page_title="Min–Max Benchmark Laboratory", layout="wide")
    render_benchmark_view()
