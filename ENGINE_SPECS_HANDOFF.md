# Model Router Backend Infrastructure — Handover & Engineering Specifications

This document provides a technical specification of the backend infrastructure implemented in the `Model-Router` repository. It is designed for engineers, teammates, and AI agents continuing work on subsequent layers (such as `core/profiler.py`, `app/components.py`, and `app/main.py`).

---

### Environment Variables
| Variable | Required | Description | Default / Fallback |
| :--- | :--- | :--- | :--- |
| `GROQ_API_KEY` | Optional | Groq API authentication key | If absent or empty, the client switches to **safe mock fallback mode**. No exceptions or crashes are raised. |

---

## 1. Module Specifications: `engine/model_client.py`

### Role
Handles interaction with Groq LLM inference endpoints. Measures exact execution latency and guarantees system resilience with a mock fallback mechanism.

### Module Constants & Variables
- **`SUPPORTED_MODELS`** (`List[str]`):
  ```python
  SUPPORTED_MODELS = [
      "llama-3.1-8b-instant",
      "qwen/qwen3.8-27b",
      "llama-3.3-70b-versatile",
  ]
  ```
- **`_cached_client`** (`Any`): Internal singleton cache for the Groq client instance.
- **`client`** (`Optional[Groq]`): Module-level instance initialized at import time if `GROQ_API_KEY` is present.

### Functions & Classes

#### `get_groq_client() -> Any`
- **Purpose**: Reads `os.getenv("GROQ_API_KEY")`. If present and client is not yet instantiated, initializes and caches `Groq(api_key=...)`.
- **Returns**: `Groq` instance if API key is configured; otherwise `None`.

#### `generate(model_name: str, prompt: str, system_prompt: str = "") -> Dict[str, Any]`
- **Purpose**: Primary generation function. Invokes the Groq API or cleanly diverts to mock fallback.
- **Parameters**:
  - `model_name` (`str`): Target model name (one of `SUPPORTED_MODELS`).
  - `prompt` (`str`): User input prompt.
  - `system_prompt` (`str`, optional): System prompt / role instructions (defaults to `""`).
- **Return Schema (`dict`)**:
  ```python
  {
      "text": str,           # Generated response or safe mock fallback response
      "latency_ms": float,   # Wall-clock elapsed time in milliseconds (e.g. 15.42)
      "input_tokens": int,   # Prompt/system token count
      "output_tokens": int,  # Generated response token count
      "model": str           # The model identifier invoked
  }
  ```
- **Resilience Behavior**:
  - If `GROQ_API_KEY` is missing or invalid: returns simulated mock text with estimated tokens and wall-clock latency.
  - If Groq API throws any exception (e.g., `AuthenticationError`, `RateLimitError`, connection timeout): catches `Exception`, logs a warning, and returns the fallback payload with the error reason annotated. **The app never crashes.**

#### `ModelClient` (Class Wrapper)
- **Constructor**: `ModelClient(api_key: Optional[str] = None)`
  - If `api_key` is passed, writes to `os.environ["GROQ_API_KEY"]` and initializes client.
- **Method**: `generate(model_name: str, prompt: str, system_prompt: str = "") -> Dict[str, Any]`
  - Proxies directly to top-level `generate()`.

---

## 2. Module Specifications: `engine/telemetry.py`

### Role
Computes token spend, compares costs against a frontier model baseline (`GPT-4o proxy`), calculates budget savings and percentage, and tracks the EdTech impact multiplier.

### Pricing Definitions
Pricing is calibrated per **1,000,000 tokens (USD)**:

| Model Identifier | Input Rate ($/1M) | Output Rate ($/1M) |
| :--- | :--- | :--- |
| `llama-3.1-8b-instant` | **$0.05** | **$0.08** |
| `qwen/qwen3.8-27b` | **$0.80** | **$4.00** |
| `llama-3.3-70b-versatile` | **$0.59** | **$0.79** |
| `Frontier Baseline (GPT-4o proxy)` | **$2.50** | **$10.00** |

- **`PRICING_PER_1M`** (`Dict[str, Dict[str, float]]`): Global dictionary mapping model name to `{"input": float, "output": float}`.
- **`BASELINE_MODEL`** (`str`): Constant pointing to `"Frontier Baseline (GPT-4o proxy)"`.

---

### Mathematical Formulas

1. **Actual Cost**:
   $$\text{actual\_cost} = \frac{(\text{in\_tokens} \times \text{model\_input\_rate}) + (\text{out\_tokens} \times \text{model\_output\_rate})}{1{,}000{,}000}$$

2. **Baseline Cost** (Frontier Baseline proxy):
   $$\text{baseline\_cost} = \frac{(\text{in\_tokens} \times 2.50) + (\text{out\_tokens} \times 10.00)}{1{,}000{,}000}$$

3. **Dollars Saved**:
   $$\text{dollars\_saved} = \text{baseline\_cost} - \text{actual\_cost}$$

4. **Savings Percentage**:
   $$\text{savings\_pct} = \begin{cases} \left(\frac{\text{dollars\_saved}}{\text{baseline\_cost}}\right) \times 100 & \text{if } \text{baseline\_cost} > 0 \\ 0.0 & \text{otherwise} \end{cases}$$

5. **EdTech Multiplier**:
   $$\text{edtech\_multiplier} = \frac{\text{baseline\_cost}}{\max(\text{actual\_cost}, 0.000001)}$$
   *Meaning*: Number of times more students can be served on the exact same budget compared to using frontier models.

---

### Classes & Helper Functions

#### `SavingsResult` (`dict` Subclass)
A dual-mode data structure allowing dictionary indexing, property access, and tuple unpacking:
- **Dict access**: `result["actual_cost"]`, `result["savings_pct"]`
- **Attribute access**: `result.actual_cost`, `result.dollars_saved`
- **Tuple unpacking**:
  ```python
  actual_cost, baseline_cost, dollars_saved, savings_pct = tracker.calculate_savings(...)
  ```

#### `calculate_edtech_multiplier(actual_cost: float, baseline_cost: float) -> float`
- Standalone mathematical function computing $\frac{\text{baseline\_cost}}{\max(\text{actual\_cost}, 0.000001)}$.

#### `TelemetryTracker` (Class)
Manages per-query calculations and session-level telemetry accumulation.

- **State Variables**:
  - `self.total_queries: int` — Cumulative queries tracked in the session.
  - `self.cumulative_spend: float` — Cumulative actual spend ($ USD).
  - `self.cumulative_baseline_spend: float` — Cumulative baseline spend ($ USD).
  - `self.cumulative_dollars_saved: float` — Cumulative savings ($ USD).
  - `self.total_input_tokens: int` — Cumulative input tokens.
  - `self.total_output_tokens: int` — Cumulative output tokens.
  - `self.query_history: List[Dict[str, Any]]` — Ordered log of all tracked query metrics.
  - `self.total_spend` (Property): Alias for `self.cumulative_spend`.

- **Methods**:
  - `calculate_savings(model_name: str, in_tokens: int, out_tokens: int, track: bool = True) -> SavingsResult`
  - `calculate_edtech_multiplier(actual_cost: Optional[float] = None, baseline_cost: Optional[float] = None) -> float`
  - `get_session_summary() -> Dict[str, Any]`
  - `reset() -> None`

---

## 3. Module Specifications: `engine/router.py`

### Role
Wires query classification, multi-model execution, heuristic output verification, and automated fallback escalation.

### Tier Architecture Mapping
```python
TIER_MODEL_MAP = {
    1: "llama-3.1-8b-instant",  # Meta fast SLM (Factual recall / Definitions)
    2: "qwen/qwen3.8-27b",      # Alibaba structured synthesis (Explanations & Comparisons)
    3: "llama-3.1-8b-instant",  # Speculative fast attempt (Complex reasoning & Proofs)
}

FALLBACK_MODEL = "llama-3.3-70b-versatile"  # Frontier-class reasoning model
```

### Class `ProductionRouter`
- **Constructor**:
  ```python
  ProductionRouter(
      classifier: Optional[EducationalQueryClassifier] = None,
      verifier: Optional[LightweightVerifier] = None,
      model_client: Optional[ModelClient] = None,
      telemetry_tracker: Optional[TelemetryTracker] = None,
  )
  ```
- **Method**:
  ```python
  route_and_execute(prompt: str, force_fallback_demo: bool = False) -> Dict[str, Any]
  ```
  **Step-by-Step Flow**:
  1. **Classify**: Invokes `classifier.classify(prompt)` $\rightarrow$ Tier 1, 2, or 3.
  2. **Select Target Architecture**:
     - Tier 1: `llama-3.1-8b-instant`
     - Tier 2: `qwen/qwen3.8-27b`
     - Tier 3: `llama-3.1-8b-instant` (speculative fast attempt)
  3. **Execute Initial Inference**: Runs `model_client.generate(initial_model, prompt)`.
  4. **Output Verification**: Evaluates candidate response via `verifier.verify(prompt, response, tier)`. If `force_fallback_demo=True`, forces failure.
  5. **Automated Fallback Escalation**: If verification fails:
     - Immediately re-routes prompt to `llama-3.3-70b-versatile`.
     - Sets `fallback_triggered = True` and records diagnostic failure reason.
  6. **Telemetry & Impact**: Computes financial metrics via `telemetry.calculate_savings()` and records session stats.
  - **Return Schema**:
    ```python
    {
        "response_text": str,
        "tier": int,
        "initial_model": str,
        "final_model": str,
        "fallback_triggered": bool,
        "latency_ms": float,
        "impact_metrics": {
            "actual_cost": float,
            "baseline_cost": float,
            "dollars_saved": float,
            "savings_pct": float,
            "edtech_multiplier": float,
            "input_tokens": int,
            "output_tokens": int,
            "fallback_reason": Optional[str]
        }
    }
    ```

---

## 4. Module Specifications: `core` Components

### `core/classifer.py` & `core/classifier.py`
- **Class**: `EducationalQueryClassifier`
  - `classify(prompt: str) -> int`: Returns `1` (Factual), `2` (Conceptual), or `3` (Complex/Proof).
  - `classify_with_metadata(prompt: str) -> dict`: Returns tier, tier name, target model, word count.

### `core/verifier.py`
- **Classes**:
  - `VerificationResult(is_valid: bool, reason: str)`: Truthy/falsy object with diagnostic reason.
  - `LightweightVerifier(min_tier1_words: int = 3, min_tier2_words: int = 10, min_tier3_words: int = 40)`:
    - `verify(prompt: str, response: str, tier: int = 1, force_fail: bool = False, model_name: Optional[str] = None) -> VerificationResult`.
    - Evaluates minimum length, error markers, and proof structure for Tier 3 speculative attempts.

---

## 5. Module Specifications: `engine/__init__.py`

Enables clean package imports:
```python
from engine import (
    generate,
    ModelClient,
    SUPPORTED_MODELS,
    ProductionRouter,
    TIER_MODEL_MAP,
    FALLBACK_MODEL,
    TelemetryTracker,
    SavingsResult,
    PRICING_PER_1M,
    BASELINE_MODEL,
    calculate_edtech_multiplier,
)
```

---

## 6. Code Examples for Downstream Modules (Person 3 Guide)

### Example 1: Full Production Router Routing & Escalation
```python
from engine import ProductionRouter

router = ProductionRouter()

# Scenario A: Tier 1 Factual
result_1 = router.route_and_execute("What is the boiling point of water?")
print(f"Tier: {result_1['tier']}, Model: {result_1['final_model']}")
# -> Tier: 1, Model: llama-3.1-8b-instant

# Scenario B: Tier 2 Conceptual
result_2 = router.route_and_execute("Explain the difference between renewable and non-renewable energy.")
print(f"Tier: {result_2['tier']}, Model: {result_2['final_model']}")
# -> Tier: 2, Model: qwen/qwen3.8-27b

# Scenario C: Tier 3 Complex Proof (Speculative attempt -> Escalates to 70B)
result_3 = router.route_and_execute("Prove by mathematical induction that 1 + 2 + ... + n = n(n+1)/2.")
print(f"Tier: {result_3['tier']}, Final Model: {result_3['final_model']}, Fallback: {result_3['fallback_triggered']}")
# -> Tier: 3, Final Model: llama-3.3-70b-versatile, Fallback: True
```

### Example 2: Inspecting Financial Impact & EdTech Multiplier
```python
metrics = result_1["impact_metrics"]
print(f"Cost: ${metrics['actual_cost']:.6f} vs Baseline ${metrics['baseline_cost']:.6f}")
print(f"Saved: {metrics['savings_pct']:.1f}%")
print(f"EdTech Multiplier: {metrics['edtech_multiplier']:.1f}x students on same budget")
```

---

## 7. Test Suites & Verification

### Running All Tests
From the workspace root directory:
```bash
# 1. Model client and telemetry test suite
python3 tests/test_engine.py

# 2. Production router, classification, verification, and fallback test suite
python3 tests/test_router.py
```
