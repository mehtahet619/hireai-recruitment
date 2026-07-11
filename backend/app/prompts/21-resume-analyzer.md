# Resume Analyzer

## Task
Analyze a resume against parsed requirements to identify matches and signals.

## Output JSON Schema
{
  "candidate_id": "string",
  "role_id": "string",
  "extraction": {
    "experience": [],
    "skills": [],
    "education": [],
    "certifications": [],
    "projects": []
  },
  "requirement_matches": [
    {
      "requirement_id": "string",
      "requirement": "string",
      "type": "must_have | nice_to_have",
      "status": "met | partial | unmet | unknown",
      "evidence": ["string (exact quotes from resume)"],
      "gap": "string | null",
      "confidence": "high | medium | low"
    }
  ],
  "signals": {
    "must_haves_met_ratio": 0.0,
    "nice_to_haves_met_ratio": 0.0,
    "evidence_density": 0.0,
    "depth_signal": { "value": "string", "confidence": "high | medium | low", "evidence": [] },
    "recency_signal": { "value": "string", "confidence": "high | medium | low" },
    "trajectory_signal": { "value": "string", "confidence": "high | medium | low" },
    "risk_flags": []
  },
  "hiring_signals": {
    "strengths": [{"point": "string", "evidence": []}],
    "concerns": [{"point": "string", "evidence": []}],
    "clarifying_questions": ["string"],
    "standout_indicators": []
  },
  "meta": {
    "bias_flag": false,
    "needs_human_review": false,
    "notes": "string"
  }
}
