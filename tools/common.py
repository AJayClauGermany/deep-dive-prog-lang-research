"""Shared helpers for the catalog tools."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
LANG_DIR = DATA / "languages"
GENERAL_DIR = DATA / "general"
SCHEMA_DIR = ROOT / "schema"
BUILD = ROOT / "build"

LEVEL_KINDS = {
    0: {"implementation-repository", "implementation-source", "reference-implementation",
        "standard-library-source", "grammar-source", "conformance-tests", "tooling-source"},
    1: {"standard", "standard-draft", "specification", "reference-manual", "library-reference", "grammar",
        "proposal", "proposal-index", "formal-semantics", "original-paper", "design-document", "release-notes"},
    2: {"tutorial", "book", "guide", "course", "by-example", "cheatsheet", "article", "paper", "history",
        "video", "style-guide", "faq", "interactive", "comparison-guide", "internals-guide"},
    3: {"encyclopedia", "wiki", "catalog", "comparison-table", "curated-list", "bibliography", "benchmark",
        "code-collection", "index"},
}


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def concept_ids():
    return {c["id"] for c in load(DATA / "concepts.json")["concepts"]}


def language_files():
    return sorted(LANG_DIR.glob("*.json"))


def general_files():
    return sorted(GENERAL_DIR.glob("*.json"))
