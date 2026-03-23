"""Google Drive document reader for fetching and extracting text."""

import io
import logging
from dataclasses import dataclass
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build

from src.config import GOOGLE_SCOPES, get_google_credentials_info

logger = logging.getLogger(__name__)

MIME_GOOGLE_DOC = "application/vnd.google-apps.document"
MIME_GOOGLE_SHEET = "application/vnd.google-apps.spreadsheet"
MIME_GOOGLE_SLIDES = "application/vnd.google-apps.presentation"
MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# Documents larger than this (bytes) use plain text export instead of Docs API
LARGE_DOC_THRESHOLD = 5_000_000  # 5 MB


@dataclass
class DocumentMetadata:
    doc_id: str
    name: str
    mime_type: str
    modified_time: str
    last_editor: str
    size: int = 0


class DriveReader:
    """Reads text content from Google Drive documents."""

    def __init__(self, credentials_info: Optional[dict] = None):
        if credentials_info is None:
            credentials_info = get_google_credentials_info()

        credentials = service_account.Credentials.from_service_account_info(
            credentials_info, scopes=GOOGLE_SCOPES
        )
        self._drive = build("drive", "v3", credentials=credentials)
        self._docs = build("docs", "v1", credentials=credentials)
        self._sheets = build("sheets", "v4", credentials=credentials)

    def get_document_metadata(self, doc_id: str) -> DocumentMetadata:
        """Get metadata for a document including last editor and size."""
        result = (
            self._drive.files()
            .get(
                fileId=doc_id,
                fields="id, name, mimeType, modifiedTime, lastModifyingUser, size",
                supportsAllDrives=True,
            )
            .execute()
        )

        last_user = result.get("lastModifyingUser", {})
        last_editor = last_user.get("displayName", "Unknown")

        # Google Workspace files don't report size via this field,
        # so we fall back to 0 (will use Docs API by default)
        size = int(result.get("size", 0))

        return DocumentMetadata(
            doc_id=result["id"],
            name=result["name"],
            mime_type=result.get("mimeType", ""),
            modified_time=result.get("modifiedTime", ""),
            last_editor=last_editor,
            size=size,
        )

    def read_document_text(self, doc_id: str, mime_type: str = "") -> str:
        """Extract plain text from a document.

        Detects MIME type and uses the appropriate extraction method:
        - Google Sheets -> Sheets API (all tabs)
        - Google Docs -> plain text export (fast, handles large docs)
        - .docx -> download + python-docx
        - Other -> Drive API export as text/plain
        """
        if not mime_type:
            meta = self.get_document_metadata(doc_id)
            mime_type = meta.mime_type

        if mime_type == MIME_GOOGLE_DOC:
            return self._export_as_plain_text(doc_id)
        elif mime_type == MIME_DOCX:
            return self._extract_docx_text(doc_id)
        elif mime_type == MIME_GOOGLE_SHEET:
            # For spreadsheets, use read_sheets() with known_sheets
            # from the caller for incremental reads. This default
            # reads everything (used on first run).
            return self.read_sheets(doc_id)
        elif mime_type == MIME_GOOGLE_SLIDES:
            return self._export_as_plain_text(doc_id)
        else:
            logger.warning(f"Unsupported MIME type for text extraction: {mime_type}")
            return f"[Cannot extract text from file type: {mime_type}]"

    def get_sheet_names(self, doc_id: str) -> list[str]:
        """Get the names of all sheets in a Google Spreadsheet."""
        spreadsheet = (
            self._sheets.spreadsheets()
            .get(spreadsheetId=doc_id, fields="sheets.properties.title")
            .execute()
        )
        return [
            s["properties"]["title"]
            for s in spreadsheet.get("sheets", [])
        ]

    def read_sheets(self, doc_id: str, sheet_names: list[str] | None = None) -> str:
        """Read specific sheets (or all) from a Google Spreadsheet.

        Args:
            doc_id: The spreadsheet ID.
            sheet_names: List of sheet names to read. If None, reads all sheets.

        Returns a text representation with each sheet labeled by name,
        rows separated by newlines, cells separated by tabs.
        """
        if sheet_names is None:
            sheet_names = self.get_sheet_names(doc_id)

        if not sheet_names:
            logger.warning(f"Spreadsheet {doc_id}: no sheets to read")
            return ""

        logger.info(f"Reading {len(sheet_names)} sheets from spreadsheet {doc_id}")

        # Try batch read first; fall back to one-at-a-time on failure
        # (some sheet names cause API parsing errors).
        try:
            ranges = [f"'{name}'" for name in sheet_names]
            result = (
                self._sheets.spreadsheets()
                .values()
                .batchGet(spreadsheetId=doc_id, ranges=ranges)
                .execute()
            )
            value_ranges = result.get("valueRanges", [])
        except Exception as e:
            logger.warning(f"Batch read failed for {doc_id}, reading sheets individually: {e}")
            value_ranges = []
            for name in sheet_names:
                try:
                    r = (
                        self._sheets.spreadsheets()
                        .values()
                        .get(spreadsheetId=doc_id, range=f"'{name}'")
                        .execute()
                    )
                    value_ranges.append(r)
                except Exception as sheet_err:
                    logger.warning(f"Skipping sheet '{name}': {sheet_err}")
                    value_ranges.append({"values": []})

        parts = []
        for i, value_range in enumerate(value_ranges):
            sheet_name = sheet_names[i] if i < len(sheet_names) else f"Sheet{i+1}"
            rows = value_range.get("values", [])

            if not rows:
                continue

            sheet_text = f"=== {sheet_name} ===\n"
            for row in rows:
                sheet_text += "\t".join(str(cell) for cell in row) + "\n"

            parts.append(sheet_text)

        return "\n".join(parts)

    def _extract_docx_text(self, doc_id: str) -> str:
        """Download and extract text from a .docx file."""
        from docx import Document

        request = self._drive.files().get_media(fileId=doc_id)
        content = request.execute()
        doc = Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs)

    def _export_as_plain_text(self, doc_id: str) -> str:
        """Export a Google Workspace file as plain text.

        This is faster than the Docs API for large documents since it
        doesn't require parsing the full document structure.
        """
        content = (
            self._drive.files()
            .export(fileId=doc_id, mimeType="text/plain")
            .execute()
        )
        if isinstance(content, bytes):
            return content.decode("utf-8")
        return content
