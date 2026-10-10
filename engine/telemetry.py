"""Telemetry and token pricing tracker for model routing infrastructure.

Tracks:
- Exact pricing per 1M tokens across supported models and frontier baseline
- Dollar savings and percentage savings relative to the baseline
- EdTech multiplier (X-times more students educated on same budget)
- Cumulative session spend and query volume
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# Exact pricing per 1,000,000 tokens (USD)
PRICING_PER_1M: Dict[str, Dict[str, float]] = {
    "llama-3.1-8b-instant": {
        "input": 0.05,
        "output": 0.08,
    },
    "qwen/qwen3.8-27b": {
        "input": 0.80,
        "output": 4.00,
    },
    "llama-3.3-70b-versatile": {
        "input": 0.59,
        "output": 0.79,
    },
    "Frontier Baseline (GPT-4o proxy)": {
        "input": 2.50,
        "output": 10.00,
    },
}

BASELINE_MODEL = "Frontier Baseline (GPT-4o proxy)"


class SavingsResult(dict):
    """Dictionary holding savings metrics with support for attribute access and tuple unpacking.

    Supports:
        - Dict indexing: res["actual_cost"]
        - Attribute access: res.actual_cost
        - Unpacking: actual_cost, baseline_cost, dollars_saved, savings_pct = res
    """

    def __init__(
        self,
        actual_cost: float,
        baseline_cost: float,
        dollars_saved: float,
        savings_pct: float,
    ) -> None:
        super().__init__(
            actual_cost=actual_cost,
            baseline_cost=baseline_cost,
            dollars_saved=dollars_saved,
            savings_pct=savings_pct,
        )
        self.actual_cost = actual_cost
        self.baseline_cost = baseline_cost
        self.dollars_saved = dollars_saved
        self.savings_pct = savings_pct

    def __iter__(self):
        """Enable tuple unpacking in the exact order requested."""
        yield self.actual_cost
        yield self.baseline_cost
        yield self.dollars_saved
        yield self.savings_pct


def calculate_edtech_multiplier(actual_cost: float, baseline_cost: float) -> float:
    """Calculate the EdTech Multiplier:

    baseline_cost / max(actual_cost, 0.000001)
    Represents how many more students can be educated on the same budget.
    """
    return baseline_cost / max(actual_cost, 0.000001)


class TelemetryTracker:
    """Tracks token spend, financial savings, and edtech efficiency metrics."""

    def __init__(
        self,
        pricing: Optional[Dict[str, Dict[str, float]]] = None,
        baseline_model: str = BASELINE_MODEL,
    ) -> None:
        self.pricing: Dict[str, Dict[str, float]] = pricing or PRICING_PER_1M
        self.baseline_model: str = baseline_model

        # Cumulative session state
        self.total_queries: int = 0
        self.cumulative_spend: float = 0.0
        self.cumulative_baseline_spend: float = 0.0
        self.cumulative_dollars_saved: float = 0.0
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.query_history: List[Dict[str, Any]] = []

    @property
    def total_spend(self) -> float:
        """Cumulative session spend in USD."""
        return self.cumulative_spend

    def calculate_savings(
        self,
        model_name: str,
        in_tokens: int,
        out_tokens: int,
        track: bool = True,
    ) -> SavingsResult:
        """Calculate costs and savings for a query.

        Args:
            model_name: Identifier of the routed model.
            in_tokens: Number of input/prompt tokens.
            out_tokens: Number of output/completion tokens.
            track: Whether to record this query in cumulative session telemetry.

        Returns:
            SavingsResult: Dict-like object supporting unpacking of
            (actual_cost, baseline_cost, dollars_saved, savings_pct).
        """
        if model_name not in self.pricing:
            raise ValueError(
                f"Model '{model_name}' not found in pricing configuration. "
                f"Supported models: {list(self.pricing.keys())}"
            )

        if self.baseline_model not in self.pricing:
            raise ValueError(
                f"Baseline model '{self.baseline_model}' not found in pricing configuration."
            )

        model_rates = self.pricing[model_name]
        baseline_rates = self.pricing[self.baseline_model]

        actual_cost = (
            in_tokens * model_rates["input"] + out_tokens * model_rates["output"]
        ) / 1_000_000.0

        baseline_cost = (
            in_tokens * baseline_rates["input"] + out_tokens * baseline_rates["output"]
        ) / 1_000_000.0

        dollars_saved = baseline_cost - actual_cost
        savings_pct = (
            (dollars_saved / baseline_cost * 100.0) if baseline_cost > 0.0 else 0.0
        )

        if track:
            self.total_queries += 1
            self.cumulative_spend += actual_cost
            self.cumulative_baseline_spend += baseline_cost
            self.cumulative_dollars_saved += dollars_saved
            self.total_input_tokens += in_tokens
            self.total_output_tokens += out_tokens
            self.query_history.append(
                {
                    "model": model_name,
                    "in_tokens": in_tokens,
                    "out_tokens": out_tokens,
                    "actual_cost": actual_cost,
                    "baseline_cost": baseline_cost,
                    "dollars_saved": dollars_saved,
                    "savings_pct": savings_pct,
                }
            )

        return SavingsResult(
            actual_cost=actual_cost,
            baseline_cost=baseline_cost,
            dollars_saved=dollars_saved,
            savings_pct=savings_pct,
        )

    def calculate_edtech_multiplier(
        self,
        actual_cost: Optional[float] = None,
        baseline_cost: Optional[float] = None,
    ) -> float:
        """Calculate EdTech multiplier: baseline_cost / max(actual_cost, 0.000001).

        If actual_cost or baseline_cost is None, uses cumulative session metrics.
        """
        if actual_cost is None:
            actual_cost = self.cumulative_spend
        if baseline_cost is None:
            baseline_cost = self.cumulative_baseline_spend

        return calculate_edtech_multiplier(actual_cost, baseline_cost)

    def get_session_summary(self) -> Dict[str, Any]:
        """Return a structured summary of the current session telemetry."""
        return {
            "total_queries": self.total_queries,
            "cumulative_spend": self.cumulative_spend,
            "cumulative_baseline_spend": self.cumulative_baseline_spend,
            "cumulative_dollars_saved": self.cumulative_dollars_saved,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "overall_savings_pct": (
                (self.cumulative_dollars_saved / self.cumulative_baseline_spend * 100.0)
                if self.cumulative_baseline_spend > 0.0
                else 0.0
            ),
            "edtech_multiplier": self.calculate_edtech_multiplier(),
        }

    def reset(self) -> None:
        """Reset cumulative session metrics."""
        self.total_queries = 0
        self.cumulative_spend = 0.0
        self.cumulative_baseline_spend = 0.0
        self.cumulative_dollars_saved = 0.0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.query_history.clear()
