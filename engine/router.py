"""Production router infrastructure.

Wires classification, multi-model execution, output verification,
and automated fallback escalation across supported models.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from core import EducationalQueryClassifier, LightweightVerifier
from engine import ModelClient, TelemetryTracker

logger = logging.getLogger(__name__)

# Architecture mapping per query complexity tier
TIER_MODEL_MAP: Dict[int, str] = {
    1: "llama-3.1-8b-instant",       # Meta fast SLM (Factual Recall / Definitions)
    2: "qwen/qwen3.8-27b",           # Alibaba structured synthesis (Conceptual Explanations)
    3: "llama-3.1-8b-instant",       # Speculative fast attempt (Complex Reasoning / Proofs)
}

FALLBACK_MODEL: str = "llama-3.3-70b-versatile"  # Frontier-class escalation model


class ProductionRouter:
    """Intelligent educational query router with automated verification and fallback."""

    def __init__(
        self,
        classifier: Optional[EducationalQueryClassifier] = None,
        verifier: Optional[LightweightVerifier] = None,
        model_client: Optional[ModelClient] = None,
        telemetry_tracker: Optional[TelemetryTracker] = None,
    ) -> None:
        self.classifier = classifier or EducationalQueryClassifier()
        self.verifier = verifier or LightweightVerifier()
        self.model_client = model_client or ModelClient()
        self.telemetry = telemetry_tracker or TelemetryTracker()

    def route_and_execute(
        self,
        prompt: str,
        force_fallback_demo: bool = False,
    ) -> Dict[str, Any]:
        """Route prompt, execute inference, verify output, and escalate if needed.

        Args:
            prompt: Student query or educational prompt.
            force_fallback_demo: If True, forces verification failure to demonstrate escalation.

        Returns:
            dict: {
                "response_text": str,
                "tier": int,
                "initial_model": str,
                "final_model": str,
                "fallback_triggered": bool,
                "latency_ms": float,
                "impact_metrics": dict
            }
        """
        # Step 1: Classify prompt tier via classifier
        tier_raw = self.classifier.classify(prompt)
        tier = int(tier_raw) if isinstance(tier_raw, (int, float)) else 1
        if tier not in TIER_MODEL_MAP:
            tier = 1

        # Step 2: Target architecture selection
        initial_model = TIER_MODEL_MAP[tier]

        # Step 3: Run inference on selected model
        logger.info(
            "Routing Tier %d query to initial architecture '%s'...",
            tier,
            initial_model,
        )
        start_time = time.perf_counter()

        initial_result = self.model_client.generate(
            model_name=initial_model,
            prompt=prompt,
            system_prompt="You are an expert educational AI assistant.",
        )

        response_text = initial_result["text"]
        total_latency_ms = initial_result["latency_ms"]
        in_tokens = initial_result["input_tokens"]
        out_tokens = initial_result["output_tokens"]

        # Step 4: Verify output via LightweightVerifier
        if force_fallback_demo:
            verification = self.verifier.verify(
                prompt=prompt,
                response=response_text,
                tier=tier,
                force_fail=True,
                model_name=initial_model,
            )
        else:
            verification = self.verifier.verify(
                prompt=prompt,
                response=response_text,
                tier=tier,
                force_fail=False,
                model_name=initial_model,
            )

        verification_passed = bool(verification)

        # Step 5 (Fallback Escalation): If verification fails
        fallback_triggered = not verification_passed
        fallback_reason: Optional[str] = None
        final_model = initial_model

        if fallback_triggered:
            fallback_reason = getattr(
                verification,
                "reason",
                "Output verification criteria failed",
            )
            final_model = FALLBACK_MODEL

            logger.warning(
                "Verification failed for Tier %d on model '%s' (Reason: %s). Escalating to '%s'.",
                tier,
                initial_model,
                fallback_reason,
                final_model,
            )

            # Re-route prompt immediately to frontier-class model
            escalated_result = self.model_client.generate(
                model_name=final_model,
                prompt=prompt,
                system_prompt=(
                    "You are a frontier educational reasoning engine. Provide a rigorous, "
                    "pedagogically complete, step-by-step solution."
                ),
            )

            response_text = escalated_result["text"]
            total_latency_ms += escalated_result["latency_ms"]
            in_tokens += escalated_result["input_tokens"]
            out_tokens += escalated_result["output_tokens"]

        # Step 6: Compute cost savings and update telemetry
        savings = self.telemetry.calculate_savings(
            model_name=final_model,
            in_tokens=in_tokens,
            out_tokens=out_tokens,
            track=True,
        )

        edtech_multiplier = self.telemetry.calculate_edtech_multiplier(
            actual_cost=savings.actual_cost,
            baseline_cost=savings.baseline_cost,
        )

        impact_metrics = {
            "actual_cost": savings.actual_cost,
            "baseline_cost": savings.baseline_cost,
            "dollars_saved": savings.dollars_saved,
            "savings_pct": savings.savings_pct,
            "edtech_multiplier": edtech_multiplier,
            "input_tokens": in_tokens,
            "output_tokens": out_tokens,
        }
        if fallback_triggered and fallback_reason:
            impact_metrics["fallback_reason"] = fallback_reason

        return {
            "response_text": response_text,
            "tier": tier,
            "initial_model": initial_model,
            "final_model": final_model,
            "fallback_triggered": fallback_triggered,
            "latency_ms": round(total_latency_ms, 2),
            "impact_metrics": impact_metrics,
        }
