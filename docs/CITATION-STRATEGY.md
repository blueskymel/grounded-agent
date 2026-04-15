# Citation Confidence & Refusal Strategy

## Overview

This document explains how the grounded-agent uses citation confidence scores to balance **avoiding hallucinations** while **maintaining conviction in grounded answers**.

## Citation Scoring Mechanics

### FAISS Similarity Score Formula
```
score = 1 / (1 + distance)
```
This produces a normalized 0–1 range, but typical values range **0.30–0.65** for real-world retrievals:
- **0.30–0.40**: Weak match (often semantic near-misses)
- **0.40–0.50**: Moderate match (relevant but with ambiguity)
- **0.50–0.65**: Strong match (clear semantic alignment)

**Important**: These are NOT probability scores. A 0.57 score doesn't mean "57% confidence in truth" — it's a normalized vector distance metric specific to the embedding model.

## Dual-Gate Refusal Strategy

### Gate 1: Per-Citation Display Filter (0.25)
**Purpose**: Hide junk/near-zero citations from the UI, but show all reasonable matches.

```python
MIN_CITATION_SCORE_TO_DISPLAY = 0.25
```

**Behavior**:
- Retrieve all matching chunks and their scores
- **Filter for display**: Only show citations with score ≥ 0.25
- Result: Removes extremely low-quality matches while preserving normal retrieval results

**Example** (typical FAISS index behavior):
```
Retrieved:   [0.45, 0.38, 0.36, 0.05, 0.02]
Displayed:   [0.45, 0.38, 0.36]  ← Only removes bottom 0.05, 0.02 junk
```

**Note**: For this index, typical good matches score 0.32–0.40. This filter is very permissive to avoid hiding real results.

### Gate 2: Refusal Threshold (0.55)
**Purpose**: Refuse answers entirely when max score (across ALL citations, not filtered) is below threshold.

```python
SAFE_MIN_CITATION_CONFIDENCE = 0.55
```

**Behavior**:
- Calculate max score using **unfiltered** citation scores
- If `max_score < 0.55`: refuse with "I don't have enough information..."
- If `max_score ≥ 0.55`: proceed, but display only citations ≥ 0.42

**Rationale**:
- 0.55 is tuned for FAISS similarity scale (not a probability threshold)
- Avoids answering questions where the best match is only weak/ambiguous
- Prevents hallucinations when retrieval confidence is low

## Citation-Only Refusal

The refusal logic is **pure citation-based**:

```python
if mode_override == "safe" and not refused:
    all_citation_scores = [c.score for c in all_citations if isinstance(c.score, (int, float))]
    max_score = max(all_citation_scores) if all_citation_scores else 0.0
    if (not all_citation_scores) or (max_score < _SAFE_MIN_CITATION_CONFIDENCE):
        # Refuse
```

**No policy-term or other heuristics** — purely based on whether retrieved evidence meets the confidence threshold.

## Hallucination-Detection Examples

The UI includes 3 hallucination-detection prompts that are **designed to fail** in the "after" (safe) endpoint:

1. **Data breach response**: Not documented in runbooks → No citations retrieved → Refused
2. **Disaster recovery plan**: Not in corpus → Max score too low → Refused
3. **Compliance audit procedure**: Out of scope → Below 0.55 threshold → Refused

These prompts will produce plausible-sounding fabricated answers in the "before" (unsafe) endpoint, but get correctly refused in "after" (safe) endpoint.

## Tuning Guidance

### Adjusting `MIN_CITATION_SCORE_TO_DISPLAY` (Display Filter)

| Value  | Behavior                                   | Use Case              |
|--------|--------------------------------------------|-----------------------|
| 0.15   | Show almost all retrieved citations        | Maximize information  |
| 0.25   | Filter only junk/extremely low matches     | Balanced (current)    |
| 0.35   | Filter below-average matches               | Conservative          |
| 0.45   | Only show above-median matches             | Very high quality     |

**Note**: For this index, typical good matches score 0.32–0.40. Lower thresholds (0.15–0.25) are recommended.

Lower value = more citations shown (including marginal matches)
Higher value = fewer, stronger citations (but risks hiding relevant matches)

### Adjusting `SAFE_MIN_CITATION_CONFIDENCE` (Refusal Gate)

| Value  | Behavior                                 | Use Case                      |
|--------|------------------------------------------|-------------------------------|
| 0.50   | More permissive (fewer refusals)        | Favor coverage over precision |
| 0.55   | Balanced (current)                       | Default: avoid weak answers   |
| 0.60+  | Very strict (many refusals)              | Extreme caution needed        |

Lower value = more answers, more risk of weak sourcing
Higher value = fewer answers, higher confidence in what's shown

## Validation

To verify the strategy is working:

1. **Test strong-match prompt** (should pass 0.55 gate, show filtered citations):
   ```
   "According to the runbooks, what immediate actions apply when [known incident]?"
   ```
   Expected: Answer + citations all ≥ 0.42

2. **Test weak-match prompt** (should fail 0.55 gate):
   ```
   "What is our [not-in-docs] procedure?"
   ```
   Expected: Refusal, no citations

3. **Test margin case** (scores between 0.42–0.55):
   ```
   [Prompt that retrieves 0.45–0.50 scores]
   ```
   Expected: Refusal (max < 0.55), even if citations exist

## Future Enhancements

- **Per-bullet citation coverage**: Ensure every action item in response has ≥1 citation
- **Confidence-weighted ordering**: Show highest-confidence citations first
- **Retrieval augmentation**: Add more specific doc chunking for edge cases
- **Semantic clustering**: Group similar chunks to reduce noise in display
