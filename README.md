# Morning Brief

Automated daily briefing that monitors Stampede program Google Drive documents for changes, summarizes updates using Gemini AI, gathers molecular diagnostics news, and emails a formatted HTML summary.

Runs daily at 6 AM Mountain Time via GitHub Actions.

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in values:

```bash
cp .env.example .env
```

- **GOOGLE_SERVICE_ACCOUNT_KEY**: Path to service account JSON key, or the raw JSON content. Reuse the same service account from stampede-report.
- **GEMINI_API_KEY**: Google Gemini API key for AI summarization. Get one free at https://aistudio.google.com/apikey
- **EMAIL_SENDER**: Gmail address to send from.
- **EMAIL_PASSWORD**: Gmail App Password (not your regular password). Generate at https://myaccount.google.com/apppasswords
- **EMAIL_RECIPIENT**: Email address to receive the briefing.

### 3. Share documents with the service account

Each document in `config/documents.json` must be shared (Viewer access) with the service account email address found in your JSON key file (`client_email` field).

### 4. Run locally

```bash
python -m src.main
```

## Managing Documents

Documents are configured in `config/documents.json`. When journals switch (e.g., end of May), update the IDs and titles there.

### Using the CLI helper

```bash
python manage.py list                              # Show current documents
python manage.py add <doc_id> "<title>"            # Add a document
python manage.py remove <doc_id>                   # Remove a document
```

### Direct editing

Edit `config/documents.json` directly:

```json
{
  "documents": [
    {"id": "your-google-doc-id", "title": "Document Title"},
    ...
  ]
}
```

## GitHub Actions

The workflow runs daily at `0 13 * * *` UTC (6 AM MST / 7 AM MDT).

### Required Secrets

| Secret | Description |
|--------|-------------|
| `GOOGLE_SERVICE_ACCOUNT_KEY` | Full JSON content of service account keyfile |
| `GEMINI_API_KEY` | Google Gemini API key for AI summarization |
| `EMAIL_SENDER` | Gmail address to send from |
| `EMAIL_PASSWORD` | Gmail App Password |
| `EMAIL_RECIPIENT` | Recipient email address |

### Manual trigger

Use the "Run workflow" button in the Actions tab, or:

```bash
gh workflow run morning-brief.yml
```

## How It Works

1. **Document monitoring**: Reads all configured Google Drive files (Docs, Sheets, Slides, docx), compares against cached snapshots, and detects additions using `difflib.SequenceMatcher`.
2. **AI summarization**: Sends document changes to Gemini 2.0 Flash to produce a concise thematic summary highlighting key decisions, progress, blockers, and action items.
3. **News aggregation**: Queries Google News RSS for molecular diagnostics articles (TB diagnostics, PCR, POC testing, CRISPR diagnostics, biosensors, and more) from the last 24 hours.
4. **Email**: Composes an HTML email with the AI summary, a reference list of updated documents, MDx news headlines, and any errors, then sends via Gmail SMTP.
5. **Cache**: Saves document snapshots to `cache/doc_snapshots.json`, committed back to the repo by GitHub Actions with `[skip ci]` to avoid re-triggering.
