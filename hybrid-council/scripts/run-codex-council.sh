#!/usr/bin/env bash
# Launch the Codex ten-agent council non-interactively for the hybrid skills.
# Usage:
#   run-codex-council.sh [--skill council|review-council] <packet-file> [workdir]
#                                                                 new council run
#   run-codex-council.sh resume <session-id> <follow-up-file> [workdir]
#                                                    follow-up in an existing session
# --skill picks the Codex skill to invoke: council (default) for general
# inquiry, review-council for the ten-agent code review. Both report the same
# COUNCIL_SUBAGENTS sentinel, so the status contract is identical.
# Prints STATUS/SUBAGENTS/RESULT_FILE/LOG_FILE/SESSION_ID lines; read RESULT_FILE
# for the answer.
# STATUS: ok (all ten subagents self-reported complete)
#         | degraded (fewer than ten self-reported; SUBAGENTS has the count,
#         0 meaning no council ran and the answer is a single model's)
#         | unverified (usable answer, but the self-reported count is missing or
#         implausible; every resume reports this, since a follow-up does not
#         re-verify council completeness) | failed (no usable answer).
# The council is read-only by instruction, not by sandbox: Codex runs with full
# access so subagents can reach the network, and the prompt forbids changes.
# Run artifacts are kept under ${TMPDIR:-/tmp} so the caller can read them after
# exit; nothing deletes them automatically — clear old hybrid-council.*
# directories if they accumulate.
set -u

SUBAGENTS=unknown

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
  # `codex exec resume` has no -C flag, so run from the workdir instead.
  cd "$WORKDIR" || fail "cannot cd to workdir: $WORKDIR"
  codex exec resume "${CODEX_FLAGS[@]}" \
    "$SESSION_ID" - <"$FOLLOW_UP_FILE" >"$LOG_FILE" 2>&1
  EXIT_CODE=$?
else
  # The sentinel line is the machine contract for STATUS below; the packet file
  # itself needs no preamble.
  PROMPT_FILE=$RUN_DIR/prompt.md
  {
    printf 'Use the $%s skill to answer the request in the task packet below.\n' "$COUNCIL_SKILL"
    cat <<'EOF'
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
  STATUS=unverified
else
  # Tolerant sentinel parse: scan the last lines with formatting stripped, since
  # models sometimes wrap the sentinel in backticks, bold, or stray whitespace.
  AGENTS=$(tail -n 5 "$RESULT_FILE" | tr -d '`*' \
    | sed 's/^[[:space:]]*//; s/[[:space:]]*$//' \
    | grep -oE '^COUNCIL_SUBAGENTS=[0-9]+$' | tail -n 1 | cut -d= -f2)
  # String classification only — no arithmetic, so odd values like 08 or huge
  # numbers land on unverified instead of tripping bash octal/overflow rules.
  case ${AGENTS:-} in
    10) STATUS=ok; SUBAGENTS=$AGENTS ;;
    [0-9]) STATUS=degraded; SUBAGENTS=$AGENTS ;;
    *) STATUS=unverified ;;
  esac
fi

echo "STATUS=$STATUS"
echo "SUBAGENTS=$SUBAGENTS"
echo "RESULT_FILE=$RESULT_FILE"
echo "LOG_FILE=$LOG_FILE"
echo "SESSION_ID=${SESSION_ID:-unknown}"
