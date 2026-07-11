import json
from typing import Any
from ..llm.client import complete_json, complete_chat_json
from ..prompts_loader import build_system_prompt


def parse_jd(job_description: str) -> dict[str, Any]:
    system_prompt = build_system_prompt("20-jd-parser.md")
    user_content = f"Job description:\n{job_description}\n\nPAYLOAD_JSON:{json.dumps({'job_description': job_description}, ensure_ascii=False)}"
    return complete_json(system_prompt, user_content, stage="jd_parser")


def analyze_resume(resume: str, requirements: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    system_prompt = build_system_prompt("21-resume-analyzer.md")
    payload = {"resume": resume, "requirements": requirements, "candidate_id": candidate_id}
    user_content = f"Resume:\n{resume}\n\nRequirements JSON:\n{json.dumps(requirements, ensure_ascii=False)}\n\nPAYLOAD_JSON:{json.dumps(payload, ensure_ascii=False)}"
    return complete_json(system_prompt, user_content, stage="resume_analyzer")


def generate_questions(requirements: dict[str, Any], candidate_id: str | None = None) -> dict[str, Any]:
    system_prompt = build_system_prompt("22-question-generator.md")
    payload = {"requirements": requirements, "candidate_id": candidate_id}
    user_content = f"Requirements JSON:\n{json.dumps(requirements, ensure_ascii=False)}\n\nPAYLOAD_JSON:{json.dumps(payload, ensure_ascii=False)}"
    return complete_json(system_prompt, user_content, stage="question_generator")


def score_candidate(
    resume_analysis: dict[str, Any],
    interview_assessments: dict[str, Any] | None = None,
    recruiter_weights: dict[str, Any] | None = None,
) -> dict[str, Any]:
    system_prompt = build_system_prompt("23-score-agent.md")
    payload = {
        "resume_analysis": resume_analysis,
        "interview_assessments": interview_assessments,
        "recruiter_weights": recruiter_weights,
    }
    user_content = f"PAYLOAD_JSON:{json.dumps(payload, ensure_ascii=False)}"
    return complete_json(system_prompt, user_content, stage="score_agent")


def generate_feedback(
    score: dict[str, Any],
    resume_analysis: dict[str, Any] | None = None,
    authorize_candidate_message: bool = False,
) -> dict[str, Any]:
    system_prompt = build_system_prompt("24-feedback.md")
    payload = {
        "score": score,
        "resume_analysis": resume_analysis,
        "authorize_candidate_message": authorize_candidate_message,
    }
    user_content = f"PAYLOAD_JSON:{json.dumps(payload, ensure_ascii=False)}"
    return complete_json(system_prompt, user_content, stage="feedback")


def interview_turn(
    role: dict[str, Any],
    candidate_id: str,
    resume_analysis: dict[str, Any],
    screening_questions: dict[str, Any],
    conversation_history: list[dict[str, str]],
    conversation_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    system_prompt = build_system_prompt("25-interview.md")
    ctx = {
        "role": role,
        "candidate_id": candidate_id,
        "resume_analysis": resume_analysis,
        "screening_questions": screening_questions,
        "conversation_state": conversation_state,
    }
    last_message = conversation_history[-1]["content"] if conversation_history else ""
    history_excluding_last = conversation_history[:-1] if len(conversation_history) > 0 else []
    system_prompt_part = system_prompt
    user_content = f"CONTEXT:{json.dumps(ctx, ensure_ascii=False)}\n\nConversation so far:\n"
    for msg in history_excluding_last:
        user_content += f"{msg['role'].upper()}: {msg['content']}\n"
    user_content += f"\nCandidate said: {last_message}\n\nReturn a single JSON blob with 'message', 'conversation_state', 'is_complete', 'handoff'."
    if not conversation_history:
        user_content = f"CONTEXT:{json.dumps(ctx, ensure_ascii=False)}\n\nBegin the interview.\n\nReturn a single JSON blob with 'message', 'conversation_state', 'is_complete', 'handoff'."
    messages = []
    for msg in history_excluding_last:
        messages.append(msg)
    messages.append({"role": "user", "content": user_content})
    return complete_chat_json(system_prompt_part, messages, stage="interview")
