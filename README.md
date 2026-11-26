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
docs/AUTHORING.md         conventions for adding entries
```

## Rebuilding

```bash
cd tools && python3 validate.py && python3 check_links.py --all && python3 build.py
```

Requires Python 3 with `jsonschema` and `requests`.
