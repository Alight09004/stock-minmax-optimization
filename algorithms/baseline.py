"""Member 1: validated, instrumented linear min-max scan."""

import math


def baseline_min_max(arr):
    """Return (minimum, maximum, data comparisons), without mutating arr.

    Validation is a separate O(n) pass and is included in this function's
    runtime. Both passes use O(1) auxiliary space. Only the scan's two value
    comparisons per subsequent element contribute to the returned count.
    """
    if type(arr) not in (list, tuple):
        raise TypeError("arr must be a list or tuple")
    if not arr:
        raise ValueError("arr must not be empty")
    for value in arr:
        if type(value) not in (int, float):
            raise TypeError("values must be Python int or float, excluding bool")
        # Arbitrarily large integers are finite; converting them may overflow.
        if type(value) is float and not math.isfinite(value):
            raise ValueError("values must be finite")

    minimum = maximum = arr[0]
    comparisons = 0
    for index in range(1, len(arr)):
        value = arr[index]
        if value < minimum:
            minimum = value
        if value > maximum:
            maximum = value
        comparisons += 2
    return minimum, maximum, comparisons
