"""Morning Brief orchestrator — fetches document changes, news, and sends email."""

import logging
import sys
from datetime import datetime, timezone

from src.config import SNAPSHOT_PATH, load_documents, get_google_credentials_info
from src.diff_engine import DocumentChange, compute_changes, load_snapshot, save_snapshot
from src.drive_reader import DriveReader
from src.email_sender import compose_html, send_email
from src.news_aggregator import fetch_diagnostics_news
from src.summarizer import summarize_updates

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


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
                text = reader.read_document_text(doc_id, metadata.mime_type)
                new_snapshots[doc_id] = text

                old_text = old_snapshots.get(doc_id, "")
                new_content = compute_changes(old_text, text)

                doc_changes.append(DocumentChange(
                    doc_id=doc_id,
                    title=title,
                    changed=bool(new_content),
                    new_content=new_content,
                    last_editor=metadata.last_editor,
                    modified_time=metadata.modified_time,
                ))
                logger.info(f"  {title}: {'changed' if new_content else 'no changes'}")
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

    # --- Section 2: News ---
    mdx_news = []
    try:
        mdx_news = fetch_diagnostics_news()
        logger.info(f"MDx news: {len(mdx_news)} articles")
    except Exception as e:
        logger.error(f"MDx news failed: {e}")
        errors.append(f"MDx news: {e}")

    # --- Section 3: Email ---
    try:
        now = datetime.now(timezone.utc)
        subject = f"Morning Brief \u2014 {now.strftime('%A, %B %d, %Y')}"
        html = compose_html(doc_changes, summary, mdx_news, errors)
        send_email(subject, html)
        logger.info("Briefing sent successfully")
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        raise


if __name__ == "__main__":
    run()
