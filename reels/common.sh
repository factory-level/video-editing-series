# Shared by reels/launch, reels/pull and reels/deliver. Sourced, not run.
repo=$(dirname "$(readlink -f "$0")")/..
repo=$(cd "$repo" && pwd)
given_root=${CONTENT_ROOT:-}   # a CONTENT_ROOT already in the environment wins over .env
if [ -f "$repo/.env" ]; then set -a; . "$repo/.env"; set +a; fi
[ -z "$given_root" ] || CONTENT_ROOT=$given_root
fail() { echo "$(basename "$0"): $*" >&2; exit 1; }

# The content root: CONTENT_ROOT from the environment or .env, else the CONTENT_ROOT= line in PATH.md.
content_root() {
  root=${CONTENT_ROOT:-}
  if [ -z "$root" ] || [ "$root" = /path/to/content ]; then
    [ -f "$repo/PATH.md" ] && root=$(sed -n 's/^CONTENT_ROOT=//p' "$repo/PATH.md" | head -n 1)
  fi
  [ -n "$root" ] || fail "no content root: set CONTENT_ROOT in .env or PATH.md (see edit/README.md)"
  [ -d "$root" ] || fail "the content root $root does not exist"
  printf '%s\n' "${root%/}"
}

check_slug() {
  case "$1" in [0-9][0-9][0-9][0-9]-?*) ;; *) fail "the reel must be named <nnnn-slug>, for example 0003-launch-reel (got $1)" ;; esac
}

# A Drive folder id from an id or a folder URL.
folder_id() {
  case "$1" in
    *folders/*) printf '%s\n' "$1" | sed -E 's#.*folders/([A-Za-z0-9_-]+).*#\1#' ;;
    *id=*) printf '%s\n' "$1" | sed -E 's#.*[?&]id=([A-Za-z0-9_-]+).*#\1#' ;;
    *) printf '%s\n' "$1" ;;
  esac
}

# gws prints "Using keyring backend" on stderr; keep stdout as clean JSON.
gws_json() { gws "$@" 2>/dev/null; }
