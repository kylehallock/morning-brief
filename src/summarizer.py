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

    Returns the AI summary text, or an empty string if no changes or on failure.
    """
    changed = [c for c in changes if c.changed and c.new_content]
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
            model="gemini-2.0-flash",
            contents=user_content,
            config={"system_instruction": SYSTEM_PROMPT, "temperature": 0.3},
        )
        summary = response.text.strip()
        logger.info(f"Gemini summary generated ({len(summary)} chars)")
        return summary
    except Exception as e:
        logger.error(f"Gemini summarization failed: {e}")
        return ""
