"""Document change detection via text diffing and snapshot caching."""

import difflib
import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_CHANGE_CHARS = 500


@dataclass
class DocumentChange:
    doc_id: str
    title: str
    changed: bool
    new_content: str
    last_editor: str
    modified_time: str


def load_snapshot(snapshot_path: Path) -> dict[str, str]:
    """Load previous document snapshots from JSON cache.

    Returns empty dict if file is missing or invalid.
    """
    if not snapshot_path.exists():
        return {}
    try:
        with open(snapshot_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load snapshot cache: {e}")
        return {}


def save_snapshot(snapshot_path: Path, snapshots: dict[str, str]) -> None:
    """Write current document snapshots to JSON cache."""
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    with open(snapshot_path, "w") as f:
        json.dump(snapshots, f, ensure_ascii=False)


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
