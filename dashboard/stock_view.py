"""Read-only historical stock analytics, one selected ticker at a time."""

import csv
from datetime import date
import math
from pathlib import Path

from algorithms.pairwise_minmax import pairwise_min_max

ROOT = Path(__file__).resolve().parents[1]
PRICE_COLUMNS = ("Open", "High", "Low", "Close")
RAW_COLUMNS = ("Date", "Open", "High", "Low", "Close", "Volume", "OpenInt")
SAMPLE_COLUMNS = ("date", "ticker", "asset_type", "price", "price_column", "source_file", "source_row")


def available_tickers(root=ROOT):
    """List canonical source files without opening the full archive."""
    archive = Path(root) / "datasets" / "archive"
    return [(asset, path.stem, path) for asset in ("Stocks", "ETFs")
            if (archive / asset).is_dir()
            for path in sorted((archive / asset).iterdir())
            if path.is_file() and path.suffix.lower() in (".txt", ".csv")]


def load_history(path, price_column="Close", *, ticker=None):
    """Read a single raw ticker or Member 1's prepared sample; return sorted rows.

    Invalid dates/prices and duplicate dates are skipped, keeping the first valid
    observation in file order. No source files are written.
    """
    if price_column not in PRICE_COLUMNS:
        raise ValueError("price_column must be Open, High, Low or Close")
    path = Path(path)
    rows = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = tuple(reader.fieldnames or ())
        raw = fields == RAW_COLUMNS
        sample = fields == SAMPLE_COLUMNS
        if not (raw or sample):
            raise ValueError("unsupported historical CSV schema")
        for row in reader:
            if None in row or None in row.values():
                continue
            if sample and (row["price_column"] != price_column or
                           (ticker is not None and row["ticker"] != ticker)):
                continue
            try:
                day = date.fromisoformat(row["Date"] if raw else row["date"])
                price = float(row[price_column] if raw else row["price"])
            except (TypeError, ValueError, OverflowError):
                continue
            if math.isfinite(price) and price >= 0 and day not in rows:
                rows[day] = price
    return [(day, rows[day]) for day in sorted(rows)]


def analyze_history(rows):
    """Compute extrema and first dates on chronologically sorted observations."""
    if not rows:
        raise ValueError("no valid records in selected period")
    values = [float(value) for _, value in rows]
    minimum, maximum, count = pairwise_min_max(values)
    return {"minimum": minimum, "maximum": maximum, "range": maximum - minimum,
            "records": len(values), "comparisons": count,
            "minimum_dates": [day for day, value in rows if value == minimum],
            "maximum_dates": [day for day, value in rows if value == maximum]}


def render_stock_view(root=ROOT):
    """Standalone Streamlit page; the shared shell can import this function."""
    import pandas as pd
    import streamlit as st

    st.title("Historical stock price extrema")
    st.caption("Kaggle Huge Stock Market Dataset · historical playback, not live prices. "
               "Prices are source units for US-listed securities (USD assumed; files have no currency field). "
               "Extrema are not exchange price ceilings or floors.")
    tickers = available_tickers(root)
    options = [(asset, ticker, path) for asset, ticker, path in tickers]
    sample = Path(root) / "datasets" / "sample_stock.csv"
    if sample.exists():
        try:
            with sample.open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                if tuple(reader.fieldnames or ()) == SAMPLE_COLUMNS:
                    options.extend(("Prepared sample", name, sample)
                                   for name in sorted({row["ticker"] for row in reader if row.get("ticker")}))
        except (OSError, UnicodeError, csv.Error):
            pass
    if not options:
        st.error("No canonical stock files or prepared sample were found.")
        return
    chosen = st.selectbox("Ticker / source", options,
                          format_func=lambda item: f"{item[0]} / {item[1]}")
    asset, ticker, path = chosen
    column = st.selectbox("Price column", PRICE_COLUMNS, index=3)
    try:
        rows = load_history(path, column, ticker=ticker if asset == "Prepared sample" else None)
    except (OSError, ValueError, UnicodeError, csv.Error) as exc:
        st.error(f"Cannot load selected file: {exc}")
        return
    if not rows:
        st.warning("No valid rows for this column and source.")
        return
    first, last = rows[0][0], rows[-1][0]
    period = st.date_input("Historical date range", value=(first, last),
                           min_value=first, max_value=last)
    if len(period) != 2:
        st.info("Choose both start and end dates.")
        return
    start, end = period
    selected = [(day, value) for day, value in rows if start <= day <= end]
    if not selected:
        st.warning("No records in this date range.")
        return
    replay = st.checkbox("Historical replay")
    if replay:
        if len(selected) > 2000:
            st.caption("Replay is limited to the first 2,000 selected historical records.")
            selected = selected[:2000]
        shown = st.slider("Records revealed", 1, len(selected), len(selected))
        selected = selected[:shown]
    stats = analyze_history(selected)
    st.caption(f"Source: {path.relative_to(root)} · {asset}/{ticker} · "
               f"{selected[0][0]} to {selected[-1][0]} · {column} · source price units (USD assumed)")
    a, b, c, d = st.columns(4)
    a.metric("Minimum", f"{stats['minimum']:,.4f}")
    b.metric("Maximum", f"{stats['maximum']:,.4f}")
    c.metric("Range", f"{stats['range']:,.4f}")
    d.metric("Records", f"{stats['records']:,}")
    st.write("Minimum date(s):", ", ".join(map(str, stats["minimum_dates"])))
    st.write("Maximum date(s):", ", ".join(map(str, stats["maximum_dates"])))
    chart = pd.DataFrame({"date": [day for day, _ in selected],
                          "price": [value for _, value in selected]})
    chart["extremum"] = chart["price"].map(
        lambda value: "Minimum" if value == stats["minimum"] else
        ("Maximum" if value == stats["maximum"] else "Other"))
    st.vega_lite_chart(chart, {
        "layer": [
            {"mark": "line", "encoding": {"x": {"field": "date", "type": "temporal"},
                                       "y": {"field": "price", "type": "quantitative"}}},
            {"transform": [{"filter": "datum.extremum != 'Other'"}],
             "mark": {"type": "point", "filled": True, "size": 90},
             "encoding": {"x": {"field": "date", "type": "temporal"},
                          "y": {"field": "price", "type": "quantitative"},
                          "color": {"field": "extremum", "type": "nominal"},
                          "tooltip": [{"field": "date", "type": "temporal"},
                                      {"field": "price", "type": "quantitative"}]}}]},
        width="stretch")
    st.write(f"Pairwise comparisons: {stats['comparisons']:,} · O(n) time, O(1) auxiliary space · "
             "C(1)=0; C(n)=ceil(3n/2)-2 for n≥2")
    try:
        from algorithms.baseline import baseline_min_max
    except ImportError:
        st.info("Baseline implementation unavailable.")
    else:
        baseline = baseline_min_max([value for _, value in selected])
        st.write(f"Baseline comparisons: {baseline[2]:,}")
        if baseline[:2] != (stats["minimum"], stats["maximum"]):
            st.error("Baseline and Pairwise extrema disagree.")


if __name__ == "__main__":
    import streamlit as st
    st.set_page_config(page_title="Historical stock extrema", layout="wide")
    render_stock_view()
