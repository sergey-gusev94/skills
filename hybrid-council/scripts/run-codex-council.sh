#!/usr/bin/env bash
# Launch the Codex ten-agent council non-interactively for the hybrid skills.
# Usage:
#   run-codex-council.sh [--skill council|review-council] <packet-file> [workdir]
#                                                                 new council run
#   run-codex-council.sh resume <session-id> <follow-up-file> [workdir]
#                                                    follow-up in an existing session
# --skill picks the Codex skill to invoke: council (default) for general
# inquiry or review-council for the ten-agent code review. Both report the same
# COUNCIL_SUBAGENTS sentinel, so the status contract is identical.
# Prints STATUS/SUBAGENTS/RESULT_FILE/LOG_FILE/SESSION_ID lines; read RESULT_FILE
# for the answer.
# STATUS: ok (usable answer) | failed (no usable answer).
# SUBAGENTS: 10 (full council) | 0-9 (partial council; 0 means no council ran
# and the answer is a single model's) | unknown (the self-reported count is
# missing or implausible). Every resume reports unknown because completeness is
# not re-checked. Even 10 is model-self-reported, not independently verified.
# The council is read-only by instruction, not by sandbox: Codex runs with full
# access so subagents can reach the network, and the prompt forbids changes.
# Run artifacts are kept under ${TMPDIR:-/tmp} so the caller can read them after
# exit; nothing deletes them automatically — clear old hybrid-council.*
# directories if they accumulate.
set -u

SUBAGENTS=unknown

fail() {
  echo "STATUS=failed"
  echo "SUBAGENTS=${SUBAGENTS:-unknown}"
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

COUNCIL_SKILL=council
if [[ ${1:-} == --skill ]]; then
  case ${2:-} in
    council|review-council) COUNCIL_SKILL=$2 ;;
    *) fail "--skill must be council or review-council, got: ${2:-<missing>}" ;;
  esac
  shift 2
fi

MODE=run
if [[ ${1:-} == resume ]]; then
  MODE=resume
  SESSION_ID=${2:-}
  FOLLOW_UP_FILE=${3:-}
  WORKDIR=${4:-$PWD}
  [[ -n $SESSION_ID && -n $FOLLOW_UP_FILE ]] \
    || fail "usage: run-codex-council.sh resume <session-id> <follow-up-file> [workdir]"
  [[ $SESSION_ID == [0-9a-f]* ]] || fail "session id does not look like a UUID: $SESSION_ID"
  [[ -s $FOLLOW_UP_FILE ]] || fail "follow-up file missing or empty: $FOLLOW_UP_FILE"
  [[ -d $WORKDIR ]] || fail "workdir is not a directory: $WORKDIR"
else
  PACKET_FILE=${1:-}
  WORKDIR=${2:-$PWD}
  [[ -n $PACKET_FILE ]] \
    || fail "usage: run-codex-council.sh [--skill council|review-council] <packet-file> [workdir]"
  [[ -s $PACKET_FILE ]] || fail "packet file missing or empty: $PACKET_FILE"
  [[ -d $WORKDIR ]] || fail "workdir is not a directory: $WORKDIR"
fi

RUN_DIR=$(mktemp -d "${TMPDIR:-/tmp}/hybrid-council.XXXXXX") || fail "mktemp failed"
RESULT_FILE=$RUN_DIR/result.md
LOG_FILE=$RUN_DIR/codex.log
PROMPT_FILE=$RUN_DIR/prompt.md

# The advisory preamble is prepended in both modes: a resume restates the
# read-only contract in case the session drifted. Build before any cd so
# relative packet and follow-up paths remain valid.
if [[ $MODE == resume ]]; then
  {
    cat <<'EOF'
This council is advisory and read-only: do not modify files, system state, or remote services.
Your answer is advisory input for a lead model's synthesis, not a user-facing message.

EOF
    cat -- "$FOLLOW_UP_FILE"
  } >"$PROMPT_FILE" || fail "failed to build prompt file"
else
  # The sentinel line is the machine contract for SUBAGENTS below; the packet
  # file itself needs no preamble.
  {
    printf 'Use the $%s skill to answer the request in the task packet below.\n' "$COUNCIL_SKILL"
    cat <<'EOF'
This council is advisory and read-only: do not modify files, system state, or remote services.
Your answer is advisory input for a lead model's synthesis, not a user-facing message.
End your answer with a final line containing exactly COUNCIL_SUBAGENTS=<n> in plain text — no backticks, quotes, or other formatting — where <n> is the number of council subagents that ran to completion (0 if none could run).

EOF
    cat -- "$PACKET_FILE"
  } >"$PROMPT_FILE" || fail "failed to build prompt file"
fi

# Shared flags for both the initial run and resume.
COUNCIL_MODEL=${CODEX_COUNCIL_MODEL:-gpt-5.6-sol}
COUNCIL_EFFORT=high

CODEX_FLAGS=(
  -c sandbox_mode=danger-full-access
  -c tools.web_search=true
  -m "$COUNCIL_MODEL"
  -c "model_reasoning_effort=$COUNCIL_EFFORT"
  --skip-git-repo-check
  -o "$RESULT_FILE"
)

if [[ $MODE == resume ]]; then
  # `codex exec resume` has no -C flag, so run from the workdir instead.
  cd "$WORKDIR" || fail "cannot cd to workdir: $WORKDIR"
  codex exec resume "${CODEX_FLAGS[@]}" \
    "$SESSION_ID" - <"$PROMPT_FILE" >"$LOG_FILE" 2>&1
  EXIT_CODE=$?
else
  codex exec "${CODEX_FLAGS[@]}" \
    -C "$WORKDIR" \
    - <"$PROMPT_FILE" >"$LOG_FILE" 2>&1
  EXIT_CODE=$?
  SESSION_ID=$(grep -m1 -oE 'session id: [0-9a-f-]+' "$LOG_FILE" | awk '{print $3}')
fi

[[ $EXIT_CODE -eq 0 ]] || fail "codex exec failed (exit $EXIT_CODE)"
[[ -s $RESULT_FILE ]] || fail "codex exec produced no answer; see LOG_FILE"
STATUS=ok

if [[ $MODE != resume ]]; then
  # Tolerant sentinel parse: scan the last lines with formatting stripped, since
  # models sometimes wrap the sentinel in backticks, bold, or stray whitespace.
  AGENTS=$(tail -n 5 "$RESULT_FILE" | tr -d '`*' \
    | sed 's/^[[:space:]]*//; s/[[:space:]]*$//' \
    | grep -oE '^COUNCIL_SUBAGENTS=[0-9]+$' | tail -n 1 | cut -d= -f2)
  # String classification only — no arithmetic, so odd values like 08 or huge
  # numbers land on unknown instead of tripping bash octal/overflow rules.
  case ${AGENTS:-} in
    10|[0-9]) SUBAGENTS=$AGENTS ;;
    *) SUBAGENTS=unknown ;;
  esac
fi

echo "STATUS=$STATUS"
echo "SUBAGENTS=$SUBAGENTS"
echo "RESULT_FILE=$RESULT_FILE"
echo "LOG_FILE=$LOG_FILE"
echo "SESSION_ID=${SESSION_ID:-unknown}"
