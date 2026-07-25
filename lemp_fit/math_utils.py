from __future__ import annotations
from math import sqrt
from typing import Sequence


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def mse(predicted: Sequence[float], actual: Sequence[float]) -> float:
    return mean([(p-a)**2 for p, a in zip(predicted, actual)])


def directional_accuracy(predicted: Sequence[float], actual: Sequence[float]) -> float:
    valid = [(p, a) for p, a in zip(predicted, actual) if p != 0 and a != 0]
    if not valid:
        return 0.0
    return sum((p > 0) == (a > 0) for p, a in valid) / len(valid)


def standard_deviation(values: Sequence[float]) -> float:
    if len(values) <= 1:
        return 0.0
    m = mean(values)
    return sqrt(sum((v-m)**2 for v in values) / len(values))
