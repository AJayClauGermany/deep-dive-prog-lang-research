#!/usr/bin/env python3
"""Merge data/ into a single catalog.json (one JSON value) with cross-language concept indexes."""
import json, re, datetime, collections
from common import *

LEVELS = [
    {"level": 0, "name": "Source code", "description": "Actual implementations: compilers, interpreters, runtimes, standard libraries, grammars, conformance suites. Shows how a language can be implemented; it is not the definition of the language."},
    {"level": 1, "name": "Primary sources", "description": "What defines the language independent of any implementation: standards, specifications, reference manuals, proposals, formal semantics and the designers' defining papers."},
    {"level": 2, "name": "Secondary sources", "description": "Material that explains or analyses the primary sources: tutorials, books, guides, courses, papers, history, comparison guides."},
    {"level": 3, "name": "Tertiary sources", "description": "Collections and summaries of other sources: encyclopedias, wikis, catalogs, comparison tables, curated lists."},
]


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def main():
    concepts_doc = load(DATA / "concepts.json")
    status = {}
    for p in sorted((BUILD / "link-status").glob("*.json")) if (BUILD / "link-status").exists() else []:
        status.update(load(p))
    ls_path = DATA / "link-status.json"
    if ls_path.exists():
        committed = load(ls_path)
        committed.update(status)
        status = committed

    languages, general = [], []
    by_concept = collections.defaultdict(lambda: collections.defaultdict(list))
    by_category = collections.defaultdict(list)
    used_status = {}
    stats = collections.Counter()

    def finish(owner_id, r, used):
        rid = f"{owner_id}:L{r['level']}:{slug(r['title'])}"
        n = 2
        base = rid
        while rid in used:
            rid = f"{base}-{n}"; n += 1
        used.add(rid)
        out = {"id": rid, **r}
        st = status.get(r["url"])
        if st:
            out["link_check"] = {k: st[k] for k in ("status", "http", "checked", "redirected_to") if st.get(k) is not None}
            used_status[r["url"]] = st
        stats[f"level_{r['level']}"] += 1
        stats["resources"] += 1
        return out

    used = set()
    for p in language_files():
        d = load(p)
        d["resources"] = [finish(d["id"], r, used) for r in sorted(d["resources"], key=lambda r: r["level"])]
        for r in d["resources"]:
            for c in r.get("concepts", []):
                by_concept[c][d["id"]].append({"resource": r["id"], "level": r["level"], "kind": r["kind"], "title": r["title"], "url": r["url"]})
        for c in d["categories"]:
            by_category[c].append(d["id"])
        languages.append(d)
    for p in general_files():
        d = load(p)
        d["resources"] = [finish("general/" + d["id"], r, used) for r in d["resources"]]
        for r in d["resources"]:
            for c in r.get("concepts", []):
                by_concept[c]["*"].append({"resource": r["id"], "level": r["level"], "kind": r["kind"], "title": r["title"], "url": r["url"], **({"languages": r["languages"]} if r.get("languages") else {})})
        general.append(d)

    concept_index = {}
    for c in concepts_doc["concepts"]:
        entry = by_concept.get(c["id"], {})
        concept_index[c["id"]] = {
            "name": c["name"],
            "language_count": len([k for k in entry if k != "*"]),
            "resource_count": sum(len(v) for v in entry.values()),
            "general": entry.get("*", []),
            "by_language": {k: sorted(v, key=lambda x: x["level"]) for k, v in sorted(entry.items()) if k != "*"},
        }
    ids = {l["id"] for l in languages}
    unresolved = sorted({x for l in languages for x in l.get("influenced_by", []) + [r["id"] for r in l.get("related", [])] if x not in ids})
    link_counts = collections.Counter(s["status"] for s in used_status.values())
    catalog = {
        "meta": {
            "title": "Computer language literature catalog",
            "generated": datetime.date.today().isoformat(),
            "levels": LEVELS,
            "counts": {"languages": len(languages), "general_collections": len(general), "concepts": len(concepts_doc["concepts"]), **dict(stats)},
            "link_check_summary": dict(link_counts),
            "link_check_legend": {
                "ok": "fetched successfully (and #fragment found when present)",
                "anchor-missing": "page exists but the #fragment was not found in static HTML",
                "repo-only": "GitHub directory/wiki/issue link; only repository existence was confirmed",
                "blocked": "site refuses automated clients; not verified",
                "dead": "404/410 at check time", "error": "timeout or server error at check time",
            },
            "unresolved_language_references": unresolved,
        },
        "concept_categories": concepts_doc["categories"],
        "concepts": concepts_doc["concepts"],
        "languages": languages,
        "general": general,
        "indexes": {
            "by_concept": concept_index,
            "languages_by_category": {k: sorted(v) for k, v in sorted(by_category.items())},
        },
    }
    (ROOT / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    ls_path.write_text(json.dumps(dict(sorted(used_status.items())), indent=0) + "\n")
    print(json.dumps(catalog["meta"]["counts"]), dict(link_counts))


if __name__ == "__main__":
    main()
