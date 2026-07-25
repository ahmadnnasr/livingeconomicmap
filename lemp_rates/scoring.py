from __future__ import annotations
import math
import uuid
from collections import defaultdict

from .models import SeriesSignal, EvidenceItem, BeliefState
from .spec import SERIES_SPECS


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def logistic(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


class EvidenceScorer:
    def score(self, signal: SeriesSignal) -> EvidenceItem | None:
        spec = SERIES_SPECS.get(signal.series_id)
        if spec is None:
            return None

        raw = getattr(signal, spec["feature"])
        if raw is None:
            return None

        normalized = clamp(raw / spec["scale"], -1.0, 1.0)
        direction = normalized * spec["direction"]
        freshness = clamp(
            1.0 - signal.freshness_days / max(1, spec["max_freshness_days"])
        )
        confidence = freshness
        reliability = clamp(signal.source_reliability)
        contribution = direction * abs(normalized) * confidence * reliability * spec["weight"]

        return EvidenceItem(
            evidence_id=str(uuid.uuid4()),
            belief_key=spec["belief"],
            series_id=signal.series_id,
            direction=direction,
            magnitude=abs(normalized),
            confidence=confidence,
            reliability=reliability,
            contribution=contribution,
            as_of_date=signal.as_of_date,
            explanation=(
                f"{spec['description']} produced a normalized signal of "
                f"{normalized:+.3f}; directional contribution={contribution:+.3f}."
            ),
            correlation_group=spec["correlation_group"],
        )


class BeliefUpdater:
    def update(
        self,
        belief_key: str,
        prior_probability: float,
        evidence: list[EvidenceItem],
        as_of_date: str,
    ) -> BeliefState:
        grouped = defaultdict(list)
        for item in evidence:
            grouped[item.correlation_group].append(item)

        adjusted_total = 0.0
        effective_weight = 0.0
        for items in grouped.values():
            ordered = sorted(items, key=lambda item: abs(item.contribution), reverse=True)
            for index, item in enumerate(ordered):
                discount = 1.0 if index == 0 else 0.50 ** index
                adjusted_total += item.contribution * discount
                effective_weight += abs(item.contribution) * discount

        prior_logit = math.log(prior_probability / (1.0 - prior_probability))
        posterior = logistic(prior_logit + adjusted_total * 3.0)
        confidence = clamp(effective_weight)

        explanation = (
            f"{belief_key} moved from {prior_probability:.1%} to "
            f"{posterior:.1%} using {len(evidence)} evidence items after "
            "correlation discounts."
        )
        return BeliefState(
            belief_key=belief_key,
            prior_probability=prior_probability,
            posterior_probability=posterior,
            confidence=confidence,
            evidence=evidence,
            as_of_date=as_of_date,
            explanation=explanation,
        )
