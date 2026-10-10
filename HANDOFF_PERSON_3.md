# Comprehensive System Handoff & Architecture Specifications (Person 3 AI Sync)

> **Document Purpose**: This markdown file is a complete, standalone reference of the entire backend infrastructure built for the **Model-Router** system. Hand this file directly to Person 3 (or provide it as the system context to Person 3's AI model) so they can understand every module, class, method, variable, mathematical formula, return schema, and test suite without any guesswork.

---

## 1. Project Directory Manifest

All files currently created and active in the repository:

```text
/home/slay_king/Documents/Model-Router/root/
├── .env                              # (Optional) Environment variables (GROQ_API_KEY)
├── .gitignore                        # Git ignore rules for Python bytecode and env files
├── HANDOFF_PERSON_3.md               # [THIS FILE] Complete handoff specification
├── ENGINE_SPECS_HANDOFF.md           # Handoff documentation
│
├── engine/
│   ├── __init__.py                   # Engine package exports
│   ├── model_client.py               # Groq LLM API wrapper, latency tracking & mock fallback
│   ├── telemetry.py                  # Token pricing, budget savings & EdTech multiplier
│   └── router.py                     # ProductionRouter (Tier classification, routing, fallback)
│
├── core/
│   ├── __init__.py                   # Core package exports
│   ├── classifer.py                  # EducationalQueryClassifier (Tier 1, 2, 3 classification)
│   ├── classifier.py                 # Clean alias import for classifer.py
│   ├── verifier.py                   # LightweightVerifier & VerificationResult
│   └── profiler.py                   # [Open for Person 3] Latency / throughput profiler
│
├── app/
│   ├── components.py                 # [Open for Person 3] Streamlit / Web UI components
│   └── main.py                       # [Open for Person 3] Application entry point
│
└── tests/
    ├── test_engine.py                # Unit & analytical tests for model_client & telemetry
    └── test_router.py                # End-to-end integration tests for routing & fallback tiers
```

---

## 2. Environment & Dependencies

### Python Version & Dependencies
- **Python**: `>= 3.10` (tested on Python 3.14)
- **Pip packages installed**:
  ```bash
  pip install groq python-dotenv
  ```

### Environment Variables
| Variable | Type | Required? | Behavior |
| :--- | :--- | :--- | :--- |
| `GROQ_API_KEY` | `str` | Optional | If present: live calls are made to Groq Cloud API.<br>If absent/empty: all calls automatically use **safe mock fallback mode**. The application **never** crashes or throws unhandled exceptions. |

---

## 3. Detailed File-by-File Technical Specifications

---

### File 1: `engine/model_client.py`
*Path*: `engine/model_client.py`  
*Role*: Low-level LLM inference client interfacing with Groq API, with latency measurement and mock fallback.

#### Module-Level Variables & Constants
| Variable Name | Type | Value / Default | Description |
| :--- | :--- | :--- | :--- |
| `SUPPORTED_MODELS` | `List[str]` | `["llama-3.1-8b-instant", "qwen/qwen3.8-27b", "llama-3.3-70b-versatile"]` | List of supported model identifiers. |
| `_cached_client` | `Any` | `None` | Internal singleton cache for the initialized `groq.Groq` client. |
| `client` | `Optional[Groq]` | `get_groq_client()` | Module-level Groq client instance initialized if `GROQ_API_KEY` exists. |

#### Functions

##### `get_groq_client() -> Any`
- **Arguments**: None.
- **Returns**: `Groq` instance if `GROQ_API_KEY` is present and valid; otherwise `None`.
- **Logic**: Inspects `os.getenv("GROQ_API_KEY")`. If found and `_cached_client` is `None`, creates `groq.Groq(api_key=...)`. Catches any initialization exception safely.

##### `_mock_generate(model_name: str, prompt: str, system_prompt: str = "", start_time: Optional[float] = None, note: str = "GROQ_API_KEY not configured") -> Dict[str, Any]`
- **Arguments**:
  - `model_name` (`str`): Target model name.
  - `prompt` (`str`): Prompt text.
  - `system_prompt` (`str`): Optional system prompt.
  - `start_time` (`Optional[float]`): `perf_counter` timestamp.
  - `note` (`str`): Diagnostic reason for fallback.
- **Returns**: `dict` conforming to the standard generate schema.
- **Logic**: Simulates realistic ~5ms delay, calculates word-based token estimates, and returns formatted fallback response text.

##### `generate(model_name: str, prompt: str, system_prompt: str = "") -> Dict[str, Any]`
- **Arguments**:
  - `model_name` (`str`): Identifier of the model to query.
  - `prompt` (`str`): User / student prompt.
  - `system_prompt` (`str`): Optional system prompt (default `""`).
- **Returns (`dict`)**:
  ```python
  {
      "text": str,           # Completion response text (or safe fallback text)
      "latency_ms": float,   # Wall-clock latency in milliseconds (e.g., 5.12)
      "input_tokens": int,   # Number of prompt + system tokens
      "output_tokens": int,  # Number of generated tokens
      "model": str           # Model identifier invoked
  }
  ```
- **Error Handling**:
  - If `GROQ_API_KEY` is missing $\rightarrow$ routes to `_mock_generate`.
  - If Groq API raises `AuthenticationError`, `RateLimitError`, `APIConnectionError`, etc. $\rightarrow$ catches `Exception`, logs a warning, and returns `_mock_generate` with the exception name documented.

#### Classes

##### `class ModelClient`
Convenience class wrapping `generate()`.
- **`__init__(self, api_key: Optional[str] = None)`**:
  - Sets `os.environ["GROQ_API_KEY"] = api_key` if `api_key` is passed.
  - Populates `self.client = get_groq_client()`.
- **`generate(self, model_name: str, prompt: str, system_prompt: str = "") -> Dict[str, Any]`**:
  - Forwards call directly to module-level `generate()`.

---

### File 2: `engine/telemetry.py`
*Path*: `engine/telemetry.py`  
*Role*: Accurate token cost calculation, budget comparison against frontier model baseline, EdTech impact calculation, and cumulative session spend tracking.

#### Module-Level Variables & Constants
- **`PRICING_PER_1M: Dict[str, Dict[str, float]]`**:
  Exact pricing per 1,000,000 tokens (USD):
  ```python
  PRICING_PER_1M = {
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
  ```
- **`BASELINE_MODEL: str = "Frontier Baseline (GPT-4o proxy)"`**:
  Reference standard for cost savings and EdTech multiplier.

#### Mathematical Formulas
1. **Actual Cost**:
   $$\text{actual\_cost} = \frac{(\text{in\_tokens} \times \text{model\_input\_rate}) + (\text{out\_tokens} \times \text{model\_output\_rate})}{1{,}000{,}000}$$
2. **Baseline Cost**:
   $$\text{baseline\_cost} = \frac{(\text{in\_tokens} \times 2.50) + (\text{out\_tokens} \times 10.00)}{1{,}000{,}000}$$
3. **Dollars Saved**:
   $$\text{dollars\_saved} = \text{baseline\_cost} - \text{actual\_cost}$$
4. **Savings Percentage**:
   $$\text{savings\_pct} = \begin{cases} \left(\frac{\text{dollars\_saved}}{\text{baseline\_cost}}\right) \times 100 & \text{if } \text{baseline\_cost} > 0 \\ 0.0 & \text{otherwise} \end{cases}$$
5. **EdTech Multiplier**:
   $$\text{edtech\_multiplier} = \frac{\text{baseline\_cost}}{\max(\text{actual\_cost}, 0.000001)}$$
   *(Meaning: How many times more students can be served on the exact same budget compared to using GPT-4o).*

#### Classes & Functions

##### `class SavingsResult(dict)`
Dictionary subclass holding cost calculation metrics. Supports:
- Dict lookup: `res["actual_cost"]`, `res["baseline_cost"]`, `res["dollars_saved"]`, `res["savings_pct"]`
- Object attributes: `res.actual_cost`, `res.baseline_cost`, `res.dollars_saved`, `res.savings_pct`
- Direct tuple unpacking:
  ```python
  actual_cost, baseline_cost, dollars_saved, savings_pct = tracker.calculate_savings(...)
  ```

##### `calculate_edtech_multiplier(actual_cost: float, baseline_cost: float) -> float`
Standalone function returning `baseline_cost / max(actual_cost, 0.000001)`.

##### `class TelemetryTracker`
Tracks per-query and cumulative session metrics.
- **Instance Attributes**:
  | Attribute | Type | Initial Value | Description |
  | :--- | :--- | :--- | :--- |
  | `self.pricing` | `Dict[str, Dict[str, float]]` | `PRICING_PER_1M` | Configured pricing lookup table. |
  | `self.baseline_model` | `str` | `BASELINE_MODEL` | Reference model identifier. |
  | `self.total_queries` | `int` | `0` | Cumulative count of queries executed. |
  | `self.cumulative_spend` | `float` | `0.0` | Total actual dollars spent in session. |
  | `self.cumulative_baseline_spend` | `float` | `0.0` | Total baseline dollars spent in session. |
  | `self.cumulative_dollars_saved` | `float` | `0.0` | Total dollars saved in session. |
  | `self.total_input_tokens` | `int` | `0` | Cumulative input tokens processed. |
  | `self.total_output_tokens` | `int` | `0` | Cumulative output tokens processed. |
  | `self.query_history` | `List[Dict[str, Any]]` | `[]` | Ordered list of query detail dicts. |
  | `self.total_spend` | `float` (property) | `self.cumulative_spend` | Read-only alias property for cumulative spend. |

- **Methods**:
  - `calculate_savings(self, model_name: str, in_tokens: int, out_tokens: int, track: bool = True) -> SavingsResult`:
    Computes query cost, baseline cost, dollars saved, and savings percentage. If `track=True`, increments all cumulative counters.
  - `calculate_edtech_multiplier(self, actual_cost: Optional[float] = None, baseline_cost: Optional[float] = None) -> float`:
    If arguments are omitted, computes the session-wide multiplier using cumulative totals. If arguments are passed, computes for those specific values.
  - `get_session_summary(self) -> Dict[str, Any]`:
    Returns:
    ```python
    {
        "total_queries": int,
        "cumulative_spend": float,
        "cumulative_baseline_spend": float,
        "cumulative_dollars_saved": float,
        "total_input_tokens": int,
        "total_output_tokens": int,
        "overall_savings_pct": float,
        "edtech_multiplier": float
    }
    ```
  - `reset(self) -> None`:
    Resets all cumulative counters to 0 and clears `query_history`.

---

### File 3: `core/classifer.py` & `core/classifier.py`
*Path*: `core/classifer.py` (with alias `core/classifier.py`)  
*Role*: Fast, deterministic heuristic tier classification of incoming student queries.

#### Class `EducationalQueryClassifier`
- **Class Attributes**:
  - `TIER_3_PATTERNS`: Regex patterns for mathematical proofs, induction, derivations, and multi-step algorithmic complexity (`r"\bprove\b"`, `r"\binduction\b"`, etc.).
  - `TIER_2_PATTERNS`: Regex patterns for explanations, comparisons, and structured overviews (`r"\bexplain\b"`, `r"\bcompare\b"`, `r"\bdifference between\b"`, etc.).
- **Methods**:
  - `classify(self, prompt: str) -> int`:
    - Returns `3` if prompt matches Tier 3 patterns or has $>60$ words.
    - Returns `2` if prompt matches Tier 2 patterns or has $>25$ words.
    - Returns `1` by default (simple factual recall, definitions, short Q&A).
  - `classify_with_metadata(self, prompt: str) -> Dict[str, Any]`:
    - Returns `{"tier": int, "tier_name": str, "target_model": str, "prompt_length_words": int}`.

---

### File 4: `core/verifier.py`
*Path*: `core/verifier.py`  
*Role*: Output verification to ensure generated responses satisfy educational pedagogical depth and rigor before reaching students.

#### Classes

##### `class VerificationResult`
- **`__init__(self, is_valid: bool, reason: str = "")`**
- **Attributes**: `self.is_valid: bool`, `self.reason: str`.
- **Dunder `__bool__(self) -> bool`**: Allows `if verification:` or `if not verification:`.
- **`to_dict(self) -> Dict[str, Any]`**: Returns `{"is_valid": bool, "reason": str}`.

##### `class LightweightVerifier`
- **`__init__(self, min_tier1_words: int = 3, min_tier2_words: int = 10, min_tier3_words: int = 40)`**
- **Method `verify(self, prompt: str, response: str, tier: int = 1, force_fail: bool = False, model_name: Optional[str] = None) -> VerificationResult`**:
  - If `force_fail=True`: returns `VerificationResult(is_valid=False, reason="Simulated verification failure (force_fallback_demo=True)")`.
  - If response is empty or contains error markers (`"[error]"`, etc.): returns `is_valid=False`.
  - If `tier == 1`: checks response has $\ge 3$ words.
  - If `tier == 2`: checks response has $\ge 10$ words.
  - If `tier == 3`: checks response has $\ge 40$ words AND contains step-by-step reasoning/proof markers (`"step"`, `"proof"`, `"therefore"`, `"induction"`). If speculative fast SLM attempt fails these depth requirements, returns `is_valid=False` with diagnostic failure reason.

---

### File 5: `engine/router.py`
*Path*: `engine/router.py`  
*Role*: Primary orchestration engine wiring classifier, multi-model execution, verifier, automated fallback escalation, and telemetry tracking.

#### Module-Level Variables & Constants
```python
TIER_MODEL_MAP: Dict[int, str] = {
    1: "llama-3.1-8b-instant",  # Meta fast SLM (Factual Recall & Definitions)
    2: "qwen/qwen3.8-27b",      # Alibaba structured synthesis (Conceptual Explanations)
    3: "llama-3.1-8b-instant",  # Speculative fast attempt (Complex Reasoning & Proofs)
}

FALLBACK_MODEL: str = "llama-3.3-70b-versatile"  # Frontier-class reasoning model
```

#### Class `ProductionRouter`
- **Constructor**:
  ```python
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
  ```
- **Method `route_and_execute(self, prompt: str, force_fallback_demo: bool = False) -> Dict[str, Any]`**:
  - **Step 1**: Classifies prompt $\rightarrow$ `tier` ($1$, $2$, or $3$).
  - **Step 2**: Selects `initial_model = TIER_MODEL_MAP[tier]`.
  - **Step 3**: Generates response via `self.model_client.generate(initial_model, prompt)`.
  - **Step 4**: Verifies output via `self.verifier.verify(prompt, response, tier, force_fail=force_fallback_demo)`.
  - **Step 5 (Fallback Escalation)**: If verification fails:
    - Sets `fallback_triggered = True` and records `fallback_reason`.
    - Immediately re-routes prompt to `final_model = "llama-3.3-70b-versatile"`.
    - Accumulates latency and token counts.
    - If verification passes: `fallback_triggered = False`, `final_model = initial_model`.
  - **Step 6**: Computes cost savings and updates telemetry tracker.
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
            "fallback_reason": Optional[str],
        },
    }
    ```

---

### File 6: `engine/__init__.py`
*Path*: `engine/__init__.py`  
*Role*: Clean package imports for the `engine` module.

```python
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
```

---

### File 7: `core/__init__.py`
*Path*: `core/__init__.py`  
*Role*: Clean package imports for the `core` module.

```python
from core.classifer import EducationalQueryClassifier
from core.verifier import LightweightVerifier, VerificationResult

__all__ = [
    "EducationalQueryClassifier",
    "LightweightVerifier",
    "VerificationResult",
]
```

---

## 4. How to Use & Integrate (Developer Guide for Person 3)

### Pattern 1: One-Line Production Router Execution
```python
from engine import ProductionRouter

router = ProductionRouter()

# Example: Run any prompt
output = router.route_and_execute("Explain the difference between DNA and RNA.")

print("Response:", output["response_text"])
print("Tier:", output["tier"])
print("Initial Model:", output["initial_model"])
print("Final Model:", output["final_model"])
print("Fallback Triggered:", output["fallback_triggered"])
print("Latency:", output["latency_ms"], "ms")
print("Cost:", f"${output['impact_metrics']['actual_cost']:.6f}")
print("Savings:", f"{output['impact_metrics']['savings_pct']:.1f}%")
print("EdTech Multiplier:", f"{output['impact_metrics']['edtech_multiplier']:.1f}x")
```

### Pattern 2: Inspecting Cumulative Session Telemetry
```python
summary = router.telemetry.get_session_summary()
print(f"Total Queries: {summary['total_queries']}")
print(f"Total Spent: ${summary['cumulative_spend']:.6f}")
print(f"Baseline Spend: ${summary['cumulative_baseline_spend']:.6f}")
print(f"Total Dollars Saved: ${summary['cumulative_dollars_saved']:.6f}")
print(f"Overall Savings: {summary['overall_savings_pct']:.1f}%")
print(f"Overall Multiplier: {summary['edtech_multiplier']:.1f}x")
```

### Pattern 3: Using Direct ModelClient
```python
from engine import generate, ModelClient

# Direct function call
res = generate("llama-3.1-8b-instant", "What is Newton's second law?")
print(res["text"], res["latency_ms"])

# Or class instance
client = ModelClient()
res2 = client.generate("qwen/qwen3.8-27b", "Summarize cellular respiration.")
```

---

## 5. Test Suites & Verification Results

### Test Suite 1: `tests/test_engine.py`
Runs analytical mathematical proofs and engine unit tests:
```bash
python3 tests/test_engine.py
```
**Test Coverage**:
1. Exact pricing table values per 1M tokens.
2. `generate()` across all 3 models with latency and token assertions.
3. Strict analytical math validation of `calculate_savings` ($10^{-7}$ tolerance).
4. Analytical validation of `calculate_edtech_multiplier`.
5. Cumulative session state tracking across multiple queries.
6. Safe mock fallback behavior under missing or invalid API keys.

---

### Test Suite 2: `tests/test_router.py`
Runs live routing scenarios across all tiers and fallback escalation:
```bash
python3 tests/test_router.py
```
**Verified Scenarios**:
1. **Tier 1 (Factual Recall)**:
   - Query: `"What is the speed of light in a vacuum and who first measured it?"`
   - Initial Model: `llama-3.1-8b-instant`
   - Final Model: `llama-3.1-8b-instant`
   - Fallback: `False` (Direct routing succeeded).
2. **Tier 2 (Conceptual Explanation & Synthesis)**:
   - Query: `"Explain the differences between mitosis and meiosis, highlighting stages and genetic outcomes."`
   - Initial Model: `qwen/qwen3.8-27b`
   - Final Model: `qwen/qwen3.8-27b`
   - Fallback: `False` (Direct routing succeeded).
3. **Tier 3 (Complex Multi-step Proof & Automated Escalation)**:
   - Query: `"Prove by mathematical induction that for all positive integers n, 1 + 2 + ... + n = n(n + 1)/2."`
   - Initial Model: `llama-3.1-8b-instant` (Speculative attempt)
   - Verifier: `FAILED` (Heuristic checks identified insufficient depth)
   - Fallback: `True`
   - Escalated Final Model: `llama-3.3-70b-versatile` (Frontier-class reasoning model).
4. **Forced Fallback Demo**:
   - `route_and_execute("What is DNA?", force_fallback_demo=True)`
   - Verified that `fallback_triggered=True` and escalated cleanly to `llama-3.3-70b-versatile`.

---

## 6. What Person 3 Can Build Next

Person 3's model can immediately build upon this foundation:
1. **`core/profiler.py`**:
   - Profile token throughput (tokens/sec) and latency distributions across models.
2. **`app/components.py`**:
   - UI metrics cards displaying:
     - Real-time cost vs. Frontier baseline.
     - EdTech Impact Multiplier badge (e.g. `83.3x more students`).
     - Tier badges (Tier 1 green, Tier 2 blue, Tier 3 purple).
     - Fallback escalation alert banner when `fallback_triggered=True`.
3. **`app/main.py`**:
   - Streamlit or FastAPI frontend allowing students/teachers to submit queries, view the routed model, inspect the step-by-step reasoning, and observe real-time cost savings.
