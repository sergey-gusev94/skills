---
name: hybrid-council
description: Convene an explicitly requested three-adviser council — a Fable adviser, an Opus adviser, and the Codex ten-agent council — then produce one critically synthesized answer.
disable-model-invocation: true
effort: high
allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/run-codex-council.sh *)
---

# Hybrid Council

Act as the lead. Three advisers answer separately, none seeing another's reply; you own the reasoning and final answer. Stay in the main conversation — do not run this skill or its synthesis inside a subagent.

The entire council is strictly read-only: no changes to the project, system state, or external services by you or any adviser. The sole exception is the skill's own temporary orchestration artifacts — the task packet, follow-up files, and the script's run directory and session metadata. Read-only is enforced by instruction, not by sandboxing: no adviser is sandboxed, every adviser keeps Bash and network access, and each is trusted to comply. The deliverable is analysis and advice only.

## Convene the council

1. Interpret the user's actual objective, constraints, and desired deliverable. Inspect enough context to write one task packet: the normalized objective, the original request, constraints, and pointers to relevant files or evidence. State which decisions are settled and which remain open to challenge; advisers must not re-litigate settled decisions without new evidence. Settled means an explicit user decision, a governing constraint, or a fact established by primary evidence — proposed approaches, inferred preferences, and your own framing stay open to challenge. Every adviser receives this same packet; none may see another adviser's answer before finishing.
2. Write the task packet to a temp file. The script prepends the `$council` invocation, the advisory framing, and the status-sentinel instruction, so the packet needs no preamble.
3. Dispatch all three advisers in parallel, in a single block:
   - Spawn the `council-fable` agent with the packet, asking for its complete, independent answer to the request.
   - Spawn the `council-opus` agent with the same packet and the same ask.
   - Run the script as a background Bash command — foreground commands are capped at ten minutes and council runs often exceed that. Example, with the packet at `/tmp/council-packet-<unique-suffix>.md` (pick a fresh suffix per run so concurrent councils cannot clobber each other) and the project under investigation as the last argument (defaults to the current directory):
     `${CLAUDE_SKILL_DIR}/scripts/run-codex-council.sh /tmp/council-packet-<unique-suffix>.md /path/to/project`
   Runtime scales with the task: minutes for a focused question, hours for a large investigation such as a whole-codebase bug hunt. That is expected — wait for every adviser, and never impose a timeout, kill, or restart an adviser merely because it is slow.
4. Collect all three results. The script prints `STATUS`, `SUBAGENTS`, `RESULT_FILE`, `LOG_FILE`, and `SESSION_ID` lines; Read `RESULT_FILE` for the Codex answer rather than relying on command output. `STATUS=failed` means there is no usable Codex answer — the script prints an `ERROR` line and the last log lines. Otherwise judge the council by `SUBAGENTS`: `10` is a full council; below ten is a partial council — say so, with `0` meaning no council ran and the answer is a single model's; `unknown` means the count could not be confirmed — use the answer normally, without claiming a full or partial council. Ignore the trailing `COUNCIL_SUBAGENTS=` line in the result; it is the script's status contract, not content.
5. Follow up only when clarification would materially improve the answer: message the same Claude agents, or write the follow-up to its own temp file and run `${CLAUDE_SKILL_DIR}/scripts/run-codex-council.sh resume <SESSION_ID> <follow-up-file> /path/to/project`, using the same project path as the original run. A resume always reports `SUBAGENTS=unknown` because council completeness is not re-checked. If `SESSION_ID` is `unknown`, skip the Codex follow-up.
6. Treat the three replies as leads, not votes. A reply is a source of claims and reasoning, not evidence in itself: check every consequential claim against the primary artifact yourself, whether the replies agree or not. All three advisers answered the same packet you wrote and their training overlaps — the two Claude advisers especially, since they share a model family — so agreement can be shared error as easily as truth. Repetition adds no support; use agreement and disagreement only to decide where to check first. Settle contradictions on the evidence, discard errors, duplicates, and weak speculation, and keep a well-supported conclusion even when only one reply reaches it.
7. Produce one answer in your own voice, shaped to the original task. Lead with your conclusion — when the evidence shows a materially better approach or a flawed premise, that is the conclusion to lead with rather than only the question as posed — and include the reasoning, evidence, options, caveats, or next steps that materially help the user. Do not expose transcripts or a per-adviser rollup. Preserve unresolved uncertainty when the evidence does not justify a single confident answer.

If a Claude adviser fails or the Codex council comes back partial (`SUBAGENTS` below ten) or failed, say so plainly and label the result as a partial council; never silently present fewer advisers as the full council.
