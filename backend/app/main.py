from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from typing import Annotated, Any
from .config import get_settings
from .schemas import (
    JDParseRequest,
    ResumeAnalyzeRequest,
    QuestionRequest,
    ScoreRequest,
    FeedbackRequest,
    PipelineRequest,
    InterviewStartRequest,
    InterviewMessageRequest,
    InterviewCompleteRequest,
    InterviewSaveReviewRequest,
    InterviewUpdateTabChangeRequest,
    BanCheckRequest,
    BanUserRequest,
    UnbanUserRequest,
    EmployerRegisterRequest,
    EmployerLoginRequest,
    JobCreateRequest,
    JobUpdateRequest,
    ApplicationSubmitRequest,
    GoogleAuthRequest,
    CreateOrderRequest,
    VerifyPaymentRequest,
    SignalIngestRequest,
    SignalResponse,
    OnboardingTaskSchema,
    OnboardingTemplateCreateRequest,
    OnboardingTemplateUpdateRequest,
    OnboardingPlanCreateRequest,
)
from .pipeline import (
    parse_jd,
    analyze_resume,
    generate_questions,
    score_candidate,
    generate_feedback,
)
from .pipeline.stages import interview_turn
from .sessions import (
    create_session,
    get_session,
    save_session,
    delete_session,
    is_banned,
    ban_user,
    unban_user,
)
from .review_store import save_review, save_recording
from .employer_store import (
    create_employer,
    authenticate_employer,
    get_employer,
    get_employer_by_email,
    create_job,
    get_job,
    update_job,
    list_jobs,
    list_employer_jobs,
    create_application,
    get_application,
    update_application,
    list_job_applications,
    employer_can_post_job,
    activate_plan,
    PLANS,
)
from .auth import create_token, get_current_employer
from .signal_store import (
    Signal_Processor,
    query_signals,
    compute_pseudonymous_id,
    SignalType,
    ConsentError,
)
from .onboarding_store import (
    save_template,
    get_template,
    list_employer_templates,
    create_plan_from_template,
    complete_task,
    get_plan,
    list_employer_plans,
    OnboardingTemplate,
    OnboardingTask,
)
from .evaluation_models import hiring_ability_predictor
import json
import uuid
from datetime import datetime, timedelta, timezone

settings = get_settings()

app = FastAPI(title="AI Recruiter API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "mock": settings.use_mock,
        "model": settings.gemini_model,
        "session_backend": "valkey" if settings.valkey_url else "memory",
        "storage_backend": "s3" if settings.s3_bucket else "local",
    }


@app.post("/api/jd/parse")
async def api_parse_jd(req: JDParseRequest):
    try:
        result = parse_jd(req.job_description)
        return {"result": result, "mock": settings.use_mock}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/resume/analyze")
async def api_analyze_resume(req: ResumeAnalyzeRequest):
    try:
        result = analyze_resume(req.resume, req.requirements, req.candidate_id)
        return {"result": result, "mock": settings.use_mock}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/questions/generate")
async def api_generate_questions(req: QuestionRequest):
    try:
        result = generate_questions(req.requirements, req.candidate_id)
        return {"result": result, "mock": settings.use_mock}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/score")
async def api_score(req: ScoreRequest):
    try:
        result = score_candidate(
            req.resume_analysis,
            req.interview_assessments,
            req.recruiter_weights,
        )
        return {"result": result, "mock": settings.use_mock}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/feedback")
async def api_feedback(req: FeedbackRequest):
    try:
        result = generate_feedback(
            req.score,
            req.resume_analysis,
            req.authorize_candidate_message,
        )
        return {"result": result, "mock": settings.use_mock}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pipeline/run")
async def api_pipeline_run(req: PipelineRequest):
    try:
        requirements = parse_jd(req.job_description)
        resume_analysis = analyze_resume(req.resume, requirements, req.candidate_id)
        questions = generate_questions(requirements, req.candidate_id)
        score = score_candidate(resume_analysis)
        feedback = generate_feedback(score, resume_analysis)
        return {
            "requirements": requirements,
            "resume_analysis": resume_analysis,
            "questions": questions,
            "score": score,
            "feedback": feedback,
            "mock": settings.use_mock,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ban/check")
async def api_ban_check(req: BanCheckRequest):
    try:
        return is_banned(req.candidate_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ban/user")
async def api_ban_user(req: BanUserRequest):
    try:
        return ban_user(req.candidate_id, req.reason)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ban/unban")
async def api_unban_user(req: UnbanUserRequest):
    try:
        return unban_user(req.candidate_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/interview/start")
async def api_interview_start(req: InterviewStartRequest):
    try:
        # Check if user is banned
        ban_status = is_banned(req.candidate_id)
        if ban_status.get("banned"):
            raise HTTPException(
                status_code=403,
                detail=f"You are banned: {ban_status.get('reason', 'Violation of terms')}",
            )
        requirements = parse_jd(req.job_description)
        resume_analysis = analyze_resume(req.resume, requirements, req.candidate_id)
        questions = generate_questions(requirements, req.candidate_id)
        session = create_session(
            candidate_id=req.candidate_id,
            job_description=req.job_description,
            resume=req.resume,
            requirements=requirements,
            resume_analysis=resume_analysis,
            questions=questions,
        )
        interview_result = interview_turn(
            role=requirements,
            candidate_id=req.candidate_id,
            resume_analysis=resume_analysis,
            screening_questions=questions,
            conversation_history=[],
            conversation_state=None,
        )
        transcript = [{"speaker": "aria", "text": interview_result["message"]}]
        session.transcript = transcript
        session.history = [{"role": "model", "content": interview_result["message"]}]
        session.conversation_state = interview_result["conversation_state"]
        session.handoff = interview_result["handoff"]
        session.is_complete = interview_result["is_complete"]
        save_session(session)
        return {
            "session_id": session.session_id,
            "transcript": transcript,
            "conversation_state": interview_result["conversation_state"],
            "message": interview_result["message"],
            "is_complete": interview_result["is_complete"],
            "handoff": interview_result["handoff"],
            "mock": settings.use_mock,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/interview/message")
async def api_interview_message(req: InterviewMessageRequest):
    try:
        session = get_session(req.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session.is_complete:
            raise HTTPException(status_code=400, detail="Interview already complete")
        session.history.append({"role": "user", "content": req.message})
        session.transcript.append({"speaker": "candidate", "text": req.message})
        interview_result = interview_turn(
            role=session.requirements,
            candidate_id=session.candidate_id,
            resume_analysis=session.resume_analysis,
            screening_questions=session.questions,
            conversation_history=session.history,
            conversation_state=session.conversation_state,
        )
        session.history.append({"role": "model", "content": interview_result["message"]})
        session.transcript.append({"speaker": "aria", "text": interview_result["message"]})
        session.conversation_state = interview_result["conversation_state"]
        session.handoff = interview_result["handoff"]
        session.is_complete = interview_result["is_complete"]
        save_session(session)
        return {
            "session_id": session.session_id,
            "transcript": session.transcript,
            "conversation_state": interview_result["conversation_state"],
            "message": interview_result["message"],
            "is_complete": interview_result["is_complete"],
            "handoff": interview_result["handoff"],
            "mock": settings.use_mock,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/interview/update-tab-changes")
async def api_interview_update_tab_changes(req: InterviewUpdateTabChangeRequest):
    try:
        session = get_session(req.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        session.tab_changes_count = req.warnings_count
        save_session(session)
        return {
            "session_id": session.session_id,
            "tab_changes_count": session.tab_changes_count,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/interview/complete")
async def api_interview_complete(req: InterviewCompleteRequest):
    try:
        session = get_session(req.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        score = score_candidate(
            session.resume_analysis,
            session.handoff.get("assessments") if session.handoff else None,
        )
        feedback = generate_feedback(score, session.resume_analysis)
        return {
            "session_id": session.session_id,
            "transcript": session.transcript,
            "handoff": session.handoff,
            "score": score,
            "feedback": feedback,
            "mock": settings.use_mock,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/interview/save-review")
async def api_interview_save_review(req: InterviewSaveReviewRequest):
    try:
        result = save_review(req.session_id, req.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/interview/upload-recording")
async def api_interview_upload_recording(
    session_id: Annotated[str, Form()],
    recording: Annotated[UploadFile, File()],
    review_id: Annotated[str | None, Form()] = None,
):
    try:
        data = await recording.read()
        result = save_recording(session_id, review_id, data, recording.filename or "interview.webm")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


# ============================================================
# B2B: Employer Auth
# ============================================================

@app.post("/api/employer/auth/google")
async def api_employer_google_auth(req: GoogleAuthRequest):
    """Verify Google ID token, create or fetch employer, return JWT."""
    if not settings.google_client_id:
        raise HTTPException(status_code=501, detail="Google auth not configured — set GOOGLE_CLIENT_ID")
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as grequests
        idinfo = id_token.verify_oauth2_token(
            req.credential,
            grequests.Request(),
            settings.google_client_id,
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {e}")

    email = idinfo.get("email", "").lower()
    name = idinfo.get("name", "")
    if not email:
        raise HTTPException(status_code=400, detail="Google account has no email")

    # Get existing or create new employer
    emp = get_employer_by_email(email)
    if not emp:
        company = req.company_name or name or email.split("@")[0]
        # Create with a random unusable password (Google-authed users won't use password login)
        import secrets
        emp = create_employer(email, secrets.token_hex(32), company)

    token = create_token(emp.employer_id, emp.email, emp.company_name)
    return {
        "token": token,
        "employer_id": emp.employer_id,
        "email": emp.email,
        "company_name": emp.company_name,
    }


@app.post("/api/employer/register")
async def api_employer_register(req: EmployerRegisterRequest):
    try:
        emp = create_employer(req.email, req.password, req.company_name)
        token = create_token(emp.employer_id, emp.email, emp.company_name)
        return {"token": token, "employer_id": emp.employer_id,
                "email": emp.email, "company_name": emp.company_name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/employer/login")
async def api_employer_login(req: EmployerLoginRequest):
    emp = authenticate_employer(req.email, req.password)
    if not emp:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_token(emp.employer_id, emp.email, emp.company_name)
    return {"token": token, "employer_id": emp.employer_id,
            "email": emp.email, "company_name": emp.company_name}


@app.get("/api/employer/me")
async def api_employer_me(authorization: Annotated[str | None, Header()] = None):
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    emp = get_employer(claims["sub"])
    if not emp:
        raise HTTPException(status_code=404, detail="Employer not found")
    return {"employer_id": emp.employer_id, "email": emp.email, "company_name": emp.company_name}


# ============================================================
# B2B: Jobs (public + employer-protected)
# ============================================================

@app.get("/api/jobs")
async def api_list_jobs():
    """Public: list all active job openings."""
    jobs = list_jobs(active_only=True)
    return [{"job_id": j.job_id, "title": j.title, "location": j.location,
             "employment_type": j.employment_type, "application_count": j.application_count,
             "created_at": j.created_at} for j in jobs]


@app.get("/api/jobs/{job_id}")
async def api_get_job(job_id: str):
    """Public: get full job details."""
    job = get_job(job_id)
    if not job or not job.is_active:
        raise HTTPException(status_code=404, detail="Job not found")
    emp = get_employer(job.employer_id)
    return {
        "job_id": job.job_id,
        "title": job.title,
        "description": job.description,
        "location": job.location,
        "employment_type": job.employment_type,
        "company_name": emp.company_name if emp else "Company",
        "application_count": job.application_count,
        "created_at": job.created_at,
    }


@app.post("/api/employer/jobs")
async def api_create_job(req: JobCreateRequest,
                         authorization: Annotated[str | None, Header()] = None):
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    allowed, reason = employer_can_post_job(claims["sub"])
    if not allowed:
        raise HTTPException(status_code=403, detail=reason)
    try:
        job = create_job(
            employer_id=claims["sub"],
            title=req.title,
            description=req.description,
            location=req.location,
            employment_type=req.employment_type,
        )
        return {"job_id": job.job_id, "title": job.title, "is_active": job.is_active,
                "created_at": job.created_at}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/employer/jobs")
async def api_employer_list_jobs(authorization: Annotated[str | None, Header()] = None):
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    jobs = list_employer_jobs(claims["sub"])
    return [{"job_id": j.job_id, "title": j.title, "location": j.location,
             "employment_type": j.employment_type, "is_active": j.is_active,
             "application_count": j.application_count, "created_at": j.created_at}
            for j in jobs]


@app.patch("/api/employer/jobs/{job_id}")
async def api_update_job(job_id: str, req: JobUpdateRequest,
                         authorization: Annotated[str | None, Header()] = None):
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    job = get_job(job_id)
    if not job or job.employer_id != claims["sub"]:
        raise HTTPException(status_code=404, detail="Job not found")
    if req.title is not None:
        job.title = req.title
    if req.description is not None:
        job.description = req.description
    if req.location is not None:
        job.location = req.location
    if req.employment_type is not None:
        job.employment_type = req.employment_type
    if req.is_active is not None:
        job.is_active = req.is_active
    update_job(job)
    return {"job_id": job.job_id, "is_active": job.is_active}


# ============================================================
# B2B: Applications — candidate submits resume, auto-interview
# ============================================================

@app.post("/api/apply")
async def api_apply(req: ApplicationSubmitRequest):
    """Candidate applies for a job — immediately starts interview pipeline."""
    job = get_job(req.job_id)
    if not job or not job.is_active:
        raise HTTPException(status_code=404, detail="Job not found or no longer accepting applications")

    # Create application record
    application = create_application(
        job_id=job.job_id,
        employer_id=job.employer_id,
        candidate_name=req.candidate_name,
        candidate_email=req.candidate_email,
        resume=req.resume,
    )

    # Run the pipeline: parse JD, analyze resume, generate questions
    try:
        requirements = parse_jd(job.description)
        resume_analysis = analyze_resume(req.resume, requirements, application.application_id)
        questions = generate_questions(requirements, application.application_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {e}")

    # Create interview session
    session = create_session(
        candidate_id=application.application_id,
        job_description=job.description,
        resume=req.resume,
        requirements=requirements,
        resume_analysis=resume_analysis,
        questions=questions,
    )

    # First interview turn
    try:
        interview_result = interview_turn(
            role=requirements,
            candidate_id=application.application_id,
            resume_analysis=resume_analysis,
            screening_questions=questions,
            conversation_history=[],
            conversation_state=None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Interview start failed: {e}")

    transcript = [{"speaker": "aria", "text": interview_result["message"]}]
    session.transcript = transcript
    session.history = [{"role": "model", "content": interview_result["message"]}]
    session.conversation_state = interview_result["conversation_state"]
    session.handoff = interview_result["handoff"]
    session.is_complete = interview_result["is_complete"]
    save_session(session)

    # Link session to application
    application.session_id = session.session_id
    application.status = "interviewing"
    update_application(application)

    return {
        "application_id": application.application_id,
        "session_id": session.session_id,
        "job_title": job.title,
        "transcript": transcript,
        "message": interview_result["message"],
        "conversation_state": interview_result["conversation_state"],
        "is_complete": interview_result["is_complete"],
        "mock": settings.use_mock,
    }


@app.post("/api/apply/message")
async def api_apply_message(req: InterviewMessageRequest):
    """Continue the candidate's interview."""
    session = get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.is_complete:
        raise HTTPException(status_code=400, detail="Interview already complete")

    session.history.append({"role": "user", "content": req.message})
    session.transcript.append({"speaker": "candidate", "text": req.message})

    try:
        interview_result = interview_turn(
            role=session.requirements,
            candidate_id=session.candidate_id,
            resume_analysis=session.resume_analysis,
            screening_questions=session.questions,
            conversation_history=session.history,
            conversation_state=session.conversation_state,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    session.history.append({"role": "model", "content": interview_result["message"]})
    session.transcript.append({"speaker": "aria", "text": interview_result["message"]})
    session.conversation_state = interview_result["conversation_state"]
    session.handoff = interview_result["handoff"]
    session.is_complete = interview_result["is_complete"]
    save_session(session)

    return {
        "session_id": session.session_id,
        "transcript": session.transcript,
        "message": interview_result["message"],
        "conversation_state": interview_result["conversation_state"],
        "is_complete": interview_result["is_complete"],
        "mock": settings.use_mock,
    }


@app.post("/api/apply/complete")
async def api_apply_complete(req: InterviewCompleteRequest):
    """Finalize interview — score and save results."""
    session = get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    score = score_candidate(
        session.resume_analysis,
        session.handoff.get("assessments") if session.handoff else None,
    )
    feedback = generate_feedback(score, session.resume_analysis)

    # Find application by candidate_id == application_id
    # candidate_id on session is the application_id
    application = get_application(session.candidate_id)
    if application:
        application.score = score
        application.feedback = feedback
        application.status = "scored"
        # Save review
        review_result = save_review(session.session_id, {
            "application_id": application.application_id,
            "candidate_name": application.candidate_name,
            "candidate_email": application.candidate_email,
            "job_id": application.job_id,
            "transcript": session.transcript,
            "score": score,
            "feedback": feedback,
            "handoff": session.handoff,
        })
        application.review_id = review_result.get("review_id")
        update_application(application)
        
        # Emit interview_transcript_embedding Signal if applicant has consent
        # Requirement 3.4: after interview completion, emit signal with session metadata (no PII)
        try:
            processor = Signal_Processor()
            processor.normalize_signal(
                engineer_id=application.candidate_email,  # Use email as engineer identifier
                signal_type=SignalType.INTERVIEW_TRANSCRIPT_EMBEDDING,
                raw_payload={
                    "source": "platform_interview",
                    "session_id": session.session_id,
                },
                source_system="platform_interview",
                employer_id=application.employer_id,
                consent_version="1.0",
            )
        except ConsentError:
            # Silently skip signal ingestion if no consent - don't fail the apply/complete
            pass
        except Exception:
            # Don't fail the endpoint if signal ingestion fails for any reason
            pass

        # Call hiring_ability_predictor and store in evaluation_model_score
        # Requirements 3.1, 3.2: supplement LLM score with model prediction
        try:
            since_dt = datetime.now(timezone.utc) - timedelta(days=30)
            until_dt = datetime.now(timezone.utc)
            pseudonymous_id = compute_pseudonymous_id(application.candidate_email)
            engineer_signals = query_signals(pseudonymous_id, None, since_dt, until_dt)
            pred = hiring_ability_predictor.predict(
                engineer_id=application.candidate_email,
                signals=engineer_signals,
            )
            application.evaluation_model_score = {
                "score": pred.score,
                "model_version": pred.model_version,
                "confidence_interval": list(pred.confidence_interval),
                "model_type": pred.model_type.value,
            }
            update_application(application)
        except Exception:
            # Don't fail the endpoint if prediction fails
            pass

    return {
        "session_id": session.session_id,
        "transcript": session.transcript,
        "score": score,
        "feedback": feedback,
        "mock": settings.use_mock,
    }


# ============================================================
# B2B: Employer reviews applicants
# ============================================================

@app.get("/api/employer/jobs/{job_id}/applicants")
async def api_job_applicants(job_id: str,
                              authorization: Annotated[str | None, Header()] = None):
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    job = get_job(job_id)
    if not job or job.employer_id != claims["sub"]:
        raise HTTPException(status_code=404, detail="Job not found")
    apps = list_job_applications(job_id)
    return {
        "job_id": job_id,
        "job_title": job.title,
        "applicants": [
            {
                "application_id": a.application_id,
                "candidate_name": a.candidate_name,
                "candidate_email": a.candidate_email,
                "status": a.status,
                "score": a.score,
                "feedback": a.feedback,
                "review_id": a.review_id,
                "created_at": a.created_at,
            }
            for a in apps
        ],
    }


@app.get("/api/employer/applicants/{application_id}")
async def api_get_applicant(application_id: str,
                             authorization: Annotated[str | None, Header()] = None):
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    app = get_application(application_id)
    if not app or app.employer_id != claims["sub"]:
        raise HTTPException(status_code=404, detail="Application not found")
    session = get_session(app.session_id) if app.session_id else None
    return {
        "application_id": app.application_id,
        "job_id": app.job_id,
        "candidate_name": app.candidate_name,
        "candidate_email": app.candidate_email,
        "resume": app.resume,
        "status": app.status,
        "score": app.score,
        "feedback": app.feedback,
        "transcript": session.transcript if session else [],
        "review_id": app.review_id,
        "evaluation_model_score": app.evaluation_model_score,
        "created_at": app.created_at,
    }


# ============================================================
# Pricing & Payments (Razorpay)
# ============================================================

PLAN_PRICES_PAISE = {
    "starter": 9900,   # ₹99 in paise
    "growth":  19900,  # ₹199 in paise
}


@app.get("/api/pricing")
async def api_pricing():
    """Public: return plan details."""
    return {
        "plans": [
            {"id": "starter", "name": "Starter", "price": 99, "currency": "INR",
             "job_limit": 3, "features": ["3 active job postings", "AI interviews", "Candidate scoring", "Email support"]},
            {"id": "growth", "name": "Growth", "price": 199, "currency": "INR",
             "job_limit": 20, "features": ["20 active job postings", "AI interviews", "Candidate scoring", "Priority support", "Analytics"]},
            {"id": "enterprise", "name": "Enterprise", "price": None, "currency": "INR",
             "job_limit": None, "features": ["Unlimited postings", "Custom AI tuning", "Dedicated support", "SLA", "Custom integrations"]},
        ]
    }


@app.post("/api/employer/payment/create-order")
async def api_create_order(req: CreateOrderRequest,
                           authorization: Annotated[str | None, Header()] = None):
    """Create a Razorpay order for the selected plan."""
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        raise HTTPException(status_code=501, detail="Payment gateway not configured")
    try:
        import razorpay
        client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))
        order = client.order.create({
            "amount": PLAN_PRICES_PAISE[req.plan],
            "currency": "INR",
            "notes": {
                "employer_id": claims["sub"],
                "plan": req.plan,
            }
        })
        return {
            "order_id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "key_id": settings.razorpay_key_id,
            "plan": req.plan,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/employer/payment/verify")
async def api_verify_payment(req: VerifyPaymentRequest,
                              authorization: Annotated[str | None, Header()] = None):
    """Verify Razorpay signature and activate plan."""
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not settings.razorpay_key_secret:
        raise HTTPException(status_code=501, detail="Payment gateway not configured")
    try:
        import razorpay
        client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))
        client.utility.verify_payment_signature({
            "razorpay_order_id": req.razorpay_order_id,
            "razorpay_payment_id": req.razorpay_payment_id,
            "razorpay_signature": req.razorpay_signature,
        })
    except Exception:
        raise HTTPException(status_code=400, detail="Payment verification failed — invalid signature")

    emp = activate_plan(claims["sub"], req.plan)
    return {
        "success": True,
        "plan": emp.plan,
        "plan_expires_at": emp.plan_expires_at,
        "message": f"{PLANS[req.plan]['name']} plan activated successfully",
    }


@app.get("/api/employer/plan")
async def api_get_plan(authorization: Annotated[str | None, Header()] = None):
    """Return current employer plan status."""
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    emp = get_employer(claims["sub"])
    if not emp:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "plan": emp.plan,
        "plan_expires_at": emp.plan_expires_at,
        "can_post_jobs": emp.plan != "free",
    }


# ============================================================
# Signal Management
# ============================================================

@app.post("/api/signals/ingest")
async def api_signal_ingest(req: SignalIngestRequest):
    """Ingest a behavioral signal for an engineer.
    
    Returns HTTP 403 if consent is missing.
    Returns HTTP 400 if signal type is invalid.
    """
    try:
        # Validate signal_type — ConsentError is a subclass of ValueError, catch it first
        signal_type = SignalType(req.signal_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid signal_type: '{req.signal_type}'. Must be one of: {[t.value for t in SignalType]}"
        )
    
    try:
        processor = Signal_Processor()
        signal = processor.normalize_signal(
            engineer_id=req.engineer_id,
            signal_type=signal_type,
            raw_payload=req.payload,
            source_system=req.source_system,
            employer_id=req.employer_id,
            consent_version=req.consent_version,
        )
        
        return SignalResponse(
            signal_id=signal.signal_id,
            pseudonymous_id=signal.pseudonymous_id,
            signal_type=signal.signal_type.value,
            payload=signal.payload,
            source_system=signal.source_system,
            collected_at=signal.collected_at,
            consent_version=signal.consent_version,
            employer_id=signal.employer_id,
            revoked=signal.revoked,
        )
    except ConsentError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/signals/me")
async def api_signals_me(
    engineer_id: str,
    signal_type: str | None = None,
    since: str | None = None,
    until: str | None = None,
):
    """Engineer self-service: retrieve own signals.
    
    Query parameters:
    - engineer_id (required): Engineer identifier
    - signal_type (optional): Filter by specific signal type
    - since (optional): ISO datetime string (defaults to 30 days ago)
    - until (optional): ISO datetime string (defaults to now)
    """
    # Parse optional signal_type filter first (can raise 400)
    signal_type_enum = None
    if signal_type is not None:
        try:
            signal_type_enum = SignalType(signal_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid signal_type: '{signal_type}'. Must be one of: {[t.value for t in SignalType]}"
            )
    
    try:
        # Parse date range with defaults
        if until is None:
            until_dt = datetime.now(timezone.utc)
        else:
            until_dt = datetime.fromisoformat(until)
            if until_dt.tzinfo is None:
                until_dt = until_dt.replace(tzinfo=timezone.utc)
        
        if since is None:
            since_dt = until_dt - timedelta(days=30)
        else:
            since_dt = datetime.fromisoformat(since)
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=timezone.utc)
        
        # Compute pseudonymous ID and query
        pseudonymous_id = compute_pseudonymous_id(engineer_id)
        signals = query_signals(pseudonymous_id, signal_type_enum, since_dt, until_dt)
        
        return [
            SignalResponse(
                signal_id=s.signal_id,
                pseudonymous_id=s.pseudonymous_id,
                signal_type=s.signal_type.value,
                payload=s.payload,
                source_system=s.source_system,
                collected_at=s.collected_at,
                consent_version=s.consent_version,
                employer_id=s.employer_id,
                revoked=s.revoked,
            )
            for s in signals
        ]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Onboarding Module
# ============================================================

@app.post("/api/employer/onboarding/templates")
async def api_create_onboarding_template(
    req: OnboardingTemplateCreateRequest,
    authorization: Annotated[str | None, Header()] = None,
):
    """Employer: create an onboarding template."""
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        template = OnboardingTemplate(
            template_id=str(uuid.uuid4()),
            employer_id=claims["sub"],
            name=req.name,
            tasks=[
                OnboardingTask(
                    task_id=str(uuid.uuid4()),
                    title=t.title,
                    description=t.description,
                    due_offset_days=t.due_offset_days,
                    assigned_role=t.assigned_role,
                )
                for t in req.tasks
            ],
        )
        save_template(template)
        return {
            "template_id": template.template_id,
            "employer_id": template.employer_id,
            "name": template.name,
            "version": template.version,
            "created_at": template.created_at,
            "tasks": [
                {
                    "task_id": t.task_id,
                    "title": t.title,
                    "description": t.description,
                    "due_offset_days": t.due_offset_days,
                    "assigned_role": t.assigned_role,
                }
                for t in template.tasks
            ],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/employer/onboarding/templates/{template_id}")
async def api_get_onboarding_template(
    template_id: str,
    authorization: Annotated[str | None, Header()] = None,
):
    """Employer: retrieve an onboarding template by ID."""
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    template = get_template(template_id)
    if not template or template.employer_id != claims["sub"]:
        raise HTTPException(status_code=404, detail="Template not found")
    return {
        "template_id": template.template_id,
        "employer_id": template.employer_id,
        "name": template.name,
        "version": template.version,
        "created_at": template.created_at,
        "tasks": [
            {
                "task_id": t.task_id,
                "title": t.title,
                "description": t.description,
                "due_offset_days": t.due_offset_days,
                "assigned_role": t.assigned_role,
            }
            for t in template.tasks
        ],
    }


@app.patch("/api/employer/onboarding/templates/{template_id}")
async def api_update_onboarding_template(
    template_id: str,
    req: OnboardingTemplateUpdateRequest,
    authorization: Annotated[str | None, Header()] = None,
):
    """Employer: update an onboarding template (name and/or tasks)."""
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    template = get_template(template_id)
    if not template or template.employer_id != claims["sub"]:
        raise HTTPException(status_code=404, detail="Template not found")
    try:
        if req.name is not None:
            template.name = req.name
        if req.tasks is not None:
            template.tasks = [
                OnboardingTask(
                    task_id=str(uuid.uuid4()),
                    title=t.title,
                    description=t.description,
                    due_offset_days=t.due_offset_days,
                    assigned_role=t.assigned_role,
                )
                for t in req.tasks
            ]
        template.version += 1
        save_template(template)
        return {
            "template_id": template.template_id,
            "employer_id": template.employer_id,
            "name": template.name,
            "version": template.version,
            "created_at": template.created_at,
            "tasks": [
                {
                    "task_id": t.task_id,
                    "title": t.title,
                    "description": t.description,
                    "due_offset_days": t.due_offset_days,
                    "assigned_role": t.assigned_role,
                }
                for t in template.tasks
            ],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/employer/onboarding/plans")
async def api_list_employer_onboarding_plans(
    authorization: Annotated[str | None, Header()] = None,
):
    """Employer: list all onboarding plans (one per engineer) for this employer."""
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        plans = list_employer_plans(claims["sub"])
        return [
            {
                "plan_id": p.plan_id,
                "engineer_id": p.engineer_id,
                "employer_id": p.employer_id,
                "template_id": p.template_id,
                "hire_date": p.hire_date,
                "tasks": [
                    {
                        "task_id": t.task_id,
                        "title": t.title,
                        "description": t.description,
                        "due_offset_days": t.due_offset_days,
                        "assigned_role": t.assigned_role,
                        "completed_at": t.completed_at,
                    }
                    for t in p.tasks
                ],
                "created_at": p.created_at,
            }
            for p in plans
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/employer/onboarding/templates")
async def api_list_employer_onboarding_templates(
    authorization: Annotated[str | None, Header()] = None,
):
    """Employer: list all onboarding templates."""
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        templates = list_employer_templates(claims["sub"])
        return [
            {
                "template_id": t.template_id,
                "name": t.name,
                "version": t.version,
                "task_count": len(t.tasks),
                "created_at": t.created_at,
            }
            for t in templates
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/onboarding/plans")
async def api_create_onboarding_plan(req: OnboardingPlanCreateRequest):
    """Create an onboarding plan for an engineer from a template."""
    try:
        plan = create_plan_from_template(
            engineer_id=req.engineer_id,
            employer_id=req.employer_id,
            template_id=req.template_id,
            hire_date=req.hire_date,
        )
        return {
            "plan_id": plan.plan_id,
            "engineer_id": plan.engineer_id,
            "employer_id": plan.employer_id,
            "template_id": plan.template_id,
            "hire_date": plan.hire_date,
            "created_at": plan.created_at,
            "tasks": [
                {
                    "task_id": t.task_id,
                    "title": t.title,
                    "description": t.description,
                    "due_offset_days": t.due_offset_days,
                    "assigned_role": t.assigned_role,
                    "completed_at": t.completed_at,
                }
                for t in plan.tasks
            ],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/onboarding/plans/{plan_id}")
async def api_get_onboarding_plan(plan_id: str):
    """Retrieve an onboarding plan by ID."""
    plan = get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {
        "plan_id": plan.plan_id,
        "engineer_id": plan.engineer_id,
        "employer_id": plan.employer_id,
        "template_id": plan.template_id,
        "hire_date": plan.hire_date,
        "created_at": plan.created_at,
        "tasks": [
            {
                "task_id": t.task_id,
                "title": t.title,
                "description": t.description,
                "due_offset_days": t.due_offset_days,
                "assigned_role": t.assigned_role,
                "completed_at": t.completed_at,
            }
            for t in plan.tasks
        ],
    }


@app.post("/api/onboarding/plans/{plan_id}/tasks/{task_id}/complete")
async def api_complete_onboarding_task(plan_id: str, task_id: str):
    """Mark an onboarding task as complete and emit an onboarding_task_completion Signal."""
    try:
        updated_plan = complete_task(plan_id, task_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Find the completed task to get its title for the Signal payload
    completed_task_title = next(
        (t.title for t in updated_plan.tasks if t.task_id == task_id),
        task_id,
    )

    # Emit onboarding_task_completion Signal (Requirement 4.3)
    try:
        processor = Signal_Processor()
        processor.normalize_signal(
            engineer_id=updated_plan.engineer_id,
            signal_type=SignalType.ONBOARDING_TASK_COMPLETION,
            raw_payload={
                "plan_id": plan_id,
                "task_id": task_id,
                "task_title": completed_task_title,
            },
            source_system="platform_onboarding",
            employer_id=updated_plan.employer_id,
            consent_version="1.0",
        )
    except ConsentError:
        # Silently skip if engineer has no consent — don't fail the completion
        pass
    except Exception:
        # Don't fail the endpoint if signal emission fails for any reason
        pass

    return {
        "plan_id": updated_plan.plan_id,
        "task_id": task_id,
        "completed": True,
        "tasks": [
            {
                "task_id": t.task_id,
                "title": t.title,
                "description": t.description,
                "due_offset_days": t.due_offset_days,
                "assigned_role": t.assigned_role,
                "completed_at": t.completed_at,
            }
            for t in updated_plan.tasks
        ],
    }
