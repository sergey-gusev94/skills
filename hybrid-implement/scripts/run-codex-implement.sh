#!/usr/bin/env bash
# Launch Codex non-interactively to implement a task packet for the
# hybrid-implement skill.
# Usage:
#   run-codex-implement.sh <packet-file> [workdir]        new implementation run
#   run-codex-implement.sh resume <session-id> <fix-packet> [workdir]
#                                                  fix round in the same session
# Prints STATUS plus repository-fact lines; Read RESULT_FILE for Codex's report
# and PATCH_FILE for the tracked diff against START_HEAD (untracked files show
# only in the AFTER status snapshot inside the run directory).
# STATUS: ok (codex succeeded, the tree changed, and it self-reported complete)
#         | no-change (codex succeeded but nothing changed — judge the report;
#           an already-satisfied spec and a stalled model look identical here)
#         | degraded (codex self-reported partial or blocked, or violated the
#           git policy — POLICY_VIOLATION names the drift)
#         | unverified (the tree changed but the self-report sentinel is
#           missing, malformed, or contradicts the tree)
#         | failed (no usable result).
# REPORTED_IMPLEMENTATION and REPORTED_TESTS are the model's self-report;
# CHANGED_FILES, POLICY_VIOLATION, and the HEAD/branch lines are verified
# against git, so trust them over the report when they disagree.
# Codex runs write-enabled with full access (danger-full-access) so it can
# fetch dependencies and run checks; the guardrails are the git preconditions
# below, the prompt contract, and the post-run drift checks — not a sandbox.
# New-run preconditions: a git repository with at least one commit, no
# merge/rebase/cherry-pick in progress, and a clean tree — the current branch,
# whichever it is, is used as-is. Override the clean-tree check with
# HYBRID_IMPLEMENT_ALLOW_DIRTY=1, accepting that attribution of changes
# becomes uncertain.
# Run artifacts are kept under ${TMPDIR:-/tmp} so the caller can read them after
# exit; nothing deletes them automatically — clear old hybrid-implement.*
# directories if they accumulate.
set -u

fail() {
  echo "STATUS=failed"
  echo "ERROR=$1"
  echo "RESULT_FILE=${RESULT_FILE:-none}"
  echo "LOG_FILE=${LOG_FILE:-none}"
  echo "SESSION_ID=${SESSION_ID:-unknown}"
  if [[ -s ${LOG_FILE:-} ]]; then
    echo "--- last log lines ---"
    tail -n 20 "$LOG_FILE"
  fi
  exit 1
}

command -v codex >/dev/null 2>&1 || fail "codex CLI not found on PATH"

MODE=run
if [[ ${1:-} == resume ]]; then
  MODE=resume
  SESSION_ID=${2:-}
  PACKET_FILE=${3:-}
  WORKDIR=${4:-$PWD}
  [[ -n $SESSION_ID && -n $PACKET_FILE ]] \
    || fail "usage: run-codex-implement.sh resume <session-id> <fix-packet> [workdir]"
  [[ $SESSION_ID == [0-9a-f]* ]] || fail "session id does not look like a UUID: $SESSION_ID"
else
  PACKET_FILE=${1:-}
  WORKDIR=${2:-$PWD}
  [[ -n $PACKET_FILE ]] || fail "usage: run-codex-implement.sh <packet-file> [workdir]"
fi
[[ -s $PACKET_FILE ]] || fail "packet file missing or empty: $PACKET_FILE"
[[ -d $WORKDIR ]] || fail "workdir is not a directory: $WORKDIR"

REPO_ROOT=$(git -C "$WORKDIR" rev-parse --show-toplevel 2>/dev/null) \
  || fail "workdir is not inside a git repository: $WORKDIR"
git -C "$REPO_ROOT" rev-parse -q --verify HEAD >/dev/null \
  || fail "repository has no commits"
GIT_DIR=$(git -C "$REPO_ROOT" rev-parse --absolute-git-dir)
if [[ -e $GIT_DIR/MERGE_HEAD || -e $GIT_DIR/CHERRY_PICK_HEAD \
   || -d $GIT_DIR/rebase-merge || -d $GIT_DIR/rebase-apply ]]; then
  fail "repository has a merge, rebase, or cherry-pick in progress"
fi

START_BRANCH=$(git -C "$REPO_ROOT" branch --show-current)
START_HEAD=$(git -C "$REPO_ROOT" rev-parse HEAD)

if [[ $MODE == run ]]; then
  if [[ ${HYBRID_IMPLEMENT_ALLOW_DIRTY:-0} != 1 ]]; then
    [[ -z $(git -C "$REPO_ROOT" status --porcelain) ]] \
      || fail "working tree is dirty; commit or stash first, or set HYBRID_IMPLEMENT_ALLOW_DIRTY=1"
  fi
fi

RUN_DIR=$(mktemp -d "${TMPDIR:-/tmp}/hybrid-implement.XXXXXX") || fail "mktemp failed"
RESULT_FILE=$RUN_DIR/result.md
LOG_FILE=$RUN_DIR/codex.log
BEFORE_STATUS=$RUN_DIR/before-status.txt
AFTER_STATUS=$RUN_DIR/after-status.txt
PATCH_FILE=$RUN_DIR/changes.patch
git -C "$REPO_ROOT" status --porcelain >"$BEFORE_STATUS"

# The contract preamble is prepended in both modes: a resume restates the rules
# in case the session drifted, and fix packets stay self-contained. The two
# sentinel lines are the machine contract for the STATUS classification below.
PROMPT_FILE=$RUN_DIR/prompt.md
{
  cat <<'EOF'
You are the implementer in a lead model's implement-review loop; your report is status input for the lead, not a user-facing message.
Implement exactly what the task packet below asks — no unrelated cleanup, nothing beyond its scope.
Work only inside this repository's working tree. Run the project's relevant checks and report what you ran and the results.
Leave every change uncommitted and unstaged. Never commit, merge, rebase, reset, restore, stash, clean, tag, switch branches, or push; never touch git config, hooks, remotes, or history; never modify files outside the working tree.
End your report with two final lines in plain text — no backticks, quotes, or other formatting:
IMPLEMENT_STATUS=<complete|partial|blocked|no-change>
IMPLEMENT_TESTS=<passed|failed|not-run>

EOF
  cat "$PACKET_FILE"
} >"$PROMPT_FILE" || fail "failed to build prompt file"

CODEX_FLAGS=(
  -c sandbox_mode=danger-full-access
  -c tools.web_search=true
  -m "${CODEX_IMPLEMENT_MODEL:-gpt-5.6-sol}"
  -c model_reasoning_effort=high
  -o "$RESULT_FILE"
)

if [[ $MODE == resume ]]; then
  # `codex exec resume` has no -C flag, so run from the repo instead.
  cd "$REPO_ROOT" || fail "cannot cd to repo: $REPO_ROOT"
  codex exec resume "${CODEX_FLAGS[@]}" \
    "$SESSION_ID" - <"$PROMPT_FILE" >"$LOG_FILE" 2>&1
  EXIT_CODE=$?
else
  codex exec "${CODEX_FLAGS[@]}" \
    -C "$REPO_ROOT" \
    - <"$PROMPT_FILE" >"$LOG_FILE" 2>&1
  EXIT_CODE=$?
  SESSION_ID=$(grep -m1 -oE 'session id: [0-9a-f-]+' "$LOG_FILE" | awk '{print $3}')
fi

# Capture repository facts before judging the exit code, so even a failed run
# leaves the state snapshots and patch behind for the lead.
END_BRANCH=$(git -C "$REPO_ROOT" branch --show-current)
END_HEAD=$(git -C "$REPO_ROOT" rev-parse HEAD)
git -C "$REPO_ROOT" status --porcelain >"$AFTER_STATUS"
git -C "$REPO_ROOT" diff "$START_HEAD" >"$PATCH_FILE" 2>/dev/null

POLICY_VIOLATION=none
violation() {
  if [[ $POLICY_VIOLATION == none ]]; then POLICY_VIOLATION=$1; else POLICY_VIOLATION="$POLICY_VIOLATION,$1"; fi
}
[[ $END_HEAD == "$START_HEAD" ]] || violation head-moved
[[ $END_BRANCH == "$START_BRANCH" ]] || violation branch-changed
# Porcelain lines whose first column is neither space nor ? are staged entries.
if grep -q '^[^ ?]' "$AFTER_STATUS" && ! grep -q '^[^ ?]' "$BEFORE_STATUS"; then
  violation staged-changes
fi

# Working-tree entries that were not there before the run; exact on a clean
# start, approximate under HYBRID_IMPLEMENT_ALLOW_DIRTY=1.
CHANGED_FILES=$(comm -13 <(sort "$BEFORE_STATUS") <(sort "$AFTER_STATUS") | wc -l | tr -d ' ')

[[ $EXIT_CODE -eq 0 ]] || fail "codex exec failed (exit $EXIT_CODE)"
[[ -s $RESULT_FILE ]] || fail "codex exec produced no report; see LOG_FILE"

# Tolerant sentinel parse, as in run-codex-council.sh: scan the last lines with
# formatting stripped, since models sometimes wrap sentinels in backticks or bold.
REPORTED_IMPLEMENTATION=$(tail -n 8 "$RESULT_FILE" | tr -d '`*' \
  | sed 's/^[[:space:]]*//; s/[[:space:]]*$//' \
  | grep -oE '^IMPLEMENT_STATUS=(complete|partial|blocked|no-change)$' | tail -n 1 | cut -d= -f2)
REPORTED_TESTS=$(tail -n 8 "$RESULT_FILE" | tr -d '`*' \
  | sed 's/^[[:space:]]*//; s/[[:space:]]*$//' \
  | grep -oE '^IMPLEMENT_TESTS=(passed|failed|not-run)$' | tail -n 1 | cut -d= -f2)
REPORTED_IMPLEMENTATION=${REPORTED_IMPLEMENTATION:-unknown}
REPORTED_TESTS=${REPORTED_TESTS:-unknown}

if [[ $POLICY_VIOLATION != none ]]; then
  STATUS=degraded
elif [[ $REPORTED_IMPLEMENTATION == partial || $REPORTED_IMPLEMENTATION == blocked ]]; then
  STATUS=degraded
elif [[ $CHANGED_FILES -eq 0 ]]; then
  STATUS=no-change
elif [[ $REPORTED_IMPLEMENTATION == complete ]]; then
  STATUS=ok
else
  STATUS=unverified
fi

echo "STATUS=$STATUS"
echo "REPORTED_IMPLEMENTATION=$REPORTED_IMPLEMENTATION"
echo "REPORTED_TESTS=$REPORTED_TESTS"
echo "CHANGED_FILES=$CHANGED_FILES"
echo "POLICY_VIOLATION=$POLICY_VIOLATION"
echo "BRANCH=$END_BRANCH"
echo "START_HEAD=$START_HEAD"
echo "END_HEAD=$END_HEAD"
echo "PATCH_FILE=$PATCH_FILE"
echo "RESULT_FILE=$RESULT_FILE"
echo "LOG_FILE=$LOG_FILE"
echo "SESSION_ID=${SESSION_ID:-unknown}"
