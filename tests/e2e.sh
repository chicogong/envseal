#!/usr/bin/env bash
# End-to-end test for envseal: exercises every command against real sops / age /
# git in a fully isolated sandbox (its own $HOME, throwaway repos / keys / vault).
#
# Requires: python3, sops, age, git.
# Run from anywhere:  bash tests/e2e.sh
#
# This is NOT a pytest file (pytest only collects test_*.py); run it directly.
set -u

REPO="$(cd "$(dirname "$0")/.." && pwd)"
S="$(mktemp -d "${TMPDIR:-/tmp}/envseal-e2e-XXXXXX")"
export HOME="$S/home"
mkdir -p "$HOME"
PASS=0
FAIL=0

chk() {
  local desc="$1"
  shift
  if "$@"; then
    echo "  PASS  $desc"
    PASS=$((PASS + 1))
  else
    echo "  FAIL  $desc"
    FAIL=$((FAIL + 1))
  fi
}
absent() { ! "$@"; }
EV() { (cd "$REPO" && python3 -m envseal.cli "$@"); }

if [ "$(uname)" = "Darwin" ]; then
  KEYFILE="$HOME/Library/Application Support/sops/age/keys.txt"
  perms() { stat -f '%Lp' "$1"; }
else
  KEYFILE="$HOME/.config/sops/age/keys.txt"
  perms() { stat -c '%a' "$1"; }
fi

echo "sandbox: $S"

# --- two project repos with varied env files ---
for r in repo-a repo-b; do
  mkdir -p "$S/projects/$r"
  (cd "$S/projects/$r" && git init -q && git config user.email t@e.com && git config user.name T)
done
printf 'API_KEY=a-local\nDB_URL=postgres://localhost/a\n' >"$S/projects/repo-a/.env"
printf 'API_KEY=a-prod\nDB_URL=postgres://prod/a\nDEBUG=0\n' >"$S/projects/repo-a/.env.prod"
printf 'API_KEY=b-dev\nDB_URL=postgres://localhost/b\n' >"$S/projects/repo-b/.env.dev"
printf 'API_KEY=b-prod\nDB_URL=postgres://prod/b\n' >"$S/projects/repo-b/.env.prod"

# --- vault: a git repo cloned from a bare remote ---
git init -q --bare "$S/remote.git"
git clone -q "$S/remote.git" "$S/vault" 2>/dev/null
(cd "$S/vault" && git config user.email t@e.com && git config user.name T)

CFG="$HOME/.config/envseal/config.yaml"

echo
echo "############ [1] init — generate key, scan repos, write config ############"
printf '%s\n' "$S/vault" | EV init --root "$S/projects"
chk "age key generated" test -f "$KEYFILE"
chk "config.yaml written" test -f "$CFG"
chk ".sops.yaml created" test -f "$S/vault/.sops.yaml"
chk "config has repo-a" grep -q repo-a "$CFG"
chk "config has repo-b" grep -q repo-b "$CFG"

echo
echo "############ [2] status before push — all should be 'new' ############"
EV status

echo
echo "############ [3] push --commit — encrypt all + auto-commit ############"
EV push --commit
chk "vault repo-a/local.env" test -f "$S/vault/secrets/repo-a/local.env"
chk "vault repo-a/prod.env" test -f "$S/vault/secrets/repo-a/prod.env"
chk "vault repo-b/dev.env" test -f "$S/vault/secrets/repo-b/dev.env"
chk "vault repo-b/prod.env" test -f "$S/vault/secrets/repo-b/prod.env"
chk "file is SOPS-encrypted" grep -q sops "$S/vault/secrets/repo-a/prod.env"
chk "plaintext value hidden" absent grep -q 'postgres://prod/a' "$S/vault/secrets/repo-a/prod.env"
chk "vault commit created" test -n "$(git -C "$S/vault" log --oneline)"

echo
echo "############ [4] status after push — all up to date ############"
EV status

echo
echo "############ [5] push again, no change — must SKIP ############"
cp "$S/vault/secrets/repo-a/prod.env" "$S/snap-before"
EV push >"$S/o5" 2>&1
cat "$S/o5"
chk "reports 'no changes'" grep -qi "no changes" "$S/o5"
chk "vault file untouched" cmp -s "$S/snap-before" "$S/vault/secrets/repo-a/prod.env"

echo
echo "############ [6] modify repo-a prod -> status + diff ############"
printf 'API_KEY=a-prod-NEW\nDB_URL=postgres://prod/a\nDEBUG=1\nNEW_KEY=x\n' >"$S/projects/repo-a/.env.prod"
EV status
EV diff repo-a --env prod >"$S/o6" 2>&1
cat "$S/o6"
chk "diff shows added NEW_KEY" grep -q NEW_KEY "$S/o6"
chk "diff shows MODIFIED" grep -qi modified "$S/o6"
chk "diff hides values" absent grep -q 'a-prod-NEW' "$S/o6"

echo
echo "############ [7] pull --stdout — decrypt to stdout ############"
EV pull repo-a --env prod --stdout >"$S/o7" 2>&1
cat "$S/o7"
chk "stdout decrypt has keys" grep -q API_KEY "$S/o7"

echo
echo "############ [8] pull default — temp file, honest message, 0600 ############"
EV pull repo-b --env prod >"$S/o8" 2>&1
cat "$S/o8"
chk "honest 'NOT auto-deleted' message" grep -q "NOT auto-deleted" "$S/o8"
PF="$(grep -oE '/[^ ]+prod\.env' "$S/o8" | head -1)"
if [ -n "${PF:-}" ] && [ -f "$PF" ]; then
  chk "temp file perms = 600" test "$(perms "$PF")" = "600"
  rm -rf "$(dirname "$PF")"
else
  chk "temp file located" false
fi

echo
echo "############ [9] pull --replace — overwrite local + .backup ############"
EV pull repo-b --env prod --replace
chk "backup file created" test -f "$S/projects/repo-b/.env.prod.backup"
chk "local .env.prod restored" grep -q API_KEY "$S/projects/repo-b/.env.prod"

echo
echo "############ [10] update --commit — collect changes, encrypt, commit ############"
EV update --commit >"$S/o10" 2>&1
cat "$S/o10"
chk "update picked up repo-a" grep -q repo-a "$S/o10"
EV diff repo-a --env prod >"$S/o10b" 2>&1
chk "repo-a/prod now in sync" grep -qi "no changes" "$S/o10b"

echo
echo "############ [11] push --push — commit + push to remote ############"
DEF="$(git -C "$S/vault" branch --show-current)"
git -C "$S/vault" push -u origin "$DEF" -q 2>/dev/null
printf 'API_KEY=a-local-v2\nDB_URL=postgres://localhost/a\n' >"$S/projects/repo-a/.env"
EV push --push >"$S/o11" 2>&1
cat "$S/o11"
chk "reports pushed to remote" grep -q "Pushed vault to remote" "$S/o11"
chk "remote received commits" test "$(git -C "$S/remote.git" rev-list --count HEAD)" -ge 1
chk "backup NOT ingested" absent test -f "$S/vault/secrets/repo-b/prod.backup.env"

echo
echo "############ [12] encrypt/decrypt round-trip integrity ############"
EV pull repo-a --env local --stdout >"$S/o12" 2>&1
chk "value round-trips intact" grep -q 'a-local-v2' "$S/o12"

echo
echo "############ [13] list / report — key-only overview ############"
EV list >"$S/o13" 2>&1
cat "$S/o13"
chk "list shows a repo" grep -q repo-a "$S/o13"
chk "list shows a key name" grep -q API_KEY "$S/o13"
chk "list hides values" absent grep -q 'a-local-v2' "$S/o13"
EV report --output "$S/report.html" >"$S/o13b" 2>&1
chk "report.html created" test -f "$S/report.html"
chk "report shows project/key counts" grep -q 'projects' "$S/report.html"
chk "report has a key name" grep -q API_KEY "$S/report.html"
chk "report hides values" absent grep -q 'a-local-v2' "$S/report.html"

echo
echo "=================================================================="
echo "   RESULT:  $PASS passed,  $FAIL failed"
echo "=================================================================="
rm -rf "$S"
[ "$FAIL" -eq 0 ]
