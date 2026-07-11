# Question Generator

## Task
Generate screening questions based on requirements and resume analysis.

## Output JSON Schema
{
  "role_id": "string",
  "candidate_id": "string | null",
  "questions": [
    {
      "question_id": "string (unique id)",
      "text": "string (the question)",
      "maps_to": ["requirement_id"],
      "type": "behavioral | situational | technical",
      "expected_signals": ["string"],
      "rubric": {
        "strong": "string (what a strong answer looks like)",
        "adequate": "string (what an adequate answer looks like)",
        "weak": "string (what a weak answer looks like)"
      },
      "candidate_visible": true
    }
  ]
}
