# app/agents/jd_chat_creator.py
# Chat-based JD Creator Agent
# Generates a professional JD from a natural language prompt
# Replaces the multi-step form + clarifier + profile builder + generator pipeline

import json
import os
from datetime import datetime
from app.utils.llm import get_llm
from app.utils.constants import ABOUT_WOGOM_TEXT, WOGOM_BRAND
from app.agents.jd_generator import normalize_bullets

# ─────────────────────────────────────────────
# Log directory
# ─────────────────────────────────────────────
LOG_DIR = os.path.join(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")),
    "exports",
    "chat_creator_logs"
)
os.makedirs(LOG_DIR, exist_ok=True)


# ─────────────────────────────────────────────
# System Prompt
# ─────────────────────────────────────────────
CHAT_CREATE_PROMPT = """You are an expert HR and talent acquisition specialist at WOGOM.

Your task: Generate a COMPLETE, professional, hiring-ready Job Description (JD) from the user's natural language prompt.

─────────────────────────────
ABOUT THE COMPANY
─────────────────────────────
{about_wogom}

─────────────────────────────
COMPANY BRAND GUIDELINES
─────────────────────────────
Mission: {mission}
Vision: {vision}
Tone: {tone}
Culture: {culture}
Language Rules: {language_rules}

{memory_context}

─────────────────────────────
USER PROMPT
─────────────────────────────
{user_prompt}

─────────────────────────────
INSTRUCTIONS
─────────────────────────────
From the user's prompt, extract as much information as possible:
- Role/Title, Department, Location, Experience level
- Key responsibilities, Skills, Employment type
- Any specific tone or style preferences

Then generate a complete JD with this EXACT structure:

# [Role Title]

**Location:** [Location or "India"]
**Type:** [Employment Type or "Full-time"]

## About Us
{about_wogom}

## Role Overview
2-3 sentences about the purpose of the role and its impact.

## Key Responsibilities
5-7 bullet points (one line each, max 30 words, start with "- ").

## Requirements

### Must-Have Skills
4-6 bullet points (one line each, start with "- ").

### Nice-to-Have Skills
2-3 bullet points (one line each, start with "- ").

## Who Will Succeed in This Role
2-3 sentences describing the ideal mindset and work ethic.

─────────────────────────────
OUTPUT FORMAT
─────────────────────────────
Return a JSON object with this structure:
{{
    "jd": "<the complete JD in markdown format>",
    "role": "<extracted role title>",
    "department": "<extracted department or 'General'>",
    "location": "<extracted location or 'India'>",
    "experience": "<extracted experience or ''>",
    "employment_type": "<extracted type or 'Full-time'>"
}}

RULES:
- Output ONLY the JSON object. No explanations, no markdown code fences.
- The JD must be professional, specific, and complete.
- Use bullet points with "- " prefix (markdown style).
- If the user prompt is vague, make reasonable assumptions and generate the best possible JD.
- Incorporate any user preferences from the memory context section.
"""


def create_jd_from_prompt(user_prompt: str, memory_context: str = "", session_id: str = "", department: str = "") -> dict:
    """
    Generate a complete JD from a natural language prompt.

    Args:
        user_prompt: The user's natural language description of the role.
        memory_context: Optional user preference summary from memory system.
        session_id: Session ID for logging.

    Returns:
        dict with keys: jd, role, department, location, experience, employment_type
    """
    llm = get_llm()

    # Build memory section
    memory_section = ""
    if memory_context:
        memory_section = f"""─────────────────────────────
USER PREFERENCES (from memory)
─────────────────────────────
{memory_context}

Apply these preferences when generating the JD. They represent this user's preferred style and format."""

    # Brand pieces
    mission = WOGOM_BRAND.get("mission", "")
    vision = WOGOM_BRAND.get("vision", "")
    tone = WOGOM_BRAND.get("tone", "")
    culture = ", ".join(WOGOM_BRAND.get("culture", []))
    language_rules = ", ".join(WOGOM_BRAND.get("language_rules", []))

    # Build enhanced user prompt with department context
    enhanced_prompt = user_prompt
    if department:
        enhanced_prompt = f"Department: {department}\n\n{user_prompt}"

    prompt = CHAT_CREATE_PROMPT.format(
        about_wogom=ABOUT_WOGOM_TEXT.strip(),
        mission=mission,
        vision=vision,
        tone=tone,
        culture=culture,
        language_rules=language_rules,
        memory_context=memory_section,
        user_prompt=enhanced_prompt,
    )

    try:
        response = llm.invoke(prompt)
        content = response.content

        # Handle list responses
        if isinstance(content, list):
            content = "\n".join(
                part.get("text", str(part))
                if isinstance(part, dict)
                else str(part)
                for part in content
            )

        content = content.strip()

        # Try to parse as JSON
        # Remove potential markdown code fences
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        result = json.loads(content)

        # Normalize bullets in JD
        if "jd" in result:
            result["jd"] = normalize_bullets(result["jd"])

        # Ensure all expected keys exist
        result.setdefault("role", "Untitled Role")
        result.setdefault("department", "General")
        result.setdefault("location", "India")
        result.setdefault("experience", "")
        result.setdefault("employment_type", "Full-time")

    except json.JSONDecodeError:
        # If JSON parsing fails, treat the whole response as JD text
        print(f"[JD_CHAT_CREATOR] JSON parse failed, using raw response as JD")
        jd_text = normalize_bullets(content)
        result = {
            "jd": jd_text,
            "role": "Job Role",
            "department": "General",
            "location": "India",
            "experience": "",
            "employment_type": "Full-time",
        }
    except Exception as e:
        print(f"[JD_CHAT_CREATOR] Error: {e}")
        raise

    # Save log
    _save_log(session_id, user_prompt, result, memory_context)

    return result


def refine_jd_chat(current_jd: str, instruction: str, memory_context: str = "",
                   role: str = "", session_id: str = "") -> str:
    """
    Refine an existing JD based on user instruction (chat-based).
    Wraps the existing jd_chatbot.refine_jd with memory context.
    """
    from app.agents.jd_chatbot import refine_jd

    # If memory context exists, prepend it to the instruction
    enhanced_instruction = instruction
    if memory_context:
        enhanced_instruction = (
            f"[User preferences: {memory_context}]\n\n"
            f"User instruction: {instruction}"
        )

    return refine_jd(
        current_jd=current_jd,
        instruction=enhanced_instruction,
        role=role,
        session_id=session_id,
    )


def _save_log(session_id: str, prompt: str, result: dict, memory_context: str):
    """Save creation log for analysis."""
    if not session_id:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    log_file = os.path.join(LOG_DIR, f"{session_id}.json")

    log_data = {
        "session_id": session_id,
        "created_at": datetime.now().isoformat(),
        "user_prompt": prompt,
        "had_memory": bool(memory_context),
        "result_role": result.get("role", ""),
        "result_department": result.get("department", ""),
        "jd_length": len(result.get("jd", "")),
    }

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)

    print(f"[JD_CHAT_CREATOR] Log saved → {log_file}")
