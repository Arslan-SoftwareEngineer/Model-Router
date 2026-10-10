"""Terminal test demonstrating ProductionRouter capabilities.

Demonstrates:
(1) Tier 1 direct routing to Llama-8B (Factual recall)
(2) Tier 2 direct routing to Qwen-27B (Conceptual explanation & structured synthesis)
(3) Tier 3 speculative execution failing verifier and escalating to Llama-70B
"""

import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.router import ProductionRouter


def run_demonstration():
    print("=" * 80)
    print("🚀 PRODUCTION ROUTER DEMONSTRATION & TEST SUITE")
    print("=" * 80)

    router = ProductionRouter()

    # -------------------------------------------------------------------------
    # DEMO 1: Tier 1 Direct Routing -> Llama-8B (Meta Fast SLM)
    # -------------------------------------------------------------------------
    print("\n[SCENARIO 1] Tier 1: Factual Recall Query")
    tier1_prompt = "What is the speed of light in a vacuum and who first measured it?"
    print(f"Prompt: \"{tier1_prompt}\"")

    res1 = router.route_and_execute(tier1_prompt)

    print(f"  -> Detected Tier:       {res1['tier']} (Factual Recall)")
    print(f"  -> Initial Model:       {res1['initial_model']}")
    print(f"  -> Final Model:         {res1['final_model']}")
    print(f"  -> Fallback Triggered:  {res1['fallback_triggered']}")
    print(f"  -> Latency:             {res1['latency_ms']} ms")
    print(f"  -> Cost / Savings:      Actual: ${res1['impact_metrics']['actual_cost']:.6f} | "
          f"Baseline: ${res1['impact_metrics']['baseline_cost']:.6f} | "
          f"Saved: {res1['impact_metrics']['savings_pct']:.1f}%")
    print(f"  -> EdTech Multiplier:   {res1['impact_metrics']['edtech_multiplier']:.1f}x students on same budget")

    # Assertions for Scenario 1
    assert res1["tier"] == 1, f"Expected Tier 1, got {res1['tier']}"
    assert res1["initial_model"] == "llama-3.1-8b-instant"
    assert res1["final_model"] == "llama-3.1-8b-instant"
    assert res1["fallback_triggered"] is False
    print("  [SUCCESS] Tier 1 directly routed to Llama-8B without fallback escalation.")

    # -------------------------------------------------------------------------
    # DEMO 2: Tier 2 Direct Routing -> Qwen-27B (Alibaba Structured Synthesis)
    # -------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("[SCENARIO 2] Tier 2: Conceptual Explanation & Synthesis Query")
    tier2_prompt = "Explain the differences between mitosis and meiosis, highlighting stages and genetic outcomes."
    print(f"Prompt: \"{tier2_prompt}\"")

    res2 = router.route_and_execute(tier2_prompt)

    print(f"  -> Detected Tier:       {res2['tier']} (Conceptual Explanation & Synthesis)")
    print(f"  -> Initial Model:       {res2['initial_model']}")
    print(f"  -> Final Model:         {res2['final_model']}")
    print(f"  -> Fallback Triggered:  {res2['fallback_triggered']}")
    print(f"  -> Latency:             {res2['latency_ms']} ms")
    print(f"  -> Cost / Savings:      Actual: ${res2['impact_metrics']['actual_cost']:.6f} | "
          f"Baseline: ${res2['impact_metrics']['baseline_cost']:.6f} | "
          f"Saved: {res2['impact_metrics']['savings_pct']:.1f}%")
    print(f"  -> EdTech Multiplier:   {res2['impact_metrics']['edtech_multiplier']:.1f}x students on same budget")

    # Assertions for Scenario 2
    assert res2["tier"] == 2, f"Expected Tier 2, got {res2['tier']}"
    assert res2["initial_model"] == "qwen/qwen3.8-27b"
    assert res2["final_model"] == "qwen/qwen3.8-27b"
    assert res2["fallback_triggered"] is False
    print("  [SUCCESS] Tier 2 directly routed to Qwen-27B without fallback escalation.")

    # -------------------------------------------------------------------------
    # DEMO 3: Tier 3 Speculative Attempt Failing Verifier -> Escalate to Llama-70B
    # -------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("[SCENARIO 3] Tier 3: Complex Multi-step Proof failing Verifier & Escalating to Llama-70B")
    tier3_prompt = "Prove by mathematical induction that for all positive integers n, 1 + 2 + ... + n = n(n + 1)/2."
    print(f"Prompt: \"{tier3_prompt}\"")

    # In Tier 3, fast SLM attempts speculative execution; verification criteria fail and trigger escalation.
    res3 = router.route_and_execute(tier3_prompt, force_fallback_demo=False)

    print(f"  -> Detected Tier:       {res3['tier']} (Complex Multi-step Reasoning / Proof)")
    print(f"  -> Initial Model:       {res3['initial_model']} (Speculative fast attempt)")
    print(f"  -> Verification Status: FAILED (Heuristic checks identified insufficient depth)")
    print(f"  -> Fallback Triggered:  {res3['fallback_triggered']}")
    print(f"  -> Escalated Model:     {res3['final_model']} (Frontier-class reasoning model)")
    print(f"  -> Fallback Reason:     {res3['impact_metrics'].get('fallback_reason')}")
    print(f"  -> Cumulative Latency:  {res3['latency_ms']} ms")
    print(f"  -> Cost / Savings:      Actual: ${res3['impact_metrics']['actual_cost']:.6f} | "
          f"Baseline: ${res3['impact_metrics']['baseline_cost']:.6f} | "
          f"Saved: {res3['impact_metrics']['savings_pct']:.1f}%")
    print(f"  -> EdTech Multiplier:   {res3['impact_metrics']['edtech_multiplier']:.1f}x students on same budget")

    # Assertions for Scenario 3
    assert res3["tier"] == 3, f"Expected Tier 3, got {res3['tier']}"
    assert res3["initial_model"] == "llama-3.1-8b-instant"
    assert res3["final_model"] == "llama-3.3-70b-versatile"
    assert res3["fallback_triggered"] is True
    print("  [SUCCESS] Tier 3 speculative attempt failed verification and successfully escalated to Llama-70B.")

    # -------------------------------------------------------------------------
    # Bonus Check: Explicit force_fallback_demo flag test
    # -------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("[SCENARIO 4] Explicit force_fallback_demo=True Test on Tier 1 Prompt")
    res_forced = router.route_and_execute("What is DNA?", force_fallback_demo=True)
    assert res_forced["fallback_triggered"] is True
    assert res_forced["final_model"] == "llama-3.3-70b-versatile"
    print("  [SUCCESS] force_fallback_demo=True correctly forced verification failure and escalated.")

    # -------------------------------------------------------------------------
    # Session Telemetry Summary
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("📊 CUMULATIVE ROUTER SESSION TELEMETRY")
    print("=" * 80)
    summary = router.telemetry.get_session_summary()
    print(f"Total Routed Queries:             {summary['total_queries']}")
    print(f"Total Actual Spend:               ${summary['cumulative_spend']:.6f}")
    print(f"Total Frontier Baseline Spend:    ${summary['cumulative_baseline_spend']:.6f}")
    print(f"Total Net Dollars Saved:          ${summary['cumulative_dollars_saved']:.6f}")
    print(f"Overall Net Savings Percentage:   {summary['overall_savings_pct']:.2f}%")
    print(f"Overall EdTech Impact Multiplier: {summary['edtech_multiplier']:.1f}x more students supported")
    print("=" * 80)
    print("🎉 ALL 3 ROUTING AND FALLBACK SPECIFICATIONS VERIFIED 100% GREEN!\n")


if __name__ == "__main__":
    run_demonstration()
