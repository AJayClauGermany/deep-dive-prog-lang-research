#!/usr/bin/env python3
"""Validate data files. Usage: tools/validate.py [files...]  (default: everything)."""
import sys
from pathlib import Path
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from common import *


def validators():
    res = {n: load(SCHEMA_DIR / n) for n in ("resource.schema.json", "language.schema.json", "general.schema.json")}
    reg = Registry().with_resources([(n, Resource.from_contents(s)) for n, s in res.items()])
    return (Draft202012Validator(res["language.schema.json"], registry=reg),
            Draft202012Validator(res["general.schema.json"], registry=reg))


def check(path, lang_v, gen_v, concepts, strict=True):
    errs, warns = [], []
    try:
        doc = load(path)
    except Exception as e:
        return [f"invalid JSON: {e}"], []
    is_lang = path.parent.name == "languages"
    v = lang_v if is_lang else gen_v
    for e in sorted(v.iter_errors(doc), key=lambda e: list(e.absolute_path)):
        errs.append(f"schema: {'/'.join(map(str, e.absolute_path))}: {e.message[:200]}")
    if errs:
        return errs, warns
    if doc["id"] != path.stem:
        errs.append(f"id '{doc['id']}' does not match file name")
    seen = {}
    levels = set()
    for i, r in enumerate(doc["resources"]):
        where = f"resources[{i}] ({r['title'][:50]})"
        if r["kind"] not in LEVEL_KINDS[r["level"]]:
            errs.append(f"{where}: kind '{r['kind']}' is not a level-{r['level']} kind")
        for c in r.get("concepts", []):
            if c not in concepts:
                errs.append(f"{where}: unknown concept '{c}'")
        if r["url"] in seen:
            errs.append(f"{where}: duplicate url (also resources[{seen[r['url']]}])")
        seen[r["url"]] = i
        if " " in r["url"]:
            errs.append(f"{where}: url contains a space")
        if is_lang and "languages" in r:
            errs.append(f"{where}: 'languages' is only for data/general files")
        if r.get("scope") == "section" and not r.get("concepts"):
            warns.append(f"{where}: section-scoped resource without concepts")
        levels.add(r["level"])
    if is_lang:
        notes = doc.get("level_notes", {})
        for lv in range(4):
            if lv not in levels and str(lv) not in notes:
                warns.append(f"no level-{lv} resources and no level_notes['{lv}'] explaining why")
        if "defined_by" not in doc:
            warns.append("missing defined_by")
        if "status" not in doc:
            warns.append("missing status")
    return errs, warns


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    quiet = "-q" in sys.argv
    files = [Path(a).resolve() for a in args] or language_files() + general_files()
    lang_v, gen_v = validators()
    concepts = concept_ids()
    nerr = nwarn = 0
    for p in files:
        errs, warns = check(p, lang_v, gen_v, concepts)
        nerr += len(errs); nwarn += len(warns)
        for e in errs:
            print(f"ERROR {p.name}: {e}")
        if not quiet:
            for w in warns:
                print(f"warn  {p.name}: {w}")
    print(f"{len(files)} files, {nerr} errors, {nwarn} warnings")
    sys.exit(1 if nerr else 0)


if __name__ == "__main__":
    main()
