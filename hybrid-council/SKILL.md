---
name: hybrid-council
description: Convene an explicitly requested three-voice council — a Fable adviser, an Opus adviser, and the Codex ten-agent council — then produce one critically synthesized answer.
disable-model-invocation: true
effort: high
allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/run-codex-council.sh *)
---

# Hybrid Council

Act as the lead. Three independent voices advise; you own the reasoning and final answer. Stay in the main conversation — do not run this skill or its synthesis inside a subagent.

## Convene the council

1. Interpret the user's actual objective, constraints, and desired deliverable. Inspect enough context to write one task packet: the normalized objective, the original request, constraints, and pointers to relevant files or evidence. Every voice receives this same packet; none may see another voice's answer before finishing.
2. Write the Codex prompt file to a temp path. Its first line must be: `Use the $council skill to answer the following request.` followed by the task packet.
3. Dispatch all three voices in parallel, in a single block:
   - Spawn the `council-fable` agent with the packet, asking for its complete, independent answer to the request.
   - Spawn the `council-opus` agent with the same packet and the same ask. Deliberate replication: the diversity comes from the models, so agreement between voices is evidence and disagreement is a flag.
   - Run `${CLAUDE_SKILL_DIR}/scripts/run-codex-council.sh <prompt-file> [workdir]` as a background Bash command, where `<prompt-file>` is the temp file from step 2 and `[workdir]` is the project directory under investigation (defaults to the current directory).
   Runtime scales with the task: minutes for a focused question, hours for a large investigation such as a whole-codebase bug hunt. That is expected — wait for every voice, and never impose a timeout, kill, or restart a voice merely because it is slow.
4. Collect all three results. The script prints `STATUS`, `RESULT_FILE`, `LOG_FILE`, and `SESSION_ID` lines followed by the Codex answer. Honor `STATUS`: `degraded` means Codex answered without completing its ten-agent council; `failed` means there is no usable Codex answer — report useful lines from the log.
5. Follow up only when clarification would materially improve the answer: message the same Claude agents, or resume the Codex session with `codex exec resume <SESSION_ID> --sandbox read-only -o <file> "<follow-up>"`.
6. Treat the three replies as advisory evidence, not votes. Reconcile contradictions; discard errors, duplicates, and weak speculation. Consensus is not proof, and a minority view with stronger evidence should survive.
7. Produce one answer in your own voice, shaped to the original task. Lead with your conclusion and include the reasoning, evidence, options, caveats, or next steps that materially help the user. Do not expose transcripts or a per-voice rollup. Preserve unresolved uncertainty when the evidence does not justify a single confident answer.

If a voice fails or comes back degraded, say so plainly and label the result as a partial council; never silently present fewer voices as the full council. A full run uses roughly fourteen model contexts, so it is invoked manually only.
