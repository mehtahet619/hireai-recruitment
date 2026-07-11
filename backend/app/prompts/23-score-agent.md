# Score Agent

## Task
Calculate a structured, auditable score for a candidate based on resume analysis and interview assessments.

## Default Weights
- must_have_coverage: 45%
- interview_performance: 25%
- experience_depth: 15%
- skills_match: 10%
- recency: 5%

## Output JSON Schema
{
  "candidate_id": "string",
  "role_id": "string",
  "overall_score": 0-100,
  "score_range": [min, max],
  "band": "strong_advance | advance | borderline | hold | do_not_advance",
  "recommendation": "strong_advance | advance | borderline | hold | do_not_advance | needs_human_review",
  "category_scores": [
    {
      "category": "string",
      "weight": 0-100,
      "subscore_0_100": 0-100,
      "weighted_points": 0-100,
      "rationale": "string",
      "evidence": []
    }
  ],
  "must_have_status": {
    "met": 0,
    "total": 0,
    "blocking": []
  },
  "key_reasons": ["string"],
  "flags": {
    "bias_flag": false,
    "needs_human_review": false,
    "prompt_injection_detected": false
  },
  "calculation": "string (show how score was computed)"
}
