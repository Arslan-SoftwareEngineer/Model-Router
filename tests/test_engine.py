"""Unit and integration test suite for engine/model_client.py and engine/telemetry.py."""

import math
import os
import sys

# Ensure repository root is in Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.model_client import generate, ModelClient, SUPPORTED_MODELS
from engine.telemetry import (
    TelemetryTracker,
    PRICING_PER_1M,
    BASELINE_MODEL,
    calculate_edtech_multiplier,
)


def test_pricing_table():
    """Verify exact pricing per 1M tokens matches specifications."""
    print("--> Testing exact pricing table definitions...")
    expected_pricing = {
        "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
        "qwen/qwen3.8-27b": {"input": 0.80, "output": 4.00},
        "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
        "Frontier Baseline (GPT-4o proxy)": {"input": 2.50, "output": 10.00},
    }

    for model, rates in expected_pricing.items():
        assert model in PRICING_PER_1M, f"Model {model} missing from PRICING_PER_1M"
        assert math.isclose(PRICING_PER_1M[model]["input"], rates["input"]), (
            f"Input price mismatch for {model}: {PRICING_PER_1M[model]['input']} != {rates['input']}"
        )
        assert math.isclose(PRICING_PER_1M[model]["output"], rates["output"]), (
            f"Output price mismatch for {model}: {PRICING_PER_1M[model]['output']} != {rates['output']}"
        )

    print(" [PASS] Pricing table is 100% compliant with specifications.")


def test_model_client_generate():
    """Verify generate function works across all models with latency & safe fallback."""
    print("--> Testing model_client.generate across supported models...")
    for model_name in SUPPORTED_MODELS:
        res = generate(
            model_name=model_name,
            prompt="Explain the difference between supervised and unsupervised learning.",
            system_prompt="You are a helpful tutor.",
        )

        assert isinstance(res, dict), "Response must be a dict"
        assert "text" in res and isinstance(res["text"], str) and len(res["text"]) > 0, "Missing or invalid 'text'"
        assert "latency_ms" in res and isinstance(res["latency_ms"], float) and res["latency_ms"] > 0, "Invalid latency_ms"
        assert "input_tokens" in res and isinstance(res["input_tokens"], int) and res["input_tokens"] > 0, "Invalid input_tokens"
        assert "output_tokens" in res and isinstance(res["output_tokens"], int) and res["output_tokens"] > 0, "Invalid output_tokens"
        assert res["model"] == model_name, f"Model mismatch: {res['model']} != {model_name}"

        print(
            f"  * [{model_name}] latency: {res['latency_ms']}ms, "
            f"tokens in/out: {res['input_tokens']}/{res['output_tokens']}"
        )

    # Test class wrapper
    client = ModelClient()
    class_res = client.generate("llama-3.1-8b-instant", "Quick test")
    assert class_res["model"] == "llama-3.1-8b-instant"

    print(" [PASS] Model client generate works seamlessly with fallback and metrics.")


def test_telemetry_calculations():
    """Assert savings and EdTech multiplier math against exact analytical values."""
    print("--> Testing TelemetryTracker calculations and math assertions...")
    tracker = TelemetryTracker()

    in_tokens = 10_000
    out_tokens = 2_000
    model = "llama-3.1-8b-instant"

    # Expected values:
    # actual_cost = (10000 * 0.05 + 2000 * 0.08) / 1_000_000 = (500 + 160) / 1,000_000 = 0.00066
    # baseline_cost = (10000 * 2.50 + 2000 * 10.00) / 1_000_000 = (25000 + 20000) / 1_000_000 = 0.045
    # dollars_saved = 0.045 - 0.00066 = 0.04434
    # savings_pct = (0.04434 / 0.045) * 100 = 98.5333... %
    # edtech_multiplier = 0.045 / max(0.00066, 0.000001) = 68.1818...x

    expected_actual = 0.00066
    expected_baseline = 0.045
    expected_saved = 0.04434
    expected_pct = (expected_saved / expected_baseline) * 100.0
    expected_multiplier = expected_baseline / max(expected_actual, 0.000001)

    # 1. Test unpackability: actual_cost, baseline_cost, dollars_saved, savings_pct
    actual_cost, baseline_cost, dollars_saved, savings_pct = tracker.calculate_savings(
        model, in_tokens, out_tokens
    )

    assert math.isclose(actual_cost, expected_actual, rel_tol=1e-7), f"Actual cost {actual_cost} != {expected_actual}"
    assert math.isclose(baseline_cost, expected_baseline, rel_tol=1e-7), f"Baseline cost {baseline_cost} != {expected_baseline}"
    assert math.isclose(dollars_saved, expected_saved, rel_tol=1e-7), f"Dollars saved {dollars_saved} != {expected_saved}"
    assert math.isclose(savings_pct, expected_pct, rel_tol=1e-4), f"Savings pct {savings_pct} != {expected_pct}"

    # 2. Test EdTech multiplier
    query_multiplier = tracker.calculate_edtech_multiplier(actual_cost, baseline_cost)
    assert math.isclose(query_multiplier, expected_multiplier, rel_tol=1e-4), (
        f"EdTech multiplier {query_multiplier} != {expected_multiplier}"
    )

    standalone_multiplier = calculate_edtech_multiplier(actual_cost, baseline_cost)
    assert math.isclose(standalone_multiplier, expected_multiplier, rel_tol=1e-4)

    # 3. Test cumulative session tracking
    assert tracker.total_queries == 1
    assert math.isclose(tracker.total_spend, expected_actual, rel_tol=1e-7)
    assert math.isclose(tracker.cumulative_baseline_spend, expected_baseline, rel_tol=1e-7)

    # Run a second query with qwen/qwen3.8-27b
    # 5,000 in, 1,000 out:
    # qwen actual: (5000 * 0.80 + 1000 * 4.00) / 1M = (4000 + 4000) / 1M = 0.008
    # baseline: (5000 * 2.50 + 1000 * 10.00) / 1M = (12500 + 10000) / 1M = 0.0225
    q_actual, q_base, q_saved, q_pct = tracker.calculate_savings("qwen/qwen3.8-27b", 5_000, 1_000)
    assert math.isclose(q_actual, 0.008, rel_tol=1e-7)
    assert math.isclose(q_base, 0.0225, rel_tol=1e-7)

    # Cumulative verification
    assert tracker.total_queries == 2
    assert math.isclose(tracker.total_spend, expected_actual + 0.008, rel_tol=1e-7)
    assert math.isclose(tracker.cumulative_baseline_spend, expected_baseline + 0.0225, rel_tol=1e-7)

    # Cumulative session multiplier:
    session_mult = tracker.calculate_edtech_multiplier()
    expected_session_mult = (expected_baseline + 0.0225) / (expected_actual + 0.008)
    assert math.isclose(session_mult, expected_session_mult, rel_tol=1e-4)

    summary = tracker.get_session_summary()
    assert summary["total_queries"] == 2
    assert math.isclose(summary["edtech_multiplier"], expected_session_mult, rel_tol=1e-4)

    print(f"  * Query 1 Savings: {savings_pct:.2f}% | EdTech Multiplier: {query_multiplier:.1f}x students")
    print(f"  * Cumulative Session Spend: ${tracker.total_spend:.6f} vs Baseline ${tracker.cumulative_baseline_spend:.6f}")
    print(f"  * Overall Session EdTech Multiplier: {session_mult:.1f}x students")
    print(" [PASS] Telemetry math and cumulative session assertions passed perfectly.")


def test_end_to_end_integration():
    """Generate responses using model_client and feed telemetry in real-time."""
    print("--> Testing end-to-end integration: generate() -> calculate_savings()...")
    tracker = TelemetryTracker()

    models = ["llama-3.1-8b-instant", "llama-3.3-70b-versatile"]
    for model in models:
        resp = generate(
            model_name=model,
            prompt="What is the capital of France and why is it culturally significant?",
        )
        savings = tracker.calculate_savings(
            model_name=resp["model"],
            in_tokens=resp["input_tokens"],
            out_tokens=resp["output_tokens"],
        )
        mult = tracker.calculate_edtech_multiplier(savings.actual_cost, savings.baseline_cost)
        print(
            f"  * Generated via {resp['model']}: in={resp['input_tokens']}, out={resp['output_tokens']}, "
            f"latency={resp['latency_ms']}ms, cost=${savings.actual_cost:.6f}, saved=${savings.dollars_saved:.6f} "
            f"({savings.savings_pct:.1f}%), edtech={mult:.1f}x"
        )

    assert tracker.total_queries == len(models)
    print(" [PASS] End-to-end integration verified successfully.")


if __name__ == "__main__":
    test_pricing_table()
    test_model_client_generate()
    test_telemetry_calculations()
    test_end_to_end_integration()
    print("\n==========================================")
    print("ALL TESTS PASSED SUCCESSFULLY! (100% GREEN)")
    print("==========================================")
