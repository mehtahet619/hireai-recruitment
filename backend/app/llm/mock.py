import json
import re
from typing import Any


def _payload(user_content: str) -> dict[str, Any]:
    marker = "PAYLOAD_JSON:"
    idx = user_content.find(marker)
    if idx == -1:
        return {}
    try:
        return json.loads(user_content[idx + len(marker):].strip())
    except json.JSONDecodeError:
        return {}


def mock_response(stage: str, user_content: str) -> dict[str, Any]:
    data = _payload(user_content)
    if stage == "jd_parser":
        return _mock_jd(data)
    if stage == "resume_analyzer":
        return _mock_resume(data)
    if stage == "question_generator":
        return _mock_questions(data)
    if stage == "score_agent":
        return _mock_score(data)
    if stage == "feedback":
        return _mock_feedback(data)
    return {}


def mock_chat_response(stage: str, messages: list[dict[str, str]]) -> dict[str, Any]:
    if stage == "interview":
        return _mock_interview_turn(messages)
    return {}


def _mock_jd(data: dict[str, Any]) -> dict[str, Any]:
    jd = str(data.get("job_description", ""))
    reqs = []
    for i, line in enumerate(re.split(r"[\n\.;]", jd)):
        line = line.strip("-• \t")
        if len(line) < 6:
            continue
        is_must = bool(re.search(r"\b(\d+\+?\s*years|must|required|strong)\b", line, re.I))
        reqs.append({
            "requirement_id": f"req_{i+1}",
            "text": line[:160],
            "type": "must_have" if is_must else "nice_to_have",
            "weight": 4 if is_must else 2,
            "threshold": None,
            "classification_confidence": "low",
        })
        if len(reqs) >= 6:
            break
    if not reqs:
        reqs = [{"requirement_id": "req_1", "text": "Relevant professional experience",
                 "type": "must_have", "weight": 4, "threshold": None, "classification_confidence": "low"}]
    return {
        "role_id": "role_mock",
        "title": (jd.strip().split("\n")[0][:80] or "Untitled role"),
        "summary": jd.strip()[:200],
        "work_model": "unknown",
        "requirements": reqs,
        "removed_or_flagged": [],
        "meta": {"needs_human_review": False, "notes": "MOCK output"},
    }


def _mock_resume(data: dict[str, Any]) -> dict[str, Any]:
    resume = str(data.get("resume", ""))
    reqs = data.get("requirements", {}).get("requirements", [])
    blob = resume.lower()
    matches, met = [], 0
    for r in reqs:
        keywords = [w for w in re.findall(r"[a-zA-Z\+\#\.]{3,}", r["text"].lower())]
        hit = any(k in blob for k in keywords[:5]) if keywords else False
        status = "met" if hit else "unknown"
        if hit and r["type"] == "must_have":
            met += 1
        matches.append({
            "requirement_id": r["requirement_id"], "requirement": r["text"], "type": r["type"],
            "status": status, "evidence": [resume[:80]] if hit else [],
            "gap": None if hit else "Not evidenced in resume", "confidence": "low",
        })
    must_total = sum(1 for r in reqs if r["type"] == "must_have") or 1
    return {
        "candidate_id": data.get("candidate_id", "cand_mock"),
        "role_id": data.get("requirements", {}).get("role_id", "role_mock"),
        "extraction": {"experience": [], "skills": [], "education": [], "certifications": [], "projects": []},
        "requirement_matches": matches,
        "signals": {
            "must_haves_met_ratio": round(met / must_total, 2),
            "nice_to_haves_met_ratio": 0.0, "evidence_density": 0.3,
            "depth_signal": {"value": "MOCK", "confidence": "low", "evidence": []},
            "recency_signal": {"value": "unknown", "confidence": "low"},
            "trajectory_signal": {"value": "unclear", "confidence": "low"},
            "risk_flags": [],
        },
        "hiring_signals": {
            "strengths": [{"point": "Keyword matches present", "evidence": [resume[:60]]}] if met else [],
            "concerns": [] if met else [{"point": "Few must-haves evidenced", "evidence": []}],
            "clarifying_questions": ["Can you detail your most relevant project?"],
            "standout_indicators": [],
        },
        "meta": {"bias_flag": False, "needs_human_review": met == 0, "notes": "MOCK output"},
    }


def _mock_questions(data: dict[str, Any]) -> dict[str, Any]:
    reqs = data.get("requirements", {}).get("requirements", [])
    questions = []
    for i, r in enumerate(reqs[:5]):
        questions.append({
            "question_id": f"q{i+1}",
            "text": f"Tell me about your experience related to: {r['text'][:80]}",
            "maps_to": [r["requirement_id"]], "type": "behavioral",
            "expected_signals": ["Concrete, relevant, quantified experience"],
            "rubric": {"strong": "Specific, quantified, directly relevant",
                       "adequate": "Relevant but general", "weak": "Vague or unrelated"},
            "candidate_visible": True,
        })
    return {
        "role_id": data.get("requirements", {}).get("role_id", "role_mock"),
        "candidate_id": data.get("candidate_id"),
        "questions": questions,
    }


def _mock_score(data: dict[str, Any]) -> dict[str, Any]:
    analysis = data.get("resume_analysis", {})
    ratio = float(analysis.get("signals", {}).get("must_haves_met_ratio", 0.0))
    must_sub = round(ratio * 100)
    overall = round(0.45 * must_sub + 0.20 * 50 + 0.10 * 20 + 0.20 * 50 + 0.05 * 50)
    band = "strong_advance" if overall >= 80 else "advance" if overall >= 65 else "borderline" if overall >= 50 else "hold" if overall >= 35 else "do_not_advance"
    matches = analysis.get("requirement_matches", [])
    met = sum(1 for m in matches if m["type"] == "must_have" and m["status"] == "met")
    total = sum(1 for m in matches if m["type"] == "must_have")
    return {
        "candidate_id": analysis.get("candidate_id", "cand_mock"),
        "role_id": analysis.get("role_id", "role_mock"),
        "overall_score": overall, "score_range": [max(0, overall - 10), min(100, overall + 10)],
        "band": band, "recommendation": "needs_human_review",
        "category_scores": [{"category": "must_have_coverage", "weight": 45, "subscore_0_100": must_sub,
                           "weighted_points": round(0.45 * must_sub, 2), "rationale": "MOCK", "evidence": []}],
        "must_have_status": {"met": met, "total": total, "blocking": []},
        "key_reasons": ["MOCK score"], "flags": {"bias_flag": False, "needs_human_review": True, "prompt_injection_detected": False},
        "calculation": f"MOCK: 0.45*{must_sub} + defaults = {overall}",
    }


def _mock_feedback(data: dict[str, Any]) -> dict[str, Any]:
    score = data.get("score", {})
    return {
        "candidate_id": score.get("candidate_id", "cand_mock"),
        "role_id": score.get("role_id", "role_mock"),
        "headline": f"MOCK summary — band {score.get('band', 'unknown')}",
        "recommendation": score.get("recommendation", "needs_human_review"),
        "confidence": "low",
        "must_haves": {"met": score.get("must_have_status", {}).get("met", 0),
                       "total": score.get("must_have_status", {}).get("total", 0), "unmet": []},
        "top_strengths": [], "top_concerns": [],
        "open_questions_for_human": ["MOCK run — connect Gemini for real output."],
        "bias_flag": False,
    }


def _mock_interview_turn(messages: list[dict[str, str]]) -> dict[str, Any]:
    last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    is_start = "Begin the interview" in last_user
    candidate_text = ""
    if "Candidate said:" in last_user:
        candidate_text = last_user.split("Candidate said:", 1)[1].split("\n\n")[0].strip().lower()
    aria_turns = sum(1 for m in messages if m["role"] == "model")
    questions, role_id, candidate_id, role_title = [], "role_mock", "cand_mock", "this role"
    q_count = 0
    screen_turn = 0
    for msg in messages:
        if msg["role"] != "user" or "CONTEXT:" not in msg["content"]:
            continue
        try:
            body = msg["content"]
            ctx_start = body.index("CONTEXT:") + len("CONTEXT:")
            for end_marker in ("\n\nReturn a single JSON", "\n\nWhen the conversation"):
                if end_marker in body[ctx_start:]:
                    ctx = json.loads(body[ctx_start:body.index(end_marker, ctx_start)].strip())
                    questions = ctx.get("screening_questions", {}).get("questions", [])
                    role_id = ctx.get("role", {}).get("role_id", role_id)
                    candidate_id = ctx.get("candidate_id", candidate_id)
                    role_title = ctx.get("role", {}).get("title", role_title)
                    q_count = len(questions) or 3
                    screen_turn = aria_turns - 3
                    break
        except (ValueError, json.JSONDecodeError):
            pass

    # Handle off-topic questions
    off_topic_keywords = ["mock", "llm", "ai", "what are you", "who are you", "how do you work"]
    if any(keyword in candidate_text for keyword in off_topic_keywords) and aria_turns > 1:
        return {
            "message": "I'm an AI assistant helping conduct this screening interview! Let's get back to talking about your qualifications — what's your most relevant experience for this role?",
            "conversation_state": {"state": "SCREEN", "role_id": role_id, "consent_given": True,
                                   "collected": {}, "answers": [],
                                   "flags": {"needs_human_review": False, "possible_injection": False},
                                   "next_action": "ask_q1"},
            "is_complete": False, "handoff": None,
        }
        
    # Handle nonsensical answers
    special_chars = set("\\-+!@#$%^&*()_=[]{}|;:\"'<>,.?/~`")
    if len(candidate_text.strip()) < 2:
        if aria_turns == 2:
            return {
                "message": "Could you please share your actual current role and years of relevant experience? That helps me conduct the screening properly!",
                "conversation_state": {"state": "COLLECT", "role_id": role_id, "consent_given": True,
                                       "collected": {}, "answers": [],
                                       "flags": {"needs_human_review": False, "possible_injection": False},
                                       "next_action": "collect_basics"},
                "is_complete": False, "handoff": None,
            }
        else:
            q = questions[screen_turn] if screen_turn < len(questions) else {"text": "Tell me about your relevant experience", "question_id": "q1"}
            return {
                "message": f"Could you please give a proper answer to the question: {q['text']}?",
                "conversation_state": {"state": "SCREEN", "role_id": role_id, "consent_given": True,
                                       "collected": {}, "answers": [],
                                       "flags": {"needs_human_review": False, "possible_injection": False},
                                       "next_action": f"ask_{q.get('question_id', 'q1')}"},
                "is_complete": False, "handoff": None,
            }
    # Check if most characters are special characters
    special_count = sum(1 for ch in candidate_text if ch in special_chars)
    if special_count > len(candidate_text) * 0.7:
        if aria_turns == 2:
            return {
                "message": "Could you please share your actual current role and years of relevant experience? That helps me conduct the screening properly!",
                "conversation_state": {"state": "COLLECT", "role_id": role_id, "consent_given": True,
                                       "collected": {}, "answers": [],
                                       "flags": {"needs_human_review": False, "possible_injection": False},
                                       "next_action": "collect_basics"},
                "is_complete": False, "handoff": None,
            }
        else:
            q = questions[screen_turn] if screen_turn < len(questions) else {"text": "Tell me about your relevant experience", "question_id": "q1"}
            return {
                "message": f"Could you please give a proper answer to the question: {q['text']}?",
                "conversation_state": {"state": "SCREEN", "role_id": role_id, "consent_given": True,
                                       "collected": {}, "answers": [],
                                       "flags": {"needs_human_review": False, "possible_injection": False},
                                       "next_action": f"ask_{q.get('question_id', 'q1')}"},
                "is_complete": False, "handoff": None,
            }

    if is_start:
        return {
            "message": f"Hi — I'm Aria, an AI assistant for recruiting. We'll do a short screening for {role_title}. Ready to continue?",
            "conversation_state": {"state": "CONSENT", "role_id": role_id, "consent_given": False,
                                   "collected": {}, "answers": [],
                                   "flags": {"needs_human_review": False, "possible_injection": False},
                                   "next_action": "await_consent"},
            "is_complete": False, "handoff": None,
        }
    if aria_turns <= 1 and any(w in candidate_text for w in ("no", "decline", "stop")):
        return _mock_handoff(role_id, candidate_id, messages, questions, declined=True)
    if aria_turns <= 1:
        return {
            "message": "Great. What's your current role and years of relevant experience?",
            "conversation_state": {"state": "COLLECT", "role_id": role_id, "consent_given": True,
                                   "collected": {}, "answers": [],
                                   "flags": {"needs_human_review": False, "possible_injection": False},
                                   "next_action": "collect_basics"},
            "is_complete": False, "handoff": None,
        }
    if aria_turns == 2:
        q = questions[0] if questions else {"question_id": "q1", "text": "Tell me about your most relevant experience."}
        return {
            "message": f"Thanks. {q['text']}",
            "conversation_state": {"state": "SCREEN", "role_id": role_id, "consent_given": True,
                                   "collected": {"current_role": candidate_text[:80]}, "answers": [],
                                   "flags": {"needs_human_review": False, "possible_injection": False},
                                   "next_action": f"ask_{q['question_id']}"},
            "is_complete": False, "handoff": None,
        }
    if screen_turn < q_count - 1:
        next_q = questions[screen_turn + 1] if screen_turn + 1 < len(questions) else {
            "question_id": f"q{screen_turn + 2}", "text": "Describe a challenging project you worked on recently."}
        return {
            "message": f"Got it. {next_q['text']}",
            "conversation_state": {"state": "SCREEN", "role_id": role_id, "consent_given": True,
                                   "collected": {}, "answers": [{"question_id": f"q{screen_turn + 1}", "answer": candidate_text[:200]}],
                                   "flags": {"needs_human_review": False, "possible_injection": False},
                                   "next_action": f"ask_{next_q['question_id']}"},
            "is_complete": False, "handoff": None,
        }
    return _mock_handoff(role_id, candidate_id, messages, questions, declined=False)


def _mock_handoff(role_id, candidate_id, messages, questions, declined):
    transcript = []
    for msg in messages:
        if msg["role"] == "user" and "Begin the interview" not in msg["content"]:
            if "Candidate said:" in msg["content"]:
                text = msg["content"].split("Candidate said:", 1)[1].split("\n\n")[0].strip()
                transcript.append({"speaker": "candidate", "text": text})
        elif msg["role"] == "model":
            transcript.append({"speaker": "aria", "text": msg["content"]})
    wrap_msg = "No problem — thank you for your time." if declined else "That's everything. A recruiter will review and follow up soon."
    assessments = []
    if not declined:
        for i, q in enumerate(questions[:5] or [{"question_id": "q1"}]):
            assessments.append({
                "question_id": q.get("question_id", f"q{i+1}"),
                "answer_summary": "MOCK: relevant experience provided",
                "evidence": ["MOCK quote"], "rubric_level": "adequate",
                "confidence": "low", "follow_up_used": False, "notes": "MOCK",
            })
    handoff = {
        "role_id": role_id, "candidate_id": candidate_id, "transcript": transcript,
        "assessments": assessments,
        "flags": {"needs_human_review": True, "possible_injection": False, "candidate_declined": declined},
        "skipped_questions": [],
    }
    return {
        "message": wrap_msg,
        "conversation_state": {"state": "HANDOFF", "role_id": role_id, "consent_given": not declined,
                               "collected": {}, "answers": [], "flags": handoff["flags"], "next_action": "complete"},
        "is_complete": True, "handoff": handoff,
    }
