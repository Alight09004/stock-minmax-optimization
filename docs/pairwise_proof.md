# Pairwise Min-Max: proof and analysis

## Problem and contract

Given a nonempty one-dimensional list or tuple of finite Python `int` or
`float` values, return its minimum, maximum and the number of comparisons
between data values. Booleans and all other types are rejected. Validation is
a separate pass and is excluded from the reported comparison count. The input
is never changed.

## Pairwise idea and pseudocode

Each pair requires one comparison to decide its smaller and larger member.
Only the smaller can improve the global minimum; only the larger can improve
the global maximum. This uses three comparisons per subsequent pair.

```text
validate all input elements
if n is odd:
    minimum = maximum = a[0]; i = 1; comparisons = 0
else:
    compare a[0] and a[1] to initialize minimum and maximum
    i = 2; comparisons = 1
while i < n:
    compare a[i] and a[i+1]; assign smaller and larger
    compare smaller with minimum; update minimum if necessary
    compare larger with maximum; update maximum if necessary
    comparisons += 3; i += 2
return minimum, maximum, comparisons
```

After every processed pair, `minimum` and `maximum` are the extrema of all
processed elements. Initialization establishes this invariant. The smaller
member is the only member of a new pair that can lower the minimum, and the
larger is the only member that can raise the maximum; the two updates preserve
the invariant. At termination all elements have been processed.

## Exact comparison counts

For even `n >= 2`, the initial pair costs one comparison and `(n-2)/2`
remaining pairs cost three each:

`C_even(n) = 1 + 3(n-2)/2 = 3n/2 - 2`.

For odd `n >= 3`, the first element needs no comparison and `(n-1)/2`
pairs cost three each:

`C_odd(n) = 3(n-1)/2`.

For `n=1`, `C(1)=0`. The unified formula for `n>=2` is
`C(n)=ceil(3n/2)-2`. Baseline independently compares every element after the
first with both extrema, costing `2n-2` comparisons.

| n | Baseline | Pairwise | Reduction |
|---:|---:|---:|---:|
| 1 | 0 | 0 | 0% |
| 2 | 2 | 1 | 50% |
| 3 | 4 | 3 | 25% |
| 10 | 18 | 13 | 27.8% |
| 100 | 198 | 148 | 25.3% |
| 1,000 | 1,998 | 1,498 | 25.0% |

The reduction tends to 25% as `n` grows. The pairwise bound is the optimal
worst-case comparison bound for simultaneous minimum and maximum in the
comparison model; it does not imply a 25% wall-clock speedup.

## Example

For `[8, 3, 7, 2, 9, 4]`, compare `(8,3)` to initialize `(min,max)=(3,8)`
at count 1. Pair `(7,2)` gives local `(2,7)`, global `(2,8)`, count 4.
Pair `(9,4)` gives local `(4,9)`, global `(2,9)`, count 7. The result is
`(2,9,7)`, matching `3*6/2-2`.

## Complexity, assumptions and practical limits

Validation and scanning each take linear time, so overall time is `O(n)`.
The production scan stores a fixed number of values and uses `O(1)` auxiliary
space. It neither sorts nor copies the full input. The optional trace is a
bounded teaching tool and uses `O(n)` space for at most 20 values.

Invalid containers or elements raise `TypeError`; empty input or nonfinite
floats raise `ValueError`. Python integers of arbitrary size are supported
without conversion to float. Equal values still incur comparisons. Actual
runtime also reflects Python loop and validation overhead, memory layout and
hardware; benchmark measurements are needed to assess elapsed time.

## Dashboard integration

`dashboard.stock_view.render_stock_view()` is independently callable from a
Streamlit shell. For example, the shared app can import it and call it in a
selected page branch. The view reads one canonical ticker file at a time from
`datasets/archive/Stocks` or `ETFs`; it never scans the duplicate `Data` tree.
The Member 1 prepared sample is supported when its exact schema and selected
price column match. Because that prepared CSV holds only one price column,
Open/High/Low selection uses the read-only canonical file adapter. Invalid
dates, missing or nonfinite prices, and duplicate dates are filtered with the
first valid date occurrence retained; rows are then sorted by date. The
historical replay is capped at 2,000 observations. The view calls the real
Pairwise and, when present, the real Baseline implementation. The shared
`dashboard/app.py` has not been changed.
