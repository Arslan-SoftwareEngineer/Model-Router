<<<<<<< HEAD
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
=======
"""
core/classifier.py
Educational Query Classifier for dynamic model routing.

Classifies incoming student queries into compute tiers based on complexity,
intent, and structural indicators within a <15ms latency budget.
"""

import re
import time
from typing import Dict, Any


class EducationalQueryClassifier:
    """
    Ultra-fast rule and heuristic classifier for educational queries.
    Routes queries to Micro (Tier 1), Mid (Tier 2), or Heavy (Tier 3) model backends.
    """

    # Tier 3 (Heavy / STEM_REASONING) patterns
    _CODE_FENCE_PATTERN = re.compile(r"```|~~~")
    _CODE_SYNTAX_PATTERN = re.compile(
        r"\b(?:def\s+|class\s+|import\s+|return\b|console\.log|function\s+\w+|=>\s*\{|big-o|complexity)\b",
        re.IGNORECASE
    )
    _CODE_REQUEST_PATTERN = re.compile(
        r"\b(?:write\s+(?:a\s+)?(?:python|javascript|java|c\+\+|code|script|function|program)|code\s+for|algorithm\s+for|binary\s+search)\b",
        re.IGNORECASE
    )
    _LATEX_MATH_PATTERN = re.compile(
        r"\$|\\(?:int|sum|frac|sqrt|partial|lim|alpha|beta|theta|pi|infty|times|div|pm|leq|geq|neq)\b",
        re.IGNORECASE
    )
    _STEM_KEYWORDS_PATTERN = re.compile(
        r"\b(?:solve|proof|calculate|integral|derivative|calculus|equation|matrices|matrix|theorem|prove|computation|algorithm|complexity)\b",
        re.IGNORECASE
    )

    # Tier 2 (Mid / CONCEPT_SYNTHESIS) patterns
    _TIER2_KEYWORDS_PATTERN = re.compile(
        r"\b(?:summarize|summary|summarise|explain|explanation|compare|comparison|essay|curriculum|differentiate|analyze|analysis|overview)\b",
        re.IGNORECASE
    )

    # Tier 1 (Micro / FACTUAL_VOCAB) patterns
    _TIER1_KEYWORDS_PATTERN = re.compile(
        r"\b(?:define|definition|flashcard|flashcards|vocabulary|vocab|synonym|synonyms|antonym|antonyms|meaning|spell|spelling)\b",
        re.IGNORECASE
    )
    _TIER1_PHRASES_PATTERN = re.compile(
        r"\bwhat\s+(?:is|are|was|were)\b|\bwho\s+(?:is|was)\b",
        re.IGNORECASE
    )

    def __init__(self) -> None:
        pass

    def classify(self, prompt: str) -> Dict[str, Any]:
        """
        Classifies an educational query prompt into one of three compute tiers.

        - Tier 1 (Micro): Word count < 40, keywords like 'define', 'flashcard',
          'vocabulary', 'synonym', 'what is'. Intent: "FACTUAL_VOCAB".
        - Tier 2 (Mid): Keywords like 'summarize', 'explain', 'compare', 'essay',
          'curriculum', or word count between 40 and 120 without math/code. Intent: "CONCEPT_SYNTHESIS".
        - Tier 3 (Heavy): Code blocks, Python/JS syntax ('def ', 'class ', 'import ', 'return'),
          LaTeX/Math symbols ('$', '\\int', 'solve', 'proof', 'calculate', 'integral').
          Intent: "STEM_REASONING".

        Returns:
            dict: {"tier": int, "intent": str, "latency_ms": float}
        """
        start_time = time.perf_counter()

        text = prompt.strip() if prompt else ""
        words = text.split()
        word_count = len(words)

        # 1. Tier 3 Evaluation (Heavy: STEM / Code / Formal Math)
        # STEM queries take top priority because math/code reasoning requires heavy models
        if self._is_stem_reasoning(text):
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return {
                "tier": 3,
                "intent": "STEM_REASONING",
                "latency_ms": round(elapsed_ms, 3),
            }

        # 2. Check keyword triggers for Tier 2 and Tier 1
        has_tier2_kw = bool(self._TIER2_KEYWORDS_PATTERN.search(text))
        has_tier1_kw = bool(
            self._TIER1_KEYWORDS_PATTERN.search(text)
            or self._TIER1_PHRASES_PATTERN.search(text)
        )

        # 3. Disambiguate Tier 1 vs Tier 2
        # If Tier 2 keywords ('summarize', 'explain', 'compare', 'essay', 'curriculum') are present:
        if has_tier2_kw:
            tier = 2
            intent = "CONCEPT_SYNTHESIS"
        # If Tier 1 keywords and word count < 40:
        elif has_tier1_kw and word_count < 40:
            tier = 1
            intent = "FACTUAL_VOCAB"
        # Word count between 40 and 120 without math/code:
        elif 40 <= word_count <= 120:
            tier = 2
            intent = "CONCEPT_SYNTHESIS"
        # Word count < 40 without explicit Tier 2 keywords:
        elif word_count < 40:
            tier = 1
            intent = "FACTUAL_VOCAB"
        # Longer essays / queries (> 120 words without code/math):
        else:
            tier = 2
            intent = "CONCEPT_SYNTHESIS"

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return {
            "tier": tier,
            "intent": intent,
            "latency_ms": round(elapsed_ms, 3),
        }

    def _is_stem_reasoning(self, text: str) -> bool:
        """Detects whether prompt contains code, math symbols, or STEM reasoning triggers."""
        if not text:
            return False

        # Code fences
        if self._CODE_FENCE_PATTERN.search(text):
            return True

        # Python/JS syntax indicators ('def ', 'class ', 'import ', 'return', 'complexity', etc.)
        if self._CODE_SYNTAX_PATTERN.search(text):
            return True

        # Code or algorithm requests ('write a python function', 'code for', etc.)
        if self._CODE_REQUEST_PATTERN.search(text):
            return True

        # LaTeX or explicit math symbols ('$', '\int', etc.)
        if self._LATEX_MATH_PATTERN.search(text):
            return True

        # STEM keywords ('solve', 'proof', 'calculate', 'integral', etc.)
        if self._STEM_KEYWORDS_PATTERN.search(text):
            return True

        return False
>>>>>>> cb891aa (Added Core folder files)
