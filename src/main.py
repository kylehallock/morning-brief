"""Morning Brief orchestrator — fetches document changes, news, and sends email."""

import logging
import sys
from datetime import datetime, timezone

from src.config import SNAPSHOT_PATH, load_documents, get_google_credentials_info
from src.diff_engine import (
    DocumentChange,
    compute_changes,
    doc_modified_since_snapshot,
    load_snapshot,
    save_snapshot,
)
from src.drive_reader import MIME_GOOGLE_SHEET, DriveReader
from src.email_reader import fetch_recent_emails
from src.email_sender import compose_html, send_email
from src.news_aggregator import fetch_diagnostics_news
from src.tb_news_scraper import fetch_tb_news
from src.summarizer import (
    generate_condensed_summary,
    load_rolling_summary,
    save_rolling_summary,
    summarize_emails,
    summarize_updates,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def _read_spreadsheet_incremental(
    reader: DriveReader, doc_id: str, old_entry: dict
) -> tuple[str, str, list[str]]:
    """Read only new sheets from a spreadsheet, appending to cached text.

    Returns (full_text, new_content, all_sheet_names).
    """
    all_sheet_names = reader.get_sheet_names(doc_id)
    known_sheets = set(old_entry.get("sheet_names", []))
    new_sheets = [s for s in all_sheet_names if s not in known_sheets]

    old_text = old_entry.get("text", "")

    if not new_sheets:
        # No new sheets — but the spreadsheet was modified, so existing
        # sheets may have changed. Read nothing new; the modifiedTime gate
        # already confirmed something changed, but we can't efficiently
        # detect per-cell changes without reading everything.
        logger.info(f"  Spreadsheet {doc_id}: no new sheets (existing sheets may have minor edits)")
        return old_text, "", all_sheet_names

    logger.info(
        f"  Spreadsheet {doc_id}: {len(new_sheets)} new sheet(s): "
        + ", ".join(new_sheets)
    )

    new_text = reader.read_sheets(doc_id, new_sheets)
    full_text = old_text + ("\n" if old_text else "") + new_text

    return full_text, new_text, all_sheet_names


def run():
    logger.info("Starting Morning Brief")

    errors = []

    # --- Section 1: Document Updates ---
    doc_changes = []
    try:
        credentials_info = get_google_credentials_info()
        reader = DriveReader(credentials_info)
        documents = load_documents()

        old_snapshots = load_snapshot(SNAPSHOT_PATH)
        new_snapshots = {}

        for doc in documents:
            doc_id = doc["id"]
            title = doc["title"]
            try:
                metadata = reader.get_document_metadata(doc_id)
                old_entry = old_snapshots.get(doc_id, {})

                # Skip expensive text extraction if document hasn't been modified
                if not doc_modified_since_snapshot(old_entry, metadata.modified_time):
                    new_snapshots[doc_id] = old_entry  # carry forward
                    doc_changes.append(DocumentChange(
                        doc_id=doc_id,
                        title=title,
                        changed=False,
                        new_content="",
                        last_editor=metadata.last_editor,
                        modified_time=metadata.modified_time,
                    ))
                    logger.info(f"  {title}: not modified since last run, skipped")
                    continue

                # Spreadsheets: only read new sheets, not the entire workbook
                if metadata.mime_type == MIME_GOOGLE_SHEET:
                    text, new_content, all_sheet_names = (
                        _read_spreadsheet_incremental(reader, doc_id, old_entry)
                    )
                    new_snapshots[doc_id] = {
                        "text": text,
                        "modified_time": metadata.modified_time,
                        "sheet_names": all_sheet_names,
                    }
                else:
                    text = reader.read_document_text(doc_id, metadata.mime_type)
                    if not text.strip():
                        logger.warning(f"  {title}: text extraction returned empty")
                        errors.append(
                            f"Document '{title}': Text extraction returned empty. "
                            f"The file may use an unsupported format or have no text content."
                        )
                    old_text = old_entry.get("text", "")
                    new_content = compute_changes(old_text, text)
                    new_snapshots[doc_id] = {
                        "text": text,
                        "modified_time": metadata.modified_time,
                    }

                doc_changes.append(DocumentChange(
                    doc_id=doc_id,
                    title=title,
                    changed=bool(new_content),
                    new_content=new_content,
                    last_editor=metadata.last_editor,
                    modified_time=metadata.modified_time,
                ))
                logger.info(f"  {title}: {'changed' if new_content else 'no changes'} "
                            f"({len(text)} chars extracted)")
            except Exception as e:
                logger.error(f"Failed to read {title}: {e}")
                err_str = str(e)
                if "404" in err_str or "not found" in err_str.lower():
                    errors.append(
                        f"Document '{title}': File not found. "
                        f"The file ID may be stale (document moved/deleted) or "
                        f"not shared with the service account. "
                        f"Update config/documents.json with the current file ID."
                    )
                else:
                    errors.append(f"Document '{title}': {e}")

        save_snapshot(SNAPSHOT_PATH, new_snapshots)
        logger.info(f"Snapshot saved ({len(new_snapshots)} documents)")

    except Exception as e:
        logger.error(f"Document section failed: {e}")
        errors.append(f"Document section: {e}")

    # --- Section 1b: Summarize changes ---
    summary = ""
    try:
        summary = summarize_updates(doc_changes)
    except Exception as e:
        logger.error(f"Summarization failed: {e}")

    # --- Section 1c: Update rolling summary ---
    if summary:
        try:
            condensed = generate_condensed_summary(summary)
            if condensed:
                rolling = load_rolling_summary()
                today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                # Replace existing entry for today, or append
                rolling = [e for e in rolling if e.get("date") != today_str]
                rolling.append({"date": today_str, "summary": condensed})
                rolling.sort(key=lambda e: e.get("date", ""))
                save_rolling_summary(rolling)
        except Exception as e:
            logger.error(f"Rolling summary update failed: {e}")

    # --- Section 2: Email Highlights ---
    email_summary = ""
    try:
        recent_emails = fetch_recent_emails(hours_back=24)
        if recent_emails:
            email_summary = summarize_emails(recent_emails)
            logger.info(f"Email summary: {len(recent_emails)} emails summarized")
        else:
            logger.info("No public emails found for summary")
    except Exception as e:
        logger.error(f"Email summary failed: {e}")
        errors.append(f"Email summary: {e}")

    # --- Section 3: News ---
    mdx_news = []
    try:
        mdx_news = fetch_diagnostics_news()
        logger.info(f"MDx news: {len(mdx_news)} articles")
    except Exception as e:
        logger.error(f"MDx news failed: {e}")
        errors.append(f"MDx news: {e}")

    # --- Section 3b: TB Tongue Swab News ---
    tb_news = []
    try:
        tb_news = fetch_tb_news()
        logger.info(f"TB tongue swab news: {len(tb_news)} articles")
    except Exception as e:
        logger.error(f"TB tongue swab news failed: {e}")
        errors.append(f"TB tongue swab news: {e}")

    # --- Section 4: Send Email ---
    try:
        now = datetime.now(timezone.utc)
        subject = f"Morning Brief \u2014 {now.strftime('%A, %B %d, %Y')}"
        html = compose_html(doc_changes, summary, mdx_news, tb_news, errors, email_summary)
        send_email(subject, html)
        logger.info("Briefing sent successfully")
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        raise


if __name__ == "__main__":
    run()
