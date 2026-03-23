"""AI-powered summarization of journal updates using Gemini."""

import json
import logging
from datetime import date, timedelta

from google import genai

from src.config import (
    get_gemini_api_key,
    PROJECT_CONTEXT_PATH,
    ROLLING_SUMMARY_PATH,
)
from src.diff_engine import DocumentChange

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are summarizing daily updates from a molecular diagnostics R&D team's "
    "project journals. The team (Stampede) is building a point-of-care TB testing "
    "device. The team includes R&D scientists, software engineers, electrical "
    "engineers, and UX designers.\n\n"
    "Provide a thorough summary with ~8-12 bullet points grouped by theme. "
    "For each bullet, include brief context so the reader understands the "
    "significance. Cover:\n"
    "- Key decisions made and their rationale\n"
    "- Progress against current goals and milestones\n"
    "- Blockers, risks, or issues raised\n"
    "- Connections to broader project objectives\n"
    "- Action items and next steps\n\n"
    "Be direct and informative — this is read over morning coffee, but the reader "
    "wants substance, not just headlines."
)

EMAIL_SUMMARY_PROMPT = (
    "You are summarizing recent team and group emails for a morning briefing. "
    "The team (Stampede) is building a point-of-care TB testing device.\n\n"
    "Provide 3-5 concise bullet points covering:\n"
    "- Action items or requests directed at the team\n"
    "- Key decisions or announcements\n"
    "- External stakeholder communications\n"
    "- Meeting follow-ups or scheduling changes\n\n"
    "Be direct. Skip routine/automated emails (calendar invites, notifications). "
    "Focus on what the reader needs to know or act on today."
)

CONDENSED_SUMMARY_PROMPT = (
    "Condense the following daily summary into exactly 2-3 sentences that capture "
    "the most important developments. This will be used as historical context for "
    "future summaries. Be specific — mention names, experiments, and decisions.\n\n"
    "{summary}"
)


def _load_project_context() -> str:
    """Load the project context markdown file if it exists."""
    if PROJECT_CONTEXT_PATH.exists():
        text = PROJECT_CONTEXT_PATH.read_text(encoding="utf-8").strip()
        if text:
            return text
    return ""


def load_rolling_summary() -> list[dict]:
    """Load the rolling summary JSON file.

    Returns a list of dicts with 'date' and 'summary' keys.
    """
    if ROLLING_SUMMARY_PATH.exists():
        try:
            data = json.loads(ROLLING_SUMMARY_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load rolling summary: {e}")
    return []


def save_rolling_summary(entries: list[dict]) -> None:
    """Save the rolling summary, pruning entries older than 14 days."""
    cutoff = (date.today() - timedelta(days=14)).isoformat()
    pruned = [e for e in entries if e.get("date", "") >= cutoff]

    ROLLING_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    ROLLING_SUMMARY_PATH.write_text(
        json.dumps(pruned, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info(f"Rolling summary saved ({len(pruned)} entries)")


def _build_rolling_context(entries: list[dict]) -> str:
    """Format rolling summary entries into a context block."""
    if not entries:
        return ""
    lines = []
    for e in entries:
        lines.append(f"- **{e['date']}**: {e['summary']}")
    return "\n".join(lines)


def summarize_updates(changes: list[DocumentChange]) -> str:
    """Summarize document changes using Gemini 2.5 Flash Lite.

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

    # Prepend project context if available
    project_context = _load_project_context()
    if project_context:
        user_content = (
            "## Project Context\n"
            f"{project_context}\n\n"
            "---\n\n"
            f"{user_content}"
        )

    # Prepend rolling summary if available
    rolling_entries = load_rolling_summary()
    rolling_context = _build_rolling_context(rolling_entries)
    if rolling_context:
        user_content = (
            "## Recent Days (rolling context)\n"
            f"{rolling_context}\n\n"
            "---\n\n"
            f"{user_content}"
        )

    try:
        api_key = get_gemini_api_key()
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=user_content,
            config={"system_instruction": SYSTEM_PROMPT, "temperature": 0.3},
        )
        summary = response.text.strip()
        token_estimate = len(user_content) // 4 + len(SYSTEM_PROMPT) // 4
        logger.info(
            f"Gemini summary generated ({len(summary)} chars, "
            f"~{token_estimate} prompt tokens estimated)"
        )
        return summary
    except Exception as e:
        logger.error(f"Gemini summarization failed: {e}")
        return _fallback_summary(changed)


def generate_condensed_summary(daily_summary: str) -> str:
    """Generate a 2-3 sentence condensed version of today's summary.

    Used for the rolling summary historical context.
    Returns empty string if generation fails.
    """
    if not daily_summary:
        return ""

    prompt = CONDENSED_SUMMARY_PROMPT.format(summary=daily_summary)

    try:
        api_key = get_gemini_api_key()
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
            config={"temperature": 0.2},
        )
        condensed = response.text.strip()
        logger.info(f"Condensed summary generated ({len(condensed)} chars)")
        return condensed
    except Exception as e:
        logger.error(f"Condensed summary generation failed: {e}")
        return ""


def summarize_emails(email_items) -> str:
    """Summarize recent team emails using Gemini.

    Args:
        email_items: list of EmailItem dataclass instances from email_reader.

    Returns the AI summary text, or empty string if no emails or generation fails.
    """
    if not email_items:
        return ""

    parts = []
    for item in email_items:
        parts.append(
            f"Subject: {item.subject}\n"
            f"From: {item.sender}\n"
            f"Recipients: {item.recipient_count}\n"
            f"Snippet: {item.snippet}"
        )
    user_content = (
        "Here are recent team/group emails from the last 24 hours:\n\n"
        + "\n\n---\n\n".join(parts)
    )

    # Prepend project context if available
    project_context = _load_project_context()
    if project_context:
        user_content = (
            "## Project Context\n"
            f"{project_context}\n\n"
            "---\n\n"
            f"{user_content}"
        )

    try:
        api_key = get_gemini_api_key()
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=user_content,
            config={"system_instruction": EMAIL_SUMMARY_PROMPT, "temperature": 0.3},
        )
        summary = response.text.strip()
        logger.info(f"Email summary generated ({len(summary)} chars)")
        return summary
    except Exception as e:
        logger.error(f"Email summarization failed: {e}")
        return ""


def _fallback_summary(changes: list[DocumentChange]) -> str:
    """Build a simple raw-content summary when Gemini is unavailable."""
    parts = []
    for c in changes:
        parts.append(f"{c.title}:\n{c.new_content}")
    return "\n\n".join(parts)
