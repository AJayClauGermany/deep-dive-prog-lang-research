#!/usr/bin/env python3
"""Smoke tests for the read-side tools. Run from anywhere: python3 tools/test_tools.py"""
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_explorer
import q
from catalog_lib import Catalog

cat = Catalog()


def run(*argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        q.main(list(argv))
    return buf.getvalue()


def check(name, ok):
    print(("ok   " if ok else "FAIL ") + name)
    if not ok:
        check.failed = True


check.failed = False

# lookups resolve ids, names and aliases
check("find_language by id/name/alias", cat.find_language("rust")["id"] == "rust" and cat.find_language("Golang")["id"] == "go" and cat.find_language("no-such-language") is None)
check("find_concept by alias", cat.find_concept("closures")["id"] == "closures" and cat.find_concept("regex")["id"] == "regular-expressions")

# every resource is reachable and filters narrow
check("resource count matches meta", len(cat.resources) == cat.meta["counts"]["resources"])
spec = cat.filter_resources(levels=[1], concepts=["conditionals"], owners=["go"])
check("filter by level+concept+owner", spec and all(r["level"] == 1 and "conditionals" in r["concepts"] for r in spec))

# graph: edges are symmetric and paths are real chains
check("influence edges mirror", all(l in cat.influenced[x] for l, xs in cat.influences.items() for x in xs))
p = cat.path("fortran", "rust")
check("path is a chain of neighbours", p[0] == "fortran" and p[-1] == "rust" and all(b in cat.neighbours[a] for a, b in zip(p, p[1:])))
s_ab, s_ba = cat.similarity("ocaml", "standard-ml")[0], cat.similarity("standard-ml", "ocaml")[0]
check("similarity symmetric and bounded", abs(s_ab - s_ba) < 1e-9 and 0 < s_ab <= 1 and cat.similarity("ocaml", "ocaml")[0] > 0.99)

# CLI: every command runs; JSON output parses
for argv in (["stats"], ["langs", "--category", "query", "-n", "3"], ["lang", "rust"], ["lang", "go", "-l", "1", "-c", "conditionals"], ["lang", "go", "--mentions", "-n", "3"],
             ["concepts", "--grep", "match"], ["concept", "tail-calls", "-l", "1"], ["compare", "rust", "go"], ["compare", "rust", "go", "-c", "closures"],
             ["search", "borrow", "checker"], ["lineage", "standard-ml"], ["path", "c", "python"], ["similar", "gleam"], ["sites"], ["site", "tc39.es", "-n", "3"],
             ["people", "--grep", "wirth"], ["gaps", "zig"], ["gaps", "-c", "joins", "--category", "query"], ["links"], ["shared"], ["dossier", "gleam"]):
    check("q.py " + " ".join(argv), len(run(*argv)) > 20)
rows = json.loads(run("concept", "pattern-matching", "-l", "1", "--langs", "rust", "ocaml", "--no-general", "-f", "json"))
check("json output", rows and {r["owner"] for r in rows} == {"rust", "ocaml"} and all(r["url"].startswith("http") for r in rows))
check("urls output", all(u.startswith("http") for u in run("lang", "gleam", "--all", "-f", "urls").split()))

# explorer data round-trips the catalog
data = build_explorer.explorer_data(cat)
with tempfile.TemporaryDirectory() as tmp:
    build_explorer.write_data(data, Path(tmp) / "data.json")
    back = json.loads((Path(tmp) / "data.json").read_text(encoding="utf-8"))
check("explorer rows = resources", len(back["res"]) == len(cat.resources) and len(back["langs"]) == len(cat.languages))
row = back["res"][0]
check("explorer row decodes", back["langs"][row[0]]["id"] == cat.resources[0]["_owner"] and row[4] == cat.resources[0]["url"] and back["sites"][row[5]] == cat.resources[0]["_domain"])

sys.exit(1 if check.failed else 0)
