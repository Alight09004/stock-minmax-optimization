"""Small deterministic tests for the read-only historical view adapter."""

from pathlib import Path

import pytest

from dashboard.stock_view import analyze_history, available_tickers, load_history


def test_canonical_history_and_extrema():
    root = Path(__file__).resolve().parents[1]
    path = root / "datasets/archive/Stocks/aapl.us.txt"
    if not path.exists():
        pytest.skip("canonical archive unavailable")
    rows = load_history(path, "Close")
    assert rows and rows == sorted(rows)
    assert rows[0][0].isoformat() == "1984-09-07"
    assert rows[0][1] == 0.42388
    stats = analyze_history(rows[:10])
    assert stats["minimum"] == min(price for _, price in rows[:10])
    assert stats["maximum"] == max(price for _, price in rows[:10])
    assert stats["comparisons"] == 13
    assert any(name == "aapl.us" for _, name, _ in available_tickers(root))


def test_prepared_sample_is_ticker_filtered():
    path = Path(__file__).resolve().parents[1] / "datasets/sample_stock.csv"
    if not path.exists():
        pytest.skip("prepared sample unavailable")
    rows = load_history(path, "Close", ticker="aapl.us")
    assert rows[0][0].isoformat() == "2016-01-04"
    assert rows[0][1] == 101.44
    assert len(rows) == 120
    assert load_history(path, "Open", ticker="aapl.us") == []


def test_missing_folder_and_invalid_rows(tmp_path):
    assert available_tickers(tmp_path) == []
    source = tmp_path / "case.csv"
    source.write_text("Date,Open,High,Low,Close,Volume,OpenInt\n"
                      "2020-01-02,2,3,1,2.5,1,0\n"
                      "2020-01-01,1,2,0,1.5,1,0\n"
                      "2020-01-01,9,9,9,9,1,0\n"
                      "bad,1,2,0,1.5,1,0\n"
                      "2020-01-03,1,2,0,NaN,1,0\n", encoding="utf-8")
    rows = load_history(source)
    assert [value for _, value in rows] == [1.5, 2.5]
    assert analyze_history(rows)["comparisons"] == 1
    with pytest.raises(ValueError):
        analyze_history([])
