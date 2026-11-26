# Computer language literature catalog

A machine-readable catalog of literature for **comparing computer languages**: programming languages, but also
query, configuration, data, markup, schema, shell, hardware-description, intermediate and esoteric languages, and
theoretical models such as the lambda calculus and Turing machines.

Every entry is a link plus metadata, and — where the link is specific enough — the **concepts** it covers
(`conditionals`, `pattern-matching`, `garbage-collection`, `joins`, ...), so that everything about one concept can be
pulled together across languages and source levels.

## The single JSON value

[`catalog.json`](catalog.json) is the whole catalog as one JSON object (generated; do not edit by hand):

| Key | Contents |
|---|---|
| `meta` | Level definitions, counts, link-check legend and summary |
| `concept_categories`, `concepts` | The concept taxonomy (id, name, category, aliases, description) |
| `languages[]` | One object per language: metadata + `resources[]` |
| `general[]` | Cross-language collections (textbooks, comparison tables, catalogs, concept articles, ...) |
| `indexes.by_concept` | `concept id → { general: [...], by_language: { language id: [resources...] } }` |
| `indexes.languages_by_category` | `category → [language ids]` |

### Source levels

| Level | Name | Meaning |
|---|---|---|
| 0 | Source code | Real implementations (compilers, interpreters, runtimes, standard libraries, grammars, conformance suites). Shows how a language *can be implemented*; it does not define the language. |
| 1 | Primary | What defines the language independent of an implementation: standards, specifications, reference manuals, proposals, formal semantics, the designers' defining papers. |
| 2 | Secondary | Explains or analyses the primary sources: tutorials, books, guides, courses, papers, history, comparison guides. |
| 3 | Tertiary | Collections and summaries of the above: encyclopedias, wikis, catalogs, comparison tables, curated lists. |

Each language also records `defined_by` (international standard, vendor specification, reference implementation,
academic paper, ...) and `level_notes`, which say how levels 0 and 1 relate for that language — for example when the
reference implementation *is* the definition, or when a standard is paywalled and a free draft is linked instead.

### Resource fields

`id`, `level`, `kind`, `title`, `url`, `concepts[]`, `scope` (`whole` language or a deep-linked `section`),
`implementation` (level 0), `authority`, `authors`, `year`, `version`, `format`, `access`, `notes`, and `link_check`
(`status`, `http`, `checked`). Full definitions: [`schema/`](schema).

`link_check.status`: `ok` (fetched, and the `#fragment` exists when there is one), `anchor-missing`, `repo-only`
(GitHub directory links: only the repository could be confirmed), `blocked` (site refuses automated clients — not
verified), `dead`, `error`.

### Example queries

```bash
# Everything about if/else, across languages, with level and URL
jq -r '.indexes.by_concept.conditionals.by_language | to_entries[] | .key as $l | .value[] | [$l, .level, .title, .url] | @tsv' catalog.json
```

```bash
# Specification-level (level 1) material on pattern matching only
jq '.indexes.by_concept["pattern-matching"].by_language | map_values(map(select(.level == 1))) | with_entries(select(.value | length > 0))' catalog.json
```

```bash
# Source code (level 0) that implements garbage collectors
jq -r '.languages[] | .id as $l | .resources[] | select(.level == 0 and (.concepts // [] | index("garbage-collection"))) | [$l, .implementation, .url] | @tsv' catalog.json
```

```bash
# All query languages and what defines them
jq -r '.languages[] | select(.categories | index("query")) | [.id, .name, (.defined_by // [] | join(","))] | @tsv' catalog.json
```

## Exploring the catalog

Two tools read `catalog.json` so you do not have to: a command-line query tool for quick answers and exports, and a
browsable explorer where every link is one click away. Both need only the Python 3 standard library.

### `tools/q.py` — ask questions from the terminal

```bash
python3 tools/q.py lang rust                      # profile, lineage, relations, nearest languages, link counts
python3 tools/q.py lang rust -l 1 -c generics     # its level-1 links tagged generics
python3 tools/q.py concept pattern-matching -l 1  # one concept across every language
python3 tools/q.py compare rust go zig            # facts, how they are connected, concept coverage matrix
python3 tools/q.py compare rust go -c closures    # the links for one concept, side by side
python3 tools/q.py search tail call -l 1          # full text over titles, URLs, notes, authors
python3 tools/q.py lineage standard-ml -d 2       # influence tree, both directions
python3 tools/q.py path fortran rust              # shortest chain of influence/family links
python3 tools/q.py similar gleam                  # nearest languages and what they share
python3 tools/q.py sites; python3 tools/q.py site tc39.es   # which websites hold the material
python3 tools/q.py people --grep wirth            # what a designer/author connects
python3 tools/q.py gaps zig                       # concepts its peers document at level 1 but it does not
python3 tools/q.py gaps -c joins --category query # languages still missing a spec-level link for a concept
python3 tools/q.py links --status blocked error   # links the checker could not verify
python3 tools/q.py dossier ocaml > ocaml.md       # Markdown research brief for one language
python3 tools/q.py sqlite                         # build/catalog.sqlite for ad-hoc SQL, with full-text search
```

Every listing takes `--format text|md|json|tsv|urls` and `--limit N`, so results can be piped into a follow-up task
(`--format urls` gives a plain list to fetch; `--format md` a clickable reading list). Language and concept arguments
accept ids, names or aliases; a miss prints the nearest matches. `q.py <command> --help` lists the filters.

### `explorer/` — browse it

```bash
python3 tools/q.py serve        # builds explorer/data.json, then serves http://127.0.0.1:8000/
```

| View | What it answers |
|---|---|
| Languages | Filter the 1,110 languages by kind, status, typing, paradigm, what defines them and year; tick several to compare |
| Language page | Profile, influences in both directions, relations, closest languages, and its links filterable by level, kind, concept and text |
| Concepts | The taxonomy with coverage counts; a concept page lists every language's links for it, plus the cross-language material |
| Compare | Up to six languages: facts, how they are connected, and a concept-by-concept matrix whose rows open to show the links side by side |
| Lineage | Influence graph around one language (click to refocus) and the shortest connection between any two |
| Sites | Which websites hold the material, with per-level counts; a site page lists everything catalogued there |
| People | Designers and authors, and the languages each one links together |
| Saved | Links starred while browsing; copy as Markdown, URLs or JSON to hand to a follow-up research task |

The same page is published to GitHub Pages from `main` by `.github/workflows/explorer.yml`, which rebuilds the data
on every push (repository Settings → Pages → Source must be "GitHub Actions"):
<https://ajayclaugermany.github.io/deep-dive-prog-lang-research/>

Any filtered list can be copied as Markdown. `explorer/data.json` is generated (`tools/build_explorer.py`) and not
committed; `tools/build_explorer.py --page DIR` also writes a single-file build of the page.

### How the connections are computed

* **Lineage** uses `influenced_by` and `related` from the language files, read in both directions. Ids that are
  named but have no catalog entry (see `meta.unresolved_language_references`) are shown as such.
* **Closest languages** is a 0–1 score: rarity-weighted overlap of categories (30%), paradigms (20%), concept
  coverage (20%), direct influences (18%) and typing (12%). It reflects how the catalog describes the languages, so
  treat it as a pointer for what to read next, not as a measurement of the languages themselves.
* **Often tagged together** counts links that carry both concepts.
* **Gaps** compares a language with its 15 closest languages, or lists the languages of a category with no link for
  a concept at the chosen level. A gap means nothing is catalogued, not that the language lacks the feature.

## Repository layout

```
catalog.json              generated single-value catalog (the deliverable)
data/concepts.json        concept taxonomy
data/languages/<id>.json  one source file per language
data/general/<id>.json    cross-language resource collections
data/link-status.json     result of the last link check, per URL
schema/                   JSON Schemas for the source files
tools/validate.py         schema + referential checks
tools/check_links.py      fetches every URL, verifies #fragments
tools/build.py            merges data/ into catalog.json and builds the indexes
tools/catalog_lib.py      read-side model: lookups, filters, lineage, similarity (shared by the tools below)
tools/q.py                command-line queries and exports
tools/build_explorer.py   reshapes catalog.json into explorer/data.json
tools/test_tools.py       smoke tests for the three files above
explorer/                 static browsable explorer (index.html, app.js, style.css)
.github/workflows/        tool smoke tests on pull requests; explorer deploy to GitHub Pages from main
docs/AUTHORING.md         conventions for adding entries
```

## Rebuilding

```bash
cd tools && python3 validate.py && python3 check_links.py --all && python3 build.py && python3 build_explorer.py
```

Requires Python 3 with `jsonschema` and `requests`.
