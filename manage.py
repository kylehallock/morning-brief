"""CLI helper for managing the document list in config/documents.json."""

import json
import sys
from pathlib import Path

DOCS_PATH = Path(__file__).resolve().parent / "config" / "documents.json"


def load():
    with open(DOCS_PATH) as f:
        return json.load(f)


def save(data):
    with open(DOCS_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def cmd_list():
    data = load()
    docs = data.get("documents", [])
    if not docs:
        print("No documents configured.")
        return
    print(f"{'#':<4} {'Title':<45} {'ID'}")
    print("-" * 100)
    for i, doc in enumerate(docs, 1):
        print(f"{i:<4} {doc['title']:<45} {doc['id']}")


def cmd_add(doc_id: str, title: str):
    data = load()
    for doc in data["documents"]:
        if doc["id"] == doc_id:
            print(f"Document {doc_id} already exists: {doc['title']}")
            return
    data["documents"].append({"id": doc_id, "title": title})
    save(data)
    print(f"Added: {title} ({doc_id})")


def cmd_remove(doc_id: str):
    data = load()
    original_count = len(data["documents"])
    data["documents"] = [d for d in data["documents"] if d["id"] != doc_id]
    if len(data["documents"]) == original_count:
        print(f"Document {doc_id} not found.")
        return
    save(data)
    print(f"Removed document {doc_id}")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python manage.py list")
        print('  python manage.py add <doc_id> "<title>"')
        print("  python manage.py remove <doc_id>")
        sys.exit(1)

    command = sys.argv[1]

    if command == "list":
        cmd_list()
    elif command == "add":
        if len(sys.argv) < 4:
            print('Usage: python manage.py add <doc_id> "<title>"')
            sys.exit(1)
        cmd_add(sys.argv[2], sys.argv[3])
    elif command == "remove":
        if len(sys.argv) < 3:
            print("Usage: python manage.py remove <doc_id>")
            sys.exit(1)
        cmd_remove(sys.argv[2])
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
