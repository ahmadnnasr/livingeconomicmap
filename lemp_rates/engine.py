from __future__ import annotations
from collections import defaultdict

from .models import (
    SeriesSignal, BeliefState, RegimeState,
    PropagationResult, RatesLiquiditySnapshot,
)
from .scoring import EvidenceScorer, BeliefUpdater, clamp, logistic
from .spec import SERIES_SPECS, COMPONENT_WEIGHTS, RATE_WEIGHTS


class RatesLiquidityEngine:
    REQUIRED_SERIES = list(SERIES_SPECS)

    def __init__(self) -> None:
        self.scorer = EvidenceScorer()
        self.updater = BeliefUpdater()

    def run(
        self,
        signals: list[SeriesSignal],
        as_of_date: str,
        priors: dict[str, float] | None = None,
    ) -> RatesLiquiditySnapshot:
        priors = priors or {}
        evidence_by_belief = defaultdict(list)
        available_series = set()

        for signal in signals:
            evidence = self.scorer.score(signal)
            if evidence is None:
                continue
            available_series.add(signal.series_id)
            evidence_by_belief[evidence.belief_key].append(evidence)

        beliefs = {}
        all_belief_keys = set(spec["belief"] for spec in SERIES_SPECS.values())
        for belief_key in all_belief_keys:
            beliefs[belief_key] = self.updater.update(
                belief_key,
                priors.get(belief_key, 0.50),
                evidence_by_belief.get(belief_key, []),
                as_of_date,
            )

        component_beliefs = {
            key: beliefs[key] for key in COMPONENT_WEIGHTS
        }
        rate_beliefs = {
            key: beliefs[key] for key in RATE_WEIGHTS
        }

        composite = self._composite_liquidity(
            component_beliefs,
            as_of_date,
            priors.get("composite_liquidity", 0.50),
        )
        regimes = self._regimes(component_beliefs, rate_beliefs, composite, as_of_date)
        propagation = self._propagate(composite, rate_beliefs, as_of_date)

        missing = [
            series_id for series_id in self.REQUIRED_SERIES
            if series_id not in available_series
        ]
        coverage = 1.0 - len(missing) / len(self.REQUIRED_SERIES)

        return RatesLiquiditySnapshot(
            as_of_date=as_of_date,
            component_beliefs=component_beliefs,
            composite_liquidity=composite,
            rate_beliefs=rate_beliefs,
            regimes=regimes,
            propagation=propagation,
            coverage_ratio=coverage,
            missing_series=missing,
        )

    def _composite_liquidity(
        self,
        components: dict[str, BeliefState],
        as_of_date: str,
        prior: float,
    ) -> BeliefState:
        posterior = sum(
            components[key].posterior_probability * weight
            for key, weight in COMPONENT_WEIGHTS.items()
        )
        confidence = sum(
            components[key].confidence * weight
            for key, weight in COMPONENT_WEIGHTS.items()
        )
        explanation = (
            "Composite liquidity uses 40% central-bank liquidity, "
            "30% Treasury liquidity, and 30% money-market liquidity."
        )
        evidence = []
        for item in components.values():
            evidence.extend(item.evidence)

        return BeliefState(
            belief_key="composite_liquidity",
            prior_probability=prior,
            posterior_probability=posterior,
            confidence=confidence,
            evidence=evidence,
            as_of_date=as_of_date,
            explanation=explanation,
        )

    def _regimes(
        self,
        components: dict[str, BeliefState],
        rates: dict[str, BeliefState],
        composite: BeliefState,
        as_of_date: str,
    ) -> list[RegimeState]:
        cb = components["central_bank_liquidity"].posterior_probability
        treasury = components["treasury_liquidity"].posterior_probability
        money = components["money_market_liquidity"].posterior_probability
        real_pressure = rates["real_yield_pressure"].posterior_probability
        long_pressure = rates["long_rate_pressure"].posterior_probability

        scores = {
            "QE": composite.posterior_probability * cb,
            "QT": (1 - composite.posterior_probability) * (1 - cb),
            "mixed_liquidity": 1 - abs(composite.posterior_probability - 0.5) * 2,
            "treasury_stress": (1 - treasury) * long_pressure,
            "money_market_stress": (1 - money) * (
                1 - rates.get("money_market_stress", BeliefState(
                    "", .5, .5, 0, [], as_of_date, ""
                )).posterior_probability
            ),
            "real_rate_tightening": real_pressure,
        }
        total = sum(max(0.001, value) for value in scores.values())
        regimes = []
        for key, value in scores.items():
            probability = max(0.001, value) / total
            regimes.append(
                RegimeState(
                    regime_key=key,
                    probability=probability,
                    as_of_date=as_of_date,
                    supporting_beliefs={
                        "composite_liquidity": composite.posterior_probability,
                        "central_bank_liquidity": cb,
                        "treasury_liquidity": treasury,
                        "money_market_liquidity": money,
                        "real_yield_pressure": real_pressure,
                        "long_rate_pressure": long_pressure,
                    },
                    explanation=f"{key} probability derived from rates and liquidity beliefs.",
                )
            )
        return sorted(regimes, key=lambda item: item.probability, reverse=True)

    def _propagate(
        self,
        composite: BeliefState,
        rates: dict[str, BeliefState],
        as_of_date: str,
    ) -> list[PropagationResult]:
        real_pressure = rates["real_yield_pressure"].posterior_probability
        long_pressure = rates["long_rate_pressure"].posterior_probability

        financial_conditions = clamp(
            0.50
            + (composite.posterior_probability - 0.50) * 0.70
            - (real_pressure - 0.50) * 0.40
            - (long_pressure - 0.50) * 0.20
        )

        growth_prior = 0.50
        growth_support = clamp(
            growth_prior + (financial_conditions - 0.50) * 0.80
        )

        blocked = []
        active = [
            "composite_liquidity -> financial_conditions_easing",
            "financial_conditions_easing -> growth_valuation_support",
        ]
        if real_pressure >= 0.65:
            growth_support = min(growth_support, 0.50)
            blocked.append(
                "growth_valuation_support blocked by elevated real-yield pressure"
            )

        ai_support = clamp(
            0.50 + (growth_support - 0.50) * 0.60
        )

        return [
            PropagationResult(
                node_key="financial_conditions_easing",
                prior_probability=0.50,
                posterior_probability=financial_conditions,
                active_edges=[active[0]],
                blocked_edges=[],
                explanation="Liquidity support offset by nominal and real-rate pressure.",
            ),
            PropagationResult(
                node_key="growth_valuation_support",
                prior_probability=growth_prior,
                posterior_probability=growth_support,
                active_edges=[active[1]],
                blocked_edges=blocked,
                explanation="Easing financial conditions support duration-sensitive valuations unless real yields block transmission.",
            ),
            PropagationResult(
                node_key="ai_capex_financing_support",
                prior_probability=0.50,
                posterior_probability=ai_support,
                active_edges=["growth_valuation_support -> ai_capex_financing_support"],
                blocked_edges=[],
                explanation="Growth valuation support improves financing conditions for capital-intensive AI infrastructure.",
            ),
        ]
