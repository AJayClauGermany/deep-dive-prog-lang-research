#!/usr/bin/env python3
"""Query the language literature catalog from the command line.

  q.py stats                                  what is in the catalog
  q.py langs --category query --from 2010     find languages by facets
  q.py lang rust --level 1 --concept generics one language: profile, connections, links
  q.py concepts --grep match                  find concept ids
  q.py concept pattern-matching --level 1     one concept across every language
  q.py compare rust go zig                    side-by-side concept coverage with links
  q.py search tail call optimisation          full-text over titles, URLs, notes, authors
  q.py lineage ml --depth 2                   ancestors and descendants by influence
  q.py path fortran rust                      how two languages are connected
  q.py similar gleam                          nearest languages and why
  q.py sites / q.py site tc39.es              which websites hold the material
  q.py people --grep wirth                    designers and authors across languages
  q.py gaps zig / q.py gaps --concept joins --category query --level 1
  q.py links --status blocked error           links the checker could not verify
  q.py shared                                 documents filed under several languages
  q.py dossier ocaml > ocaml.md               Markdown research brief for one language
  q.py sqlite build/catalog.sqlite            export for ad-hoc SQL (with full-text search)
  q.py serve                                  build and open the browsable explorer

Every listing accepts --format text|md|json|tsv|urls (default text) and --limit N.
"""
import argparse
import collections
import json
import sys

from catalog_lib import Catalog, LEVEL_NAMES, ROOT, domain_of, slug

FORMATS = ("text", "md", "json", "tsv", "urls")


def die(msg):
    sys.exit(f"q.py: {msg}")


def clean(r):
    return {k: v for k, v in r.items() if not k.startswith("_")}


def need_lang(cat, q):
    l = cat.find_language(q)
    if not l:
        hint = ", ".join(cat.suggest_languages(q)) or "nothing similar"
        die(f"no language '{q}'. Did you mean: {hint}")
    return l


def need_concept(cat, q):
    c = cat.find_concept(q)
    if not c:
        hint = ", ".join(cat.suggest_concepts(q)) or "nothing similar; try: q.py concepts --grep <word>"
        die(f"no concept '{q}'. Did you mean: {hint}")
    return c


def flag(r):
    st = r.get("link_check", {}).get("status")
    bits = []
    if st and st != "ok":
        bits.append({"blocked": "unverified: site blocks robots", "repo-only": "repository verified, path not",
                     "error": "link check failed", "dead": "dead", "anchor-missing": "anchor missing"}.get(st, st))
    if r.get("access") and r["access"] != "open":
        bits.append(r["access"])
    return f" ({'; '.join(bits)})" if bits else ""


def emit_resources(rows, fmt, limit=None, owner=True, cat=None, out=None):
    """Print a flat resource list. `rows` is a list of resources (already filtered and ordered)."""
    out = out or sys.stdout
    total = len(rows)
    if limit:
        rows = rows[:limit]
    w = out.write
    if fmt == "json":
        json.dump([{"owner": r["_owner"], **clean(r)} for r in rows], out, ensure_ascii=False, indent=1)
        w("\n")
    elif fmt == "urls":
        for u in dict.fromkeys(r["url"] for r in rows):
            w(u + "\n")
    elif fmt == "tsv":
        w("owner\tlevel\tkind\ttitle\turl\tconcepts\tlink_status\n")
        for r in rows:
            w("\t".join([r["_owner"], str(r["level"]), r["kind"], r["title"], r["url"], ",".join(r.get("concepts", [])),
                         r.get("link_check", {}).get("status", "")]) + "\n")
    elif fmt == "md":
        last = None
        for r in rows:
            if owner and r["_owner"] != last:
                last = r["_owner"]
                w(f"\n### {cat.name(last) if cat and not r['_general'] else last}\n\n")
            tags = f" — `{'`, `'.join(r['concepts'])}`" if r.get("concepts") else ""
            w(f"- **L{r['level']}** {r['kind']}: [{r['title']}]({r['url']}){tags}{flag(r)}\n")
    else:
        last = None
        for r in rows:
            if owner and r["_owner"] != last:
                last = r["_owner"]
                w(f"\n{cat.name(last) if cat and not r['_general'] else last}  [{'general/' if r['_general'] else ''}{last}]\n")
            extra = " ".join(filter(None, [", ".join(r.get("authors", [])[:3]), str(r.get("year") or ""), r.get("implementation", "")]))
            w(f"  L{r['level']} {r['kind']:<24} {r['title']}{flag(r)}\n")
            w(f"     {r['url']}\n")
            tags = ("[" + ", ".join(r["concepts"]) + "]") if r.get("concepts") else ""
            if tags or extra:
                w(f"     {'  '.join(filter(None, [tags, extra]))}\n")
    if limit and total > limit and fmt in ("text", "md"):
        w(f"\n... {total - limit} more (raise --limit)\n")


def table(rows, headers, fmt, out=None):
    """Print rows of scalars as an aligned table, Markdown table, TSV or JSON."""
    out = out or sys.stdout
    if fmt == "json":
        json.dump([dict(zip(headers, r)) for r in rows], out, ensure_ascii=False, indent=1)
        out.write("\n")
        return
    rows = [[("" if v is None else str(v)) for v in r] for r in rows]
    if fmt == "tsv" or fmt == "urls":
        out.write("\t".join(headers) + "\n")
        for r in rows:
            out.write("\t".join(r) + "\n")
    elif fmt == "md":
        out.write("| " + " | ".join(headers) + " |\n|" + "---|" * len(headers) + "\n")
        for r in rows:
            out.write("| " + " | ".join(c.replace("|", "\\|") for c in r) + " |\n")
    else:
        widths = [min(60, max(len(h), *(len(r[i]) for r in rows))) if rows else len(h) for i, h in enumerate(headers)]
        line = lambda r: "  ".join((c[:w - 1] + "…" if len(c) > w else c).ljust(w) for c, w in zip(r, widths)).rstrip()
        out.write(line(headers) + "\n" + "  ".join("-" * w for w in widths) + "\n")
        for r in rows:
            out.write(line(r) + "\n")


def level_counts(resources):
    c = collections.Counter(r["level"] for r in resources)
    return [c.get(i, 0) for i in range(4)]


# ---- commands --------------------------------------------------------------------------------------

def cmd_stats(cat, a):
    c = cat.meta["counts"]
    print(f"{c['languages']} languages, {c['resources']} links, {c['concepts']} concepts, {c['general_collections']} cross-language collections")
    print(f"generated {cat.meta['generated']}\n")
    table([[f"L{l['level']}", l["name"], c.get(f"level_{l['level']}", 0)] for l in cat.meta["levels"]], ["level", "name", "links"], "text")
    print()
    table(sorted(cat.meta["link_check_summary"].items(), key=lambda kv: -kv[1]), ["link status", "links"], "text")
    cats = collections.Counter(x for l in cat.languages for x in l["categories"])
    print()
    table(cats.most_common(), ["language category", "languages"], "text")


def cmd_langs(cat, a):
    langs = cat.filter_languages(categories=a.category, paradigms=a.paradigm, typing=a.typing, status=a.status,
                                 defined_by=a.defined_by, year_from=a.year_from, year_to=a.year_to, designer=a.designer,
                                 text=" ".join(a.grep) if a.grep else None)
    key = {"name": lambda l: l["name"].lower(), "year": lambda l: (l.get("first_appeared") or 9999, l["id"]),
           "links": lambda l: -len(l["resources"])}[a.sort]
    langs = sorted(langs, key=key)[: a.limit or None]
    if a.format == "json":
        json.dump([{k: v for k, v in l.items() if k != "resources"} | {"resource_count": len(l["resources"])} for l in langs],
                  sys.stdout, ensure_ascii=False, indent=1)
        return
    table([[l["id"], l["name"], l.get("first_appeared"), ",".join(l["categories"]), ",".join(l.get("typing", [])[:3]),
            "/".join(map(str, level_counts(l["resources"])))] for l in langs],
          ["id", "name", "year", "categories", "typing", "L0/L1/L2/L3"], a.format)
    if a.format == "text":
        print(f"\n{len(langs)} languages")


def print_connections(cat, l, out=None, md=False):
    out = out or sys.stdout
    lid = l["id"]
    b = (lambda s: f"**{s}**") if md else (lambda s: s)
    fmt = lambda ids: ", ".join(f"{cat.name(i)} ({cat.year(i) or '?'})" if i in cat.lang else f"{i} (not in catalog)" for i in ids)
    if cat.influences.get(lid):
        out.write(f"{b('Influenced by')}: {fmt(cat.influences[lid])}\n\n" if md else f"influenced by : {fmt(cat.influences[lid])}\n")
    if cat.influenced.get(lid):
        ids = sorted(cat.influenced[lid], key=lambda i: (cat.year(i) or 9999, i))
        out.write(f"{b('Influenced')}: {fmt(ids)}\n\n" if md else f"influenced    : {fmt(ids)}\n")
    groups = collections.defaultdict(list)
    for other, label, _ in cat.relations.get(lid, []):
        groups[label].append(other)
    for label, ids in groups.items():
        names = ", ".join(cat.name(i) for i in dict.fromkeys(ids))
        out.write(f"{b(label.capitalize())}: {names}\n\n" if md else f"{label:<14}: {names}\n")


def cmd_lang(cat, a):
    l = need_lang(cat, a.language)
    filtered = any([a.level is not None, a.kind, a.concept, a.site, a.grep])
    rows = cat.filter_resources(l["resources"], levels=a.level, kinds=a.kind, concepts=a.concept, domain=a.site,
                                text=" ".join(a.grep) if a.grep else None)
    if a.mentions:
        rows = [r for r in cat.resources if r["_general"] and l["id"] in r.get("languages", [])]
        rows = cat.filter_resources(rows, levels=a.level, kinds=a.kind, concepts=a.concept, domain=a.site,
                                    text=" ".join(a.grep) if a.grep else None)
    if a.format != "text":
        return emit_resources(rows, a.format, a.limit, owner=a.mentions, cat=cat)
    lc = level_counts(l["resources"])
    print(f"{l['name']}  [{l['id']}]  {l.get('first_appeared') or ''}  {l.get('status', '')}")
    if l.get("aliases"):
        print("also known as : " + ", ".join(l["aliases"]))
    print(f"\n{l['summary']}\n")
    for label, key in [("categories", "categories"), ("paradigms", "paradigms"), ("typing", "typing"), ("designers", "designers"),
                       ("defined by", "defined_by"), ("standards", "standards"), ("extensions", "file_extensions")]:
        if l.get(key):
            print(f"{label:<14}: {', '.join(l[key])}")
    if l.get("homepage"):
        print(f"homepage      : {l['homepage']}")
    print_connections(cat, l)
    sim = cat.similar(l["id"], 6)
    print("similar       : " + ", ".join(f"{cat.name(o)} ({s:.2f})" for s, o, _ in sim))
    for lvl, note in sorted(l.get("level_notes", {}).items()):
        print(f"\nL{lvl} note: {note}")
    mentions = sum(1 for r in cat.resources if r["_general"] and l["id"] in r.get("languages", []))
    print(f"\nlinks: L0 {lc[0]} · L1 {lc[1]} · L2 {lc[2]} · L3 {lc[3]}   (+{mentions} cross-language links mention it: --mentions)")
    if not (filtered or a.all or a.mentions):
        cov = cat.coverage(l["id"])
        print(f"concepts covered: {len(cov)}   (list links with --all, or filter: --level 1 --concept generics --grep word)")
        return
    emit_resources(rows, "text", a.limit, owner=a.mentions, cat=cat)


def cmd_concepts(cat, a):
    idx = collections.defaultdict(lambda: [set(), 0])
    for r in cat.resources:
        for c in r.get("concepts", []):
            idx[c][1] += 1
            if not r["_general"]:
                idx[c][0].add(r["_owner"])
    terms = [t.lower() for t in a.grep or []]
    rows = []
    for c in cat.concepts:
        hay = " ".join([c["id"], c["name"], c.get("description", ""), " ".join(c.get("aliases", []))]).lower()
        if all(t in hay for t in terms) and (not a.category or c["category"] in a.category):
            rows.append([c["id"], c["name"], c["category"], len(idx[c["id"]][0]), idx[c["id"]][1], ", ".join(c.get("aliases", []))])
    table(rows[: a.limit or None], ["id", "name", "group", "languages", "links", "aliases"], a.format)


def cmd_concept(cat, a):
    c = need_concept(cat, a.concept)
    langs = [need_lang(cat, x)["id"] for x in a.langs] if a.langs else None
    by_lang, general = cat.concept_resources(c["id"], levels=a.level, languages=langs, categories=a.category)
    rows = [r for rs in by_lang.values() for r in sorted(rs, key=lambda r: r["level"])]
    if a.general_only:
        rows = []
    elif a.no_general:
        general = []
    if a.format != "text":
        return emit_resources(rows + general, a.format, a.limit, cat=cat)
    print(f"{c['name']}  [{c['id']}]  group: {c['category']}")
    print(c.get("description", ""))
    if c.get("aliases"):
        print("aliases: " + ", ".join(c["aliases"]))
    rel = cat.related_concepts().get(c["id"], [])
    if rel:
        print("often tagged together with: " + ", ".join(f"{o} ({n})" for o, n, _ in rel))
    print(f"\n{len(by_lang)} languages, {len(rows)} links; {len(general)} cross-language links")
    emit_resources(rows + general, "text", a.limit, cat=cat)


def cmd_compare(cat, a):
    langs = [need_lang(cat, x) for x in a.languages]
    ids = [l["id"] for l in langs]
    want = [need_concept(cat, x)["id"] for x in a.concept] if a.concept else None
    cov = {i: collections.defaultdict(list) for i in ids}
    for l in langs:
        for r in l["resources"]:
            if a.level is None or r["level"] in a.level:
                for c in r.get("concepts", []):
                    cov[l["id"]][c].append(r)
    concepts = [c for c in cat.concepts if (want is None or c["id"] in want) and any(cov[i].get(c["id"]) for i in ids)]
    if a.shared:
        concepts = [c for c in concepts if all(cov[i].get(c["id"]) for i in ids)]
    if a.diff:
        concepts = [c for c in concepts if not all(cov[i].get(c["id"]) for i in ids)]
    if a.format == "json":
        json.dump({c["id"]: {i: [clean(r) for r in cov[i].get(c["id"], [])] for i in ids} for c in concepts}, sys.stdout, ensure_ascii=False, indent=1)
        return
    if a.links or want:
        md = a.format == "md"
        for c in concepts:
            print(f"\n## {c['name']} (`{c['id']}`)" if md else f"\n== {c['name']}  [{c['id']}]")
            for i in ids:
                rs = sorted(cov[i].get(c["id"], []), key=lambda r: r["level"])
                print(f"\n**{cat.name(i)}**\n" if md else f"\n{cat.name(i)}")
                if not rs:
                    print("- nothing tagged" if md else "  (nothing tagged)")
                for r in rs[: a.limit or None]:
                    print(f"- **L{r['level']}** {r['kind']}: [{r['title']}]({r['url']}){flag(r)}" if md
                          else f"  L{r['level']} {r['kind']:<22} {r['title']}{flag(r)}\n     {r['url']}")
        return
    if a.format == "text":
        facts = [("first appeared", lambda l: l.get("first_appeared")), ("typing", lambda l: ", ".join(l.get("typing", []))),
                 ("paradigms", lambda l: ", ".join(l.get("paradigms", []))), ("defined by", lambda l: ", ".join(l.get("defined_by", []))),
                 ("status", lambda l: l.get("status")), ("links L0/L1/L2/L3", lambda l: "/".join(map(str, level_counts(l["resources"]))))]
        table([[n] + [f(l) for l in langs] for n, f in facts], [""] + [l["name"] for l in langs], "text")
        for i, x in enumerate(ids):
            for y in ids[i + 1:]:
                p = cat.path(x, y)
                if p:
                    chain = cat.name(p[0]) + "".join(f" —{cat.link_label(p[k], p[k + 1])}→ {cat.name(p[k + 1])}" for k in range(len(p) - 1))
                    print(f"\n{chain}")
        print("\nConcept coverage (digits = source levels with a link; add --links or --concept <id> to see the links)\n")
    cell = lambda rs: "".join(str(x) for x in sorted({r["level"] for r in rs})) or "·"
    table([[c["id"], c["category"]] + [cell(cov[i].get(c["id"], [])) for i in ids] for c in concepts],
          ["concept", "group"] + ids, a.format)


def cmd_search(cat, a):
    text = " ".join(a.terms)
    owners = [need_lang(cat, x)["id"] for x in a.lang] if a.lang else None
    rows = cat.filter_resources(levels=a.level, kinds=a.kind, concepts=a.concept, domain=a.site, text=text, owners=owners)
    if a.format == "text":
        langs = cat.filter_languages(text=text)[:10]
        if langs:
            print("languages: " + ", ".join(f"{l['name']} [{l['id']}]" for l in langs))
        cs = cat.suggest_concepts(text)
        if cs:
            print("concepts : " + ", ".join(cs))
        print(f"{len(rows)} links")
    rows.sort(key=lambda r: (r["_general"], r["_owner"], r["level"]))
    emit_resources(rows, a.format, a.limit, cat=cat)


def cmd_lineage(cat, a):
    l = need_lang(cat, a.language)

    def tree(direction):
        edges = cat.influences if direction == "up" else cat.influenced
        seen = {l["id"]}

        def rec(node, depth, indent):
            kids = sorted(dict.fromkeys(edges.get(node, [])), key=lambda i: (cat.year(i) or 9999, i))
            for k in kids:
                again = k in seen
                print(f"{indent}{cat.name(k)} ({cat.year(k) or '?'}){'  ↺' if again else ''}")
                if not again:
                    seen.add(k)
                    if depth < a.depth:
                        rec(k, depth + 1, indent + "   ")
        rec(l["id"], 1, "   ")

    if a.format == "json":
        json.dump({"id": l["id"], "ancestors": {k: v[0] for k, v in cat.walk(l["id"], "up", a.depth).items()},
                   "descendants": {k: v[0] for k, v in cat.walk(l["id"], "down", a.depth).items()},
                   "relations": [{"id": o, "relation": lab} for o, lab, _ in cat.relations.get(l["id"], [])]}, sys.stdout, indent=1)
        return
    print(f"{l['name']} ({l.get('first_appeared') or '?'})\n\nInfluenced by (depth {a.depth}):")
    tree("up")
    print(f"\nInfluenced (depth {a.depth}):")
    tree("down")
    rel = cat.relations.get(l["id"], [])
    if rel:
        print("\nOther relations:")
        for other, label, _ in rel:
            print(f"   {label} {cat.name(other)}")


def cmd_path(cat, a):
    x, y = need_lang(cat, a.a)["id"], need_lang(cat, a.b)["id"]
    p = cat.path(x, y)
    if not p:
        die(f"no chain of influence or relation links connects {x} and {y}")
    print(cat.name(p[0]))
    for k in range(len(p) - 1):
        print(f"   {cat.link_label(p[k], p[k + 1])} → {cat.name(p[k + 1])} ({cat.year(p[k + 1]) or '?'})")


def cmd_similar(cat, a):
    l = need_lang(cat, a.language)
    rows = []
    for s, other, shared in cat.similar(l["id"], a.limit or 12):
        why = "; ".join(f"{g}: {', '.join(v[:4])}" for g, v in shared.items())
        rows.append([other, cat.name(other), f"{s:.2f}", why])
    table(rows, ["id", "name", "score", "shared"], a.format)


def cmd_sites(cat, a):
    terms = [t.lower() for t in a.grep or []]
    rows = [[s["domain"], s["resources"], len(s["languages"])] + [s["levels"].get(i, 0) for i in range(4)]
            for s in cat.sites() if all(t in s["domain"] for t in terms)]
    table(rows[: a.limit or 40], ["site", "links", "languages", "L0", "L1", "L2", "L3"], a.format)


def cmd_site(cat, a):
    dom = domain_of(a.domain) if "//" in a.domain else a.domain.lower().removeprefix("www.")
    owners = [need_lang(cat, x)["id"] for x in a.lang] if a.lang else None
    rows = cat.filter_resources(domain=dom, levels=a.level, concepts=a.concept, owners=owners, text=" ".join(a.grep) if a.grep else None)
    if not rows:
        die(f"no links on '{dom}'. Try: q.py sites --grep {dom.split('.')[0]}")
    if a.format == "text":
        by = collections.Counter(r["_owner"] for r in rows)
        print(f"https://{dom}/ — {len(rows)} links across {len(by)} languages/collections")
        print("most links: " + ", ".join(f"{k} ({v})" for k, v in by.most_common(12)))
    rows.sort(key=lambda r: (r["_general"], r["_owner"], r["level"]))
    emit_resources(rows, a.format, a.limit, cat=cat)


def cmd_people(cat, a):
    people = cat.people()
    terms = [t.lower() for t in a.grep or []]
    hits = {n: p for n, p in people.items() if all(t in n.lower() for t in terms)}
    if terms and len(hits) <= 3 and a.format == "text":
        for n, p in hits.items():
            print(f"{n}")
            if p["designed"]:
                print("  designed: " + ", ".join(f"{cat.name(i)} ({cat.year(i) or '?'})" for i in sorted(p["designed"], key=lambda i: cat.year(i) or 9999)))
            if p["authored"]:
                print(f"  authored {len(p['authored'])} catalogued links:")
                emit_resources(sorted(p["authored"], key=lambda r: (r.get("year") or 9999)), "text", a.limit or 40, owner=False)
        return
    rows = sorted(([n, len(p["designed"]), len(p["authored"]), ", ".join(p["designed"][:8])] for n, p in hits.items()),
                  key=lambda r: (-(r[1] * 3 + r[2]), r[0]))
    table(rows[: a.limit or 40], ["name", "languages designed", "links authored", "designed"], a.format)


def cmd_gaps(cat, a):
    lvls = a.level if a.level is not None else [1]
    if a.concept:
        c = need_concept(cat, a.concept[0])
        pool = cat.filter_languages(categories=a.category)
        have = {l["id"] for l in pool if any(r["level"] in lvls and c["id"] in r.get("concepts", []) for r in l["resources"])}
        rows = [[l["id"], l["name"], l.get("first_appeared"), len(l["resources"]), ",".join(l["categories"])]
                for l in sorted(pool, key=lambda l: -len(l["resources"])) if l["id"] not in have]
        if a.format == "text":
            print(f"{len(have)} of {len(pool)} languages have a level {'/'.join(map(str, lvls))} link tagged '{c['id']}'. Without one (best documented first):\n")
        return table(rows[: a.limit or 40], ["id", "name", "year", "links", "categories"], a.format)
    if not a.language:
        die("give a language, or --concept <id> [--category <cat>]")
    l = need_lang(cat, a.language)
    peers = [o for _, o, _ in cat.similar(l["id"], 15)]
    mine = cat.coverage(l["id"])
    peer_cov = collections.Counter()
    examples = collections.defaultdict(list)
    for p in peers:
        for c, levels in cat.coverage(p).items():
            if set(lvls) & levels:
                peer_cov[c] += 1
                examples[c].append(p)
    rows = [[c, cat.concept[c]["category"], f"{n}/{len(peers)}", "".join(map(str, sorted(mine.get(c, [])))) or "none", ", ".join(examples[c][:4])]
            for c, n in peer_cov.most_common() if not (set(lvls) & mine.get(c, set())) and n >= 3]
    if a.format == "text":
        print(f"Concepts that {l['name']}'s nearest peers cover at level {'/'.join(map(str, lvls))} but {l['name']} does not:\n")
    table(rows[: a.limit or 40], ["concept", "group", "peers covering", "levels here", "see e.g."], a.format)


def cmd_links(cat, a):
    status = a.status or ["blocked", "error", "dead", "anchor-missing", "repo-only"]
    owners = [need_lang(cat, x)["id"] for x in a.lang] if a.lang else None
    rows = cat.filter_resources(status=status, owners=owners, domain=a.site)
    if a.format == "text" and not (a.lang or a.site):
        by = collections.Counter((r["link_check"]["status"], r["_domain"]) for r in rows)
        return table([[s, d, n] for (s, d), n in by.most_common(a.limit or 40)], ["status", "site", "links"], "text")
    emit_resources(rows, a.format, a.limit, cat=cat)


def cmd_shared(cat, a):
    rows = [[len(ls), u, ", ".join(ls[:10]) + (" …" if len(ls) > 10 else ""), t] for u, ls, t in cat.shared_documents(a.min)]
    table(rows[: a.limit or 40], ["languages", "document", "filed under", "title"], a.format)


def cmd_dossier(cat, a):
    l = need_lang(cat, a.language)
    w = sys.stdout.write
    w(f"# {l['name']}\n\n{l['summary']}\n\n")
    facts = [("First appeared", l.get("first_appeared")), ("Status", l.get("status")), ("Categories", ", ".join(l["categories"])),
             ("Paradigms", ", ".join(l.get("paradigms", []))), ("Typing", ", ".join(l.get("typing", []))),
             ("Designers", ", ".join(l.get("designers", []))), ("Defined by", ", ".join(l.get("defined_by", []))),
             ("Standards", ", ".join(l.get("standards", []))), ("Homepage", l.get("homepage"))]
    for k, v in facts:
        if v:
            w(f"- **{k}:** {v}\n")
    w("\n## Connections\n\n")
    print_connections(cat, l, md=True)
    w("**Most similar in the catalog**: " + ", ".join(f"{cat.name(o)} ({s:.2f})" for s, o, _ in cat.similar(l["id"], 8)) + "\n")
    for lvl in range(4):
        rs = [r for r in l["resources"] if r["level"] == lvl]
        if not rs and not l.get("level_notes", {}).get(str(lvl)):
            continue
        w(f"\n## Level {lvl} — {LEVEL_NAMES[lvl]} ({len(rs)})\n\n")
        if l.get("level_notes", {}).get(str(lvl)):
            w(f"> {l['level_notes'][str(lvl)]}\n\n")
        emit_resources(rs, "md", owner=False)
    mentions = [r for r in cat.resources if r["_general"] and l["id"] in r.get("languages", [])]
    if mentions:
        w(f"\n## Cross-language material that covers {l['name']} ({len(mentions)})\n")
        emit_resources(sorted(mentions, key=lambda r: r["_owner"]), "md")


def cmd_sqlite(cat, a):
    import sqlite3
    from pathlib import Path
    path = Path(a.path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    db = sqlite3.connect(path)
    db.executescript("""
      create table languages(id text primary key, name text, first_appeared int, status text, summary text, homepage text, resource_count int);
      create table language_tags(language text, facet text, value text);          -- facet: category|paradigm|typing|designer|defined_by|alias|standard|extension
      create table language_links(source text, target text, relation text);       -- relation: influenced-by or a related[].relation
      create table concepts(id text primary key, name text, category text, description text);
      create table resources(id text primary key, owner text, owner_type text, level int, kind text, title text, url text, site text, scope text,
                             authority text, year int, version text, format text, access text, implementation text, authors text, notes text, link_status text);
      create table resource_concepts(resource text, concept text);
      create table resource_languages(resource text, language text);              -- cross-language resources -> languages they cover
      create index ix_tags on language_tags(facet, value); create index ix_links_s on language_links(source); create index ix_links_t on language_links(target);
      create index ix_res_owner on resources(owner); create index ix_res_site on resources(site); create index ix_rc_c on resource_concepts(concept);
      create index ix_rc_r on resource_concepts(resource); create index ix_rl_l on resource_languages(language);
      create view concept_links as select rc.concept, r.* from resource_concepts rc join resources r on r.id = rc.resource;
    """)
    facets = [("category", "categories"), ("paradigm", "paradigms"), ("typing", "typing"), ("designer", "designers"), ("defined_by", "defined_by"),
              ("alias", "aliases"), ("standard", "standards"), ("extension", "file_extensions")]
    for l in cat.languages:
        db.execute("insert into languages values(?,?,?,?,?,?,?)", (l["id"], l["name"], l.get("first_appeared"), l.get("status"), l["summary"], l.get("homepage"), len(l["resources"])))
        db.executemany("insert into language_tags values(?,?,?)", [(l["id"], f, v) for f, k in facets for v in l.get(k, [])])
        db.executemany("insert into language_links values(?,?,?)", [(l["id"], x, "influenced-by") for x in l.get("influenced_by", [])] +
                       [(l["id"], r["id"], r["relation"]) for r in l.get("related", [])])
    db.executemany("insert into concepts values(?,?,?,?)", [(c["id"], c["name"], c["category"], c.get("description")) for c in cat.concepts])
    for r in cat.resources:
        db.execute("insert into resources values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (r["id"], r["_owner"], "general" if r["_general"] else "language", r["level"], r["kind"], r["title"], r["url"], r["_domain"], r.get("scope"),
                    r.get("authority"), r.get("year"), r.get("version"), r.get("format"), r.get("access"), r.get("implementation"),
                    "; ".join(r.get("authors", [])) or None, r.get("notes"), r.get("link_check", {}).get("status")))
        db.executemany("insert into resource_concepts values(?,?)", [(r["id"], c) for c in r.get("concepts", [])])
        db.executemany("insert into resource_languages values(?,?)", [(r["id"], x) for x in r.get("languages", [])])
    try:
        db.execute("create virtual table resources_fts using fts5(id unindexed, title, url, authors, notes, tokenize='porter unicode61')")
        db.execute("insert into resources_fts select id, title, url, authors, notes from resources")
        fts = " and full-text table resources_fts"
    except sqlite3.OperationalError:
        fts = " (this SQLite has no FTS5; full-text table skipped)"
    db.commit()
    db.close()
    print(f"wrote {path} ({path.stat().st_size / 1e6:.1f} MB): languages, language_tags, language_links, concepts, resources, resource_concepts, resource_languages{fts}")
    print(f"""try:  sqlite3 {path} "select owner, level, title, url from concept_links where concept='tail-calls' and level=1 limit 10" """)


def cmd_serve(cat, a):
    import functools
    import http.server
    import build_explorer
    build_explorer.build(cat)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT / "explorer"))
    with http.server.ThreadingHTTPServer(("127.0.0.1", a.port), handler) as srv:
        print(f"explorer at http://127.0.0.1:{a.port}/  (Ctrl-C to stop)")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass


# ---- argument parsing --------------------------------------------------------------------------------

def main(argv=None):
    p = argparse.ArgumentParser(prog="q.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True, metavar="command")

    def cmd(name, fn, help, resource_filters=False, **kw):
        s = sub.add_parser(name, help=help, description=help, **kw)
        s.set_defaults(fn=fn)
        s.add_argument("--format", "-f", choices=FORMATS, default="text")
        s.add_argument("--limit", "-n", type=int, default=0, help="maximum rows (0 = command default)")
        if resource_filters:
            s.add_argument("--level", "-l", type=int, nargs="+", choices=range(4), help="source levels: 0 code, 1 primary, 2 secondary, 3 tertiary")
            s.add_argument("--kind", "-k", nargs="+", help="resource kinds, e.g. specification tutorial original-paper")
            s.add_argument("--concept", "-c", nargs="+", help="concept ids that must all be tagged")
            s.add_argument("--site", "-s", help="only links on this domain")
        return s

    cmd("stats", cmd_stats, "Counts per level, link status and language category")
    s = cmd("langs", cmd_langs, "List languages filtered by facets")
    s.add_argument("--category", nargs="+"); s.add_argument("--paradigm", nargs="+"); s.add_argument("--typing", nargs="+")
    s.add_argument("--status", nargs="+"); s.add_argument("--defined-by", nargs="+"); s.add_argument("--designer")
    s.add_argument("--from", dest="year_from", type=int); s.add_argument("--to", dest="year_to", type=int)
    s.add_argument("--grep", nargs="+"); s.add_argument("--sort", choices=("name", "year", "links"), default="name")
    s = cmd("lang", cmd_lang, "Profile, connections and links of one language", resource_filters=True)
    s.add_argument("language"); s.add_argument("--grep", nargs="+"); s.add_argument("--all", action="store_true", help="list every link")
    s.add_argument("--mentions", action="store_true", help="list cross-language links that cover this language instead")
    s = cmd("concepts", cmd_concepts, "List the concept taxonomy with coverage counts")
    s.add_argument("--grep", nargs="+"); s.add_argument("--category", nargs="+")
    s = cmd("concept", cmd_concept, "Everything tagged with one concept, across languages")
    s.add_argument("concept"); s.add_argument("--level", "-l", type=int, nargs="+", choices=range(4))
    s.add_argument("--langs", nargs="+", help="restrict to these languages"); s.add_argument("--category", nargs="+", help="restrict to language categories")
    s.add_argument("--no-general", action="store_true"); s.add_argument("--general-only", action="store_true")
    s = cmd("compare", cmd_compare, "Concept coverage of several languages side by side")
    s.add_argument("languages", nargs="+"); s.add_argument("--concept", "-c", nargs="+", help="show the links for these concepts")
    s.add_argument("--level", "-l", type=int, nargs="+", choices=range(4)); s.add_argument("--links", action="store_true", help="print the links, not the matrix")
    s.add_argument("--shared", action="store_true", help="only concepts every language covers"); s.add_argument("--diff", action="store_true", help="only concepts some language lacks")
    s = cmd("search", cmd_search, "Full-text search over link titles, URLs, notes, authors", resource_filters=True)
    s.add_argument("terms", nargs="+"); s.add_argument("--lang", nargs="+")
    s = cmd("lineage", cmd_lineage, "Influence tree around one language"); s.add_argument("language"); s.add_argument("--depth", "-d", type=int, default=2)
    s = cmd("path", cmd_path, "Shortest chain of links between two languages"); s.add_argument("a"); s.add_argument("b")
    s = cmd("similar", cmd_similar, "Nearest languages by categories, paradigms, typing, lineage and concept coverage"); s.add_argument("language")
    s = cmd("sites", cmd_sites, "Websites ranked by number of catalogued links"); s.add_argument("--grep", nargs="+")
    s = cmd("site", cmd_site, "All links on one website", resource_filters=True); s.add_argument("domain"); s.add_argument("--lang", nargs="+"); s.add_argument("--grep", nargs="+")
    s = cmd("people", cmd_people, "Designers and authors and what connects them"); s.add_argument("--grep", nargs="+")
    s = cmd("gaps", cmd_gaps, "Where coverage is thin: per language (vs. its peers) or per concept")
    s.add_argument("language", nargs="?"); s.add_argument("--concept", "-c", nargs=1); s.add_argument("--category", nargs="+")
    s.add_argument("--level", "-l", type=int, nargs="+", choices=range(4))
    s = cmd("links", cmd_links, "Links the checker could not verify")
    s.add_argument("--status", nargs="+", choices=("blocked", "error", "dead", "anchor-missing", "repo-only", "ok")); s.add_argument("--lang", nargs="+"); s.add_argument("--site")
    s = cmd("shared", cmd_shared, "Documents filed under several languages"); s.add_argument("--min", type=int, default=3)
    s = cmd("dossier", cmd_dossier, "Markdown research brief for one language"); s.add_argument("language")
    s = cmd("sqlite", cmd_sqlite, "Export the catalog to a SQLite database"); s.add_argument("path", nargs="?", default=str(ROOT / "build" / "catalog.sqlite"))
    s = cmd("serve", cmd_serve, "Build the explorer data and serve it locally"); s.add_argument("--port", type=int, default=8000)

    a = p.parse_args(argv)
    cat = Catalog()
    try:
        a.fn(cat, a)
    except BrokenPipeError:
        pass


if __name__ == "__main__":
    main()
