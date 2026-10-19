# Experiment Report — Thành viên 1

## 1. Phạm vi và câu hỏi nghiên cứu

Đánh giá số phép so sánh và thời gian của Baseline Min-Max trên giá lịch sử
thực. Kiểm tra count có khớp 2(n−1), và runtime có xu hướng tuyến tính theo n.
So sánh thực nghiệm với Pairwise chỉ được thực hiện khi callable thật của
Thành viên 2 tồn tại và vượt correctness checks.

**Trạng thái Pairwise: PENDING — chưa định nghĩa `pairwise_min_max`.** Không có
thời gian, speedup hay phần trăm giảm so sánh thực nghiệm của Pairwise trong
báo cáo này. Công thức Pairwise được trình bày như lý thuyết, không phải số đo.

## 2. Dataset và provenance

- Tên: Huge Stock Market Dataset.
- Nguồn: <https://www.kaggle.com/datasets/borismarjanovic/price-volume-data-for-all-us-stocks-etfs>.
- Bản làm việc: local archive `datasets/archive/`; chưa xác thực upstream
  version/checksum trực tiếp với Kaggle.
- Canonical inputs: `Stocks/` và `ETFs/`; tuyệt đối không đọc cây trùng `Data/`.
- Dữ liệu gốc là TXT chứa CSV: Date, Open, High, Low, Close, Volume, OpenInt.
- Giữ nguyên mọi raw file, bao gồm file rỗng và hai cây dữ liệu trùng.

### 2.1. Quy tắc preparation

Dùng `scripts/prepare_dataset.py`, đọc từng file theo thứ tự asset yêu cầu
(mặc định Stocks rồi ETFs), filename tăng dần, và ngày tăng dần trong file.
Chỉ giữ cột giá được chọn, nhưng kiểm tra cả bốn OHLC: parse số được, hữu hạn,
không âm. Parse ngày hợp lệ; duplicate ticker/date bị từ chối, giữ dòng hợp lệ
đầu tiên. Filter ngày inclusive. File lỗi schema, rỗng, encoding hoặc CSV parser
được báo cáo, không giả lập dữ liệu thay thế. Không kiểm định thống kê chất
lượng giá hoặc tự điều chỉnh corporate actions.

Mỗi CSV giữ ticker, asset_type, date, price_column, source_file và source_row.
Metadata lưu lựa chọn, số dòng, danh sách ticker, date coverage, SHA-256 raw
sources và CSV kết quả. JSONL lưu lý do từ chối kèm vị trí nguồn. Rejection
count chỉ áp dụng cho những file đã xét, không phải toàn archive.

Memory preparation giới hạn theo một ticker file; không nạp toàn archive vào
RAM. Benchmark giữ tối đa một triệu float và tuple tiền tố; không tuyên bố
toàn pipeline có auxiliary space O(1).

### 2.2. Dữ liệu đã thực sự tạo và kiểm tra

| Artifact | Số quan sát | Ticker | Khoảng ngày | Cột |
|---|---:|---:|---|---|
| `datasets/sample_stock.csv` | 240 | 2: AAPL, MSFT; 120 mỗi ticker | 2016-01-04 → 2016-06-23 | Close |
| `datasets/generated/benchmark_prices.csv` | 1.000.000 | 460 | 1970-01-02 → 2017-11-10 | Close |
| `datasets/generated/etf_validation.csv` | 100 | 1: AGG (ETF) | 2010-01-04 → 2010-05-26 | Open |

Sample chọn cửa sổ 2016-01-01 → 2017-12-31, rồi lấy 120 quan sát đầu mỗi ticker.
Benchmark chọn tiền tố một triệu dòng từ `Stocks/a.us` đến `Stocks/arlp.us`.
Đã xét 463 source files, dùng 460 file có dữ liệu; ba file rỗng được bỏ qua:
`accp.us.txt`, `amrh.us.txt`, `amrhw.us.txt`. Không gặp lý do từ chối khác trong
những file đã xét. Limit đạt trước khi tới ETFs; do đó dataset đo lần này chỉ
gồm Stocks, dù pipeline hỗ trợ cả ETFs.

SHA-256 CSV benchmark:

```text
2e6fb2cc4f39c0fb0554548f2d0f531b81059c3bec1927e3497e357538a13cbc
```

SHA-256 CSV sample:

```text
2a4cb7ca10cea902cef45e31c5eb6b28416aa7b15d21fb4e701cfa3d61154fbc
```

Test đối chiếu từng dòng của sample, dataset một triệu dòng và mẫu ETF với raw
`source_row`, ticker, ngày và giá gốc; đồng thời kiểm tra SHA-256 từng nguồn đã
dùng và ngày tăng nghiêm ngặt trong mỗi ticker. Không tạo giá ngẫu nhiên hoặc
nhân bản quan sát để đạt kích thước. Test fixtures nhân tạo chỉ dành cho parser
và thống kê, không xuất hiện trong kết quả chính thức.

**Diễn giải:** đây là dãy tổng hợp giá lịch sử từ nhiều ticker, không phải
history của một cổ phiếu, không sắp xếp ngày toàn thị trường. Giá nhỏ/lớn nhất
giữa các mã khác nhau chỉ là extrema trên input phục vụ bài toán thuật toán,
không phải chỉ số biến động, lợi suất hoặc khuyến nghị đầu tư.

## 3. Phương pháp benchmark

1. Load và xác minh hash CSV/metadata trước khi đo.
2. Chọn tiền tố n từ cùng một dataset; tạo tuple immutable ngoài timer.
3. Tính oracle bằng built-in min/max ngoài timer.
4. Warm-up hai lần cho mỗi algorithm/size.
5. Đo bảy lần với `time.perf_counter_ns()`. Khi có nhiều callable, xoay thứ tự
   mỗi repetition để cân bằng vị trí (chênh tối đa một lần).
6. Chỉ vùng gọi thuật toán nằm trong timer. Function Baseline tự validation
   và cập nhật counter, nên **instrumented timing bao gồm hai chi phí này**.
   Chưa có uninstrumented measurement để đối chứng.
7. Sau từng lời gọi, kiểm tra extrema, kiểu tuple/count, count ổn định và count
   so với công thức. Không export chính thức nếu correctness thất bại.
8. Median của bảy samples; Q1/Q3 dùng `statistics.quantiles(method='inclusive')`,
   IQR=Q3−Q1. IQR là độ phân tán, không phải confidence interval.
9. Export JSON chứa samples thô, order, thống kê, environment và provenance.

Giới hạn cấu hình: tối đa 1.000.000 records, 31 repetitions, 5 warmups; lần đo
này có budget 60 giây, kiểm tra giữa các lời gọi, không phải hard preemption
một function bị treo. Targets thiếu dữ liệu sẽ được báo omitted và thêm size
thực sự có. Lần này không omitted target nào.

Một pilot đã chạy đồng thời với tests để kiểm tra pipeline. **Bảng dưới dùng
lần chạy lại riêng sau khi tests hoàn tất**, không dùng timing pilot bị cạnh
tranh CPU với test suite. Chưa kiểm soát được toàn bộ background processes.

## 4. Môi trường thực nghiệm

| Thành phần | Giá trị ghi trong output |
|---|---|
| Python | CPython 3.14.8, 64-bit, MSC v.1944 |
| OS | Windows-11-10.0.26300-SP0 |
| CPU | AMD64 Family 25 Model 117 Stepping 2, AuthenticAMD |
| Logical CPUs | 16 |
| pandas / Streamlit / pytest | 3.0.6 / 1.66.0 / 9.1.1 |
| Interpreter | `.venv/Scripts/python.exe` |
| Git HEAD | `5781e47a3496b6f29873b953bac7393a373b683a`; implementation changes chưa commit |
| Timestamp output (UTC, clock máy chạy) | 2026-10-19T17:00:27.920541+00:00 |

Hash source Baseline được lưu vì Git HEAD chưa bao gồm implementation mới:

```text
3e0be0a691dcd7d8804902d9e93eba2158af22970340466c14ff1d0e7fc8585d
```

## 5. Kết quả thực nghiệm Baseline

Nguồn: `results/generated/baseline_benchmark.json`, lần chạy riêng nêu trên.
Đơn vị thời gian đã chuyển từ ns sang ms, không điền giá trị ước lượng.

| n | Ticker trong tiền tố | Minimum | Maximum | Count đo | 2(n−1) | Median (ms) | IQR (ms) |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1.000 | 1 | 7.3238 | 107.32 | 1.998 | 1.998 | 0.1169 | 0.00305 |
| 10.000 | 2 | 1.2528 | 107.32 | 19.998 | 19.998 | 1.0921 | 0.05540 |
| 100.000 | 34 | 0.23051 | 1196.36 | 199.998 | 199.998 | 11.3072 | 0.47005 |
| 500.000 | 217 | 0.0056 | 18333.33 | 999.998 | 999.998 | 55.3956 | 1.34230 |
| 1.000.000 | 460 | 0.0056 | 127500.0 | 1.999.998 | 1.999.998 | 108.7390 | 5.08685 |

Experimental count − theoretical count = 0 cho cả năm kích thước.

## 6. Phân tích và diễn giải

Count khớp chính xác 2(n−1), độc lập với nguồn/ticker và thứ tự giá. Median từ
100.000 lên 1.000.000 records tăng khoảng 9,62 lần khi n tăng 10 lần, phù hợp
với kỳ vọng tuyến tính trên khoảng đo. Đây là bằng chứng thực nghiệm giới hạn,
không thay thế chứng minh Θ(n) hoặc chứng minh scaling cho mọi phần cứng.

IQR khác nhau theo size, cho thấy runtime không phải một hằng số tuyệt đối.
Không dùng một sample duy nhất hoặc minimum runtime làm kết luận chính.

### Pairwise — pending

Chưa có callable thật, nên **median/IQR/count đo/speedup đều chưa có**. Công
thức mục tiêu Pairwise là ceil(3n/2)−2 khi n≥2. Trên n chẵn lớn, theoretical
comparison reduction tiến gần 25%, nhưng không suy ra giảm tương ứng runtime.
Khi tích hợp, `speedup = baseline_median / pairwise_median`; chỉ tính khi cả
hai có samples hợp lệ trên cùng input và cùng phạm vi timing.

## 7. Kiểm tra và giới hạn độ tin cậy

- Lần chạy toàn suite sau cùng: `.venv\Scripts\python.exe -m pytest -q`
  → **53 passed in 9.53s**. Lần chạy riêng baseline: 40 passed. Không có lỗi
  collection từ placeholder test của Thành viên 2.
- Unit tests bao phủ n chẵn/lẻ, singleton, tăng/giảm, lặp, bằng nhau, số âm,
  invalid types, NaN/Infinity, immutable input và Python int rất lớn.
- Pipeline tests xác minh rejection paths, provenance tampering, per-row raw
  matching, count formula, order balancing và statistics trên fixtures xác định.
- Streamlit AppTest kiểm tra chạy Baseline thật, load export thật, missing data,
  missing/invalid JSON; HTTP smoke test kiểm tra health và root trả HTTP 200.
- Toàn bộ raw archive được kiểm tra content-hash manifest trước/sau quá trình
  triển khai. Protected files và shared shell không được sửa.
- CSV sample/metadata được giữ nhỏ trong repository; raw archive không có diff
  mới; dataset lớn, JSON result và rejection logs nằm trong đường dẫn ignore.
- Snapshot này không tự động cập nhật khi người dùng chạy lại benchmark. Output
  mới phải đi kèm cập nhật timestamp, tables và source hashes của báo cáo.

Threats to validity: prefix alphabetical selection bias; không có random
sampling; bất đối xứng giá giữa ticker; source history có thể đã được vendor
điều chỉnh nhưng chưa kiểm toán corporate actions; date/price validation không
chứng minh dữ liệu thị trường không sai; không đo RSS hoặc kiểm soát CPU affinity,
power governor/background workloads; chỉ một máy và một interpreter; timing
instrumentation/validation có thể làm thay đổi relative speedup; chưa pin toàn
bộ transitive dependencies; chưa có Pairwise và shared dashboard integration.

## 8. Tái lập

Các lệnh PowerShell chính xác để preparation, test, benchmark và dashboard nằm
trong [README](../README.md). Chạy benchmark riêng, sau tests, không đồng thời.
Mỗi JSON xuất ra có source/code hashes và đầy đủ samples để tính lại median/IQR.
Các phép đo mới có thể khác timing bảng này dù dùng cùng input; count và extrema
phải tái lập được chính xác.

Content-hash manifest của 17.078 raw paths trước/sau giống nhau (SHA-256 trên
danh sách đường dẫn và raw Git object hashes, không normalize line endings):

```text
dd4f2a0648e93156133dbec4e08a1c0808b51c462e82e3fa9f7fd11e4360419f
```
