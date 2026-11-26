#!/usr/bin/env python3
"""Build the data file for the browsable explorer (explorer/index.html).

  build_explorer.py                 write explorer/data.json from catalog.json
  build_explorer.py --page DIR      also write DIR/language-literature-explorer.html, a single page with the
                                    stylesheet and script inlined (plus DIR/data.json) for hosts that wrap the
                                    page in their own document skeleton

data.json is catalog.json reshaped for a browser: resources become positional rows with enum and site
indexes, and the connection analyses that are expensive to do client-side (similar languages, related
concepts) are precomputed here with the same code the CLI uses.
"""
import argparse
import json
import re
from pathlib import Path

from catalog_lib import Catalog, ROOT

EXPLORER = ROOT / "explorer"
ENUM_FIELDS = ("kind", "authority", "format", "access")


def dumps(x):
    return json.dumps(x, ensure_ascii=False, separators=(",", ":"))


def explorer_data(cat):
    lang_index = {l["id"]: i for i, l in enumerate(cat.languages)}
    concept_index = {c["id"]: i for i, c in enumerate(cat.concepts)}
    enums = {f: sorted({r[f] for r in cat.resources if r.get(f)}) for f in ENUM_FIELDS}
    enums["status"] = sorted({r.get("link_check", {}).get("status", "unchecked") for r in cat.resources})
    enum_index = {f: {v: i for i, v in enumerate(vs)} for f, vs in enums.items()}
    sites = [s["domain"] for s in cat.sites()]
    site_index = {s: i for i, s in enumerate(sites)}

    related = cat.related_concepts()
    concepts = [{"id": c["id"], "name": c["name"], "cat": c["category"], "aka": c.get("aliases", []), "desc": c.get("description", ""),
                 "rel": [[concept_index[o], n] for o, n, _ in related.get(c["id"], [])]} for c in cat.concepts]

    langs = []
    for l in cat.languages:
        sim = []
        for score, other, shared in cat.similar(l["id"], 8):
            why = "; ".join(f"{g}: {', '.join(v[:3])}" for g, v in shared.items())
            sim.append([lang_index[other], round(score * 100), why])
        langs.append({
            "id": l["id"], "name": l["name"], "aka": l.get("aliases", []), "cats": l["categories"], "par": l.get("paradigms", []),
            "typ": l.get("typing", []), "year": l.get("first_appeared"), "des": l.get("designers", []), "sum": l["summary"],
            "status": l.get("status", ""), "def": l.get("defined_by", []), "std": l.get("standards", []), "ext": l.get("file_extensions", []),
            "home": l.get("homepage", ""), "inf": list(dict.fromkeys(l.get("influenced_by", []))),
            "rel": [[r["id"], r["relation"]] for r in l.get("related", [])], "notes": l.get("level_notes", {}), "sim": sim,
        })

    rows = []
    for r in cat.resources:
        owner = -1 - next(i for i, g in enumerate(cat.general) if g["id"] == r["_owner"]) if r["_general"] else lang_index[r["_owner"]]
        extra = {}
        for key, short in (("implementation", "i"), ("authors", "a"), ("year", "y"), ("version", "v"), ("notes", "n")):
            if r.get(key):
                extra[short] = r[key]
        if r.get("languages"):
            extra["l"] = [lang_index[x] for x in r["languages"] if x in lang_index]
        rows.append([
            owner, r["level"], enum_index["kind"][r["kind"]], r["title"], r["url"], site_index[r["_domain"]],
            [concept_index[c] for c in r.get("concepts", []) if c in concept_index],
            1 if r.get("scope") == "section" else 0,
            enum_index["authority"].get(r.get("authority"), -1), enum_index["format"].get(r.get("format"), -1),
            enum_index["access"].get(r.get("access"), -1), enum_index["status"][r.get("link_check", {}).get("status", "unchecked")],
            extra or 0,
        ])

    return {
        "meta": {"generated": cat.meta["generated"], "counts": cat.meta["counts"], "levels": cat.meta["levels"],
                 "linkLegend": cat.meta["link_check_legend"], "linkSummary": cat.meta["link_check_summary"]},
        "enums": enums, "sites": sites, "conceptCats": cat.concept_categories, "concepts": concepts, "langs": langs,
        "collections": [{"id": g["id"], "title": g["title"], "desc": g.get("description", "")} for g in cat.general],
        "res": rows,
    }


def write_data(data, path):
    """One record per line so the file diffs and greps sensibly."""
    parts = []
    for key, value in data.items():
        if isinstance(value, list) and len(value) > 20:
            parts.append(f"{dumps(key)}:[\n" + ",\n".join(dumps(v) for v in value) + "\n]")
        else:
            parts.append(f"{dumps(key)}:{dumps(value)}")
    path.write_text("{\n" + ",\n".join(parts) + "\n}\n", encoding="utf-8")


def build(cat=None):
    cat = cat or Catalog()
    data = explorer_data(cat)
    out = EXPLORER / "data.json"
    write_data(data, out)
    print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size / 1e6:.1f} MB, {len(data['res'])} links, {len(data['langs'])} languages)")
    return out


def write_page(directory):
    """Single-file variant of explorer/index.html: head tags + inlined CSS and JS, no <html>/<body> wrapper."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    html = (EXPLORER / "index.html").read_text(encoding="utf-8")
    head = re.search(r"<head>(.*?)</head>", html, re.S).group(1)
    body = re.search(r"<body>(.*?)</body>", html, re.S).group(1)
    keep = [l.strip() for l in head.splitlines() if re.search(r"<title>|fonts\.g|claude:", l)]
    css = (EXPLORER / "style.css").read_text(encoding="utf-8")
    js = (EXPLORER / "app.js").read_text(encoding="utf-8")
    body = re.sub(r"\s*<script src=\"app\.js\"></script>", "", body).strip()
    page = "\n".join(keep) + f"\n<style>\n{css}</style>\n{body}\n<script>\n{js}</script>\n"
    (directory / "language-literature-explorer.html").write_text(page, encoding="utf-8")
    (directory / "data.json").write_bytes((EXPLORER / "data.json").read_bytes())
    print(f"wrote {directory / 'language-literature-explorer.html'} and data.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--page", metavar="DIR", help="also write a single-page build into DIR")
    args = ap.parse_args()
    build()
    if args.page:
        write_page(args.page)
