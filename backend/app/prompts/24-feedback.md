# Feedback Generator

## Task
Generate a recruiter-facing summary of the candidate evaluation.

## Output JSON Schema
{
  "candidate_id": "string",
  "role_id": "string",
  "headline": "string (one-line summary)",
  "recommendation": "string",
  "confidence": "high | medium | low",
  "must_haves": {
    "met": 0,
    "total": 0,
    "unmet": []
  },
  "top_strengths": [{"point": "string", "evidence": []}],
  "top_concerns": [{"point": "string", "evidence": []}],
  "open_questions_for_human": ["string"],
  "bias_flag": false
}
