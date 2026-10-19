"""Member 1 baseline contract and count tests."""

import random

import pytest

from algorithms.baseline import baseline_min_max


@pytest.mark.parametrize("values", [
    [7], (2.5,), [2, 1], [1, 2], [1, 2, 3, 4], [5, 4, 3, 2, 1],
    [3, 1, 3, 2, 1], [4] * 9, [-8, -2, -6], [-7, 0, 2.5, -1],
    [10**400, -(10**500), 1.5], [0.0, -0.0],
])
def test_result_count_and_immutability(values):
    before = values[:]
    result = baseline_min_max(values)
    assert result == (min(values), max(values), 2 * (len(values) - 1))
    assert type(result) is tuple
    assert type(result[2]) is int
    assert values == before


def test_deterministic_random_sequences():
    randomizer = random.Random(42)
    for size in range(1, 101):
        values = [randomizer.uniform(-100, 100) for _ in range(size)]
        assert baseline_min_max(values) == (min(values), max(values), 2 * (size - 1))


@pytest.mark.parametrize("values", [[], ()])
def test_empty(values):
    with pytest.raises(ValueError):
        baseline_min_max(values)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("position", [0, 1, 2])
def test_nonfinite(value, position):
    values = [1, 2]
    values.insert(position, value)
    ids = [id(item) for item in values]
    with pytest.raises(ValueError):
        baseline_min_max(values)
    assert [id(item) for item in values] == ids
    with pytest.raises(ValueError):
        baseline_min_max([value])


@pytest.mark.parametrize("values", [None, True, "12", 2, 2.5, {1, 2}, {"a": 2}, iter([1, 2])])
def test_invalid_container(values):
    with pytest.raises(TypeError):
        baseline_min_max(values)


@pytest.mark.parametrize("value", [None, True, False, "2", 1j, [], (), object()])
def test_invalid_elements(value):
    values = [1, value, 3]
    before = values[:]
    with pytest.raises(TypeError):
        baseline_min_max(values)
    assert values == before
    with pytest.raises(TypeError):
        baseline_min_max([value])
