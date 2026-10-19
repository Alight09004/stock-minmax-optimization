"""Prepare genuine Kaggle records, one source file at a time; never edit raw data."""

import argparse
import collections
import csv
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PRICE_COLUMNS = ("Close", "Open", "High", "Low")
SOURCE_COLUMNS = ("Date", "Open", "High", "Low", "Close", "Volume", "OpenInt")
OUTPUT_COLUMNS = ("date", "ticker", "asset_type", "price", "price_column",
                  "source_file", "source_row")


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare_dataset(output, *, root=ROOT, tickers=None, assets=("Stocks", "ETFs"),
                    start=None, end=None, price_column="Close", limit=1000,
                    per_ticker_limit=None):
    """Write a bounded CSV plus provenance and rejection sidecars.

    Ordering: Stocks before ETFs (or requested asset order), filename ascending,
    then date ascending within each file. Never combines the duplicate Data tree.
    Memory is bounded by one ticker file, not the complete archive.
    """
    root, output = Path(root).resolve(), Path(output).resolve()
    archive = root / "datasets" / "archive"
    if output.is_relative_to(archive) or not output.is_relative_to(root):
        raise ValueError("output must be inside the project and outside raw archive")
    if output.suffix.lower() != ".csv":
        raise ValueError("output must have .csv extension")
    if output != root / "datasets" / "sample_stock.csv" and not output.is_relative_to(root / "datasets" / "generated"):
        raise ValueError("use datasets/generated/ or datasets/sample_stock.csv")
    if price_column not in PRICE_COLUMNS or not 1 <= limit <= 1_000_000:
        raise ValueError("invalid price column or limit (1..1,000,000)")
    if per_ticker_limit is not None and per_ticker_limit < 1:
        raise ValueError("per_ticker_limit must be positive")
    if not assets or any(asset not in ("Stocks", "ETFs") for asset in assets) or len(set(assets)) != len(assets):
        raise ValueError("assets must be distinct Stocks/ETFs entries")
    start = date.fromisoformat(start) if isinstance(start, str) else start
    end = date.fromisoformat(end) if isinstance(end, str) else end
    if start and end and start > end:
        raise ValueError("start must not exceed end")
    selected = {ticker.lower() for ticker in tickers} if tickers else None
    sources = []
    for asset in assets:
        folder = archive / asset
        if not folder.is_dir():
            raise FileNotFoundError(f"Missing canonical source directory: {folder}")
        sources.extend((asset, path) for path in sorted(folder.iterdir())
                       if path.suffix.lower() in (".txt", ".csv") and path.is_file()
                       and (selected is None or path.stem.lower() in selected))
    found = {path.stem.lower() for _, path in sources}
    if selected and selected - found:
        raise ValueError(f"Tickers not found: {sorted(selected - found)}")
    if not sources:
        raise ValueError("No source files match the selection")

    output.parent.mkdir(parents=True, exist_ok=True)
    reasons = collections.Counter()
    source_log, ticker_counts = [], collections.Counter()
    count = filtered = 0
    first_date = last_date = None
    # Temporary artifacts are on the same filesystem, then published atomically.
    with tempfile.TemporaryDirectory(dir=output.parent) as temp:
        temp = Path(temp)
        csv_path, reject_path = temp / "data.csv", temp / "rejections.jsonl"
        with csv_path.open("w", newline="", encoding="utf-8") as dest, reject_path.open("w", encoding="utf-8") as rejected:
            writer = csv.DictWriter(dest, fieldnames=OUTPUT_COLUMNS)
            writer.writeheader()

            def reject(relative, row_number, reason):
                reasons[reason] += 1
                rejected.write(json.dumps({"source_file": relative, "source_row": row_number,
                                           "reason": reason}) + "\n")

            for asset, path in sources:
                if count >= limit:
                    break
                relative = path.relative_to(root).as_posix()
                records, seen_dates = [], set()
                info = {"path": relative, "sha256": file_sha256(path),
                        "bytes": path.stat().st_size, "selected_records": 0}
                source_log.append(info)
                try:
                    with path.open(newline="", encoding="utf-8-sig") as handle:
                        reader = csv.reader(handle, strict=True)
                        header = next(reader, None)
                        if header is None:
                            reject(relative, 0, "empty_file")
                            continue
                        if tuple(header) != SOURCE_COLUMNS:
                            reject(relative, 1, "invalid_header")
                            continue
                        for row in reader:
                            number = reader.line_num
                            if len(row) != len(SOURCE_COLUMNS):
                                reject(relative, number, "column_count")
                                continue
                            try:
                                trading_date = date.fromisoformat(row[0])
                            except ValueError:
                                reject(relative, number, "invalid_date")
                                continue
                            try:
                                prices = [float(row[i]) for i in range(1, 5)]
                            except ValueError:
                                reject(relative, number, "nonnumeric_price")
                                continue
                            if any(not math.isfinite(value) or value < 0 for value in prices):
                                reject(relative, number, "nonfinite_or_negative_price")
                                continue
                            if trading_date in seen_dates:
                                reject(relative, number, "duplicate_ticker_date")
                                continue
                            seen_dates.add(trading_date)
                            if (start and trading_date < start) or (end and trading_date > end):
                                filtered += 1
                                continue
                            records.append((trading_date, number, prices[SOURCE_COLUMNS.index(price_column) - 1]))
                except (OSError, UnicodeError, csv.Error) as exc:
                    reject(relative, 0, f"unreadable_file:{type(exc).__name__}")
                    # A partially parsed malformed file is not accepted.
                    continue
                records.sort(key=lambda row: row[0])
                for trading_date, number, price in records:
                    if count >= limit or (per_ticker_limit is not None and info["selected_records"] >= per_ticker_limit):
                        break
                    writer.writerow(dict(zip(OUTPUT_COLUMNS, (
                        trading_date.isoformat(), path.stem.lower(), asset, price,
                        price_column, relative, number))))
                    count += 1
                    info["selected_records"] += 1
                    ticker_counts[f"{asset}/{path.stem.lower()}"] += 1
                    day = trading_date.isoformat()
                    first_date = day if first_date is None else min(first_date, day)
                    last_date = day if last_date is None else max(last_date, day)
        if not count:
            raise ValueError(f"No valid records selected; rejected reasons: {dict(reasons)}")
        metadata = {
            "schema_version": 1, "dataset": "Huge Stock Market Dataset",
            "source_url": "https://www.kaggle.com/datasets/borismarjanovic/price-volume-data-for-all-us-stocks-etfs",
            "source_version": "Local archive; upstream version/checksum not independently verified",
            "canonical_roots": [f"datasets/archive/{asset}" for asset in assets],
            "selection": {"tickers": sorted(selected) if selected else "all",
                          "start": start.isoformat() if start else None,
                          "end": end.isoformat() if end else None,
                          "price_column": price_column, "limit": limit,
                          "per_ticker_limit": per_ticker_limit},
            "ordering": "asset order, filename ascending, date ascending within file; prefix truncation",
            "series_kind": "aggregate historical price series across tickers" if len(ticker_counts) > 1 else "single ticker historical price series",
            "record_count": count, "requested_limit_reached": count == limit,
            "date_min": first_date, "date_max": last_date,
            "ticker_counts": dict(ticker_counts), "filtered_date_rows": filtered,
            "rejected": dict(reasons), "rejected_total": sum(reasons.values()),
            "rejection_scope": "examined source files only; file-level errors use source_row=0",
            "sources": source_log, "csv_sha256": file_sha256(csv_path),
        }
        meta_path = temp / "metadata.json"
        meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        csv_path.replace(output)
        reject_path.replace(output.with_suffix(".rejections.jsonl"))
        meta_path.replace(output.with_suffix(".metadata.json"))
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "datasets/generated/benchmark_prices.csv")
    parser.add_argument("--tickers", nargs="+", help="Filename stems, e.g. aapl.us msft.us")
    parser.add_argument("--assets", nargs="+", choices=("Stocks", "ETFs"), default=["Stocks", "ETFs"])
    parser.add_argument("--start", help="Inclusive YYYY-MM-DD")
    parser.add_argument("--end", help="Inclusive YYYY-MM-DD")
    parser.add_argument("--price-column", choices=PRICE_COLUMNS, default="Close")
    parser.add_argument("--limit", type=int, default=1000, help="Maximum real records, capped at 1,000,000")
    parser.add_argument("--per-ticker-limit", type=int)
    args = parser.parse_args()
    try:
        result = prepare_dataset(**vars(args))
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Preparation failed: {exc}\n")
    print(json.dumps({key: result[key] for key in ("record_count", "date_min", "date_max", "rejected", "series_kind")}, indent=2))


if __name__ == "__main__":
    main()
