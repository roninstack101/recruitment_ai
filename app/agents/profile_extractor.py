# app/agents/profile_extractor.py
# Extracts a structured Ideal Candidate Profile from finalized JD text.
# This bridges the new chat-based JD flow with the existing
# persona builder and CV evaluator pipeline.

import json
from app.utils.llm import get_llm

PROFILE_FROM_JD_PROMPT = """
You are a senior HR strategist.

You are given a finalized Job Description (JD). Your task is to extract
a structured "Ideal Candidate Profile" from it.

This profile will later be used to:
1. Generate ideal candidate personas.
2. Evaluate candidate CVs against those personas.

So make it specific, detailed, and grounded in what the JD says.

─────────────────────────────
JOB DESCRIPTION:
{jd_text}
─────────────────────────────

OUTPUT FORMAT (STRICT JSON ONLY):
{{
  "role": "<job title extracted from the JD>",
  "department": "<department if mentioned, otherwise 'General'>",
  "profile_summary": "2–3 sentence paragraph: Who is the ideal person for this role? What mindset and background do they bring?",
  "core_competencies": [
    "Competency 1: brief explanation of why it matters",
    "Competency 2: brief explanation",
    "Competency 3: brief explanation"
  ],
  "behavioral_traits": [
    "Trait 1: why it's relevant to this role",
    "Trait 2: why it's relevant"
  ],
  "success_metrics": [
    "What does success look like in 30 days?",
    "What does success look like in 90 days?",
    "What does success look like in 6 months?"
  ],
  "team_context": "1–2 sentences: Who does this person work with?",
  "key_responsibilities_refined": [
    "Key responsibility 1",
    "Key responsibility 2"
  ],
  "must_have_skills_refined": [
    "Required skill 1",
    "Required skill 2"
  ],
  "nice_to_have_skills": [
    "Bonus skill 1",
    "Bonus skill 2"
  ]
}}

RULES:
- Output ONLY valid JSON. No markdown, no explanations.
- Extract ALL information from the JD. Do NOT hallucinate.
- If a section is not mentioned in the JD, use an empty list [] or a reasonable inference.
- Keep language professional and specific.
"""


def extract_profile_from_jd(jd_text: str, department: str = "") -> dict:
    """
    Extract a structured Ideal Candidate Profile from finalized JD text.

    Args:
        jd_text: The full job description text (plain text or markdown).
        department: Optional department context for better extraction.

    Returns:
        dict: Structured profile matching the profile_builder output format.
    """
    if not jd_text or not jd_text.strip():
        return _fallback_profile("Unknown Role")

    llm = get_llm()

    # Enhance JD text with department context
    enhanced_jd = jd_text
    if department:
        enhanced_jd = f"Department: {department}\n\n{jd_text}"

    prompt = PROFILE_FROM_JD_PROMPT.format(jd_text=enhanced_jd)

    try:
        response = llm.invoke(prompt)
        content = response.content

        # Handle list responses from some LLM providers
        if isinstance(content, list):
            content = "\n".join(
                part.get("text", str(part))
                if isinstance(part, dict)
                else str(part)
                for part in content
            )

        # Extract JSON from the response
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        profile = json.loads(content)
        print(f"[PROFILE_EXTRACTOR] Successfully extracted profile for role: {profile.get('role', '?')}")
        return profile

    except json.JSONDecodeError as e:
        print(f"[PROFILE_EXTRACTOR] JSON parse error: {e}")
        return _fallback_profile("Unknown Role")

    except Exception as e:
        print(f"[PROFILE_EXTRACTOR] Unexpected error: {e}")
        return _fallback_profile("Unknown Role")


def _fallback_profile(role: str) -> dict:
    """Return a minimal fallback profile."""
    return {
        "role": role,
        "department": "General",
        "profile_summary": f"Profile for {role}.",
        "core_competencies": [],
        "behavioral_traits": [],
        "success_metrics": [],
        "team_context": "",
        "key_responsibilities_refined": [],
        "must_have_skills_refined": [],
        "nice_to_have_skills": [],
    }
