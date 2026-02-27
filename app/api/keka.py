# app/api/keka.py
# Keka Hire API Integration Router
# Endpoints for importing jobs and candidates from Keka into the local system.

from typing import Optional, List
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import (
    JobRequest, JobStatus, Candidate, CandidateStage,
    User, UserRole,
)
from app.api.auth import get_current_user, require_role
from app.utils.keka_client import get_keka_client, KekaAuthError, KekaAPIError

router = APIRouter(prefix="/keka", tags=["Keka Integration"])


# ── Response Schemas ──────────────────────────────────

class KekaJobOut(BaseModel):
    id: str
    title: str
    department: Optional[str] = None
    location: Optional[str] = None
    status: Optional[str] = None
    created_on: Optional[str] = None
    positions: Optional[int] = None


class KekaCandidateOut(BaseModel):
    id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    stage: Optional[str] = None
    source: Optional[str] = None
    applied_on: Optional[str] = None
    has_resume: bool = False


class ImportResult(BaseModel):
    imported: int
    skipped: int
    errors: List[str]
    candidates: List[dict]


class ConnectionStatus(BaseModel):
    status: str
    authenticated: bool
    jobs_found: Optional[int] = None
    error: Optional[str] = None
    base_url: str


# ── Helper ────────────────────────────────────────────

def _get_client():
    """Get KekaClient or raise a clear HTTP error."""
    try:
        return get_keka_client()
    except ValueError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Keka integration not configured: {e}"
        )


def _map_keka_stage(keka_stage: str) -> CandidateStage:
    """Map Keka candidate stage names to our CandidateStage enum."""
    mapping = {
        "applied": CandidateStage.applied,
        "new": CandidateStage.applied,
        "screening": CandidateStage.applied,
        "shortlisted": CandidateStage.shortlisted,
        "interview": CandidateStage.interviewed,
        "evaluation": CandidateStage.cv_evaluated,
        "offer": CandidateStage.offer_made,
        "hired": CandidateStage.hired,
        "rejected": CandidateStage.rejected,
    }
    stage_lower = (keka_stage or "").lower().strip()
    for key, value in mapping.items():
        if key in stage_lower:
            return value
    return CandidateStage.applied


# ── Endpoints ─────────────────────────────────────────


@router.get("/test-connection", response_model=ConnectionStatus)
def test_keka_connection(
    current_user: User = Depends(require_role(UserRole.hr)),
):
    """Test the connection to Keka API."""
    client = _get_client()
    result = client.test_connection()
    return ConnectionStatus(**result)


@router.get("/jobs", response_model=List[KekaJobOut])
def list_keka_jobs(
    status: Optional[str] = Query(None, description="Filter by job status"),
    current_user: User = Depends(require_role(UserRole.hr)),
):
    """Fetch all jobs from Keka Hire."""
    client = _get_client()

    try:
        raw_jobs = client.get_jobs(status=status)
    except KekaAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except KekaAPIError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=str(e))

    jobs = []
    for j in raw_jobs:
        jobs.append(KekaJobOut(
            id=str(j.get("id", "")),
            title=j.get("title", j.get("jobTitle", "Untitled")),
            department=j.get("department", j.get("departmentName", None)),
            location=j.get("location", j.get("locationName", None)),
            status=j.get("status", None),
            created_on=j.get("createdOn", j.get("createdDate", None)),
            positions=j.get("noOfPositions", j.get("positions", None)),
        ))

    return jobs


@router.get("/jobs/{keka_job_id}/candidates", response_model=List[KekaCandidateOut])
def list_keka_candidates(
    keka_job_id: str,
    current_user: User = Depends(require_role(UserRole.hr)),
):
    """Fetch all candidates for a Keka job."""
    client = _get_client()

    try:
        raw_candidates = client.get_candidates(keka_job_id)
    except KekaAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except KekaAPIError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=str(e))

    candidates = []
    for c in raw_candidates:
        candidates.append(KekaCandidateOut(
            id=str(c.get("id", "")),
            first_name=c.get("firstName", c.get("first_name", None)),
            last_name=c.get("lastName", c.get("last_name", None)),
            email=c.get("email", c.get("emailAddress", None)),
            phone=c.get("phone", c.get("mobileNumber", None)),
            stage=c.get("stage", c.get("currentStage", None)),
            source=c.get("source", c.get("candidateSource", None)),
            applied_on=c.get("appliedOn", c.get("appliedDate", None)),
            has_resume=bool(c.get("hasResume", c.get("resumeId", False))),
        ))

    return candidates


class ImportCandidatesRequest(BaseModel):
    local_job_id: int  # The local job_request ID to import into
    candidate_ids: Optional[List[str]] = None  # Specific Keka candidate IDs (None = all)


@router.post("/import-candidates/{keka_job_id}", response_model=ImportResult)
def import_candidates_from_keka(
    keka_job_id: str,
    body: ImportCandidatesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.hr)),
):
    """
    Import candidates from a Keka job into a local job request.

    Fetches candidates (and optionally their resumes) from Keka
    and creates corresponding Candidate records in the local DB.
    Skips candidates whose email already exists for the same job.
    """
    client = _get_client()

    # Verify local job exists
    local_job = db.query(JobRequest).filter(JobRequest.id == body.local_job_id).first()
    if not local_job:
        raise HTTPException(status_code=404, detail=f"Local job {body.local_job_id} not found")

    # Fetch candidates from Keka
    try:
        raw_candidates = client.get_candidates(keka_job_id)
    except KekaAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except KekaAPIError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=str(e))

    # Filter to specific IDs if provided
    if body.candidate_ids:
        id_set = set(body.candidate_ids)
        raw_candidates = [c for c in raw_candidates if str(c.get("id", "")) in id_set]

    imported = 0
    skipped = 0
    errors = []
    imported_candidates = []

    for kc in raw_candidates:
        keka_id = str(kc.get("id", ""))
        email = kc.get("email", kc.get("emailAddress", ""))
        name_parts = [
            kc.get("firstName", kc.get("first_name", "")),
            kc.get("lastName", kc.get("last_name", "")),
        ]
        name = " ".join(p for p in name_parts if p).strip() or "Unknown"
        phone = kc.get("phone", kc.get("mobileNumber", ""))
        keka_stage = kc.get("stage", kc.get("currentStage", "applied"))

        # Skip if candidate with same email already exists for this job
        if email:
            existing = db.query(Candidate).filter(
                Candidate.job_id == body.local_job_id,
                Candidate.email == email,
            ).first()
            if existing:
                skipped += 1
                continue

        # Try to fetch resume text
        resume_text = ""
        try:
            resume_bytes = client.get_candidate_resume(keka_id)
            if resume_bytes:
                # Store raw text representation — actual parsing can be done later
                resume_text = f"[Resume imported from Keka — candidate {keka_id}]"
        except Exception:
            pass  # Resume is optional

        # Parse salary info if available
        current_salary = None
        expected_salary = None
        try:
            current_salary = float(kc.get("currentSalary", 0)) or None
            expected_salary = float(kc.get("expectedSalary", 0)) or None
        except (ValueError, TypeError):
            pass

        try:
            candidate = Candidate(
                job_id=body.local_job_id,
                name=name,
                email=email or None,
                phone=phone or None,
                current_salary=current_salary,
                expected_salary=expected_salary,
                resume_text=resume_text or None,
                stage=_map_keka_stage(keka_stage),
                applied_at=datetime.now(timezone.utc),
            )
            db.add(candidate)
            db.flush()  # Get the ID

            imported += 1
            imported_candidates.append({
                "local_id": candidate.id,
                "keka_id": keka_id,
                "name": name,
                "email": email,
                "stage": candidate.stage.value,
            })
        except Exception as e:
            errors.append(f"Failed to import {name} ({email}): {str(e)}")

    db.commit()

    return ImportResult(
        imported=imported,
        skipped=skipped,
        errors=errors,
        candidates=imported_candidates,
    )


@router.get("/job-boards")
def list_keka_job_boards(
    current_user: User = Depends(require_role(UserRole.hr)),
):
    """Fetch all available job boards from Keka."""
    client = _get_client()

    try:
        boards = client.get_job_boards()
    except KekaAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except KekaAPIError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=str(e))

    return boards
