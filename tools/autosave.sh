#!/usr/bin/env bash
# Periodically commit and push every data file that currently validates (used while long research runs are in flight).
# Usage: tools/autosave.sh [interval-seconds] [iterations]
cd "$(dirname "$0")/.." || exit 1
interval="${1:-300}"; iterations="${2:-20}"
for _ in $(seq "$iterations"); do
  sleep "$interval"
  changed=$(git status --porcelain -- data/languages data/general | awk '{print $2}' | grep '\.json$')
  [ -z "$changed" ] && continue
  ok=()
  for f in $changed; do
    (cd tools && python3 validate.py -q "../$f" >/dev/null 2>&1) && ok+=("$f")
  done
  [ "${#ok[@]}" -eq 0 ] && continue
  git add -- "${ok[@]}"
  git commit -q -m "Add researched catalog entries (${#ok[@]} files)

Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01JwRzLNRREUjAUGA6MHCbkp" || continue
  for attempt in 1 2 3 4; do git push -q origin HEAD && break; sleep $((attempt * 5)); done
done
