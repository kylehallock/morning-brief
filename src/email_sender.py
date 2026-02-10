"""HTML email composition and SMTP sending."""

import logging
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
    mdx_news: list[NewsItem],
    tech_news: list[NewsItem],
    errors: list[str],
) -> str:
    """Build an HTML email body with inline CSS."""
    sections = []

    # --- Document Updates ---
    doc_rows = []
    for dc in doc_changes:
        if dc.changed:
            content_html = _escape(dc.new_content).replace("\n", "<br>")
            doc_rows.append(
                f'<div style="margin-bottom:16px; padding:12px; background:#f0f7ff; '
                f'border-left:4px solid #2563eb; border-radius:4px;">'
                f'<div style="font-weight:bold; font-size:15px; color:#1e40af;">{_escape(dc.title)}</div>'
                f'<div style="font-size:13px; color:#6b7280; margin-top:4px;">'
                f'Edited by {_escape(dc.last_editor)} &middot; {_format_time(dc.modified_time)}</div>'
                f'<div style="margin-top:8px; font-size:14px; color:#374151; '
                f'white-space:pre-wrap;">{content_html}</div>'
                f'</div>'
            )
        else:
            doc_rows.append(
                f'<div style="margin-bottom:8px; padding:8px 12px; color:#9ca3af; font-size:14px;">'
                f'{_escape(dc.title)} &mdash; No changes</div>'
            )

    sections.append(
        '<h2 style="color:#1e3a5f; border-bottom:2px solid #e5e7eb; padding-bottom:8px;">'
        '&#128203; STAMPEDE DOCUMENT UPDATES</h2>'
        + "\n".join(doc_rows)
    )

    # --- MDx News ---
    if mdx_news:
        news_rows = []
        for item in mdx_news:
            summary_html = f'<div style="font-size:13px; color:#6b7280; margin-top:2px;">{_escape(item.summary)}</div>' if item.summary else ""
            news_rows.append(
                f'<div style="margin-bottom:12px;">'
                f'<a href="{_escape(item.url)}" style="color:#2563eb; text-decoration:none; '
                f'font-size:14px; font-weight:bold;">{_escape(item.title)}</a>'
                f'<span style="font-size:12px; color:#9ca3af; margin-left:8px;">{_escape(item.source)}</span>'
                f'{summary_html}</div>'
            )
        sections.append(
            '<h2 style="color:#1e3a5f; border-bottom:2px solid #e5e7eb; padding-bottom:8px;">'
            '&#128300; MOLECULAR DIAGNOSTICS NEWS</h2>'
            + "\n".join(news_rows)
        )
    else:
        sections.append(
            '<h2 style="color:#1e3a5f; border-bottom:2px solid #e5e7eb; padding-bottom:8px;">'
            '&#128300; MOLECULAR DIAGNOSTICS NEWS</h2>'
            '<div style="color:#9ca3af; font-size:14px;">No recent articles found.</div>'
        )

    # --- Tech News ---
    if tech_news:
        tech_rows = []
        for item in tech_news:
            tech_rows.append(
                f'<div style="margin-bottom:10px;">'
                f'<a href="{_escape(item.url)}" style="color:#2563eb; text-decoration:none; '
                f'font-size:14px; font-weight:bold;">{_escape(item.title)}</a>'
                f'<span style="font-size:12px; color:#9ca3af; margin-left:8px;">{_escape(item.source)}</span>'
                f'</div>'
            )
        sections.append(
            '<h2 style="color:#1e3a5f; border-bottom:2px solid #e5e7eb; padding-bottom:8px;">'
            '&#128187; TECH NEWS HIGHLIGHTS</h2>'
            + "\n".join(tech_rows)
        )
    else:
        sections.append(
            '<h2 style="color:#1e3a5f; border-bottom:2px solid #e5e7eb; padding-bottom:8px;">'
            '&#128187; TECH NEWS HIGHLIGHTS</h2>'
            '<div style="color:#9ca3af; font-size:14px;">No recent articles found.</div>'
        )

    # --- Errors ---
    if errors:
        error_rows = "\n".join(
            f'<div style="font-size:13px; color:#dc2626; margin-bottom:4px;">&bull; {_escape(e)}</div>'
            for e in errors
        )
        sections.append(
            '<h2 style="color:#991b1b; border-bottom:2px solid #fecaca; padding-bottom:8px;">'
            '&#9888;&#65039; ERRORS</h2>'
            + error_rows
        )

    body = "\n".join(sections)

    return (
        '<div style="max-width:600px; margin:0 auto; font-family:Arial,Helvetica,sans-serif; '
        'padding:20px; color:#1f2937;">'
        f'<h1 style="color:#111827; font-size:22px; margin-bottom:24px;">'
        f'MORNING BRIEF &mdash; {datetime.now().strftime("%A, %B %d, %Y")}</h1>'
        f'{body}'
        '<div style="margin-top:32px; padding-top:16px; border-top:1px solid #e5e7eb; '
        'font-size:12px; color:#9ca3af;">Generated automatically by Morning Brief</div>'
        '</div>'
    )


def send_email(subject: str, html_body: str) -> None:
    """Send an HTML email via Gmail SMTP."""
    config = get_email_config()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config["sender"]
    msg["To"] = config["recipient"]
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(config["smtp_host"], config["smtp_port"]) as server:
        server.starttls()
        server.login(config["sender"], config["password"])
        server.sendmail(config["sender"], config["recipient"], msg.as_string())

    logger.info(f"Email sent to {config['recipient']}")


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
