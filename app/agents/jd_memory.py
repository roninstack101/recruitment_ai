# app/agents/jd_memory.py
# JD Memory System Agent
# Analyzes edit prompts and final JDs to learn user preferences
# Stores per-user preference summaries for future JD generation

import json
from datetime import datetime
from app.utils.llm import get_llm


# ─────────────────────────────────────────────
# Memory Analysis Prompt
# ─────────────────────────────────────────────
MEMORY_ANALYSIS_PROMPT = """You are a user preference analyst for a Job Description creation tool.

Your task: Analyze this user's JD creation session to understand their preferences, style, and patterns.

─────────────────────────────
SESSION DATA
─────────────────────────────
Initial Prompt: {initial_prompt}

Edit History (chronological):
{edit_history}

Final JD (the version the user accepted):
{final_jd}

{existing_preferences}

─────────────────────────────
ANALYSIS INSTRUCTIONS
─────────────────────────────
Study the user's behavior:
1. What did they add/remove/change in their edits?
2. What tone do they prefer? (formal, casual, professional, creative)
3. What sections do they emphasize or de-emphasize?
4. How detailed do they like bullet points?
5. Do they prefer concise or comprehensive JDs?
6. Any recurring patterns in their edit instructions?
7. What structure preferences do they have?

Return a JSON object:
{{
    "preferences_summary": "<A 3-5 sentence natural language summary of this user's JD preferences. Be specific and actionable. Example: 'User prefers concise JDs with strong action verbs. They always add a Why Join Us section and prefer 5-6 bullet responsibilities. They dislike generic phrases and want quantifiable metrics in requirements.'>",
    "patterns": {{
        "tone": "<preferred tone>",
        "detail_level": "<concise|moderate|comprehensive>",
        "bullet_count_preference": "<few|moderate|many>",
        "emphasis_sections": ["<sections they expand or care about>"],
        "removed_sections": ["<sections they remove or minimize>"],
        "style_notes": ["<specific style observations>"]
    }}
}}

RULES:
- Output ONLY the JSON object. No explanations.
- If this is the first session (no existing preferences), create initial preferences.
- If existing preferences exist, MERGE the new observations with existing ones.
- Be specific — vague preferences like "good JDs" are useless.
"""


MERGE_PROMPT = """You are merging JD creation preferences for a user.

EXISTING PREFERENCES:
{existing}

NEW SESSION OBSERVATIONS:
{new_observations}

TOTAL JDs ANALYZED: {total_jds}

Create an UPDATED preferences summary that intelligently combines the existing preferences with the new observations. Give more weight to consistent patterns seen across multiple sessions.

Return a JSON object:
{{
    "preferences_summary": "<Updated 3-5 sentence summary reflecting all sessions>",
    "patterns": {{
        "tone": "<preferred tone>",
        "detail_level": "<concise|moderate|comprehensive>",
        "bullet_count_preference": "<few|moderate|many>",
        "emphasis_sections": ["<sections they expand or care about>"],
        "removed_sections": ["<sections they remove or minimize>"],
        "style_notes": ["<specific style observations>"]
    }}
}}

Output ONLY the JSON. No explanations.
"""


def analyze_session(
    initial_prompt: str,
    final_jd: str,
    edit_history: list,
    existing_preferences: str = "",
    total_jds: int = 0,
) -> dict:
    """
    Analyze a JD creation session to extract user preferences.

    Args:
        initial_prompt: The user's original prompt.
        final_jd: The final accepted JD text.
        edit_history: List of dicts with {instruction, version} for each edit.
        existing_preferences: Previous preference summary (if any).
        total_jds: Total number of JDs previously analyzed.

    Returns:
        dict with keys: preferences_summary, patterns
    """
    llm = get_llm()

    # Format edit history
    if edit_history:
        edit_lines = []
        for i, edit in enumerate(edit_history, 1):
            instruction = edit.get("instruction", edit.get("text", ""))
            edit_lines.append(f"  Edit {i}: \"{instruction}\"")
        edit_text = "\n".join(edit_lines)
    else:
        edit_text = "  (No edits — user accepted the initial JD as-is)"

    # Existing preferences section
    existing_section = ""
    if existing_preferences:
        existing_section = f"""─────────────────────────────
EXISTING USER PREFERENCES (from {total_jds} previous sessions)
─────────────────────────────
{existing_preferences}

Incorporate and update these preferences based on the new session data."""

    prompt = MEMORY_ANALYSIS_PROMPT.format(
        initial_prompt=initial_prompt,
        edit_history=edit_text,
        final_jd=final_jd[:3000],  # Truncate to save tokens
        existing_preferences=existing_section,
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

        # Remove potential markdown code fences
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        result = json.loads(content)
        result.setdefault("preferences_summary", "No specific preferences detected yet.")
        result.setdefault("patterns", {})

    except json.JSONDecodeError:
        print(f"[JD_MEMORY] JSON parse failed, using raw response")
        result = {
            "preferences_summary": content[:500] if content else "Analysis failed.",
            "patterns": {},
        }
    except Exception as e:
        print(f"[JD_MEMORY] Error during analysis: {e}")
        result = {
            "preferences_summary": "Unable to analyze preferences at this time.",
            "patterns": {},
        }

    return result
