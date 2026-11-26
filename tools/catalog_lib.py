"""Read-side model of catalog.json: lookups, filters and the connection analyses.

Everything the query CLI (q.py), the SQLite export and the explorer data build need lives here,
so the three stay consistent. Nothing in this module writes to data/ or catalog.json.
"""
import collections
import heapq
import json
import math
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "catalog.json"

LEVEL_NAMES = {0: "Source code", 1: "Primary", 2: "Secondary", 3: "Tertiary"}
# Relations where the edge reads naturally in both directions get an inverse label for the target's page.
INVERSE_RELATION = {
    "dialect-of": "has dialect", "superset-of": "subset-of", "subset-of": "superset-of",
    "successor-of": "succeeded by", "compiles-to": "compile target of", "implemented-in": "implements",
    "embeds": "embedded in", "host-of": "hosted by", "variant-of": "has variant",
    "formalizes": "formalized by", "family": "family",
}


def domain_of(url):
    """Host of a URL without a leading www. (the unit the 'sites' views group by)."""
    host = urlsplit(url).netloc.lower().split("@")[-1].split(":")[0]
    return host[4:] if host.startswith("www.") else host


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def norm(s):
    return re.sub(r"[^a-z0-9+#]+", " ", s.lower()).strip()


class Catalog:
    def __init__(self, path=CATALOG):
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        self.meta = raw["meta"]
        self.concept_categories = raw["concept_categories"]
        self.concepts = raw["concepts"]
        self.languages = raw["languages"]
        self.general = raw["general"]
        self.lang = {l["id"]: l for l in self.languages}
        self.concept = {c["id"]: c for c in self.concepts}

        # Flat resource list; every resource knows its owner.
        self.resources = []
        for l in self.languages:
            for r in l["resources"]:
                r["_owner"], r["_general"] = l["id"], False
                self.resources.append(r)
        for g in self.general:
            for r in g["resources"]:
                r["_owner"], r["_general"] = g["id"], True
                self.resources.append(r)
        for r in self.resources:
            r["_domain"] = domain_of(r["url"])

        self._build_graph()

    # ---- lookups -------------------------------------------------------------------------------

    def find_language(self, query):
        """Resolve an id, exact name or alias (case-insensitive) to a language; None when ambiguous or unknown."""
        if query in self.lang:
            return self.lang[query]
        q = norm(query)
        hits = [l for l in self.languages if q == norm(l["name"]) or q in (norm(a) for a in l.get("aliases", []))]
        if len(hits) == 1:
            return hits[0]
        hits = hits or [l for l in self.languages if slug(query) == l["id"]]
        return hits[0] if len(hits) == 1 else None

    def suggest_languages(self, query, limit=8):
        q = norm(query)
        scored = []
        for l in self.languages:
            names = [l["id"], norm(l["name"])] + [norm(a) for a in l.get("aliases", [])]
            best = min((0 if n == q else 1 if n.startswith(q) else 2 if q in n else 9) for n in names)
            if best < 9:
                scored.append((best, len(l["id"]), l["id"]))
        return [i for _, _, i in sorted(scored)[:limit]]

    def find_concept(self, query):
        if query in self.concept:
            return self.concept[query]
        q = norm(query)
        hits = [c for c in self.concepts if q == norm(c["name"]) or q in (norm(a) for a in c.get("aliases", []))]
        if len(hits) == 1:
            return hits[0]
        hits = [c for c in self.concepts if q in norm(c["id"]) or q in norm(c["name"]) or any(q in norm(a) for a in c.get("aliases", []))]
        return hits[0] if len(hits) == 1 else None

    def suggest_concepts(self, query, limit=8):
        q = norm(query)
        return [c["id"] for c in self.concepts
                if q in norm(c["id"]) or q in norm(c["name"]) or any(q in norm(a) for a in c.get("aliases", []))][:limit]

    # ---- resource filtering ----------------------------------------------------------------------

    def filter_resources(self, resources=None, levels=None, kinds=None, concepts=None, domain=None, text=None,
                         status=None, access=None, owners=None, general=None):
        """AND-combine the given filters. `text` is whitespace-separated terms that must all occur in title/url/notes."""
        terms = norm(text).split() if text else []
        out = []
        for r in self.resources if resources is None else resources:
            if levels is not None and r["level"] not in levels:
                continue
            if kinds and r["kind"] not in kinds:
                continue
            if concepts and not set(concepts) <= set(r.get("concepts", [])):
                continue
            if domain and r["_domain"] != domain and not r["_domain"].endswith("." + domain):
                continue
            if status and r.get("link_check", {}).get("status") not in status:
                continue
            if access and r.get("access") not in access:
                continue
            if owners is not None and r["_owner"] not in owners and not (r["_general"] and set(r.get("languages", [])) & set(owners)):
                continue
            if general is not None and r["_general"] != general:
                continue
            if terms:
                hay = norm(" ".join([r["title"], r["url"], r.get("notes", ""), r.get("implementation", ""), " ".join(r.get("authors", []))]))
                if not all(t in hay for t in terms):
                    continue
            out.append(r)
        return out

    def filter_languages(self, categories=None, paradigms=None, typing=None, status=None, defined_by=None,
                         year_from=None, year_to=None, designer=None, text=None):
        terms = norm(text).split() if text else []
        out = []
        for l in self.languages:
            if categories and not set(categories) <= set(l["categories"]):
                continue
            if paradigms and not set(paradigms) <= set(l.get("paradigms", [])):
                continue
            if typing and not set(typing) <= set(l.get("typing", [])):
                continue
            if status and l.get("status") not in status:
                continue
            if defined_by and not set(defined_by) & set(l.get("defined_by", [])):
                continue
            y = l.get("first_appeared")
            if year_from is not None and (y is None or y < year_from):
                continue
            if year_to is not None and (y is None or y > year_to):
                continue
            if designer and not any(norm(designer) in norm(d) for d in l.get("designers", [])):
                continue
            if terms:
                hay = norm(" ".join([l["id"], l["name"], l["summary"], " ".join(l.get("aliases", [])), " ".join(l.get("designers", []))]))
                if not all(t in hay for t in terms):
                    continue
            out.append(l)
        return out

    # ---- lineage graph ---------------------------------------------------------------------------

    def _build_graph(self):
        self.influences = collections.defaultdict(list)      # id -> ids it was influenced by
        self.influenced = collections.defaultdict(list)      # id -> ids it influenced
        self.relations = collections.defaultdict(list)       # id -> [(other, label, direction)] in both directions
        self.neighbours = collections.defaultdict(set)       # undirected, for path finding
        for l in self.languages:
            for x in dict.fromkeys(l.get("influenced_by", [])):
                if x == l["id"]:
                    continue
                self.influences[l["id"]].append(x)
                self.influenced[x].append(l["id"])
                self.neighbours[l["id"]].add(x)
                self.neighbours[x].add(l["id"])
            for rel in l.get("related", []):
                x, kind = rel["id"], rel["relation"]
                if x == l["id"]:
                    continue
                self.relations[l["id"]].append((x, kind, "out"))
                self.relations[x].append((l["id"], INVERSE_RELATION[kind], "in"))
                self.neighbours[l["id"]].add(x)
                self.neighbours[x].add(l["id"])

    def name(self, lang_id):
        return self.lang[lang_id]["name"] if lang_id in self.lang else lang_id

    def year(self, lang_id):
        return self.lang.get(lang_id, {}).get("first_appeared")

    def walk(self, start, direction, depth):
        """Breadth-first ancestors ('up') or descendants ('down'): {id: (distance, parent)}."""
        edges = self.influences if direction == "up" else self.influenced
        seen, frontier = {start: (0, None)}, [start]
        for d in range(1, depth + 1):
            nxt = []
            for a in frontier:
                for b in edges.get(a, []):
                    if b not in seen:
                        seen[b] = (d, a)
                        nxt.append(b)
            frontier = nxt
        del seen[start]
        return seen

    def path(self, a, b):
        """Shortest chain of influence/relation links between two languages (undirected), or None."""
        prev, frontier = {a: None}, collections.deque([a])
        while frontier:
            x = frontier.popleft()
            if x == b:
                out = []
                while x is not None:
                    out.append(x)
                    x = prev[x]
                return out[::-1]
            for y in sorted(self.neighbours.get(x, ())):
                if y not in prev:
                    prev[y] = x
                    frontier.append(y)
        return None

    def link_label(self, a, b):
        """How a relates to b on one hop of a path."""
        if b in self.influences.get(a, []):
            return "influenced by"
        if a in self.influences.get(b, []):
            return "influenced"
        for other, label, _ in self.relations.get(a, []):
            if other == b:
                return label
        return "linked to"

    # ---- similarity ------------------------------------------------------------------------------

    def _features(self):
        if hasattr(self, "_feat"):
            return self._feat
        feat = {}
        for l in self.languages:
            concepts = {c for r in l["resources"] for c in r.get("concepts", [])}
            lineage = set(self.influences.get(l["id"], [])) | {l["id"]}
            feat[l["id"]] = {
                "category": set(l["categories"]) - {"historical"},
                "paradigm": set(l.get("paradigms", [])),
                "typing": set(l.get("typing", [])),
                "lineage": lineage,
                "concept": concepts,
            }
        idf = {}
        n = len(self.languages)
        for group in ("category", "paradigm", "typing", "lineage", "concept"):
            df = collections.Counter(x for f in feat.values() for x in f[group])
            idf[group] = {x: math.log(1 + n / c) for x, c in df.items()}
        self._feat, self._idf = feat, idf
        # Total IDF weight of every feature set, so a union's weight is wa + wb - intersection.
        self._weight = {i: {g: sum(idf[g][x] for x in f[g]) for g in idf} for i, f in feat.items()}
        return feat

    WEIGHTS = {"category": 0.30, "paradigm": 0.20, "typing": 0.12, "lineage": 0.18, "concept": 0.20}

    def similarity(self, a, b):
        """0..1 blend of IDF-weighted Jaccard overlaps; returns (score, {group: [shared values, rarest first]})."""
        feat = self._features()
        fa, fb = feat[a], feat[b]
        score, shared = 0.0, {}
        for group, w in self.WEIGHTS.items():
            idf = self._idf[group]
            inter = fa[group] & fb[group]
            if not inter:
                continue
            wi = sum(idf[x] for x in inter)
            score += w * wi / (self._weight[a][group] + self._weight[b][group] - wi)
            if inter and group != "concept":
                shared[group] = sorted(inter, key=lambda x: -idf.get(x, 0))
        return score, shared

    def similar(self, lang_id, limit=10):
        scored = []
        for other in self.lang:
            if other != lang_id:
                s, shared = self.similarity(lang_id, other)
                if s > 0:
                    scored.append((s, other, shared))
        return heapq.nlargest(limit, scored, key=lambda t: (t[0], t[1]))

    # ---- concepts --------------------------------------------------------------------------------

    def concept_resources(self, concept_id, levels=None, languages=None, categories=None):
        """({language id: [resources]}, [cross-language resources]) for one concept."""
        by_lang, general = collections.defaultdict(list), []
        for r in self.resources:
            if concept_id not in r.get("concepts", []) or (levels is not None and r["level"] not in levels):
                continue
            if r["_general"]:
                if not languages or set(languages) & set(r.get("languages", [])) or not r.get("languages"):
                    general.append(r)
                continue
            if languages and r["_owner"] not in languages:
                continue
            if categories and not set(categories) & set(self.lang[r["_owner"]]["categories"]):
                continue
            by_lang[r["_owner"]].append(r)
        return dict(sorted(by_lang.items())), general

    def related_concepts(self, limit=8):
        """{concept: [(other, shared resource count, lift)]} — concepts that are tagged on the same links."""
        if hasattr(self, "_related"):
            return self._related
        count, pair = collections.Counter(), collections.Counter()
        for r in self.resources:
            cs = sorted(set(r.get("concepts", [])))
            count.update(cs)
            for i, a in enumerate(cs):
                for b in cs[i + 1:]:
                    pair[a, b] += 1
        total = sum(1 for r in self.resources if r.get("concepts"))
        rel = collections.defaultdict(list)
        for (a, b), n in pair.items():
            if n < 3:
                continue
            lift = n * total / (count[a] * count[b])
            rel[a].append((b, n, lift))
            rel[b].append((a, n, lift))
        self._related = {c: sorted(v, key=lambda t: -t[1] * math.log(1 + t[2]))[:limit] for c, v in rel.items()}
        return self._related

    def coverage(self, lang_id):
        """{concept: set(levels)} for one language (its own resources only)."""
        cov = collections.defaultdict(set)
        for r in self.lang[lang_id]["resources"]:
            for c in r.get("concepts", []):
                cov[c].add(r["level"])
        return cov

    # ---- sites, people, shared documents ---------------------------------------------------------

    def sites(self):
        """[{domain, resources, languages, levels{0..3}}] sorted by resource count."""
        agg = {}
        for r in self.resources:
            a = agg.setdefault(r["_domain"], {"domain": r["_domain"], "resources": 0, "languages": set(), "levels": collections.Counter()})
            a["resources"] += 1
            a["levels"][r["level"]] += 1
            if not r["_general"]:
                a["languages"].add(r["_owner"])
        return sorted(agg.values(), key=lambda a: (-a["resources"], a["domain"]))

    def people(self):
        """{name: {designed: [language ids], authored: [resources]}} merged over designers and resource authors."""
        out = {}
        for l in self.languages:
            for d in l.get("designers", []):
                out.setdefault(d, {"designed": [], "authored": []})["designed"].append(l["id"])
        for r in self.resources:
            for a in r.get("authors", []):
                out.setdefault(a, {"designed": [], "authored": []})["authored"].append(r)
        return out

    def shared_documents(self, min_languages=2):
        """[(base url, [language ids], title)] — the same document (ignoring #fragment) filed under several languages."""
        docs = collections.defaultdict(lambda: (set(), []))
        for r in self.resources:
            if not r["_general"]:
                langs, titles = docs[r["url"].split("#")[0]]
                langs.add(r["_owner"])
                titles.append(r["title"])
        out = [(u, sorted(l), t[0]) for u, (l, t) in docs.items() if len(l) >= min_languages]
        return sorted(out, key=lambda t: (-len(t[1]), t[0]))
