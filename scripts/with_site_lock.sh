#!/usr/bin/env bash
# Run a command while holding the site build/publish lock, so two sessions in the same
# checkout never rebuild ui/site/out while another one is uploading it.
# Re-entrant: nested `just site-*` calls from the holder run without waiting.
set -euo pipefail

if [ "${VCLC_SITE_LOCK_HELD:-0}" = "1" ]; then exec "$@"; fi

lock="${VCLC_SITE_LOCK_DIR:-$(git rev-parse --git-common-dir)/vclc-site.lock}"
poll="${VCLC_SITE_LOCK_POLL:-10}"
announced=""
until mkdir "$lock" 2>/dev/null; do
  holder="$(cat "$lock/pid" 2>/dev/null || true)"
  if [ -n "$holder" ] && ! kill -0 "$holder" 2>/dev/null; then
    echo "site lock: removing stale lock of dead pid $holder" >&2
    rm -rf "$lock"
    continue
  fi
  if [ "$announced" != "$holder" ]; then
    echo "site lock: waiting for pid ${holder:-?} ($(cat "$lock/cmd" 2>/dev/null || echo unknown))" >&2
    announced="$holder"
  fi
  sleep "$poll"
done
echo $$ > "$lock/pid"
echo "$*" > "$lock/cmd"
trap 'rm -rf "$lock"' EXIT
export VCLC_SITE_LOCK_HELD=1
"$@"
