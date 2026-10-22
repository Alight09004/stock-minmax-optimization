"""Optimal comparison-count pairwise minimum and maximum."""

import math


def _validate(arr):
    if type(arr) not in (list, tuple):
        raise TypeError("arr must be a list or tuple")
    if not arr:
        raise ValueError("arr must not be empty")
    for value in arr:
        if type(value) not in (int, float):
            raise TypeError("values must be Python int or float, excluding bool")
        if type(value) is float and not math.isfinite(value):
            raise ValueError("values must be finite")


def _scan(arr, trace=None):
    """Scan validated input; optionally record bounded teaching steps."""
    n = len(arr)
    count = 0
    if n % 2:
        minimum = maximum = arr[0]
        start = 1
        if trace is not None:
            trace.append({"kind": "initialize", "indices": (0,), "pair": (arr[0],),
                          "local_min": arr[0], "local_max": arr[0],
                          "minimum": minimum, "maximum": maximum, "comparisons": count})
    else:
        left, right = arr[0], arr[1]
        if left <= right:
            minimum, maximum = left, right
        else:
            minimum, maximum = right, left
        count = 1
        start = 2
        if trace is not None:
            trace.append({"kind": "initialize", "indices": (0, 1), "pair": (left, right),
                          "local_min": minimum, "local_max": maximum,
                          "minimum": minimum, "maximum": maximum, "comparisons": count})
    for index in range(start, n, 2):
        left, right = arr[index], arr[index + 1]
        if left <= right:
            smaller, larger = left, right
        else:
            smaller, larger = right, left
        count += 1
        if smaller < minimum:
            minimum = smaller
        count += 1
        if larger > maximum:
            maximum = larger
        count += 1
        if trace is not None:
            trace.append({"kind": "pair", "indices": (index, index + 1),
                          "pair": (left, right), "local_min": smaller,
                          "local_max": larger, "minimum": minimum,
                          "maximum": maximum, "comparisons": count})
    return minimum, maximum, count


def pairwise_min_max(arr):
    """Return (minimum, maximum, data comparison count) without changing arr."""
    _validate(arr)
    return _scan(arr)


def pairwise_trace(arr, *, max_items=20):
    """Return (result, steps) for small educational examples only."""
    _validate(arr)
    if len(arr) > max_items or max_items < 1:
        raise ValueError("trace input exceeds the configured item limit")
    steps = []
    result = _scan(arr, steps)
    return result, steps
