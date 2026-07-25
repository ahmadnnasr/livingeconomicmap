from __future__ import annotations
from .models import DailyBrief


class DailyBriefGenerator:
    def generate(self, context: dict) -> DailyBrief:
        as_of_date = context["as_of_date"]
        top_regime = context.get("top_regime", "unknown")
        composite = context.get("composite_liquidity")
        headline = (
            f"Daily macro update for {as_of_date}: "
            f"{top_regime.replace('_', ' ')} is the leading regime."
        )
        regime_summary = (
            f"Composite liquidity is {composite:.1%}."
            if isinstance(composite, (float, int))
            else "Composite liquidity was unavailable."
        )
        return DailyBrief(
            as_of_date=as_of_date,
            headline=headline,
            regime_summary=regime_summary,
            belief_changes=context.get("belief_change_text", []),
            market_transmission=context.get("market_transmission_text", []),
            ranking_changes=context.get("ranking_change_text", []),
            alerts=context.get("alert_text", []),
            model_governance=context.get("governance_text", []),
        )

    @staticmethod
    def render_markdown(brief: DailyBrief) -> str:
        sections = [
            f"# Living Economic Map — {brief.as_of_date}",
            "",
            brief.headline,
            "",
            "## Regime",
            brief.regime_summary,
        ]
        for title, items in [
            ("Belief changes", brief.belief_changes),
            ("Market transmission", brief.market_transmission),
            ("Ranking changes", brief.ranking_changes),
            ("Alerts", brief.alerts),
            ("Model governance", brief.model_governance),
        ]:
            sections.extend(["", f"## {title}"])
            sections.extend(
                [f"- {item}" for item in items]
                or ["- No material changes."]
            )
        return "\n".join(sections)
