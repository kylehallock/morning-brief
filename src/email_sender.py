"""HTML email composition and SMTP sending."""

import logging
import re
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.config import get_email_config
from src.diff_engine import DocumentChange
from src.news_aggregator import NewsItem

logger = logging.getLogger(__name__)


def compose_html(
    doc_changes: list[DocumentChange],
    summary: str,
    mdx_news: list[NewsItem],
    tb_news: list[NewsItem],
    errors: list[str],
    email_summary: str = "",
) -> str:
    """Build an HTML email body with inline CSS and card-based layout."""
    sections = []

    # --- Document Updates (AI Summary + reference list) ---
    changed_docs = [dc for dc in doc_changes if dc.changed]

    if summary:
        summary_html = _format_summary_bullets(summary)
        sections.append(
            _card(
                title="STAMPEDE PROJECT SUMMARY",
                emoji="&#128203;",
                color="#2563eb",
                bg="#f0f7ff",
                content=summary_html,
            )
        )
    elif not changed_docs:
        sections.append(
            _card(
                title="STAMPEDE PROJECT SUMMARY",
                emoji="&#128203;",
                color="#2563eb",
                bg="#f0f7ff",
                content='<div style="color:#9ca3af; font-size:15px;">No document changes detected.</div>',
            )
        )

    # Reference list: which docs changed and who edited them
    if changed_docs:
        ref_rows = []
        for dc in changed_docs:
            ref_rows.append(
                f'<tr>'
                f'<td style="padding:6px 12px 6px 0; font-size:14px; color:#1e40af; font-weight:600;">'
                f'{_escape(dc.title)}</td>'
                f'<td style="padding:6px 12px; font-size:13px; color:#6b7280;">'
                f'{_escape(dc.last_editor)}</td>'
                f'<td style="padding:6px 0 6px 12px; font-size:13px; color:#9ca3af; text-align:right;">'
                f'{_format_time(dc.modified_time)}</td>'
                f'</tr>'
            )
        table = (
            '<table style="width:100%; border-collapse:collapse;">'
            '<tr style="border-bottom:1px solid #e5e7eb;">'
            '<th style="padding:4px 12px 4px 0; font-size:11px; color:#9ca3af; '
            'text-transform:uppercase; letter-spacing:0.5px; text-align:left;">Document</th>'
            '<th style="padding:4px 12px; font-size:11px; color:#9ca3af; '
            'text-transform:uppercase; letter-spacing:0.5px; text-align:left;">Editor</th>'
            '<th style="padding:4px 0 4px 12px; font-size:11px; color:#9ca3af; '
            'text-transform:uppercase; letter-spacing:0.5px; text-align:right;">Modified</th>'
            '</tr>'
            + "".join(ref_rows)
            + '</table>'
        )
        sections.append(
            _card(
                title="DOCUMENTS UPDATED",
                emoji="&#128196;",
                color="#6b7280",
                bg="#f9fafb",
                content=table,
            )
        )

    # --- Email Summary ---
    if email_summary:
        email_summary_html = _format_summary_bullets(email_summary)
        sections.append(
            _card(
                title="EMAIL HIGHLIGHTS",
                emoji="&#9993;",
                color="#7c3aed",
                bg="#f5f3ff",
                content=(
                    '<div style="font-size:11px; color:#9ca3af; margin-bottom:10px; '
                    'text-transform:uppercase; letter-spacing:0.5px;">'
                    'Team &amp; group communications only</div>'
                    + email_summary_html
                ),
            )
        )

    # --- MDx News ---
    if mdx_news:
        news_rows = []
        for item in mdx_news:
            news_rows.append(
                f'<div style="margin-bottom:14px; padding-bottom:14px; border-bottom:1px solid #f3f4f6;">'
                f'<a href="{_escape(item.url)}" style="color:#2563eb; text-decoration:none; '
                f'font-size:15px; font-weight:600; line-height:1.4;">{_escape(item.title)}</a>'
                f'<div style="margin-top:4px;">'
                f'<span style="display:inline-block; font-size:11px; color:#6b7280; '
                f'background:#f3f4f6; padding:2px 8px; border-radius:10px;">'
                f'{_escape(item.source)}</span>'
                f'</div>'
                f'</div>'
            )
        # Remove border from last item
        sections.append(
            _card(
                title="MOLECULAR DIAGNOSTICS NEWS",
                emoji="&#128300;",
                color="#059669",
                bg="#f0fdf4",
                content="\n".join(news_rows),
            )
        )
    else:
        sections.append(
            _card(
                title="MOLECULAR DIAGNOSTICS NEWS",
                emoji="&#128300;",
                color="#059669",
                bg="#f0fdf4",
                content='<div style="color:#9ca3af; font-size:15px;">No recent articles found.</div>',
            )
        )

    # --- TB Tongue Swab Watch ---
    if tb_news:
        tb_rows = []
        for item in tb_news:
            source_label = f' &middot; {_escape(item.source)}' if item.source else ''
            tb_rows.append(
                f'<div style="margin-bottom:14px; padding-bottom:14px; border-bottom:1px solid #f3f4f6;">'
                f'<a href="{_escape(item.url)}" style="color:#2563eb; text-decoration:none; '
                f'font-size:15px; font-weight:600; line-height:1.4;">{_escape(item.title)}</a>'
                f'<div style="margin-top:4px;">'
                f'<span style="font-size:12px; color:#9ca3af;">'
                f'{_format_time(item.published.isoformat() if item.published else "")}'
                f'{source_label}</span>'
                f'</div>'
                f'</div>'
            )
        sections.append(
            _card(
                title="TB TONGUE SWAB WATCH",
                emoji="&#129656;",
                color="#b45309",
                bg="#fffbeb",
                content="\n".join(tb_rows),
            )
        )
    else:
        sections.append(
            _card(
                title="TB TONGUE SWAB WATCH",
                emoji="&#129656;",
                color="#b45309",
                bg="#fffbeb",
                content='<div style="color:#9ca3af; font-size:15px;">No recent articles found.</div>',
            )
        )

    # --- Errors ---
    if errors:
        error_rows = "\n".join(
            f'<div style="font-size:14px; color:#dc2626; margin-bottom:6px; '
            f'line-height:1.5;">&bull; {_escape(e)}</div>'
            for e in errors
        )
        sections.append(
            _card(
                title="ERRORS",
                emoji="&#9888;&#65039;",
                color="#dc2626",
                bg="#fef2f2",
                content=error_rows,
            )
        )

    body = "\n".join(sections)
    today = datetime.now().strftime("%A, %B %d, %Y")

    return (
        '<div style="margin:0; padding:0; font-family:Arial,Helvetica,sans-serif; color:#1f2937;">'
        # Header banner
        '<div style="background:linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%); '
        'padding:32px 40px; color:white;">'
        f'<h1 style="margin:0; font-size:28px; font-weight:700; letter-spacing:-0.5px;">'
        f'MORNING BRIEF</h1>'
        f'<div style="margin-top:6px; font-size:15px; color:rgba(255,255,255,0.8);">'
        f'{today}</div>'
        '</div>'
        # Content area
        f'<div style="padding:24px 40px 40px 40px;">'
        f'{body}'
        '<div style="margin-top:32px; padding-top:16px; border-top:1px solid #e5e7eb; '
        'font-size:12px; color:#9ca3af;">Generated automatically by Morning Brief</div>'
        '</div>'
        '</div>'
    )


def _card(title: str, emoji: str, color: str, bg: str, content: str) -> str:
    """Wrap content in a styled card."""
    return (
        f'<div style="margin-bottom:24px; padding:24px; background:{bg}; '
        f'border-radius:12px; border:1px solid #e5e7eb; '
        f'box-shadow:0 1px 3px rgba(0,0,0,0.06);">'
        f'<h2 style="margin:0 0 16px 0; font-size:16px; color:{color}; '
        f'letter-spacing:0.5px; font-weight:700;">'
        f'{emoji} {title}</h2>'
        f'{content}'
        f'</div>'
    )


def _format_summary_bullets(text: str) -> str:
    """Format AI summary text with styled bullet points.

    Handles markdown-style bullets (- or *) and plain newlines.
    """
    lines = text.strip().split("\n")
    formatted = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Strip leading markdown bullets
        if stripped.startswith(("- ", "* ", "• ")):
            stripped = stripped[2:]
        elif stripped.startswith(("**") and "**" in stripped[2:]):
            # Bold header bullet like "**Theme:** details"
            pass

        # Handle bold markers for inline display
        html_line = _escape(stripped)
        # Convert **text** to <strong>
        html_line = re.sub(
            r'\*\*(.+?)\*\*',
            r'<strong>\1</strong>',
            html_line,
        )

        formatted.append(
            f'<div style="margin-bottom:10px; padding-left:16px; font-size:14px; '
            f'line-height:1.6; color:#374151; position:relative;">'
            f'<span style="position:absolute; left:0; color:#9ca3af;">&#8226;</span>'
            f'{html_line}'
            f'</div>'
        )
    return "\n".join(formatted)


def send_email(subject: str, html_body: str) -> None:
    """Send an HTML email via Gmail SMTP."""
    config = get_email_config()
    recipients = config["recipients"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config["sender"]
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(config["smtp_host"], config["smtp_port"]) as server:
        server.starttls()
        server.login(config["sender"], config["password"])
        server.sendmail(config["sender"], recipients, msg.as_string())

    logger.info(f"Email sent to {', '.join(recipients)}")


def _escape(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _format_time(iso_time: str) -> str:
    """Format ISO timestamp for display."""
    if not iso_time:
        return ""
    try:
        dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %I:%M %p UTC")
    except ValueError:
        return iso_time
