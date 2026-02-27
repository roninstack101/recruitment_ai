# app/agents/jd_clarifier.py
# Agent 1: Clarifying Questions Generator
# Generates MCQs from the "Head of Department" perspective
# No draft JD required — works solely from role + department data

from app.utils.llm import get_llm
import json
import re

# ============================================================
# CLARIFIER PROMPT — HEAD OF DEPARTMENT PERSPECTIVE
# ============================================================

CLARIFY_PROMPT = """You are a senior recruitment strategist.

SCENARIO:
The **Head of {department}** has requested to hire a **{title}**.
The Head may not be fully aware of every detail this role needs.
Your job is to generate clarifying questions FROM the Head's perspective —
questions that help the Head think more deeply about what they truly need.

CONTEXT FROM GOOGLE FORM:
- Job Title: {title}
- Department: {department}
- Location: {location}
- Experience Level: {experience_level}
- Work Mode: {work_mode}
- Must-Have Skills: {key_skills}
- Key Responsibilities: {key_responsibilities}
- Reporting To: {reporting_to}
- Additional Info: {additional_info}

TASK:
Generate exactly 5 multiple-choice questions that:
1. Are phrased as if asking the Department Head directly
   (e.g., "As the Head of {department}, what specific outcomes do you expect from this {title} in the first 90 days?")
2. Help clarify responsibilities, success metrics, team dynamics, authority level, and ownership
3. Each question MUST have exactly 4 options
4. Options should be meaningful, specific to the {title} role, and allow MULTI-SELECT
5. Focus on gaps in the form data — things the Head might not have thought about

OUTPUT FORMAT (STRICT JSON ONLY — EXACTLY 5 QUESTIONS):

[
  {{
    "id": "q1",
    "question": "As the Head of {department}, ...",
    "options": [
      "Option A",
      "Option B",
      "Option C",
      "Option D"
    ],
    "target_section": "responsibilities|authority|ownership|success_metrics|team_dynamics"
  }},
  {{
    "id": "q2",
    "question": "...",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "target_section": "responsibilities|authority|ownership|success_metrics|team_dynamics"
  }},
  {{
    "id": "q3",
    "question": "...",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "target_section": "responsibilities|authority|ownership|success_metrics|team_dynamics"
  }},
  {{
    "id": "q4",
    "question": "...",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "target_section": "responsibilities|authority|ownership|success_metrics|team_dynamics"
  }},
  {{
    "id": "q5",
    "question": "...",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "target_section": "responsibilities|authority|ownership|success_metrics|team_dynamics"
  }}
]

RULES:
- Output ONLY valid JSON array with exactly 5 questions
- NEVER include "Not Applicable" as an option
- Each question MUST have exactly 4 options
- Questions must feel like they come from a Head-of-Department conversation
- No explanations, no markdown, no extra text
- Do NOT ask about salary, CTC, compensation, work mode, remote/hybrid, travel, shift timing, or urgency
"""

# ============================================================
# POST-LLM VALIDATOR
# ============================================================

BANNED_KEYWORDS = [
    "salary", "ctc", "compensation",
    "years of experience", "years experience",
    "work mode", "remote", "hybrid", "onsite",
    "travel", "shift", "timing", "working hours",
    "urgency", "how urgent"
]


def post_validate_questions(questions: list) -> list:
    """Filter out questions with banned keywords."""
    valid = []
    for q in questions:
        text = q.get("question", "").lower()
        if any(b.lower() in text for b in BANNED_KEYWORDS):
            continue
        if not isinstance(q.get("options"), list) or len(q.get("options", [])) != 4:
            continue
        valid.append(q)
    return valid


# ============================================================
# JSON EXTRACTION (SAFE)
# ============================================================

def _extract_json(text: str) -> str:
    """Extract JSON array from LLM response."""
    match = re.search(r"\[\s*{.*?}\s*\]", text, re.DOTALL)
    if not match:
        return "[]"
    raw = match.group(0)
    raw = re.sub(r',\s+', ', ', raw)
    raw = re.sub(r':\s+', ': ', raw)
    raw = re.sub(r'\[\s+', '[', raw)
    raw = re.sub(r'\s+\]', ']', raw)
    raw = re.sub(r'{\s+', '{ ', raw)
    raw = re.sub(r'\s+}', ' }', raw)
    return raw


# ============================================================
# FINAL VALIDATION
# ============================================================

def _is_valid_question(q: dict) -> bool:
    """Validate question structure."""
    if not isinstance(q, dict):
        return False
    required = {"id", "question", "options", "target_section"}
    if not required.issubset(q.keys()):
        return False
    if not isinstance(q.get("options"), list) or len(q["options"]) != 4:
        return False
    return True


# ============================================================
# MAIN FUNCTION
# ============================================================

def generate_clarifying_questions(form_data: dict) -> list:
    """
    Agent 1: Generate 5 clarifying questions from the Head-of-Department perspective.

    This agent does NOT require a draft JD. It works solely from the
    Google Form data (role, department, skills, responsibilities).

    Args:
        form_data: dict from Google Form containing role, department, etc.

    Returns:
        List of 5 MCQ questions with 4 options each.
    """
    llm = get_llm()

    # Extract fields from form data
    title = form_data.get("role", "Unknown Role")
    department = form_data.get("department", "General")
    location = form_data.get("location", "")
    experience = form_data.get("experience", "")
    work_mode = form_data.get("work_mode", "")
    reporting_to = form_data.get("reporting_to", "")
    must_have_skills = form_data.get("must_have_skills", "")
    key_responsibilities = form_data.get("key_responsibilities", "")
    other_skills = form_data.get("other_skills", "")

    # Build additional info from remaining fields
    additional_parts = []
    if form_data.get("new_or_scaling"):
        additional_parts.append(f"Role type: {form_data['new_or_scaling']}")
    if form_data.get("minimum_education"):
        additional_parts.append(f"Education: {form_data['minimum_education']}")
    if other_skills:
        additional_parts.append(f"Other skills: {other_skills}")
    additional_info = "; ".join(additional_parts) if additional_parts else "None provided"

    prompt = CLARIFY_PROMPT.format(
        title=title,
        department=department,
        location=location,
        experience_level=experience,
        work_mode=work_mode,
        key_skills=must_have_skills,
        key_responsibilities=key_responsibilities,
        reporting_to=reporting_to,
        additional_info=additional_info,
    )

    try:
        response = llm.invoke(prompt)
        raw_text = str(response.content)
    except Exception as e:
        print(f"[JD_CLARIFIER] Error calling LLM: {e}")
        return []

    json_text = _extract_json(raw_text)

    try:
        questions = json.loads(json_text)
    except json.JSONDecodeError as e:
        print(f"[JD_CLARIFIER] JSON parse error: {e}, raw={json_text[:300]}")
        return []
    except Exception as e:
        print(f"[JD_CLARIFIER] Unexpected error: {e}")
        return []

    if not isinstance(questions, list):
        return []

    # Ensure exactly 5 valid questions
    questions = [q for q in questions if _is_valid_question(q)][:5]

    # Apply safety filter
    questions = post_validate_questions(questions)

    return questions


# ============================================================
# CLI TEST
# ============================================================
if __name__ == "__main__":
    sample = {
        "role": "AI Engineer",
        "department": "Engineering",
        "location": "Remote",
        "experience": "3-5 years",
        "work_mode": "Remote",
        "must_have_skills": "Python, ML, LLMs",
        "key_responsibilities": "Build AI agents",
        "reporting_to": "Tech Lead",
    }

    questions = generate_clarifying_questions(form_data=sample)

    print(f"\n========== CLARIFYING QUESTIONS FOR {sample['role'].upper()} ==========\n")

    if not questions:
        print("No questions generated.")
    else:
        for q in questions:
            print(f"{q['id']}: {q['question']}")
            for i, opt in enumerate(q["options"], start=1):
                print(f"  {i}. {opt}")
            print(f"Target Section: {q['target_section']}\n")