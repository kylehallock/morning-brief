"""Gmail IMAP reader with privacy filtering for Morning Brief."""

import email
import imaplib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from email.utils import parseaddr, getaddresses

from src.config import get_email_config, get_email_privacy_threshold

logger = logging.getLogger(__name__)

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993

# Keywords for filtering emails to project-relevant content only.
# Emails whose subject+snippet don't match any keyword are excluded.
PROJECT_KEYWORDS = [
    "stampede", "device", "assay", "pcr", "qpcr",
    "tb", "tuberculosis", "diagnostic", "reagent",
    "chip", "cartridge", "sputum", "sequence",
    "ftaq", "dsbio", "is6110", "rif", "melt curve",
    "rover", "bsl", "clinical", "validation",
    "r2d2", "pluslife", "formulatrix",
]


@dataclass
class EmailItem:
    subject: str
    sender: str
    recipient_count: int
    snippet: str
    date: datetime


def fetch_recent_emails(hours_back: int = 24) -> list[EmailItem]:
    """Fetch inbox emails from the last N hours, filtered for privacy.

    Excludes private emails (those with few recipients) to avoid
    leaking sensitive 1:1 or small-group conversations into the briefing.
    """
    config = get_email_config()
    threshold = get_email_privacy_threshold()

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    imap_date = cutoff.strftime("%d-%b-%Y")

    items = []

    try:
        with imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT) as mail:
            mail.login(config["sender"], config["password"])
            mail.select("INBOX", readonly=True)

            # Search for recent messages
            _, msg_ids = mail.search(None, f'(SINCE "{imap_date}")')
            if not msg_ids or not msg_ids[0]:
                logger.info("No recent emails found")
                return []

            id_list = msg_ids[0].split()
            logger.info(f"Found {len(id_list)} emails since {imap_date}")

            for msg_id in id_list:
                try:
                    item = _parse_message(mail, msg_id, cutoff, threshold)
                    if item is not None:
                        items.append(item)
                except Exception as e:
                    logger.warning(f"Failed to parse email {msg_id}: {e}")
                    continue

    except imaplib.IMAP4.error as e:
        logger.error(f"IMAP connection failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Email fetch failed: {e}")
        raise

    items.sort(key=lambda x: x.date, reverse=True)
    logger.info(
        f"{len(items)} public emails "
        f"(filtered from {len(id_list)} total, threshold={threshold})"
    )

    # Relevance filter: only keep emails related to the project
    relevant = [item for item in items if _is_project_relevant(item)]
    logger.info(
        f"Returning {len(relevant)} project-relevant emails "
        f"(from {len(items)} public)"
    )
    return relevant


def _parse_message(
    mail: imaplib.IMAP4_SSL,
    msg_id: bytes,
    cutoff: datetime,
    privacy_threshold: int,
) -> EmailItem | None:
    """Parse a single email message. Returns None if private or too old."""
    _, data = mail.fetch(msg_id, "(RFC822.HEADER BODY.PEEK[1])")

    # Parse headers
    header_data = None
    body_snippet = ""
    for part in data:
        if isinstance(part, tuple):
            desc = part[0].decode() if isinstance(part[0], bytes) else str(part[0])
            if "HEADER" in desc:
                header_data = part[1]
            elif "BODY" in desc:
                try:
                    body_snippet = part[1].decode("utf-8", errors="replace")[:300]
                except Exception:
                    body_snippet = ""

    if header_data is None:
        return None

    msg = email.message_from_bytes(header_data)

    # Parse date
    msg_date = _parse_email_date(msg.get("Date", ""))
    if msg_date is None or msg_date < cutoff:
        return None

    # Count recipients (To + CC)
    to_addrs = getaddresses(msg.get_all("To", []))
    cc_addrs = getaddresses(msg.get_all("Cc", []))
    recipient_count = len(to_addrs) + len(cc_addrs)

    # Privacy filter: skip emails with few recipients (likely private)
    if recipient_count <= privacy_threshold:
        return None

    subject = _decode_header_value(msg.get("Subject", "(no subject)"))
    _, sender_addr = parseaddr(msg.get("From", ""))
    sender_name = _decode_header_value(msg.get("From", ""))
    # Use just the name part if available
    display_name, _ = parseaddr(sender_name)
    if not display_name:
        display_name = sender_addr

    # Clean up snippet
    snippet = body_snippet.strip().replace("\r\n", " ").replace("\n", " ")
    # Truncate to ~200 chars for summarization
    if len(snippet) > 200:
        snippet = snippet[:200] + "..."

    return EmailItem(
        subject=subject,
        sender=display_name,
        recipient_count=recipient_count,
        snippet=snippet,
        date=msg_date,
    )


def _decode_header_value(value: str) -> str:
    """Decode an email header value (handles encoded words)."""
    if not value:
        return ""
    parts = decode_header(value)
    decoded = []
    for text, charset in parts:
        if isinstance(text, bytes):
            decoded.append(text.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(text)
    return " ".join(decoded)


def _is_project_relevant(item: EmailItem) -> bool:
    """Check if an email is relevant to the project based on keywords."""
    text = f"{item.subject} {item.snippet}".lower()
    return any(kw in text for kw in PROJECT_KEYWORDS)


def _parse_email_date(date_str: str) -> datetime | None:
    """Parse email Date header into timezone-aware datetime."""
    if not date_str:
        return None
    try:
        return email.utils.parsedate_to_datetime(date_str)
    except Exception:
        return None
