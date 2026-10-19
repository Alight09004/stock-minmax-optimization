# Hợp đồng giao diện Min-Max

**PROPOSED — WAITING FOR TEAMMATE CONFIRMATION**

Tài liệu này đề xuất hợp đồng chung cho hai thành viên. Đây chưa phải hành vi
đã triển khai hoặc được kiểm thử. Không thay đổi thuật toán Pairwise trong Phase 1.

## 1. Giao diện và kết quả

```python
baseline_min_max(arr)
pairwise_min_max(arr)
# Return: (minimum, maximum, comparison_count)
```

- Kết quả là một tuple có đúng ba phần tử.
- `minimum` và `maximum` là các giá trị cực trị của input hợp lệ.
- `comparison_count` là Python `int` không âm, đếm số phép so sánh dữ liệu
  thực sự được thực hiện để tìm cực trị.
- Với một phần tử `x`, kết quả là `(x, x, 0)`.

## 2. Input và xử lý lỗi

- Input là `list` hoặc `tuple` một chiều, không rỗng.
- Phần tử chỉ thuộc hai kiểu Python `int` và `float`; loại trừ `bool`.
- Mọi giá trị phải hữu hạn. Python `int` không bị giới hạn về độ lớn bởi hợp
  đồng này; không ép toàn bộ input sang `float` chỉ để kiểm tra tính hữu hạn.
- Tầng chuẩn bị dữ liệu chịu trách nhiệm chuyển pandas/NumPy sang định dạng
  Python được hỗ trợ; thuật toán không tự chuyển đổi chuỗi hoặc bỏ dữ liệu lỗi.

| Trường hợp | Hành vi đề xuất |
|---|---|
| `[]` hoặc `()` | Raise `ValueError` |
| `float('nan')` ở bất kỳ vị trí nào | Raise `ValueError` |
| `float('inf')` hoặc `float('-inf')` ở bất kỳ vị trí nào | Raise `ValueError` |
| `arr is None` | Raise `TypeError` |
| Phần tử `None`, `bool`, string hoặc complex | Raise `TypeError` |
| Nested list/tuple, object hoặc kiểu phần tử khác | Raise `TypeError` |
| String, dict, set, generator, ndarray hoặc container không hỗ trợ | Raise `TypeError` |

Thứ tự validation đề xuất: kiểm tra container, kiểm tra rỗng, rồi duyệt phần tử
theo thứ tự input; với từng phần tử, kiểm tra kiểu trước và tính hữu hạn sau.
Lỗi đầu tiên theo thứ tự đó quyết định loại exception. Phải kiểm tra cả phần tử
đầu tiên và trường hợp chỉ có một phần tử. Nội dung thông báo lỗi chưa được chốt.

## 3. Bất biến và cách đếm

- Không sửa input, kể cả khi phát sinh lỗi; không sort, xóa hoặc thay phần tử.
- Không dùng built-in `min()`/`max()` hoặc phép reduction tương đương để thay
  thuật toán chính.
- Chỉ đếm phép so sánh giá trị dữ liệu phục vụ tìm minimum/maximum, kể cả khi
  hai giá trị bằng nhau.
- Không tính kiểm tra kiểu, kiểm tra NaN/Infinity, độ dài, chỉ số hoặc điều kiện
  vòng lặp vào `comparison_count`.
- Không có kết quả hoặc comparison count được trả về khi validation thất bại.

## 4. Mốc số phép so sánh đề xuất

Baseline khởi tạo hai cực trị từ phần tử đầu, sau đó dùng hai câu `if` độc lập
cho mỗi phần tử còn lại:

```text
C_baseline(n) = 2(n - 1), n >= 1
```

Pairwise tối ưu được đề xuất có mốc:

```text
C_pairwise(1) = 0
C_pairwise(n) = ceil(3n / 2) - 2, n >= 2
```

Các mốc này là mục tiêu cần hai thành viên xác nhận, không phải kết quả đo.
Khi thiết kế benchmark, phải ghi rõ thời gian đo có bao gồm validation hay
không và áp dụng cùng phạm vi đo cho cả hai thuật toán.

## 5. Các quyết định chờ Thành viên 2

- Xác nhận tên hàm, định dạng tuple và miền input Python `int`/`float` hữu hạn.
- Xác nhận loại exception, thứ tự validation và chính sách không sửa input.
- Xác nhận quy tắc đếm và các mốc số phép so sánh.
- Thống nhất triển khai và kiểm thử chung ở Phase phù hợp; Phase 1 chưa cung
  cấp implementation hoặc test thuật toán.
