#!/bin/sh
# Nothing private in the tree or its history.
#
#   scripts/scrub-check.sh            the tree and `git log -p` of every branch
#   scripts/scrub-check.sh --tree     the tree only
#
# Greps for every line of .local/denylist.txt (case-insensitive; # lines are
# comments), and for the app's old name, lower-case and capitalised
# (case-sensitive; built below from two halves so this file never matches
# itself). Prints
# file:line for each hit — never the line itself, since the list holds
# secrets — and exits 1 if there is one, 2 if git itself failed.
#
# Allowed: the author's own public name and site (the LICENSE holder, and the
# essay's address). They are cut out of a line before it is tested, so any
# other term on the same line is still a hit.
#
# Not searched: .local/ and home/ (they are the private side), LICENSE (the
# copyright holder's name is meant to be there), the author and date lines
# of each commit (the same), mantel_api/data/cities.tsv, a public list of
# the world's towns that the photo captions name places from, and
# apps/kiosk/package-lock.json, whose integrity hashes are random letters a
# three-letter term turns up in by chance.
set -eu

REPO=$(cd "$(dirname "$0")/.." && pwd)
cd "$REPO"
LIST="$REPO/.local/denylist.txt"
[ -f "$LIST" ] || { echo "No $LIST — see .local/publish-inventory.md." >&2; exit 2; }

PATTERNS=$(mktemp "${TMPDIR:-/tmp}/scrub.XXXXXX")
trap 'rm -f "$PATTERNS"' EXIT
grep -v '^[[:space:]]*#' "$LIST" | grep -v '^[[:space:]]*$' >"$PATTERNS"

# The app's old name, in its two spellings, as one extended regex.
OLD_HALF=ally
OLD_NAME="(^|[^A-Za-z])([tT]$OLD_HALF)"
EXCLUDE="':!.local' ':!home' ':!LICENSE' ':!services/api/mantel_api/data/cities.tsv' ':!apps/kiosk/package-lock.json'"
HITS=0
ALLOWED="ankit goyal|ankitskgoyal.com"

# Keep a hit only if a term survives with the allowed strings cut out.
# Input lines are file:line:content (the tree) or commit/file/content
# (history, as "kind<TAB>where<TAB>content").
refilter() {
  awk -v list="$PATTERNS" -v old="$OLD_NAME" -v allowed="$ALLOWED" -F '\t' '
    BEGIN {
      while ((getline line < list) > 0) terms[++n] = tolower(line)
      k = split(allowed, allow, "|")
    }
    {
      # Cut every allowed string out, literally and in any case.
      text = $2
      for (j = 1; j <= k; j++) {
        p = index(tolower(text), allow[j])
        while (p > 0) {
          text = substr(text, 1, p - 1) substr(text, p + length(allow[j]))
          p = index(tolower(text), allow[j])
        }
      }
      low = tolower(text)
      hit = 0
      for (i = 1; i <= n; i++) if (index(low, terms[i])) { hit = 1; break }
      if (!hit && text ~ old) hit = 1
      if (hit) print $1
    }'
}

# git grep exits 1 when it finds nothing, which is the answer hoped for; 2
# or more means git itself failed (not a repository, a broken worktree
# pointer), and a check that cannot look must never say "clean".
OUT=$(mktemp "${TMPDIR:-/tmp}/scrub.XXXXXX")
ERR=$(mktemp "${TMPDIR:-/tmp}/scrub.XXXXXX")
trap 'rm -f "$PATTERNS" "$OUT" "$ERR"' EXIT
git_or_die() {
  STATUS=0
  eval "$1" >>"$OUT" 2>"$ERR" || STATUS=$?
  if [ "$STATUS" -ge 2 ]; then
    echo "scrub-check: git failed (exit $STATUS) — nothing was checked:" >&2
    cat "$ERR" >&2
    exit 2
  fi
}

echo "The tree:"
: >"$OUT"
git_or_die "git grep -n -I -i -F --untracked -f \"$PATTERNS\" -- . $EXCLUDE"
git_or_die "git grep -n -I -E --untracked '$OLD_NAME' -- . $EXCLUDE"
TREE=$(awk '{ i = index($0, ":"); j = index(substr($0, i + 1), ":")
             printf "%s\t%s\n", substr($0, 1, i + j - 1), substr($0, i + j + 1) }' "$OUT" |
       refilter | sort -u)
if [ -n "$TREE" ]; then
  echo "$TREE"
  HITS=$((HITS + $(printf '%s\n' "$TREE" | wc -l)))
else
  echo "  clean"
fi

if [ "${1:-}" != "--tree" ]; then
  echo "History (git log -p --all, messages and diffs):"
  : >"$OUT"
  git_or_die "git log -p --all --format='@@commit %h%n%B' -- . $EXCLUDE"
  HISTORY=$(awk -v list="$PATTERNS" -v old="$OLD_NAME" '
      BEGIN { while ((getline line < list) > 0) terms[++n] = tolower(line) }
      /^@@commit / { commit = $2; file = "(message)"; next }
      /^\+\+\+ b\// { file = substr($0, 7); next }
      /^(\+\+\+|---) / { next }
      {
        hit = 0
        low = tolower($0)
        for (i = 1; i <= n; i++) if (index(low, terms[i])) { hit = 1; break }
        if (!hit && $0 ~ old) hit = 1
        if (hit) printf "%s %s\t%s\n", commit, file, $0
      }' "$OUT" | refilter | sort -u)
  if [ -n "$HISTORY" ]; then
    echo "$HISTORY" | head -40
    COUNT=$(printf '%s\n' "$HISTORY" | wc -l | tr -d ' ')
    [ "$COUNT" -gt 40 ] && echo "  … $COUNT commit:file pairs in all"
    HITS=$((HITS + COUNT))
  else
    echo "  clean"
  fi
fi

if [ "$HITS" -gt 0 ]; then
  echo "scrub-check: $HITS hit(s)." >&2
  exit 1
fi
echo "scrub-check: clean."
