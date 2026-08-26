#!/usr/bin/env bash
# Launch the Codex ten-agent council non-interactively for the hybrid-council skill.
# Usage:
#   run-codex-council.sh <packet-file> [workdir]           new council run
#   run-codex-council.sh resume <session-id> "<follow-up>" follow-up in an existing session
# Prints STATUS/RESULT_FILE/LOG_FILE/SESSION_ID lines; read RESULT_FILE for the answer.
# STATUS: ok | degraded (fewer than ten council subagents completed) | failed.
# Run artifacts are kept under ${TMPDIR:-/tmp} so the caller can read them after exit;
# they are reclaimed by normal tmp cleanup.
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

if [[ $MODE == resume ]]; then
  codex exec \
    -c sandbox_mode=read-only \
    --skip-git-repo-check \
    -o "$RESULT_FILE" \
    resume "$SESSION_ID" "$FOLLOW_UP" </dev/null >"$LOG_FILE" 2>&1
  EXIT_CODE=$?
else
  # The sentinel line is the machine contract for STATUS below; the packet file
  # itself needs no preamble.
  PROMPT_FILE=$RUN_DIR/prompt.md
  {
    cat <<'EOF'
Use the $council skill to answer the request in the task packet below.
Your answer is advisory input for a lead model's synthesis, not a user-facing message.
End your answer with a final line of exactly `COUNCIL_SUBAGENTS=<n>`, where <n> is the number of council subagents that ran to completion (0 if none could run).

EOF
    cat "$PACKET_FILE"
  } >"$PROMPT_FILE"

  codex exec \
    --sandbox read-only \
    --skip-git-repo-check \
    -m "${CODEX_COUNCIL_MODEL:-gpt-5.6-sol}" \
    -c model_reasoning_effort=high \
    -C "$WORKDIR" \
    -o "$RESULT_FILE" \
    - <"$PROMPT_FILE" >"$LOG_FILE" 2>&1
  EXIT_CODE=$?
  SESSION_ID=$(grep -m1 -iohE 'session id: [0-9a-f-]+' "$LOG_FILE" 2>/dev/null | head -n 1 | awk '{print $3}')
fi

[[ $EXIT_CODE -eq 0 && -s $RESULT_FILE ]] || fail "codex exec failed (exit $EXIT_CODE)"

if [[ $MODE == resume ]]; then
  STATUS=ok
else
  AGENTS=$(tail -n 1 "$RESULT_FILE" | grep -oE '^COUNCIL_SUBAGENTS=[0-9]+$' | cut -d= -f2)
  if [[ ${AGENTS:-0} -ge 10 ]]; then
    STATUS=ok
  else
    STATUS=degraded
  fi
fi

echo "STATUS=$STATUS"
echo "RESULT_FILE=$RESULT_FILE"
echo "LOG_FILE=$LOG_FILE"
echo "SESSION_ID=${SESSION_ID:-unknown}"
