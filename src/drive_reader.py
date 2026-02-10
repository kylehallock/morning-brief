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
MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@dataclass
class DocumentMetadata:
    doc_id: str
    name: str
    mime_type: str
    modified_time: str
    last_editor: str


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

    def get_document_metadata(self, doc_id: str) -> DocumentMetadata:
        """Get metadata for a document including last editor."""
        result = (
            self._drive.files()
            .get(
                fileId=doc_id,
                fields="id, name, mimeType, modifiedTime, lastModifyingUser",
                supportsAllDrives=True,
            )
            .execute()
        )

        last_user = result.get("lastModifyingUser", {})
        last_editor = last_user.get("displayName", "Unknown")

        return DocumentMetadata(
            doc_id=result["id"],
            name=result["name"],
            mime_type=result.get("mimeType", ""),
            modified_time=result.get("modifiedTime", ""),
            last_editor=last_editor,
        )

    def read_document_text(self, doc_id: str, mime_type: str = "") -> str:
        """Extract plain text from a document.

        Detects MIME type and uses the appropriate extraction method:
        - Google Docs -> Docs API
        - .docx -> download + python-docx
        - Other -> Drive API export as text/plain
        """
        if not mime_type:
            meta = self.get_document_metadata(doc_id)
            mime_type = meta.mime_type

        if mime_type == MIME_GOOGLE_DOC:
            return self._extract_google_doc_text(doc_id)
        elif mime_type == MIME_DOCX:
            return self._extract_docx_text(doc_id)
        else:
            return self._export_as_plain_text(doc_id)

    def _extract_google_doc_text(self, doc_id: str) -> str:
        """Extract text from a Google Doc via Docs API."""
        doc = self._docs.documents().get(documentId=doc_id).execute()
        body = doc.get("body", {})
        content = body.get("content", [])

        text_parts = []
        for element in content:
            self._extract_text(element, text_parts)

        return "".join(text_parts)

    def _extract_text(self, element: dict, parts: list[str]) -> None:
        """Recursively extract text from a document element."""
        if "paragraph" in element:
            paragraph = element["paragraph"]
            for elem in paragraph.get("elements", []):
                if "textRun" in elem:
                    parts.append(elem["textRun"].get("content", ""))
        elif "table" in element:
            table = element["table"]
            for row in table.get("tableRows", []):
                for cell in row.get("tableCells", []):
                    for content in cell.get("content", []):
                        self._extract_text(content, parts)
                    parts.append("\t")
                parts.append("\n")
        elif "sectionBreak" in element:
            pass

    def _extract_docx_text(self, doc_id: str) -> str:
        """Download and extract text from a .docx file."""
        from docx import Document

        request = self._drive.files().get_media(fileId=doc_id)
        content = request.execute()
        doc = Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs)

    def _export_as_plain_text(self, doc_id: str) -> str:
        """Export a Google Workspace file as plain text."""
        content = (
            self._drive.files()
            .export(fileId=doc_id, mimeType="text/plain")
            .execute()
        )
        if isinstance(content, bytes):
            return content.decode("utf-8")
        return content
