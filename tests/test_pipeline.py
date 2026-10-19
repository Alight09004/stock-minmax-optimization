"""Fixtures are artificial parser test inputs, never official market results."""

import csv
import json
from pathlib import Path

import pytest

from algorithms.baseline import baseline_min_max
from benchmark.analysis import analyze_case, theoretical_comparisons, timing_statistics
from benchmark.benchmark import discover_algorithms, load_dataset, load_results, run_benchmark
from scripts.prepare_dataset import OUTPUT_COLUMNS, SOURCE_COLUMNS, file_sha256, prepare_dataset


@pytest.fixture
def archive(tmp_path):
    stocks = tmp_path / "datasets/archive/Stocks"
    stocks.mkdir(parents=True)
    (tmp_path / "datasets/archive/ETFs").mkdir()
    text = ",".join(SOURCE_COLUMNS) + "\n"
    # Deliberately unsorted; all OHLC values checked, not just selected Close.
    text += "2020-01-03,3,4,2,3,100,0\n2020-01-01,1,2,0,1,100,0\n"
    text += "2020-01-01,1,2,0,1,100,0\ninvalid,1,2,0,1,100,0\n"
    text += "2020-01-04,nan,2,0,1,100,0\n2020-01-05,x,2,0,1,100,0\nshort,row\n"
    (stocks / "a.us.txt").write_text(text, encoding="utf-8")
    (stocks / "empty.us.txt").write_text("", encoding="utf-8")
    (stocks / "bad.us.txt").write_text("wrong,header\n", encoding="utf-8")
    (stocks / "broken.us.txt").write_text(",".join(SOURCE_COLUMNS) + '\n"unterminated', encoding="utf-8")
    # Poisoned duplicate tree must never be discovered.
    duplicate = tmp_path / "datasets/archive/Data/Stocks"
    duplicate.mkdir(parents=True)
    (duplicate / "fake.us.txt").write_text(text, encoding="utf-8")
    return tmp_path


def test_preparation_rejections_order_and_provenance(archive):
    output = archive / "datasets/generated/test.csv"
    metadata = prepare_dataset(output, root=archive, limit=100)
    rows = list(csv.DictReader(output.open(encoding="utf-8", newline="")))
    assert [row["date"] for row in rows] == ["2020-01-01", "2020-01-03"]
    assert all(row["ticker"] == "a.us" for row in rows)
    assert metadata["rejected_total"] == 8
    assert metadata["rejected"]["empty_file"] == 1
    assert metadata["rejected"]["duplicate_ticker_date"] == 1
    assert metadata["rejected"]["unreadable_file:Error"] == 1
    assert not any("/Data/" in source["path"] for source in metadata["sources"])
    values, provenance = load_dataset(output, prefix_sizes=[1, 2])
    assert values == (1.0, 3.0)
    assert provenance["prefixes"]["1"]["ticker_counts"] == {"Stocks/a.us": 1}
    # Hash disagreement is detected before running an algorithm.
    with output.open("a", encoding="utf-8") as handle:
        handle.write("tampered\n")
    with pytest.raises(ValueError, match="checksum"):
        load_dataset(output)


def test_selection_filter_limit_and_raw_safety(archive):
    raw = archive / "datasets/archive/Stocks/a.us.txt"
    original = raw.read_bytes()
    output = archive / "datasets/generated/filtered.csv"
    metadata = prepare_dataset(output, root=archive, tickers=["a.us"], start="2020-01-02",
                               end="2020-01-03", price_column="High", limit=1)
    assert metadata["record_count"] == 1
    assert load_dataset(output)[0] == (4.0,)
    assert raw.read_bytes() == original
    with pytest.raises(ValueError, match="outside raw"):
        prepare_dataset(raw, root=archive)
    with pytest.raises(ValueError, match="Tickers not found"):
        prepare_dataset(output, root=archive, tickers=["missing"])
    with pytest.raises(ValueError, match="No valid records"):
        prepare_dataset(output, root=archive, start="2030-01-01")


def test_statistics_and_theory():
    assert timing_statistics([10, 20, 30, 40]) == {
        "median_ns": 25.0, "q1_ns": 17.5, "q3_ns": 32.5, "iqr_ns": 15.0, "sample_count": 4}
    assert timing_statistics([7])["iqr_ns"] == 0
    assert [theoretical_comparisons("pairwise", n) for n in range(1, 7)] == [0, 1, 3, 4, 6, 7]
    case = {"n": 4, "algorithms": {
        "baseline": {"samples_ns": [100, 200, 300], "comparison_count": 6, "minimum": 1, "maximum": 4},
        "pairwise": {"samples_ns": [50, 100, 150], "comparison_count": 4, "minimum": 1, "maximum": 4}}}
    summary = analyze_case(case)
    assert summary["empirical_speedup"] == 2
    assert summary["measured_comparison_reduction_pct"] == pytest.approx(100 / 3)
    del case["algorithms"]["pairwise"]
    assert analyze_case(case)["empirical_speedup"] is None
    assert analyze_case(case)["measured_comparison_reduction_pct"] is None
    for samples in ([], [0], [-1], [float("nan")]):
        with pytest.raises(ValueError):
            timing_statistics(samples)


def test_benchmark_real_baseline_and_export_loading(tmp_path):
    values = tuple(range(17))
    result = run_benchmark(values, sizes=[10, 1000], repetitions=3, warmups=1,
                           algorithms={"baseline": baseline_min_max})
    assert result["omitted_sizes"] == [1000]
    assert [case["n"] for case in result["cases"]] == [10, 17]
    assert result["uninstrumented_timing_available"] is False
    for case in result["cases"]:
        stats = case["analysis"]["algorithms"]["baseline"]
        assert stats["comparison_count"] == 2 * (case["n"] - 1)
        assert stats["comparison_delta"] == 0
        assert stats["sample_count"] == 3
        assert case["analysis"]["empirical_speedup"] is None
    path = tmp_path / "results.json"
    path.write_text(json.dumps(result), encoding="utf-8")
    assert load_results(path)["cases"] == result["cases"]


def test_registry_order_balancing_and_correctness():
    calls = []

    def first(data):
        assert type(data) is tuple
        calls.append("first")
        return baseline_min_max(data)

    def second(data):
        calls.append("second")
        return baseline_min_max(data)

    result = run_benchmark([3, 1, 2], sizes=[3], repetitions=4, warmups=1,
                           algorithms={"first": first, "second": second})
    assert result["cases"][0]["execution_orders"] == [["first", "second"], ["second", "first"]] * 2
    assert calls == ["first", "second", "first", "second", "second", "first",
                     "first", "second", "second", "first"]
    with pytest.raises(ValueError, match="correctness"):
        run_benchmark([1, 2], sizes=[2], repetitions=3, warmups=1,
                      algorithms={"bad": lambda data: (0, 0, 2)})
    with pytest.raises(ValueError, match="differs"):
        run_benchmark([1, 2], sizes=[2], repetitions=3, warmups=1,
                      algorithms={"baseline": lambda data: (1, 2, 0)})


def test_discovery_and_invalid_inputs():
    algorithms, status = discover_algorithms()
    assert algorithms["baseline"] is baseline_min_max
    assert status
    with pytest.raises(ValueError):
        run_benchmark([], sizes=[1])
    with pytest.raises(ValueError):
        run_benchmark([float("nan")], sizes=[1])
    with pytest.raises(TypeError):
        run_benchmark([True], sizes=[1])


@pytest.mark.parametrize("relative", ["datasets/sample_stock.csv", "datasets/generated/benchmark_prices.csv",
                                      "datasets/generated/etf_validation.csv"])
def test_real_prepared_records_match_raw_source(relative):
    root = Path(__file__).resolve().parents[1]
    sample = root / relative
    raw_root = root / "datasets/archive/Stocks"
    if not raw_root.exists() or not sample.exists():
        pytest.skip("Local Kaggle archive or generated dataset is not installed")
    metadata = json.loads(sample.with_suffix(".metadata.json").read_text(encoding="utf-8"))
    assert file_sha256(sample) == metadata["csv_sha256"]
    source_hashes = {item["path"]: item["sha256"] for item in metadata["sources"]}
    source = last_date = None
    seen_sources, count = set(), 0
    with sample.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert tuple(reader.fieldnames) == OUTPUT_COLUMNS
        for row in reader:
            if row["source_file"] != source:
                source = row["source_file"]
                assert source not in seen_sources and "/Data/" not in source
                seen_sources.add(source)
                assert file_sha256(root / source) == source_hashes[source]
                with (root / source).open(encoding="utf-8", newline="") as raw:
                    lines = list(csv.reader(raw))
                last_date = None
            original = lines[int(row["source_row"]) - 1]
            assert original[0] == row["date"]
            assert float(original[SOURCE_COLUMNS.index(row["price_column"])]) == float(row["price"])
            assert Path(source).stem == row["ticker"]
            assert last_date is None or last_date < row["date"]
            last_date = row["date"]
            count += 1
    assert count == metadata["record_count"] > 0
