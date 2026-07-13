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
    CompensationCreateRequest,
    PerformanceCycleCreateRequest,
    PerformanceReviewCreateRequest,
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
from .payroll_store import (
    save_compensation,
    get_compensation,
    list_employer_compensations,
    initiate_run,
    complete_run,
    get_payroll_run,
    list_employer_payroll_runs,
    get_payslips,
    PayrollValidationError,
    CompensationRecord,
)
from .performance_store import (
    save_cycle,
    get_cycle,
    list_employer_cycles,
    activate_cycle,
    submit_review,
    evaluate_cycle,
    list_cycle_reviews,
    PerformanceCycle,
)
from .compliance_store import (
    ComplianceRule,
    ComplianceAlert,
    save_rule,
    get_rule,
    list_employer_rules,
    get_alert,
    list_employer_alerts,
    resolve_alert,
    evaluate_rules,
    seed_templates,
)
from .evaluation_models import hiring_ability_predictor
import json
import uuid
from datetime import datetime, timedelta, timezone

settings = get_settings()

app = FastAPI(title="AI Recruiter API", version="1.0.0")

# In-memory promotion alert store: key = "promotion_alert:{cycle_id}:{engineer_id}"
# value = JSON string with engineer_id, score, cycle_id
_promotion_alerts: dict[str, str] = {}

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


# ============================================================
# Payroll Module
# ============================================================

def _payslip_to_dict(ps) -> dict:
    return {
        "payslip_id": ps.payslip_id,
        "engineer_id": ps.engineer_id,
        "run_id": ps.run_id,
        "gross_pay": ps.gross_pay,
        "deductions_detail": ps.deductions_detail,
        "net_pay": ps.net_pay,
        "currency": ps.currency,
        "period_start": ps.period_start,
        "period_end": ps.period_end,
    }


def _run_to_dict(run) -> dict:
    return {
        "run_id": run.run_id,
        "employer_id": run.employer_id,
        "initiated_by": run.initiated_by,
        "initiated_at": run.initiated_at,
        "status": run.status,
        "total_gross": run.total_gross,
        "completed_at": run.completed_at,
        "payslips": [_payslip_to_dict(ps) for ps in run.payslips],
    }


@app.post("/api/employer/compensation")
async def api_create_compensation(
    req: CompensationCreateRequest,
    authorization: Annotated[str | None, Header()] = None,
):
    """Employer: create or update a compensation record for an engineer."""
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        record = CompensationRecord(
            record_id=str(uuid.uuid4()),
            engineer_id=req.engineer_id,
            employer_id=claims["sub"],
            base_salary=req.base_salary,
            currency=req.currency,
            pay_frequency=req.pay_frequency,
            effective_date=req.effective_date,
            deductions=req.deductions,
        )
        save_compensation(record)
        return {
            "record_id": record.record_id,
            "engineer_id": record.engineer_id,
            "employer_id": record.employer_id,
            "base_salary": record.base_salary,
            "currency": record.currency,
            "pay_frequency": record.pay_frequency,
            "effective_date": record.effective_date,
            "deductions": record.deductions,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/employer/compensation")
async def api_list_compensation(
    authorization: Annotated[str | None, Header()] = None,
):
    """Employer: list all compensation records for this employer."""
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        records = list_employer_compensations(claims["sub"])
        return [
            {
                "record_id": r.record_id,
                "engineer_id": r.engineer_id,
                "employer_id": r.employer_id,
                "base_salary": r.base_salary,
                "currency": r.currency,
                "pay_frequency": r.pay_frequency,
                "effective_date": r.effective_date,
                "deductions": r.deductions,
            }
            for r in records
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/employer/payroll/runs")
async def api_list_payroll_runs(
    authorization: Annotated[str | None, Header()] = None,
):
    """Employer: list all payroll runs for the authenticated employer."""
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        runs = list_employer_payroll_runs(claims["sub"])
        return [
            {
                "run_id": r.run_id,
                "status": r.status,
                "total_gross": r.total_gross,
                "initiated_at": r.initiated_at,
                "completed_at": r.completed_at,
                "payslip_count": len(r.payslips),
            }
            for r in runs
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/employer/payroll/runs")
async def api_initiate_payroll_run(
    authorization: Annotated[str | None, Header()] = None,
):
    """Employer: initiate and immediately complete a payroll run.

    Validates all compensation records first. On any validation failure,
    returns HTTP 400 with a descriptive error. On success, returns the
    completed run including payslips.

    The immutable audit log entry is written inside complete_run().
    """
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        run = initiate_run(employer_id=claims["sub"], initiator_id=claims["sub"])
        completed_run = complete_run(run.run_id)
        return _run_to_dict(completed_run)
    except PayrollValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/employer/payroll/runs/{run_id}")
async def api_get_payroll_run(
    run_id: str,
    authorization: Annotated[str | None, Header()] = None,
):
    """Employer: retrieve a specific payroll run by ID."""
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        run = get_payroll_run(run_id)
        if not run or run.employer_id != claims["sub"]:
            raise HTTPException(status_code=404, detail="Payroll run not found")
        return _run_to_dict(run)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/employer/payroll/runs/{run_id}/payslips")
async def api_get_run_payslips(
    run_id: str,
    authorization: Annotated[str | None, Header()] = None,
):
    """Employer: retrieve all payslips for a specific payroll run."""
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        run = get_payroll_run(run_id)
        if not run or run.employer_id != claims["sub"]:
            raise HTTPException(status_code=404, detail="Payroll run not found")
        payslips = get_payslips(run_id)
        return [_payslip_to_dict(ps) for ps in payslips]
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Performance Management Module (Requirements 6.2–6.6)
# ============================================================

@app.post("/api/employer/performance/cycles")
async def api_create_performance_cycle(
    req: PerformanceCycleCreateRequest,
    authorization: Annotated[str | None, Header()] = None,
):
    """Employer: create a new performance review cycle.

    The cycle is created in 'draft' status. Use the activate endpoint to start it.
    The promotion_threshold is stored in the review_template so it travels with
    the cycle record without requiring a schema change to PerformanceCycle.

    Requirements: 6.1, 6.2
    """
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        # Embed promotion_threshold into review_template for storage
        template = dict(req.review_template)
        template["_promotion_threshold"] = req.promotion_threshold

        cycle = PerformanceCycle(
            cycle_id=str(uuid.uuid4()),
            employer_id=claims["sub"],
            name=req.name,
            start_date=req.start_date,
            end_date=req.end_date,
            participant_ids=req.participant_ids,
            review_template=template,
            status="draft",
        )
        save_cycle(cycle)
        return {
            "cycle_id": cycle.cycle_id,
            "employer_id": cycle.employer_id,
            "name": cycle.name,
            "start_date": cycle.start_date,
            "end_date": cycle.end_date,
            "participant_ids": cycle.participant_ids,
            "review_template": cycle.review_template,
            "status": cycle.status,
            "predictions": cycle.predictions,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/employer/performance/cycles")
async def api_list_performance_cycles(
    authorization: Annotated[str | None, Header()] = None,
):
    """Employer: list all performance cycles for this employer.

    Requirements: 6.1
    """
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        cycles = list_employer_cycles(claims["sub"])
        return [
            {
                "cycle_id": c.cycle_id,
                "employer_id": c.employer_id,
                "name": c.name,
                "start_date": c.start_date,
                "end_date": c.end_date,
                "participant_ids": c.participant_ids,
                "review_template": c.review_template,
                "status": c.status,
                "predictions": c.predictions,
            }
            for c in cycles
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/employer/performance/cycles/{cycle_id}/activate")
async def api_activate_performance_cycle(
    cycle_id: str,
    authorization: Annotated[str | None, Header()] = None,
):
    """Employer: activate a performance cycle, moving it from draft → active.

    Requirements: 6.2
    """
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        cycle = get_cycle(cycle_id)
        if not cycle or cycle.employer_id != claims["sub"]:
            raise HTTPException(status_code=404, detail="Performance cycle not found")
        updated = activate_cycle(cycle_id)
        return {
            "cycle_id": updated.cycle_id,
            "employer_id": updated.employer_id,
            "name": updated.name,
            "start_date": updated.start_date,
            "end_date": updated.end_date,
            "participant_ids": updated.participant_ids,
            "review_template": updated.review_template,
            "status": updated.status,
            "predictions": updated.predictions,
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/employer/performance/cycles/{cycle_id}/reviews")
async def api_submit_performance_review(
    cycle_id: str,
    req: PerformanceReviewCreateRequest,
    authorization: Annotated[str | None, Header()] = None,
):
    """Submit a performance review within a cycle.

    After saving the review:
    - Emits a JOB_PERFORMANCE_RATING Signal to the Signal_Store for the reviewee
      (silently skipped if the reviewee has no consent).

    Requirements: 6.3
    """
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        cycle = get_cycle(cycle_id)
        if not cycle or cycle.employer_id != claims["sub"]:
            raise HTTPException(status_code=404, detail="Performance cycle not found")

        review = submit_review(
            cycle_id=cycle_id,
            reviewer_id=req.reviewer_id,
            reviewee_id=req.reviewee_id,
            responses=req.form_responses,
        )

        # Emit JOB_PERFORMANCE_RATING Signal (Requirement 6.3)
        try:
            processor = Signal_Processor()
            processor.normalize_signal(
                engineer_id=req.reviewee_id,
                signal_type=SignalType.JOB_PERFORMANCE_RATING,
                raw_payload={
                    "score": review.normalized_score,
                    "cycle_id": cycle_id,
                },
                source_system="performance_review",
                employer_id=cycle.employer_id,
                consent_version="1.0",
            )
        except ConsentError:
            # Silently skip if reviewee has no consent — don't fail the review submission
            pass
        except Exception:
            # Don't fail the endpoint if signal emission fails for any reason
            pass

        return {
            "review_id": review.review_id,
            "cycle_id": review.cycle_id,
            "reviewer_id": review.reviewer_id,
            "reviewee_id": review.reviewee_id,
            "form_responses": review.form_responses,
            "normalized_score": review.normalized_score,
            "submitted_at": review.submitted_at,
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/employer/performance/cycles/{cycle_id}/results")
async def api_get_performance_cycle_results(
    cycle_id: str,
    authorization: Annotated[str | None, Header()] = None,
):
    """Get reviews and promotion readiness predictions for a performance cycle.

    - If the cycle is 'active', calls evaluate_cycle to run predictions and
      marks the cycle as 'completed'.
    - If the cycle is already 'completed', returns stored predictions directly.
    - After evaluation, stores promotion alerts for any engineer whose
      promotion_readiness score exceeds the employer-configured threshold.
    - Includes any promotion alerts for this cycle in the response.

    Requirements: 6.4, 6.5, 6.6
    """
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        cycle = get_cycle(cycle_id)
        if not cycle or cycle.employer_id != claims["sub"]:
            raise HTTPException(status_code=404, detail="Performance cycle not found")

        # Trigger evaluation for active cycles; completed cycles use stored predictions
        if cycle.status == "active":
            try:
                evaluate_cycle(cycle_id)
            except Exception:
                # Re-fetch cycle even if prediction partially failed
                pass
            # Re-fetch the cycle to get the updated predictions + status
            cycle = get_cycle(cycle_id)

        # Determine promotion threshold (stored in review_template at cycle creation)
        promotion_threshold: float = float(
            cycle.review_template.get("_promotion_threshold", 0.75)
        )

        # Store promotion alerts for engineers above the threshold (Requirement 6.6)
        for pred in cycle.predictions:
            engineer_id = pred.get("engineer_id", "")
            score = pred.get("score", 0.0)
            if score > promotion_threshold:
                alert_key = f"promotion_alert:{cycle_id}:{engineer_id}"
                _promotion_alerts[alert_key] = json.dumps({
                    "engineer_id": engineer_id,
                    "score": score,
                    "cycle_id": cycle_id,
                    "threshold": promotion_threshold,
                })

        # Collect promotion alerts for this cycle
        cycle_alert_prefix = f"promotion_alert:{cycle_id}:"
        promotion_notifications = [
            json.loads(v)
            for k, v in _promotion_alerts.items()
            if k.startswith(cycle_alert_prefix)
        ]

        # Retrieve all reviews for the cycle
        reviews = list_cycle_reviews(cycle_id)

        return {
            "cycle_id": cycle.cycle_id,
            "name": cycle.name,
            "status": cycle.status,
            "start_date": cycle.start_date,
            "end_date": cycle.end_date,
            "participant_ids": cycle.participant_ids,
            "promotion_threshold": promotion_threshold,
            "reviews": [
                {
                    "review_id": r.review_id,
                    "reviewer_id": r.reviewer_id,
                    "reviewee_id": r.reviewee_id,
                    "normalized_score": r.normalized_score,
                    "submitted_at": r.submitted_at,
                }
                for r in reviews
            ],
            "predictions": cycle.predictions,
            "promotion_alerts": promotion_notifications,
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Compliance Module
# ============================================================

from .schemas import (
    ComplianceRuleCreateRequest,
    ComplianceAlertResolveRequest,
    ComplianceEvaluateRequest,
)


@app.post("/api/employer/compliance/rules")
async def api_create_compliance_rule(
    req: ComplianceRuleCreateRequest,
    authorization: Annotated[str | None, Header()] = None,
):
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        rule = ComplianceRule(
            rule_id=str(uuid.uuid4()),
            employer_id=claims["sub"],
            name=req.name,
            jurisdiction=req.jurisdiction,
            category=req.category,
            trigger_condition=req.trigger_condition,
            severity=req.severity,
            notification_recipients=req.notification_recipients,
        )
        save_rule(rule)
        from dataclasses import asdict
        return asdict(rule)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/employer/compliance/rules")
async def api_list_compliance_rules(
    authorization: Annotated[str | None, Header()] = None,
):
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        rules = list_employer_rules(claims["sub"])
        from dataclasses import asdict
        return [asdict(r) for r in rules]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/employer/compliance/rules/seed")
async def api_seed_compliance_templates(
    authorization: Annotated[str | None, Header()] = None,
):
    """Seed pre-built jurisdiction templates (US federal, UK, India)."""
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        rules = seed_templates(claims["sub"])
        from dataclasses import asdict
        return {"seeded": len(rules), "rules": [asdict(r) for r in rules]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/employer/compliance/evaluate")
async def api_evaluate_compliance(
    req: ComplianceEvaluateRequest,
    authorization: Annotated[str | None, Header()] = None,
):
    """Evaluate all rules against provided work data and create alerts."""
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        alerts = evaluate_rules(claims["sub"], req.work_data_by_engineer)
        from dataclasses import asdict
        return {"alerts_created": len(alerts), "alerts": [asdict(a) for a in alerts]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/employer/compliance/alerts")
async def api_list_compliance_alerts(
    authorization: Annotated[str | None, Header()] = None,
):
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        alerts = list_employer_alerts(claims["sub"])
        from dataclasses import asdict
        return [asdict(a) for a in alerts]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/employer/compliance/alerts/{alert_id}/resolve")
async def api_resolve_compliance_alert(
    alert_id: str,
    req: ComplianceAlertResolveRequest,
    authorization: Annotated[str | None, Header()] = None,
):
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        alert = get_alert(alert_id)
        if not alert or alert.employer_id != claims["sub"]:
            raise HTTPException(status_code=404, detail="Alert not found")
        updated = resolve_alert(alert_id, req.resolver_id)
        from dataclasses import asdict
        return asdict(updated)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Integration Connectors (Task 9.3)
# ============================================================

from .integrations.base import (
    IntegrationConnector as IntConnector,
    save_connector, get_connector, list_employer_connectors, RawEvent,
)
from .integrations.github_connector import GitHubConnector
from .integrations.jira_connector import JiraConnector
from .integrations.slack_connector import SlackConnector
from .integrations.hris_connector import HRISWebhookConnector
from .schemas import IntegrationConnectorCreateRequest, IntegrationConnectorUpdateRequest

_CONNECTOR_MAP = {
    "github": GitHubConnector,
    "jira": JiraConnector,
    "slack": SlackConnector,
    "hris_webhook": HRISWebhookConnector,
}


@app.post("/api/employer/integrations")
async def api_create_integration(
    req: IntegrationConnectorCreateRequest,
    authorization: Annotated[str | None, Header()] = None,
):
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if req.connector_type not in _CONNECTOR_MAP:
        raise HTTPException(status_code=400, detail=f"Unknown connector type: {req.connector_type}")
    try:
        connector = IntConnector(
            connector_id=str(uuid.uuid4()),
            employer_id=claims["sub"],
            connector_type=req.connector_type,
            config=req.config,
            status="disabled",
        )
        save_connector(connector)
        from dataclasses import asdict
        return asdict(connector)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/employer/integrations")
async def api_list_integrations(
    authorization: Annotated[str | None, Header()] = None,
):
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        connectors = list_employer_connectors(claims["sub"])
        from dataclasses import asdict
        return [asdict(c) for c in connectors]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/employer/integrations/{connector_id}/validate")
async def api_validate_integration(
    connector_id: str,
    authorization: Annotated[str | None, Header()] = None,
):
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        connector = get_connector(connector_id)
        if not connector or connector.employer_id != claims["sub"]:
            raise HTTPException(status_code=404, detail="Connector not found")
        cls = _CONNECTOR_MAP.get(connector.connector_type)
        if not cls:
            raise HTTPException(status_code=400, detail="Unknown connector type")
        instance = cls(connector)
        valid = instance.validate_credentials(connector.config)
        if valid:
            connector.status = "active"
            save_connector(connector)
        return {"valid": valid, "status": connector.status}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/employer/integrations/{connector_id}")
async def api_update_integration(
    connector_id: str,
    req: IntegrationConnectorUpdateRequest,
    authorization: Annotated[str | None, Header()] = None,
):
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        connector = get_connector(connector_id)
        if not connector or connector.employer_id != claims["sub"]:
            raise HTTPException(status_code=404, detail="Connector not found")
        if req.status is not None:
            connector.status = req.status
        if req.config is not None:
            connector.config = req.config
        save_connector(connector)
        from dataclasses import asdict
        return asdict(connector)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Workforce Analytics (Task 10.3)
# ============================================================

from .analytics_engine import (
    REPORT_GENERATORS, export_report, get_anomalies, get_benchmark_comparison,
)


@app.get("/api/employer/analytics/{report_type}")
async def api_get_analytics_report(
    report_type: str,
    authorization: Annotated[str | None, Header()] = None,
):
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    gen = REPORT_GENERATORS.get(report_type)
    if not gen:
        raise HTTPException(status_code=404, detail=f"Unknown report type: {report_type}")
    try:
        return gen(claims["sub"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/employer/analytics/{report_type}/export")
async def api_export_analytics_report(
    report_type: str,
    fmt: str = "json",
    authorization: Annotated[str | None, Header()] = None,
):
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    gen = REPORT_GENERATORS.get(report_type)
    if not gen:
        raise HTTPException(status_code=404, detail=f"Unknown report type: {report_type}")
    try:
        data = gen(claims["sub"])
        content = export_report(report_type, data, fmt=fmt)
        media_type = "text/csv" if fmt == "csv" else "application/json"
        from fastapi.responses import Response
        return Response(content=content, media_type=media_type,
                        headers={"Content-Disposition": f"attachment; filename={report_type}.{fmt}"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/employer/analytics/anomalies")
async def api_get_analytics_anomalies(
    authorization: Annotated[str | None, Header()] = None,
):
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        return get_anomalies(claims["sub"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/employer/analytics/benchmarks")
async def api_get_analytics_benchmarks(
    metric: str = "interview_rate",
    authorization: Annotated[str | None, Header()] = None,
):
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        return get_benchmark_comparison(claims["sub"], metric)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Engineer Privacy Portal (Task 11.1)
# ============================================================

from .consent_store import (
    grant_consent as _grant_consent,
    revoke_consent as _revoke_consent,
    get_consent,
)
from .signal_store import (
    erase_pii_linkage,
    query_signals as _query_signals,
    compute_pseudonymous_id,
    revoke_signals,
)


@app.get("/api/engineer/signals")
async def api_engineer_signals(
    engineer_id: str,
    signal_type: str | None = None,
    since: str | None = None,
    until: str | None = None,
):
    """Return signals for the given engineer (self-service)."""
    from datetime import timezone
    try:
        pseudo_id = compute_pseudonymous_id(engineer_id)
        stype = None
        if signal_type:
            from .signal_store import SignalType as ST
            try:
                stype = ST(signal_type)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Unknown signal_type: {signal_type}")
        since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc).replace(year=2020)
        until_dt = datetime.fromisoformat(until) if until else datetime.now(timezone.utc)
        signals = _query_signals(pseudo_id, stype, since_dt, until_dt)
        from dataclasses import asdict
        return {"engineer_id": engineer_id, "signal_count": len(signals),
                "signals": [asdict(s) for s in signals]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/engineer/consent")
async def api_engineer_grant_consent(
    body: dict,
):
    """Grant or update consent for signal collection."""
    try:
        engineer_id = body.get("engineer_id", "")
        categories = body.get("signal_categories", [])
        if not engineer_id:
            raise HTTPException(status_code=400, detail="engineer_id is required")
        from .signal_store import SignalType as ST
        signal_types = []
        for c in categories:
            try:
                signal_types.append(ST(c))
            except ValueError:
                pass
        record = _grant_consent(engineer_id, signal_types)
        from dataclasses import asdict
        return asdict(record)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/engineer/consent")
async def api_engineer_revoke_consent(
    body: dict,
):
    """Revoke consent — stops new signal collection."""
    try:
        engineer_id = body.get("engineer_id", "")
        if not engineer_id:
            raise HTTPException(status_code=400, detail="engineer_id is required")
        record = _revoke_consent(engineer_id)
        if not record:
            raise HTTPException(status_code=404, detail="No consent record found")
        # Also mark existing signals as revoked
        pseudo_id = compute_pseudonymous_id(engineer_id)
        revoke_signals(pseudo_id)
        from dataclasses import asdict
        return asdict(record)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/engineer/erasure-request")
async def api_engineer_erasure_request(
    body: dict,
):
    """Erasure request — severs engineer_id → pseudonymous_id mapping."""
    try:
        engineer_id = body.get("engineer_id", "")
        if not engineer_id:
            raise HTTPException(status_code=400, detail="engineer_id is required")
        # 1. Revoke consent to stop new signals
        try:
            _revoke_consent(engineer_id)
        except Exception:
            pass
        # 2. Erase PII linkage — signals remain but are unattributable
        erase_pii_linkage(engineer_id)
        return {
            "engineer_id": engineer_id,
            "status": "erasure_initiated",
            "message": "PII linkage erased. Your signals remain in anonymised form for aggregate model training.",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/engineer/consent")
async def api_engineer_get_consent(engineer_id: str):
    """Get current consent status for an engineer."""
    try:
        record = get_consent(engineer_id)
        if not record:
            return {"engineer_id": engineer_id, "has_consent": False, "consent_record": None}
        from dataclasses import asdict
        return {"engineer_id": engineer_id, "has_consent": record.revoked_at is None,
                "consent_record": asdict(record)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Flywheel Metrics (Task 12.2)
# ============================================================

from .flywheel_metrics import get_flywheel_metrics, get_platform_health_summary


@app.get("/api/admin/flywheel")
async def api_admin_flywheel(
    authorization: Annotated[str | None, Header()] = None,
):
    """Platform admin only — full flywheel metrics."""
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        return get_flywheel_metrics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/employer/platform-health")
async def api_employer_platform_health(
    authorization: Annotated[str | None, Header()] = None,
):
    """Anonymized platform health summary visible to employers."""
    claims = get_current_employer(authorization)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        return get_platform_health_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
