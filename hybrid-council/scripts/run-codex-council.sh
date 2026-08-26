#!/usr/bin/env bash
# Run the Codex ten-agent council non-interactively for the hybrid-council skill.
# Usage: run-codex-council.sh <prompt-file> [workdir]
# Prints STATUS/RESULT_FILE/LOG_FILE/SESSION_ID lines, then the Codex answer.
# STATUS: ok | degraded (answered without the ten-agent council) | failed
set -u

PROMPT_FILE=${1:?usage: run-codex-council.sh <prompt-file> [workdir]}
WORKDIR=${2:-$PWD}

if [[ ! -s "$PROMPT_FILE" ]]; then
  echo "STATUS=failed"
  echo "ERROR=prompt file missing or empty: $PROMPT_FILE"
  exit 1
fi

RUN_DIR=$(mktemp -d /tmp/hybrid-council.XXXXXX)
RESULT_FILE=$RUN_DIR/result.md
LOG_FILE=$RUN_DIR/codex.log

# multi_agent_v2 exposes collaboration.spawn_agent in exec mode; without it the
# council skill cannot spawn its subagents and degrades to a single-model answer.
codex exec \
  --enable multi_agent_v2 \
  --sandbox read-only \
  --skip-git-repo-check \
  -m gpt-5.6-sol \
  -c model_reasoning_effort=high \
  -C "$WORKDIR" \
  -o "$RESULT_FILE" \
  - < "$PROMPT_FILE" >"$RUN_DIR/stdout.log" 2>"$LOG_FILE"
EXIT_CODE=$?

SESSION_ID=$(grep -m1 -ohE 'session id: [0-9a-f-]+' "$LOG_FILE" "$RUN_DIR/stdout.log" 2>/dev/null | head -1 | awk '{print $3}')

if [[ $EXIT_CODE -ne 0 || ! -s "$RESULT_FILE" ]]; then
  STATUS=failed
elif grep -qi 'could not be completed' "$RESULT_FILE"; then
  # Matches the council skill's mandated fallback wording when it cannot run
  # its ten subagents.
  STATUS=degraded
else
  STATUS=ok
fi

echo "STATUS=$STATUS"
echo "RESULT_FILE=$RESULT_FILE"
echo "LOG_FILE=$LOG_FILE"
echo "SESSION_ID=${SESSION_ID:-unknown}"

if [[ $STATUS == failed ]]; then
  echo "--- last log lines ---"
  tail -20 "$LOG_FILE" 2>/dev/null
  exit 1
fi

echo "--- codex answer ---"
cat "$RESULT_FILE"
