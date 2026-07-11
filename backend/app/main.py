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
import json

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
