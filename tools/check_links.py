#!/usr/bin/env python3
"""Check that resource URLs resolve (and that #fragments exist in the page).

Usage: tools/check_links.py [--workers N] [--recheck] [--all | files...]

Statuses
  ok              page fetched (and fragment found, when there is one)
  anchor-missing  page fetched but the #fragment id was not found in the HTML (may be JS-rendered)
  repo-only       GitHub non-file link: only the repository's existence could be confirmed
  blocked         server refuses automated clients (401/403/429...) - unverifiable from here, not necessarily wrong
  dead            404/410 or DNS failure - fix or remove
  error           timeout / 5xx / other - retry later

Results are written to build/link-status/<file-stem>.json and reused (ok results only) on later runs.
github.com itself is not reachable from the research sandbox, so GitHub links are verified through
raw.githubusercontent.com (files) and the jsDelivr package API (repository existence).
"""
import json, re, sys, time, threading, datetime
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit, unquote
import requests
from common import *

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
OUT = BUILD / "link-status"
MAX_BYTES = 30_000_000
_host_locks = {}
_host_guard = threading.Lock()
_local = threading.local()


def session():
    if not hasattr(_local, "s"):
        _local.s = requests.Session()
        _local.s.headers.update({"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/pdf,*/*;q=0.8",
                                 "Accept-Language": "en"})
    return _local.s


def host_lock(host):
    with _host_guard:
        return _host_locks.setdefault(host, threading.Semaphore(2))


GH = re.compile(r"^https?://github\.com/([^/]+)/([^/#?]+)(?:/(blob|tree|raw)/(.+?))?(?:/(wiki|issues|pull|pulls|releases|discussions|milestones|projects|commits?|actions|tags)(?:/.*)?)?/?(?:[?#].*)?$")


def plan(url):
    """Return (fetch_url, mode) where mode is 'page', 'raw', 'repo' or 'skip'."""
    m = GH.match(url)
    if m:
        owner, repo, kind, rest, other = m.groups()
        repo = repo.removesuffix(".git")
        if kind in ("blob", "raw") and rest:
            rest = re.sub(r"[?#].*$", "", rest)
            return f"https://raw.githubusercontent.com/{owner}/{repo}/{rest}", "raw"
        return f"https://data.jsdelivr.com/v1/packages/gh/{owner}/{repo}", "repo"
    if re.match(r"^https?://(gist\.)?github\.com/", url):
        return url, "skip"
    return url, "page"


def anchor_present(body, frag):
    if not frag or frag.startswith(":~:") or re.match(r"^(page|L\d|nameddest)", frag):
        return True
    cands = {frag, unquote(frag)}
    for f in cands:
        pat = re.compile(rb"""(?:id|name)\s*=\s*(?:"%s"|'%s'|%s(?=[\s>]))""" % ((re.escape(f.encode()),) * 3))
        if pat.search(body):
            return True
    return False


def fetch(url):
    fetch_url, mode = plan(url)
    if mode == "skip":
        return {"status": "blocked", "http": None, "note": "github page not verifiable"}
    parts = urlsplit(fetch_url)
    frag = urlsplit(url).fragment if mode == "page" else ""
    last = None
    for attempt in range(5):
        try:
            with host_lock(parts.netloc):
                r = session().get(fetch_url.split("#")[0], timeout=(15, 40), stream=True, allow_redirects=True)
                code = r.status_code
                ctype = r.headers.get("content-type", "")
                body = b""
                if code == 200 and frag and "html" in ctype:
                    for chunk in r.iter_content(65536):
                        body += chunk
                        if len(body) > MAX_BYTES:
                            break
                final = r.url
                r.close()
                time.sleep(0.15)
        except requests.exceptions.ConnectionError as e:
            msg = str(e)
            last = {"status": "dead" if ("Name or service" in msg or "NameResolution" in msg) else "error", "http": None, "note": msg[:120]}
            time.sleep(2 * (attempt + 1)); continue
        except Exception as e:
            last = {"status": "error", "http": None, "note": f"{type(e).__name__}: {str(e)[:100]}"}
            time.sleep(2 * (attempt + 1)); continue
        if code in (429, 502, 503, 504) and attempt < 4:
            last = {"status": "error", "http": code}
            time.sleep(5 * (attempt + 1)); continue
        res = {"http": code}
        if final.split("#")[0].rstrip("/") != fetch_url.split("#")[0].rstrip("/") and mode == "page":
            res["redirected_to"] = final
        if code == 200:
            if mode == "repo":
                res["status"] = "ok" if GH.match(url).group(3) is None and GH.match(url).group(5) is None else "repo-only"
            elif frag and "html" in ctype and not anchor_present(body, frag):
                res["status"] = "anchor-missing"
            else:
                res["status"] = "ok"
        elif code in (404, 410):
            res["status"] = "dead"
        elif code in (401, 403, 405, 406, 418, 429, 451, 999):
            res["status"] = "blocked"
        else:
            res["status"] = "error"
        return res
    return last


def main():
    argv = sys.argv[1:]
    workers = 6
    if "--workers" in argv:
        i = argv.index("--workers"); workers = int(argv[i + 1]); del argv[i:i + 2]
    recheck = "--recheck" in argv
    files = [Path(a).resolve() for a in argv if not a.startswith("-")]
    if "--all" in argv or not files:
        files = language_files() + general_files()
    OUT.mkdir(parents=True, exist_ok=True)
    cache = {}
    if not recheck:
        for p in OUT.glob("*.json"):
            try:
                for u, r in load(p).items():
                    if r.get("status") == "ok":
                        cache[u] = r
            except Exception:
                pass
    today = datetime.date.today().isoformat()
    bad_total = 0
    for path in files:
        doc = load(path)
        urls = [r["url"] for r in doc["resources"]]
        todo = [u for u in dict.fromkeys(urls) if u not in cache]
        with ThreadPoolExecutor(workers) as ex:
            for u, res in zip(todo, ex.map(fetch, todo)):
                res["checked"] = today
                cache[u] = res
        result = {u: cache[u] for u in urls}
        (OUT / f"{path.parent.name}--{path.stem}.json").write_text(json.dumps(result, indent=1))
        counts = {}
        for u in urls:
            counts[result[u]["status"]] = counts.get(result[u]["status"], 0) + 1
        print(f"{path.stem}: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
        for u in urls:
            r = result[u]
            if r["status"] not in ("ok", "repo-only"):
                bad_total += 1
                extra = r.get("note") or ""
                print(f"   {r['status']:<14} {r.get('http')}  {u}  {extra}")
    print(f"done; {bad_total} links need attention (dead/anchor-missing must be fixed; blocked/error are tolerated if the URL is known-good)")


if __name__ == "__main__":
    main()
