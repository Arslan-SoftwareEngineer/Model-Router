"""Engine package for Model Router."""

from engine.model_client import generate, ModelClient, SUPPORTED_MODELS
from engine.telemetry import (
    TelemetryTracker,
    SavingsResult,
    PRICING_PER_1M,
    BASELINE_MODEL,
    calculate_edtech_multiplier,
)
from engine.router import ProductionRouter, TIER_MODEL_MAP, FALLBACK_MODEL

__all__ = [
    "generate",
    "ModelClient",
    "SUPPORTED_MODELS",
    "ProductionRouter",
    "TIER_MODEL_MAP",
    "FALLBACK_MODEL",
    "TelemetryTracker",
    "SavingsResult",
    "PRICING_PER_1M",
    "BASELINE_MODEL",
    "calculate_edtech_multiplier",
]
