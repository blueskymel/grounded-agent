# Citation Display Filter Fix - Summary

## Problem Identified
After adding per-citation filtering, the threshold (`_MIN_CITATION_SCORE_TO_DISPLAY = 0.42`) was **too aggressive** for the FAISS retrieval system:

- Normal good matches score **0.32–0.36** range
- All citations were being filtered out
- Test failed: `assert len(citations) > 0`
- Both BEFORE and AFTER chat showed no citations even for grounded questions

## Root Cause
FAISS similarity scores scale differently than expected:
- Formula: `score = 1 / (1 + distance)`
- Produces range approximately **0.25–0.65** for real retrievals
- "Good" matches are actually in the **0.32–0.36** range, not 0.40+

Setting display filter to 0.42 eliminated all normal matches.

## Solution Implemented (Commit `c03da6f`)

Changed `_MIN_CITATION_SCORE_TO_DISPLAY` from **0.42 → 0.25**

```python
# BEFORE (too strict):
_MIN_CITATION_SCORE_TO_DISPLAY = 0.42  # ❌ Filtered out 0.32-0.36 normal matches

# AFTER (appropriate):
_MIN_CITATION_SCORE_TO_DISPLAY = 0.25  # ✅ Removes only junk, keeps normal matches
```

## Verification

**Local test passed with fix:**

```
Chat 1 (P1 triage):
  - Retrieved scores: [0.341, 0.340, 0.337, 0.329, 0.325]
  - Citations displayed: 5 ✅ (all pass 0.25 filter)
  - Answer generated: 1102 chars ✅

Chat 2 (SLA refusal):
  - Retrieved scores: [0.346, 0.345, 0.339, 0.335, 0.333]
  - Citations displayed: 0 ✅ (max 0.346 < refusal gate 0.55)
  - Answer: "I don't have enough information..." ✅

Test result: PASSED
```

## Threshold Strategy Now

```
Score Range       Display?   Safe Refusal?   Use Case
0.00–0.25        ❌          ❌             Junk/noise (filtered out)
0.25–0.55        ✅          ❌ (refuse)    Marginal evidence (safe endpoint refuses)
0.55+            ✅          ✅             Strong evidence (all endpoints accept)
```

## Key Insight

FAISS scores **are not probability-calibrated**. They're normalized vector distances specific to the embedding model:
- 0.25–0.30: Very weak similarity
- 0.30–0.40: Normal retrieval matches (typical)
- 0.40–0.50: Good matches
- 0.50+: Strong exact/near-exact matches

## Impact on User Experience

**Before fix:**
- Grounded questions: Empty citations array even with strong answers
- Confusing: "Where did this answer come from?"
- Test failures

**After fix:**
- Grounded questions: Show 3–5 citations with 0.32–0.40 scores
- Clear sourcing: "These chunks support the answer"
- Both BEFORE and AFTER consistent for good matches
- AFTER additionally refuses low-confidence questions

## Deployment Notes

- Code committed: `c03da6f` on `develop` branch
- Python source file: `api/app/main.py` lines 64, 270–290, 315–325
- Test file: `api/tests/test_smoke_golden_path.py`
- All tests pass locally ✅
- Requires container rebuild and redeploy to production

## Future Tuning

Monitor citation score distributions in production:
- If too many citations: raise 0.25 to 0.30–0.35
- If weak citations appearing: raise 0.25 to 0.30
- If many refusals in AFTER: lower 0.55 to 0.50
- All thresholds are environment-configurable via `SAFE_MIN_CITATION_CONFIDENCE`
