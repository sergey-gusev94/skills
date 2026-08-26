#!/usr/bin/env bash
# Launch the Codex ten-agent council non-interactively for the hybrid-council skill.
# Usage:
#   run-codex-council.sh <packet-file> [workdir]           new council run
#   run-codex-council.sh resume <session-id> "<follow-up>" follow-up in an existing session
# Prints STATUS/RESULT_FILE/LOG_FILE/SESSION_ID lines; read RESULT_FILE for the answer.
# STATUS: ok (ten subagents confirmed) | degraded (fewer than ten confirmed)
#         | unverified (usable answer, but the self-reported subagent count is
#         missing or implausible) | failed (no usable answer).
# The council is read-only by instruction, not by sandbox: Codex runs with full
# access so subagents can reach the network, and the prompt forbids changes.
# Run artifacts are kept under ${TMPDIR:-/tmp} so the caller can read them after
# exit; nothing deletes them automatically — clear old hybrid-council.*
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
  FOLLOW_UP=${3:-}
  [[ -n $SESSION_ID && -n $FOLLOW_UP ]] || fail "usage: run-codex-council.sh resume <session-id> \"<follow-up>\""
else
  PACKET_FILE=${1:-}
  WORKDIR=${2:-$PWD}
  [[ -n $PACKET_FILE ]] || fail "usage: run-codex-council.sh <packet-file> [workdir]"
  [[ -s $PACKET_FILE ]] || fail "packet file missing or empty: $PACKET_FILE"
  [[ -d $WORKDIR ]] || fail "workdir is not a directory: $WORKDIR"
fi

RUN_DIR=$(mktemp -d "${TMPDIR:-/tmp}/hybrid-council.XXXXXX") || fail "mktemp failed"
RESULT_FILE=$RUN_DIR/result.md
LOG_FILE=$RUN_DIR/codex.log

# Shared flags for both the initial run and resume.
CODEX_FLAGS=(
  -c sandbox_mode=danger-full-access
  -c tools.web_search=true
  -m "${CODEX_COUNCIL_MODEL:-gpt-5.6-sol}"
  -c model_reasoning_effort=high
  --skip-git-repo-check
  -o "$RESULT_FILE"
)

if [[ $MODE == resume ]]; then
  codex exec resume "${CODEX_FLAGS[@]}" \
    "$SESSION_ID" "$FOLLOW_UP" </dev/null >"$LOG_FILE" 2>&1
  EXIT_CODE=$?
else
  # The sentinel line is the machine contract for STATUS below; the packet file
  # itself needs no preamble.
  PROMPT_FILE=$RUN_DIR/prompt.md
  {
    cat <<'EOF'
Use the $council skill to answer the request in the task packet below.
This council is advisory and read-only: do not modify files, system state, or remote services.
Your answer is advisory input for a lead model's synthesis, not a user-facing message.
End your answer with a final line containing exactly COUNCIL_SUBAGENTS=<n> in plain text — no backticks, quotes, or other formatting — where <n> is the number of council subagents that ran to completion (0 if none could run).

EOF
    cat "$PACKET_FILE"
  } >"$PROMPT_FILE" || fail "failed to build prompt file"

  codex exec "${CODEX_FLAGS[@]}" \
    -C "$WORKDIR" \
    - <"$PROMPT_FILE" >"$LOG_FILE" 2>&1
  EXIT_CODE=$?
  SESSION_ID=$(grep -m1 -oE 'session id: [0-9a-f-]+' "$LOG_FILE" | awk '{print $3}')
fi

[[ $EXIT_CODE -eq 0 ]] || fail "codex exec failed (exit $EXIT_CODE)"
[[ -s $RESULT_FILE ]] || fail "codex exec produced no answer; see LOG_FILE"

if [[ $MODE == resume ]]; then
  # A resume only answers a follow-up; council completeness is not re-verified.
  STATUS=ok
else
  # Tolerant sentinel parse: scan the last lines with formatting stripped, since
  # models sometimes wrap the sentinel in backticks or add trailing whitespace.
  AGENTS=$(tail -n 5 "$RESULT_FILE" | tr -d '`' | sed 's/[[:space:]]*$//' \
    | grep -oE '^COUNCIL_SUBAGENTS=[0-9]+$' | tail -n 1 | cut -d= -f2)
  if [[ -z ${AGENTS:-} || $AGENTS -gt 10 ]]; then
    STATUS=unverified
  elif [[ $AGENTS -eq 10 ]]; then
    STATUS=ok
  else
    STATUS=degraded
  fi
fi

echo "STATUS=$STATUS"
echo "RESULT_FILE=$RESULT_FILE"
echo "LOG_FILE=$LOG_FILE"
echo "SESSION_ID=${SESSION_ID:-unknown}"
