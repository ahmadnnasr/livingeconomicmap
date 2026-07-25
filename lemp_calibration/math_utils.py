from __future__ import annotations
from math import sqrt
from typing import Sequence, Optional


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def pearson(x: Sequence[float], y: Sequence[float]) -> Optional[float]:
    if len(x) != len(y) or len(x) < 3:
        return None
    mx, my = mean(x), mean(y)
    dx = [v - mx for v in x]
    dy = [v - my for v in y]
    denom = sqrt(sum(v*v for v in dx) * sum(v*v for v in dy))
    if denom == 0:
        return None
    return sum(a*b for a, b in zip(dx, dy)) / denom


def ranks(values: Sequence[float]) -> list[float]:
    pairs = sorted(enumerate(values), key=lambda pair: pair[1])
    output = [0.0] * len(values)
    i = 0
    while i < len(pairs):
        j = i
        while j + 1 < len(pairs) and pairs[j + 1][1] == pairs[i][1]:
            j += 1
        average_rank = (i + j + 2) / 2.0
        for k in range(i, j + 1):
            output[pairs[k][0]] = average_rank
        i = j + 1
    return output


def spearman(x: Sequence[float], y: Sequence[float]) -> Optional[float]:
    if len(x) < 3:
        return None
    return pearson(ranks(x), ranks(y))


def mae(predicted: Sequence[float], realized: Sequence[float]) -> Optional[float]:
    if not predicted:
        return None
    return mean([abs(a-b) for a, b in zip(predicted, realized)])


def rmse(predicted: Sequence[float], realized: Sequence[float]) -> Optional[float]:
    if not predicted:
        return None
    return sqrt(mean([(a-b)**2 for a, b in zip(predicted, realized)]))


def directional_accuracy(predicted: Sequence[float], realized: Sequence[float]) -> Optional[float]:
    if not predicted:
        return None
    correct = 0
    total = 0
    for p, r in zip(predicted, realized):
        if p == 0 or r == 0:
            continue
        total += 1
        correct += int((p > 0) == (r > 0))
    return correct / total if total else None


def slope(x: Sequence[float], y: Sequence[float]) -> Optional[float]:
    if len(x) < 3:
        return None
    mx, my = mean(x), mean(y)
    denom = sum((v-mx)**2 for v in x)
    if denom == 0:
        return None
    return sum((a-mx)*(b-my) for a, b in zip(x, y)) / denom
