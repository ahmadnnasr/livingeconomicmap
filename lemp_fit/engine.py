from __future__ import annotations
from .models import TrainingRow, FitConfig, FittingReport
from .constraints import DEFAULT_CONSTRAINTS
from .optimizer import ConstrainedRidgeFitter
from .evaluation import ModelEvaluator
from .promotion import PromotionGate


class ConstrainedFittingEngine:
    def run(
        self,
        rows: list[TrainingRow],
        target_key: str,
        config: FitConfig | None = None,
        model_version: str = "rates_market_fit_v1",
    ) -> FittingReport:
        config = config or FitConfig()
        fitter = ConstrainedRidgeFitter()
        evaluator = ModelEvaluator()

        model = fitter.fit(
            rows,
            DEFAULT_CONSTRAINTS,
            config,
            target_key,
        )
        folds = evaluator.expanding_window_cv(
            rows,
            DEFAULT_CONSTRAINTS,
            config,
            target_key,
        )
        stability = evaluator.stability(folds)
        baseline = evaluator.compare_to_baseline(model, rows)
        promotion = PromotionGate().decide(
            model,
            stability,
            baseline,
            model_version,
        )

        return FittingReport(
            model=model,
            folds=folds,
            stability=stability,
            baseline=baseline,
            promotion=promotion,
        )
