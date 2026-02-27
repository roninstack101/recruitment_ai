# app/api/cv_analysis.py
# CV Analysis Pipeline API
# Endpoints for persona generation, CV evaluation, and candidate ranking

import json
import os
import shutil
import tempfile
from typing import List

from fastapi import APIRouter, UploadFile, File, Form

from app.agents.persona_builder import build_personas
from app.agents.cv_evaluator import evaluate_candidate
from app.agents.candidate_ranker import rank_candidates
from app.agents.resume_parser import _extract_resumes_from_files
from app.utils.resume_skills import extract_skills_llm, extract_section

router = APIRouter()


# ─────────────────────────────────────────────
# POST /personas — Generate personas from profile
# ─────────────────────────────────────────────
@router.post("/personas")
def generate_personas(payload: dict):
    """
    Agent 6: Generate ideal candidate personas from a role profile.

    Expects JSON body:
    {
        "profile": { ... profile dict from Agent 2 ... }
    }

    Returns:
    {
        "personas": [ ... list of persona dicts ... ]
    }
    """
    profile = payload.get("profile", {})

    if not profile:
        return {"error": "Missing 'profile' in request body", "personas": []}

    personas = build_personas(profile)
    return {"personas": personas}


# ─────────────────────────────────────────────
# POST /evaluate — Evaluate CVs against personas
# ─────────────────────────────────────────────
@router.post("/evaluate")
async def evaluate_cvs(
    resumes: UploadFile = File(...),
    personas: str = Form(...)
):
    """
    Agent 7: Evaluate uploaded CVs against personas.

    Accepts multipart/form-data:
    - resumes: ZIP file containing PDF/DOCX/TXT resumes
    - personas: JSON string of the persona list

    Returns:
    {
        "evaluations": [ ... per-candidate evaluation dicts ... ]
    }
    """
    try:
        persona_list = json.loads(personas)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON in 'personas' field", "evaluations": []}

    if not persona_list:
        return {"error": "Persona list is empty", "evaluations": []}

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Save uploaded file
        file_path = os.path.join(tmp_dir, resumes.filename)
        with open(file_path, "wb") as f:
            shutil.copyfileobj(resumes.file, f)

        # Extract resumes using existing parser
        raw_resumes = _extract_resumes_from_files([file_path])

        if not raw_resumes:
            return {
                "error": "No valid resumes found in the uploaded file",
                "evaluations": []
            }

        # Parse each resume into structured form
        parsed_resumes = []
        for r in raw_resumes:
            text = r["text"]
            parsed_resumes.append({
                "candidate_id": r["file"],
                "summary": extract_section(
                    text, ["summary", "profile", "about", "objective"]
                ),
                "skills": extract_skills_llm(resume_text=text),
                "experience": extract_section(
                    text, ["experience", "work history", "employment"]
                ),
                "projects": extract_section(
                    text, ["projects", "key projects"]
                ),
                "raw_text": text,
                "resume_path": r["path"]
            })

        # Evaluate each candidate against all personas
        evaluations = []
        for cv in parsed_resumes:
            evaluation = evaluate_candidate(cv, persona_list)
            evaluations.append(evaluation)

    return {"evaluations": evaluations}


# ─────────────────────────────────────────────
# POST /rank — Rank evaluated candidates
# ─────────────────────────────────────────────
@router.post("/rank")
def rank_evaluated_candidates(payload: dict):
    """
    Agent 8: Rank candidates and produce top-N shortlist.

    Expects JSON body:
    {
        "evaluations": [ ... list of evaluation dicts from Agent 7 ... ],
        "top_n": 10  (optional, default 10)
    }

    Returns:
    {
        "shortlist": [...],
        "total_evaluated": N,
        "persona_distribution": {...},
        "notes": "..."
    }
    """
    evaluations = payload.get("evaluations", [])
    top_n = payload.get("top_n", 10)

    if not evaluations:
        return {"error": "No evaluations provided", "shortlist": []}

    result = rank_candidates(evaluations, top_n=top_n)
    return result


# ─────────────────────────────────────────────
# POST /full — Run the entire CV analysis pipeline
# ─────────────────────────────────────────────
@router.post("/full")
async def full_cv_pipeline(
    resumes: UploadFile = File(...),
    profile: str = Form(...),
    top_n: int = Form(10)
):
    """
    End-to-end pipeline: Profile → Personas → CV Evaluation → Ranking

    Accepts multipart/form-data:
    - resumes: ZIP file containing resumes
    - profile: JSON string of the role profile
    - top_n: number of candidates to shortlist (default 10)

    Returns the full pipeline result.
    """
    try:
        profile_dict = json.loads(profile)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON in 'profile' field"}

    # Step 1: Generate personas
    personas = build_personas(profile_dict)

    # Step 2: Parse and evaluate CVs
    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, resumes.filename)
        with open(file_path, "wb") as f:
            shutil.copyfileobj(resumes.file, f)

        raw_resumes = _extract_resumes_from_files([file_path])

        if not raw_resumes:
            return {
                "error": "No valid resumes found",
                "personas": personas,
                "evaluations": [],
                "shortlist": []
            }

        parsed_resumes = []
        for r in raw_resumes:
            text = r["text"]
            parsed_resumes.append({
                "candidate_id": r["file"],
                "summary": extract_section(
                    text, ["summary", "profile", "about", "objective"]
                ),
                "skills": extract_skills_llm(resume_text=text),
                "experience": extract_section(
                    text, ["experience", "work history", "employment"]
                ),
                "projects": extract_section(
                    text, ["projects", "key projects"]
                ),
                "raw_text": text,
                "resume_path": r["path"]
            })

        evaluations = []
        for cv in parsed_resumes:
            evaluation = evaluate_candidate(cv, personas)
            evaluations.append(evaluation)

    # Step 3: Rank
    ranking = rank_candidates(evaluations, top_n=top_n)

    return {
        "personas": personas,
        "evaluations": evaluations,
        "ranking": ranking
    }
