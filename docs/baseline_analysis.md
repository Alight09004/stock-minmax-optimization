# Baseline Algorithm Analysis — Thành viên 1

## 1. Bài toán và miền dữ liệu

Cho dãy không rỗng A gồm n giá trị giá lịch sử, xác định giá nhỏ nhất và lớn
nhất, đồng thời đếm phép so sánh dữ liệu phục vụ tìm cực trị. Kết quả là
`(minimum, maximum, comparison_count)`.

`baseline_min_max` nhận list/tuple chứa đúng các kiểu Python int/float hữu hạn,
không nhận bool. Không sửa input. Xem [interface_contract.md](interface_contract.md)
cho đề xuất tích hợp với Thành viên 2; tài liệu chung vẫn chờ xác nhận.

Giá lấy từ nhiều ticker là **dãy tổng hợp các quan sát giá lịch sử**, không phải
chuỗi thời gian liên tục của một cổ phiếu và không đại diện cho lợi suất danh mục.

## 2. Thuật toán

Validation kiểm tra container, rỗng, rồi từng phần tử theo thứ tự. Sau validation,
khởi tạo cả hai cực trị bằng A[0]. Mỗi phần tử còn lại được so sánh **độc lập**
với minimum và maximum; dùng hai `if`, không dùng `if/elif`.

```text
BASELINE-MIN-MAX(A):
    require list/tuple, nonempty
    for each x in A:
        require Python int/float, excluding bool
        require finite value
    minimum <- A[0]
    maximum <- A[0]
    comparisons <- 0
    for i <- 1 to length(A) - 1:
        x <- A[i]
        if x < minimum:
            minimum <- x
        if x > maximum:
            maximum <- x
        comparisons <- comparisons + 2
    return (minimum, maximum, comparisons)
```

Implementation không dùng built-in min/max để tính kết quả, không sort và không
tạo lát cắt A[1:]. Trong test và correctness oracle của benchmark, built-in
min/max được phép sử dụng **ngoài vùng đo thời gian**.

## 3. Chứng minh tính đúng

Bất biến vòng lặp: trước lần lặp chỉ số i, minimum và maximum lần lượt là cực
trị của tiền tố A[0:i].

- Khởi tạo: i=1, tiền tố chỉ có A[0], nên cả hai cực trị đúng.
- Duy trì: so sánh A[i] với minimum cập nhật cực tiểu của tiền tố mở rộng;
  so sánh độc lập với maximum cập nhật cực đại. Vì thế bất biến đúng cho i+1.
- Kết thúc: i=n, tiền tố là toàn bộ A. Hai giá trị trả về là cực trị toàn dãy.

Validation thất bại thì raise exception trước khi quét tìm cực trị. Không có
thao tác ghi vào A, kể cả trên đường xử lý lỗi.

## 4. Chứng minh số phép so sánh

Khởi tạo bằng phép gán, không so sánh hai giá trị dữ liệu. Có n−1 lần lặp; mỗi
lần luôn thực hiện `x < minimum` và `x > maximum`, kể cả khi dữ liệu bằng nhau.

\[
C(n)=\sum_{i=1}^{n-1}2=2(n-1),\qquad n\ge1.
\]

Trường hợp n=1 cho C(1)=0. Công thức không phụ thuộc thứ tự tăng/giảm hay tần
suất giá trị lặp lại. Best/average/worst đều có cùng số phép so sánh này.

Count không bao gồm kiểm tra kiểu, tính hữu hạn, điều kiện vòng lặp, so sánh chỉ
số hoặc phép cộng bộ đếm. Nó không phải tổng số CPU instructions.

## 5. Độ phức tạp

- Validation là một pass Θ(n); không được coi là chi phí O(1).
- Quét tìm cực trị là một pass Θ(n).
- Tổng thời gian Θ(n), do Θ(n)+Θ(n)=Θ(n), theo mô hình so sánh giá trị có chi
  phí hằng số. Với Python int có số bit tùy ý, chi phí bit của so sánh còn phụ
  thuộc độ dài số; benchmark này dùng float từ dữ liệu giá.
- Auxiliary space O(1), không tính input: chỉ giữ biến vòng lặp, giá trị hiện
  tại, hai cực trị và bộ đếm. Không copy input hoặc dùng mảng phụ.
- Toàn pipeline không có space O(1): CSV preparation giữ một ticker, benchmark
  giữ tối đa 1.000.000 giá và một tuple tiền tố. Phân biệt với thuật toán lõi.

## 6. Edge cases

| Input | Hành vi |
|---|---|
| Một phần tử x | `(x, x, 0)` |
| List/tuple rỗng | ValueError |
| NaN, +Infinity, −Infinity | ValueError, kể cả phần tử đầu hoặc duy nhất |
| None, bool, string, complex, nested container, kiểu khác | TypeError |
| Python int rất lớn | Hợp lệ; không ép sang float để validation |
| Tất cả bằng nhau / giá trị lặp / tăng / giảm | Đúng cực trị và count 2(n−1) |

## 7. Giới hạn và so sánh lý thuyết

Baseline không tối ưu số phép so sánh. Pairwise tối ưu có mục tiêu 0 khi n=1,
và ceil(3n/2)−2 khi n≥2. Với n chẵn lớn, mức giảm số so sánh tiến tới 25%; đây
không phải bảo đảm giảm 25% thời gian chạy. Validation, bytecode, branch,
counter instrumentation, interpreter và nhiễu hệ thống đều ảnh hưởng runtime.

Hàm hiện là **instrumented implementation**: timing của nó bao gồm validation
và cập nhật bộ đếm. Chưa có timing uninstrumented hoặc kết quả Pairwise thật.
