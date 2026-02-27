# app/agents/cv_evaluator.py
# Agent 7: CV Evaluator
# Compares each candidate CV against each persona → scores, grades, explanations

import json
from app.utils.llm import get_llm

# ─────────────────────────────────────────────
# Prompt: Single CV vs Single Persona
# ─────────────────────────────────────────────

CV_VS_PERSONA_PROMPT = """
You are an expert technical interviewer and hiring evaluator.

You are given:
1. A candidate's CV (parsed into structured sections).
2. An ideal candidate persona describing what a successful hire looks like.

YOUR TASK:
Evaluate how well the candidate matches this specific persona.

SCORING DIMENSIONS (evaluate each):
- Skill Match: Do their skills align with required skills?
- Experience Fit: Years and depth of experience vs. persona expectation
- Responsibility Match: Have they done similar work?
- Behavioral Signals: Ownership, leadership, initiative
- Domain Fit: Industry or domain relevance
- Risk Flags: Job hopping, shallow roles, gaps

Give a score from 0 to 100.

INPUTS:
─────────────────────────────
CANDIDATE CV:
{cv}

PERSONA:
{persona}
─────────────────────────────

OUTPUT FORMAT (STRICT JSON ONLY):
{{
  "persona_id": "{persona_id}",
  "score": <integer 0–100>,
  "grade": "<A+ / A / A- / B+ / B / B- / C+ / C / C- / D / F>",
  "strengths": [
    "Strength 1",
    "Strength 2"
  ],
  "gaps": [
    "Gap 1",
    "Gap 2"
  ],
  "explanation": "2–3 sentence summary of the fit analysis"
}}

RULES:
- Be strict but fair. Do not inflate scores.
- Cite specific evidence from the CV.
- Output ONLY valid JSON. No markdown, no extra text.
"""


def evaluate_candidate_against_persona(cv: dict, persona: dict) -> dict:
    """
    Evaluate a single candidate CV against a single persona.

    Args:
        cv: dict with candidate_id, skills, experience, summary, raw_text, etc.
        persona: dict with persona_id, name, required_skills, etc.

    Returns:
        dict with persona_id, score, grade, strengths, gaps, explanation
    """
    llm = get_llm()

    # Build a clean CV representation for the prompt
    cv_for_prompt = {
        "candidate_id": cv.get("candidate_id", "unknown"),
        "summary": cv.get("summary", ""),
        "skills": cv.get("skills", {}),
        "experience": cv.get("experience", ""),
        "projects": cv.get("projects", ""),
        "raw_text": (cv.get("raw_text", ""))[:3000]  # Truncate to avoid token overflow
    }

    persona_id = persona.get("persona_id", "P0")

    prompt = CV_VS_PERSONA_PROMPT.format(
        cv=json.dumps(cv_for_prompt, indent=2),
        persona=json.dumps(persona, indent=2),
        persona_id=persona_id
    )

    try:
        response = llm.invoke(prompt)
        content = response.content

        if isinstance(content, list):
            content = "\n".join(
                part.get("text", str(part))
                if isinstance(part, dict)
                else str(part)
                for part in content
            )

        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        result = json.loads(content)
        result["persona_id"] = persona_id  # Ensure consistency
        return result

    except json.JSONDecodeError as e:
        print(f"[CV_EVALUATOR] JSON parse error for {cv.get('candidate_id')}: {e}")
        return {
            "persona_id": persona_id,
            "score": 0,
            "grade": "F",
            "strengths": [],
            "gaps": ["Unable to evaluate — LLM response parsing failed"],
            "explanation": "Evaluation could not be completed due to a parsing error."
        }

    except Exception as e:
        print(f"[CV_EVALUATOR] Unexpected error for {cv.get('candidate_id')}: {e}")
        return {
            "persona_id": persona_id,
            "score": 0,
            "grade": "F",
            "strengths": [],
            "gaps": ["Evaluation failed due to an unexpected error"],
            "explanation": str(e)
        }


def _compute_grade(score: int) -> str:
    """Convert a numeric score to a letter grade."""
    if score >= 95: return "A+"
    if score >= 90: return "A"
    if score >= 85: return "A-"
    if score >= 80: return "B+"
    if score >= 75: return "B"
    if score >= 70: return "B-"
    if score >= 65: return "C+"
    if score >= 60: return "C"
    if score >= 55: return "C-"
    if score >= 50: return "D"
    return "F"


def evaluate_candidate(cv: dict, personas: list) -> dict:
    """
    Evaluate a single candidate CV against ALL personas.

    Args:
        cv: dict — parsed resume data
        personas: list of persona dicts from Agent 6

    Returns:
        dict with candidate_id, persona_results, overall_score, overall_grade,
             best_fit_persona, summary
    """
    persona_results = []

    for persona in personas:
        result = evaluate_candidate_against_persona(cv, persona)
        persona_results.append(result)

    # Compute overall metrics
    scores = [p["score"] for p in persona_results]
    best = max(persona_results, key=lambda x: x["score"])
    avg_score = int(sum(scores) / len(scores)) if scores else 0

    return {
        "candidate_id": cv.get("candidate_id", "unknown"),
        "persona_results": persona_results,
        "overall_score": avg_score,
        "overall_grade": _compute_grade(avg_score),
        "best_fit_persona": best["persona_id"],
        "best_fit_persona_name": next(
            (p.get("name", best["persona_id"]) for p in personas
             if p["persona_id"] == best["persona_id"]),
            best["persona_id"]
        ),
        "summary": best.get("explanation", "No explanation available.")
    }
