---
name: hybrid-council
description: Convene an explicitly requested three-voice council — a Fable adviser, an Opus adviser, and the Codex ten-agent council — then produce one critically synthesized answer.
disable-model-invocation: true
effort: high
allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/run-codex-council.sh *)
---

# Hybrid Council

Act as the lead. Three independent voices advise; you own the reasoning and final answer. Stay in the main conversation — do not run this skill or its synthesis inside a subagent.

The entire council is strictly read-only: no changes to the project, system state, or external services by you or any voice. The sole exception is the skill's own temporary orchestration artifacts — the task packet, follow-up files, and the script's run directory and session metadata. Read-only is enforced by instruction, not by sandboxing: no voice is sandboxed, every voice keeps Bash and network access, and each is trusted to comply. The deliverable is findings and recommendations only.

## Convene the council

1. Interpret the user's actual objective, constraints, and desired deliverable. Inspect enough context to write one task packet: the normalized objective, the original request, constraints, and pointers to relevant files or evidence. Every voice receives this same packet; none may see another voice's answer before finishing.
2. Write the task packet to a temp file. The script prepends the `$council` invocation, the advisory framing, and the status-sentinel instruction, so the packet needs no preamble.
3. Dispatch all three voices in parallel, in a single block:
   - Spawn the `council-fable` agent with the packet, asking for its complete, independent answer to the request.
   - Spawn the `council-opus` agent with the same packet and the same ask.
   - Run the script as a background Bash command — foreground commands are capped at ten minutes and council runs often exceed that. Example, with the packet at `/tmp/council-packet-<unique-suffix>.md` (pick a fresh suffix per run so concurrent councils cannot clobber each other) and the project under investigation as the second argument (defaults to the current directory):
     `${CLAUDE_SKILL_DIR}/scripts/run-codex-council.sh /tmp/council-packet-<unique-suffix>.md /path/to/project`
   Runtime scales with the task: minutes for a focused question, hours for a large investigation such as a whole-codebase bug hunt. That is expected — wait for every voice, and never impose a timeout, kill, or restart a voice merely because it is slow.
4. Collect all three results. The script prints `STATUS`, `SUBAGENTS`, `RESULT_FILE`, `LOG_FILE`, and `SESSION_ID` lines; Read `RESULT_FILE` for the Codex answer rather than relying on command output. Honor `STATUS`: `degraded` means fewer than ten Codex subagents completed — `SUBAGENTS` gives the count, and `0` means no council ran and the answer is a single model's; `unverified` means the answer is usable but the subagent count could not be confirmed — use it normally, without claiming a full or partial council; `failed` means there is no usable Codex answer — the script prints an `ERROR` line and the last log lines. Ignore the trailing `COUNCIL_SUBAGENTS=` line in the result; it is the script's status contract, not content.
5. Follow up only when clarification would materially improve the answer: message the same Claude agents, or write the follow-up to its own temp file and run `${CLAUDE_SKILL_DIR}/scripts/run-codex-council.sh resume <SESSION_ID> <follow-up-file>`. A resume always reports `unverified` because council completeness is not re-checked. If `SESSION_ID` is `unknown`, skip the Codex follow-up.
6. Treat the three replies as advisory evidence, not votes. The two Claude voices share a model family, so their agreement is weak confirmation; agreement across families — a Claude voice and the Codex council — is stronger evidence, and any disagreement is a cue to check the primary artifact yourself. Reconcile contradictions; discard errors, duplicates, and weak speculation. Consensus is not proof, and a minority view with stronger evidence should survive.
7. Produce one answer in your own voice, shaped to the original task. Lead with your conclusion and include the reasoning, evidence, options, caveats, or next steps that materially help the user. Do not expose transcripts or a per-voice rollup. Preserve unresolved uncertainty when the evidence does not justify a single confident answer.

If a voice fails or comes back degraded, say so plainly and label the result as a partial council; never silently present fewer voices as the full council.
