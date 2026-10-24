#!/usr/bin/env bash
# Push documentation-only commits on main to GitHub so aria-agent.dev picks up
# changelog, help and feature-page updates after an internal build.
#
# Pushes ONLY when every commit in origin/main..main touches nothing but the
# allowed documentation paths, the added lines pass a secret/host scan, the
# changelog headings match (AGENTS.md section 11) and the push is a plain
# fast-forward of main. Otherwise it prints why and exits non-zero without
# pushing. Never forces, never pushes tags or other branches.
#
#   scripts/release/push_docs.sh            # check and push
#   scripts/release/push_docs.sh --dry-run  # check only
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

ALLOWED_RE='^(CHANGELOG\.de\.md|CHANGELOG\.md|docs/help/.+|docs/wiki/.+|docs/website/.+|docs/assets/screenshots/(features|themes)/.+)$'

fail() { echo "push_docs: NOT pushed - $*" >&2; exit 1; }

cd "$REPO"
[[ "$(git rev-parse --abbrev-ref HEAD)" == "main" ]] || fail "current branch is not main"

git fetch --quiet origin main || fail "git fetch origin main failed"
git merge-base --is-ancestor origin/main main || fail "main is not a fast-forward of origin/main (diverged) - owner must resolve"

commits="$(git rev-list --reverse origin/main..main)"
[[ -n "$commits" ]] || { echo "push_docs: nothing to push (main == origin/main)"; exit 0; }

# 1) Every commit may only touch allowed documentation paths.
bad=""
for c in $commits; do
  while IFS= read -r path; do
    [[ -z "$path" ]] && continue
    [[ "$path" =~ $ALLOWED_RE ]] || bad+="  $(git log -1 --format=%h "$c") $path"$'\n'
  done < <(git diff-tree --no-commit-id --name-only -r "$c")
done
[[ -z "$bad" ]] || fail $'commits touch files outside the documentation allowlist:\n'"$bad"

# 2) Secret / internal-host scan on the added text lines of the whole range.
added="$(git diff origin/main..main --unified=0 --no-color -- . ':(exclude)docs/assets/screenshots' | grep -E '^\+' | grep -vE '^\+\+\+' || true)"
hits="$(printf '%s\n' "$added" | grep -nE \
  -e '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' \
  -e '(sk-[A-Za-z0-9_-]{20,}|gh[opsu]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16})' \
  -e '\b(10|172\.(1[6-9]|2[0-9]|3[01])|192\.168)\.[0-9]{1,3}\.[0-9]{1,3}' \
  -e '\b[a-z0-9.-]+\.(lan|black)\b' \
  -e '/(home|Users)/[a-z]' \
  -e '(password|passwd|api[_-]?key|secret)[[:space:]]*[:=][[:space:]]*[^[:space:]`]{6,}' || true)"
[[ -z "$hits" ]] || fail $'secret/internal-host scan found matches in added lines:\n'"$hits"

# 3) Changelog headings must match (AGENTS.md section 11).
de="$(grep -oE '^## 0\.1\.0-alpha[0-9]+ - [0-9-]+ \[(public|intern)\]' CHANGELOG.de.md)"
en="$(grep -oE '^## 0\.1\.0-alpha[0-9]+ - [0-9-]+ \[(public|intern)\]' CHANGELOG.md | head -n "$(grep -cE '^## 0\.1\.0-alpha' CHANGELOG.de.md)")"
[[ "$de" == "$en" ]] || fail "CHANGELOG.de.md and CHANGELOG.md headings differ (run the section 11 check)"
[[ "$(git show main:CHANGELOG.de.md | grep -c '^### Sicherheit')" == "$(git show main:CHANGELOG.md | grep -c '^### Security')" ]] \
  || fail "### Sicherheit / ### Security counts differ"

echo "push_docs: $(echo "$commits" | wc -l) commit(s) pass the checks:"
git log --oneline origin/main..main
if (( DRY_RUN )); then
  echo "push_docs: dry run - not pushed"
  exit 0
fi
git push origin main:main
echo "push_docs: pushed main to origin"
