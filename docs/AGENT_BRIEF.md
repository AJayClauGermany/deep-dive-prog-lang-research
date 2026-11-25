# Research batch brief

You are one of several researchers filling a JSON catalog of literature for **comparing computer languages**
(repo root: `/home/user/deep-dive-prog-lang-research`). Others work in parallel on other batches.

1. Read, in full: `docs/AUTHORING.md`, `data/concepts.json`, `schema/language.schema.json`, `schema/resource.schema.json`,
   and the model entry `data/languages/go.json`.
2. Find your batch (the key you were given) in `tools/assignments.json`. For every id in its `languages` map write
   `data/languages/<id>.json` (the value is the display name when the id is not self-explanatory). Ids in `tier_a` get tier-A depth;
   judge tier B vs C for the rest by how much literature really exists.
3. Research with the web (search, fetch, `curl`). The efficient way to get *verified* deep links is to fetch a spec/manual/tutorial's
   table of contents or single-page HTML, list its real headings/ids (`curl -sL URL | grep -o 'id="[^"]*"'`), and map them to concept ids.
   For level 0, read the repo's README/tree via `https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<path>` to confirm real file paths.
   Use what you know to pick candidates, but every URL must survive the checker.
4. After each handful of files run, from `tools/`: `python3 validate.py ../data/languages/<id>.json ...` and
   `python3 check_links.py --workers 2 ../data/languages/<id>.json ...`; fix every `dead` and `anchor-missing`.
5. Work through the whole list: tier A first, then the rest in order. Write each file to disk as soon as it is researched and verified
   (never hold several finished languages in memory) - runs can be interrupted at any moment and only files on disk survive.
   If `data/languages/<id>.json` already exists and validates, an earlier interrupted run wrote it: leave it alone and move to the next id.
   If you truly cannot finish, stop cleanly with every written file valid.

Constraints
* Only create/edit your own `data/languages/<id>.json` files. Never touch `data/concepts.json`, `schema/`, `tools/`, `docs/`,
  `catalog.json` or other batches' files, and do not run git commands. Put helper scripts and scratch files under
  `/tmp/claude-0/-home-user-deep-dive-prog-lang-research/9dc56d96-95ec-5771-925d-1051bd940c56/scratchpad/<your-batch-key>/`, never in the repo.
  (A small generator script that stamps repeated fields is a fine way to write many entries; the JSON files are the deliverable.)
* Do not run `check_links.py --all`; pass your own files.
* If a planned id turns out to be a mistake (not a real language, or indistinguishable from another id), skip it and say so.
* You may add up to five further notable languages from your domain if their ids appear nowhere in `tools/assignments.json`
  and no file exists for them yet.
* Rosetta Code (`https://rosettacode.org/wiki/Category:<Name>`), ACM DL, ISO and doi.org report `blocked` from here; include such links
  only when you are confident they are correct. PLDB (`https://pldb.io/concepts/<id>.html`), Wikipedia, esolangs.org and
  learnxinyminutes.com are checkable.

Final message (plain text, under 200 words): files written, total resources, ids skipped or unfinished and why,
concepts you missed in the taxonomy, and anything a maintainer must know (e.g. links left as `blocked`/`error`).
