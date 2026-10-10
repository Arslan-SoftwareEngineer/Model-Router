"""Educational query classification infrastructure.

Classifies incoming student/educational prompts into 3 distinct complexity tiers:
- Tier 1: Factual Recall & Simple Definitions -> Meta fast SLM (llama-3.1-8b-instant)
- Tier 2: Conceptual Explanation & Structured Synthesis -> Alibaba structured synthesis (qwen/qwen3.8-27b)
- Tier 3: Complex Multi-step Reasoning & Proofs -> Speculative fast attempt (llama-3.1-8b-instant)
          escalating to Frontier-class reasoning (llama-3.3-70b-versatile)
"""

from __future__ import annotations

import re
from typing import Any, Dict


class EducationalQueryClassifier:
    """Classifies educational queries into operational tiers."""

    # Keywords indicative of Tier 3 (Complex Multi-step Reasoning / Proofs / Derivations)
    TIER_3_PATTERNS = [
        r"\bprove\b",
        r"\bproof\b",
        r"\bderive\b",
        r"\bderivation\b",
        r"\binduction\b",
        r"\btheorem\b",
        r"\bcalculate the integral\b",
        r"\bdifferential equation\b",
        r"\bmulti-step\b",
        r"\bcomplex reasoning\b",
        r"\balgorithmic complexity\b",
        r"\bstep-by-step mathematical\b",
        r"\bformal verification\b",
    ]

    # Keywords indicative of Tier 2 (Conceptual Explanation / Synthesis / Comparison)
    TIER_2_PATTERNS = [
        r"\bexplain\b",
        r"\bcompare\b",
        r"\bcontrast\b",
        r"\bdifference between\b",
        r"\bsummarize\b",
        r"\bhow does\b",
        r"\bwhy does\b",
        r"\bpros and cons\b",
        r"\boverview\b",
        r"\bbreak down\b",
        r"\banalyze\b",
        r"\bstructure of\b",
    ]

    def classify(self, prompt: str) -> int:
        """Classify prompt and return tier (1, 2, or 3).

        Args:
            prompt: Student query or educational prompt.

        Returns:
            int: 1 for factual/recall, 2 for conceptual/synthesis, 3 for complex reasoning.
        """
        clean_text = prompt.lower().strip()

        # Check Tier 3 indicators
        for pattern in self.TIER_3_PATTERNS:
            if re.search(pattern, clean_text):
                return 3

        # Check Tier 2 indicators
        for pattern in self.TIER_2_PATTERNS:
            if re.search(pattern, clean_text):
                return 2

        # Check prompt length heuristics: very long complex prompts default to Tier 2 or 3
        words = clean_text.split()
        if len(words) > 60:
            return 3
        elif len(words) > 25:
            return 2

        # Default to Tier 1 (fast factual recall / definition)
        return 1

    def classify_with_metadata(self, prompt: str) -> Dict[str, Any]:
        """Classify prompt with rich metadata for debugging and telemetry."""
        tier = self.classify(prompt)
        tier_names = {
            1: "Tier 1: Factual Recall / Fast SLM",
            2: "Tier 2: Conceptual Explanation / Structured Synthesis",
            3: "Tier 3: Complex Multi-step Reasoning / Deep Proof",
        }
        target_models = {
            1: "llama-3.1-8b-instant",
            2: "qwen/qwen3.8-27b",
            3: "llama-3.1-8b-instant (speculative) -> llama-3.3-70b-versatile (fallback)",
        }
        return {
            "tier": tier,
            "tier_name": tier_names[tier],
            "target_model": target_models[tier],
            "prompt_length_words": len(prompt.split()),
        }
