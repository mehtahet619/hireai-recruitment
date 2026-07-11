# JD Parser

## Task
Parse a job description into structured requirements, identifying must-haves and nice-to-haves.

## Output JSON Schema
{
  "role_id": "string (auto-generated)",
  "title": "string (role title)",
  "summary": "string (brief summary)",
  "work_model": "string (remote/hybrid/onsite/unknown)",
  "requirements": [
    {
      "requirement_id": "string (unique id)",
      "text": "string (requirement text, max 160 chars)",
      "type": "must_have | nice_to_have",
      "weight": 4 | 3 | 2 | 1 (4=most important, 1=least)",
      "threshold": "string | null",
      "classification_confidence": "high | medium | low"
    }
  ],
  "removed_or_flagged": [],
  "meta": {
    "needs_human_review": false,
    "notes": "string"
  }
}
