# FDE Demo: Hallucination Issue, Fix Path, and Multi-Client Rollout

This guide demonstrates a realistic Forward Deployed Engineering workflow:

1. Reproduce a hallucination issue intentionally.
2. Show a safe fix path in parallel.
3. Roll out the fix pattern to multiple client environments.

## 1) Demo Modes

The API now supports two explicit modes via environment variable:

- `HALLUCINATION_DEMO_MODE=safe` (default)
- `HALLUCINATION_DEMO_MODE=unsafe` (intentionally vulnerable, demo-only)

Behavior summary:

- `safe` mode:
  - Enforces refusal for unsupported high-risk questions (for example SLA/SLO/RTO/RPO).
  - Requires citation-shaped output and grounded validation.
- `unsafe` mode:
  - Disables refusal and citation enforcement paths for demonstration.
  - Uses higher generation temperature to increase variability.
  - In `LLM_PROVIDER=mock`, intentionally returns question-responsive speculative guidance that blends runbook snippets with ungrounded assumptions.
  - Unsafe demo responses intentionally omit citations.

## 2) Reproduce Hallucination (Issue Path)

From `api/`:

```powershell
$env:LLM_PROVIDER = "mock"
$env:HALLUCINATION_DEMO_MODE = "unsafe"
python -m uvicorn app.main:app --reload --app-dir .
```

Then call `/chat` with a question like:

- `What is the SLA for this service?`

Expected demo outcome:

- The response returns a plausible but unsupported answer (hallucination pattern).

## 3) Show the Fix (Safe Path)

From `api/`:

```powershell
$env:LLM_PROVIDER = "mock"
$env:HALLUCINATION_DEMO_MODE = "safe"
python -m uvicorn app.main:app --reload --app-dir .
```

Ask the same question:

- `What is the SLA for this service?`

Expected safe outcome:

- Refusal message:
  - `I don't have enough information in the provided runbooks to answer that.`

## 4) Regression Tests (Proof)

Run targeted tests:

```powershell
cd api
pytest tests/test_grounded_answer_langchain.py -q
```

Coverage includes:

- Unsafe mode can hallucinate in demo conditions.
- Safe mode refuses unsupported SLA claims.
- Existing langchain/legacy fallback behavior remains valid.

## 5) Roll Out to Other Clients

Use the same codebase, per-client environment config, and policy defaults:

1. Keep `HALLUCINATION_DEMO_MODE=safe` as baseline in all production-like environments.
2. Allow `unsafe` only in isolated demo sandboxes.
3. Add a deployment check that fails if `unsafe` is set outside approved demo subscriptions.
4. Version this policy as part of your standard client onboarding template.

Suggested client rollout model:

1. `client-a-dev`: safe mode, acceptance tests.
2. `client-a-staging`: safe mode, evaluation gate.
3. `client-a-prod`: safe mode only, policy-enforced.
4. Repeat for `client-b`, `client-c` by environment variable and pipeline variable group changes only.

## 6) Operational Guardrails for FDE Teams

- Treat `unsafe` mode as a controlled chaos test, not a feature.
- Log and alert on any non-safe mode in shared environments.
- Gate releases with refusal and citation conformance tests.
- Keep retrieval + grounding checks enabled by default for every client tenant.
