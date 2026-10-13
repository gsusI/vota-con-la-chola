#!/usr/bin/env bash
# Print a fingerprint of everything a frozen site publish ships: the site app and the Worker,
# committed or not (tracked diffs and untracked files included), so a clean rebuild of the same
# inputs can be recognized and skipped.
set -euo pipefail
paths=(ui/site infra/cloudflare/votaconlachola-worker)
untracked="$(git ls-files --others --exclude-standard -- "${paths[@]}")"
{
  git rev-parse "${paths[@]/#/HEAD:}"
  git diff HEAD --binary -- "${paths[@]}"
  printf '%s\n' "$untracked"
  if [ -n "$untracked" ]; then printf '%s\n' "$untracked" | git hash-object --stdin-paths; fi
} | shasum -a 256 | cut -c1-32
