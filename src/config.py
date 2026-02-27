"""Centralized configuration for Morning Brief."""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
]

# Cache paths
CACHE_DIR = PROJECT_ROOT / "cache"
SNAPSHOT_PATH = CACHE_DIR / "doc_snapshots.json"
ROLLING_SUMMARY_PATH = CACHE_DIR / "rolling_summary.json"

# Project context
CONFIG_DIR = PROJECT_ROOT / "config"
PROJECT_CONTEXT_PATH = CONFIG_DIR / "project_context.md"
TB_SOURCES_PATH = CONFIG_DIR / "tb_sources.json"

# News search queries — TB diagnostics + broader molecular diagnostics
MDX_TB_QUERIES = [
    '"tuberculosis diagnostics" OR "TB diagnostics" OR "TB testing" OR "tuberculosis point-of-care" OR "TB molecular test"',
    '"GeneXpert" OR "Truenat" OR "TB-LAMP" OR "tuberculosis PCR" OR "TB rapid test" OR "near-patient TB"',
    '"Pluslife" OR "Cepheid tuberculosis" OR "MolBio diagnostics" OR "Coyote Biosciences" OR "Hain Lifescience" OR "SD Biosensor tuberculosis"',
]
MDX_BROAD_QUERIES = [
    '"molecular diagnostics" OR "molecular testing" OR "PCR diagnostics" OR "nucleic acid testing"',
    '"point-of-care diagnostics" OR "rapid molecular test" OR "isothermal amplification" OR "LAMP assay"',
    '"CRISPR diagnostics" OR "lateral flow" OR "biosensor" OR "microfluidics diagnostics"',
]
MDX_QUERIES = MDX_TB_QUERIES + MDX_BROAD_QUERIES


def load_tb_sources() -> dict:
    """Read TB tongue swab news sources from config/tb_sources.json."""
    with open(TB_SOURCES_PATH) as f:
        return json.load(f)


def load_documents() -> list[dict]:
    """Read document list from config/documents.json."""
    docs_path = PROJECT_ROOT / "config" / "documents.json"
    with open(docs_path) as f:
        data = json.load(f)
    return data["documents"]


def get_google_credentials_info() -> dict:
    """Load Google service account credentials from env var.

    The env var can be either a file path to a JSON key or the JSON content itself.
    """
    key_data = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY", "")
    if not key_data:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_KEY environment variable not set")

    if os.path.isfile(key_data):
        with open(key_data) as f:
            return json.load(f)

    return json.loads(key_data)


def get_gemini_api_key() -> str:
    """Load Gemini API key from environment variable."""
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    return key


def get_email_config() -> dict:
    """Load email configuration from environment variables."""
    sender = os.getenv("EMAIL_SENDER", "")
    password = os.getenv("EMAIL_PASSWORD", "")
    recipient = os.getenv("EMAIL_RECIPIENT", "")

    if not all([sender, password, recipient]):
        missing = []
        if not sender:
            missing.append("EMAIL_SENDER")
        if not password:
            missing.append("EMAIL_PASSWORD")
        if not recipient:
            missing.append("EMAIL_RECIPIENT")
        raise ValueError(f"Missing email environment variables: {', '.join(missing)}")

    # Support comma-separated recipient list
    recipients = [r.strip() for r in recipient.split(",") if r.strip()]

    return {
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "sender": sender,
        "password": password,
        "recipients": recipients,
    }
