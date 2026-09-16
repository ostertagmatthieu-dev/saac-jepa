#!/bin/sh
# Fail when a commit in the given range would add an unwanted contributor to
# the GitHub Contributors graph: bot or Claude authors, and co-author,
# sign-off or session trailers naming Claude, Anthropic or a bot account.
#
# Usage: check_attribution.sh <rev-range>   e.g. origin/main..HEAD
set -eu

range="${1:?usage: check_attribution.sh <rev-range>}"

trailer_re='^(co-authored-by|signed-off-by):.*(claude|anthropic|\[bot\])|^claude-session:|generated with \[?claude code'
identity_re='\[bot\]|anthropic\.com|^claude '

status=0
for sha in $(git rev-list "$range"); do
  short=$(git rev-parse --short "$sha")
  subject=$(git log -1 --format=%s "$sha")

  hits=$(git log -1 --format=%B "$sha" | grep -inE "$trailer_re" || true)
  if [ -n "$hits" ]; then
    echo "::error::$short ($subject) carries a forbidden attribution line:"
    echo "$hits" | sed 's/^/    /'
    status=1
  fi

  author=$(git log -1 --format='%an <%ae>' "$sha")
  if echo "$author" | grep -qiE "$identity_re"; then
    echo "::error::$short ($subject) is authored by $author"
    status=1
  fi
done

if [ "$status" -ne 0 ]; then
  cat <<'EOF'

Only the repository owner should appear as a contributor. Reword the
commits above without these lines (git rebase -i, then reword) and push
again. When squash-merging, delete any Co-authored-by line GitHub adds.
EOF
fi
exit "$status"
