"""AI-powered summarization of journal updates using Gemini."""

import logging

from google import genai

from src.config import get_gemini_api_key
from src.diff_engine import DocumentChange

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are summarizing daily updates from a molecular diagnostics R&D team's "
    "project journals. The team (Stampede) is building a point-of-care TB testing "
    "device. The team includes R&D scientists, software engineers, electrical "
    "engineers, and UX designers.\n\n"
    "Summarize the changes concisely in a few bullet points. Highlight key "
    "decisions, progress, blockers, and action items. Group by theme rather than "
    "by document when possible. Be brief and direct — this is read over morning "
    "coffee."
)


def summarize_updates(changes: list[DocumentChange]) -> str:
    """Summarize document changes using Gemini 2.0 Flash.

    Returns the AI summary text, a raw-content fallback if Gemini fails,
    or an empty string if there are no real changes to summarize.
    """
    changed = [
        c for c in changes
        if c.changed and c.new_content and not c.new_content.startswith("[First run")
    ]
    if not changed:
        return ""

    # Build the content for the prompt
    parts = []
    for c in changed:
        parts.append(f"### {c.title}\nEdited by {c.last_editor}\n{c.new_content}")
    user_content = "Here are today's journal updates:\n\n" + "\n\n".join(parts)

    try:
        api_key = get_gemini_api_key()
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=user_content,
            config={"system_instruction": SYSTEM_PROMPT, "temperature": 0.3},
        )
        summary = response.text.strip()
        logger.info(f"Gemini summary generated ({len(summary)} chars)")
        return summary
    except Exception as e:
        logger.error(f"Gemini summarization failed: {e}")
        return _fallback_summary(changed)


def _fallback_summary(changes: list[DocumentChange]) -> str:
    """Build a simple raw-content summary when Gemini is unavailable."""
    parts = []
    for c in changes:
        parts.append(f"{c.title}:\n{c.new_content}")
    return "\n\n".join(parts)
