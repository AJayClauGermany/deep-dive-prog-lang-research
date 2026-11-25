#!/usr/bin/env python3
"""Report concept coverage per language file. Usage: tools/coverage.py ../data/languages/<id>.json ...

For each file prints the number of resources per level, and which baseline concepts have no
section-level resource at level 1 (primary) / level 2 (secondary) / level 0 (source code).
The baseline depends on the language's categories; a missing concept is only a problem if the
language actually has that feature and its documentation has a linkable section for it.
"""
import sys
from pathlib import Path
from common import *

PROG = ["lexical-structure", "comments", "literals", "variables", "scope", "primitive-types", "strings", "arrays", "maps-dictionaries",
        "records-structs", "conditionals", "switch-case", "pattern-matching", "loops", "functions", "closures", "exceptions",
        "error-handling", "modules", "imports", "operators", "type-system", "type-conversion", "generics", "classes",
        "interfaces-protocols", "concurrency", "memory-management", "macros", "standard-library", "grammar", "program-structure", "ffi"]
IMPL = ["lexer", "parser", "ast", "semantic-analysis", "intermediate-representation", "interpreter", "code-generation-backend",
        "garbage-collection", "runtime-system", "standard-library"]
DATA = ["data-model", "scalars", "collections", "comments", "escaping", "strings", "grammar", "schema-validation", "references-anchors",
        "encoding-wire-format", "security-considerations"]
QUERY = ["selection-projection", "joins", "aggregation", "sorting-limiting", "subqueries", "data-definition", "data-manipulation",
         "functions", "primitive-types", "null-semantics", "conditionals", "grammar", "lexical-structure"]
THEORY = ["formal-semantics", "reduction", "turing-completeness", "encodings", "automata", "formal-grammars", "type-soundness"]
PROGRAMMING_CATS = {"general-purpose", "systems", "scripting", "shell", "functional", "object-oriented", "logic", "array", "concatenative",
                    "scientific", "educational", "smart-contract", "shader-gpu", "database-procedural"}
DATA_CATS = {"data-serialization", "configuration", "schema-idl", "markup", "stylesheet", "template", "document-typesetting"}


def baseline(cats):
    cats = set(cats)
    b = []
    if cats & PROGRAMMING_CATS:
        b += PROG
    if cats & DATA_CATS:
        b += DATA
    if "query" in cats:
        b += QUERY
    if cats & {"theoretical-model", "calculus", "abstract-machine"}:
        b += THEORY
    return list(dict.fromkeys(b)), bool(cats & PROGRAMMING_CATS)


for a in sys.argv[1:]:
    d = load(Path(a).resolve())
    by = {0: set(), 1: set(), 2: set(), 3: set()}
    n = {0: 0, 1: 0, 2: 0, 3: 0}
    for r in d["resources"]:
        n[r["level"]] += 1
        by[r["level"]].update(r.get("concepts", []))
    base, prog = baseline(d["categories"])
    print(f"{d['id']}: resources L0={n[0]} L1={n[1]} L2={n[2]} L3={n[3]}; distinct concepts L0={len(by[0])} L1={len(by[1])} L2={len(by[2])}")
    if base:
        print("   baseline missing at L1:", ", ".join(c for c in base if c not in by[1]) or "-")
        print("   baseline missing at L2:", ", ".join(c for c in base if c not in by[2]) or "-")
    if prog:
        print("   implementation concepts missing at L0:", ", ".join(c for c in IMPL if c not in by[0]) or "-")
