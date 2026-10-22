"""Pairwise contract, trace and integration tests."""

import random

import pytest

from algorithms.pairwise_minmax import pairwise_min_max, pairwise_trace
from algorithms.baseline import baseline_min_max


def theoretical(n):
    return 0 if n == 1 else (3 * n + 1) // 2 - 2


@pytest.mark.parametrize("values", [
    [7], (2.5,), [2, 1], [1, 2], [1, 2, 3, 4], [5, 4, 3, 2, 1],
    [4] * 9, [3, 1, 1, 3, 2], [-8, -2, -6], [-7, 0, 2.5, -1],
    [10**400, -(10**500), 1.5], [0.0, -0.0],
])
def test_result_count_and_immutability(values):
    before = values[:]
    result = pairwise_min_max(values)
    assert result == (min(values), max(values), theoretical(len(values)))
    assert values == before
    assert type(result) is tuple and type(result[2]) is int
    assert result[:2] == baseline_min_max(values)[:2]


def test_deterministic_random_arrays():
    randomizer = random.Random(2026)
    for n in range(1, 101):
        values = [randomizer.uniform(-1000, 1000) for _ in range(n)]
        assert pairwise_min_max(values) == (min(values), max(values), theoretical(n))


@pytest.mark.parametrize("values", [[], ()])
def test_empty(values):
    with pytest.raises(ValueError):
        pairwise_min_max(values)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("position", [0, 1, 2])
def test_nonfinite(value, position):
    values = [1, 2]
    values.insert(position, value)
    before = [id(item) for item in values]
    with pytest.raises(ValueError):
        pairwise_min_max(values)
    assert [id(item) for item in values] == before


@pytest.mark.parametrize("values", [None, True, "12", 2, 2.5, {1, 2}, {"a": 2}, iter([1, 2])])
def test_invalid_container(values):
    with pytest.raises(TypeError):
        pairwise_min_max(values)


@pytest.mark.parametrize("value", [None, True, False, "2", 1j, [], (), object()])
def test_invalid_element(value):
    with pytest.raises(TypeError):
        pairwise_min_max([1, value, 3])
    with pytest.raises(TypeError):
        pairwise_min_max([value])


@pytest.mark.parametrize("values", [[8, 3, 7, 2, 9, 4], [6, 1, 5, 2, 3]])
def test_trace_matches_core(values):
    result, steps = pairwise_trace(values)
    assert result == pairwise_min_max(values)
    assert steps[-1]["comparisons"] == result[2]
    assert steps[-1]["minimum"] == result[0]
    assert steps[-1]["maximum"] == result[1]
    assert len(steps) == (len(values) + 1) // 2
    assert [s["comparisons"] for s in steps] == sorted(s["comparisons"] for s in steps)


def test_trace_bound_and_large_array():
    with pytest.raises(ValueError):
        pairwise_trace(list(range(21)))
    values = list(range(100_000, 0, -1))
    assert pairwise_min_max(values) == (1, 100_000, theoretical(100_000))


def test_benchmark_discovers_real_pairwise():
    from benchmark.benchmark import discover_algorithms
    algorithms, status = discover_algorithms()
    assert "pairwise" in algorithms, status
    assert algorithms["pairwise"]([5, 1, 8]) == (1, 8, 3)
