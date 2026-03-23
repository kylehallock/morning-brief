"""Document change detection via text diffing and snapshot caching."""

import difflib
import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_CHANGE_CHARS = 2000

# Max text to store per document snapshot. Keeps cache size reasonable
# for very large documents (journals with years of entries).
MAX_SNAPSHOT_CHARS = 100_000


@dataclass
class DocumentChange:
    doc_id: str
    title: str
    changed: bool
    new_content: str
    last_editor: str
    modified_time: str


def load_snapshot(snapshot_path: Path) -> dict[str, dict]:
    """Load previous document snapshots from JSON cache.

    Returns a dict of {doc_id: {"text": str, "modified_time": str}}.
    Handles the legacy format where values were plain strings.
    """
    if not snapshot_path.exists():
        return {}
    try:
        with open(snapshot_path) as f:
            data = json.load(f)

        # Migrate legacy format: plain string values -> dict with text + modified_time
        migrated = {}
        for doc_id, value in data.items():
            if isinstance(value, str):
                migrated[doc_id] = {"text": value, "modified_time": ""}
            elif isinstance(value, dict):
                migrated[doc_id] = value
            else:
                migrated[doc_id] = {"text": "", "modified_time": ""}
        return migrated

    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load snapshot cache: {e}")
        return {}


def save_snapshot(snapshot_path: Path, snapshots: dict[str, dict]) -> None:
    """Write current document snapshots to JSON cache.

    Each entry is {doc_id: {"text": str, "modified_time": str}}.
    Text is truncated to MAX_SNAPSHOT_CHARS to keep cache size manageable.
    """
    # Truncate large texts before saving
    capped = {}
    for doc_id, entry in snapshots.items():
        text = entry.get("text", "")
        if len(text) > MAX_SNAPSHOT_CHARS:
            text = text[-MAX_SNAPSHOT_CHARS:]
        capped[doc_id] = {
            "text": text,
            "modified_time": entry.get("modified_time", ""),
        }

    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    with open(snapshot_path, "w") as f:
        json.dump(capped, f, ensure_ascii=False)


def doc_modified_since_snapshot(
    snapshot_entry: dict, current_modified_time: str
) -> bool:
    """Check if a document has been modified since the last snapshot.

    Returns True if the document needs text extraction (modified or no prior data).
    """
    if not snapshot_entry:
        return True
    old_time = snapshot_entry.get("modified_time", "")
    if not old_time:
        return True
    return old_time != current_modified_time


def compute_changes(old_text: str, new_text: str) -> str:
    """Detect additions between old and new document text.

    Returns:
        - "[First run - full document cached]" if old_text is empty
        - "" if no changes
        - Joined string of added content blocks
    """
    if not old_text:
        return "[First run \u2014 full document cached]"

    if old_text == new_text:
        return ""

    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)

    added_blocks = []
    current_block = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("insert", "replace"):
            lines = new_lines[j1:j2]
            current_block.extend(lines)
        else:
            if current_block:
                added_blocks.append("".join(current_block).strip())
                current_block = []

    if current_block:
        added_blocks.append("".join(current_block).strip())

    # Filter out empty blocks
    added_blocks = [b for b in added_blocks if b]

    if not added_blocks:
        return ""

    result = "\n---\n".join(added_blocks)

    if len(result) > MAX_CHANGE_CHARS:
        result = result[:MAX_CHANGE_CHARS] + "\n[... truncated]"

    return result
